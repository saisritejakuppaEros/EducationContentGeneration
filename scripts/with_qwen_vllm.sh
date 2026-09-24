#!/usr/bin/env bash
# Run a command while Qwen vLLM is available; start/stop an ephemeral server if needed.
#
# Pipeline steps use project .venv; vLLM itself is launched from gsplat_env (GPU stack).
#
# Usage (from repo root, .venv active for python deps):
#   source .venv/bin/activate
#   ./scripts/with_qwen_vllm.sh python3 scripts/run_textbook_director.py --book-id ...
#
# Reuse an already-running server (no kill on exit):
#   ./scripts/with_qwen_vllm.sh --reuse python3 scripts/run_textbook_director.py ...
#
# Keep server running after command (debug):
#   ./scripts/with_qwen_vllm.sh --keep python3 ...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${VLLM_PORT:-8007}"
API_BASE="http://127.0.0.1:${PORT}/v1"
MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-27B}"
VLLM_CONDA_ENV="${VLLM_CONDA_ENV:-gsplat_env}"
CONDA_SH="${CONDA_SH:-/devwork/MiniConda/miniconda3/etc/profile.d/conda.sh}"
VLLM_GPU_ID="${VLLM_GPU_ID:-0}"
STARTUP_TIMEOUT_SEC="${VLLM_STARTUP_TIMEOUT_SEC:-300}"

# Fit vLLM into *free* VRAM when VLLM_GPU_UTIL is unset (avoids 0.86 while Flux/other jobs run).
compute_vllm_gpu_util() {
  if [[ -n "${VLLM_GPU_UTIL:-}" ]]; then
    echo "$VLLM_GPU_UTIL"
    return 0
  fi
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "0.65"
    return 0
  fi
  local line free_mib total_mib
  line="$(nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader,nounits -i "$VLLM_GPU_ID" 2>/dev/null | head -1)"
  if [[ -z "$line" ]]; then
    echo "0.65"
    return 0
  fi
  free_mib="${line%%,*}"
  total_mib="${line##*,}"
  free_mib="${free_mib// /}"
  total_mib="${total_mib// /}"
  python3 - <<PY
free, total = float("${free_mib}"), float("${total_mib}")
if total <= 0:
    print("0.65")
else:
    # Leave a small headroom; cap at 0.86
    print(f"{min(0.86, max(0.40, (free / total) * 0.97)):.2f}")
PY
}
LOG_DIR="${ROOT}/output/pipeline"
LOG_FILE="${LOG_DIR}/ephemeral_vllm_${PORT}.log"

REUSE=0
KEEP=0
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reuse)
      REUSE=1
      shift
      ;;
    --keep)
      KEEP=1
      shift
      ;;
    --)
      shift
      ARGS+=("$@")
      break
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ ${#ARGS[@]} -eq 0 ]]; then
  echo "Usage: $0 [--reuse] [--keep] -- <command...>" >&2
  exit 2
fi

mkdir -p "$LOG_DIR"

server_has_qwen() {
  curl -sf "${API_BASE}/models" 2>/dev/null | grep -qi qwen
}

# Director stages need a text model; do not reuse a VL-only server on :8007.
server_suitable_for_pipeline() {
  local models_json
  models_json="$(curl -sf "${API_BASE}/models" 2>/dev/null)" || return 1
  MODEL="$MODEL" python3 -c '
import json, os, sys
data = json.loads(sys.stdin.read())
want = (os.environ.get("MODEL") or "").lower()
ids = [m.get("id", "") for m in data.get("data", [])]
if not ids:
    sys.exit(1)
for mid in ids:
    if mid == os.environ.get("MODEL") or mid.lower() == want:
        sys.exit(0)
    if want and want in mid.lower() and "vl" not in mid.lower():
        sys.exit(0)
for mid in ids:
    low = mid.lower()
    if "qwen" in low and "vl" not in low:
        sys.exit(0)
sys.exit(1)
' <<<"$models_json"
}

stop_foreign_vllm_on_port() {
  if server_has_qwen && ! server_suitable_for_pipeline; then
    echo "Replacing incompatible vLLM on ${API_BASE} (need text Qwen: ${MODEL})..."
    pkill -f "vllm serve.*--port ${PORT}" 2>/dev/null || true
    local j
    for j in 1 2 3 4 5 6 7 8 9 10; do
      server_has_qwen || return 0
      sleep 2
    done
  fi
}

wait_for_server() {
  local i max
  max=$((STARTUP_TIMEOUT_SEC / 2))
  for ((i = 1; i <= max; i++)); do
    if server_has_qwen; then
      return 0
    fi
    if [[ -n "${VLLM_PID:-}" ]] && ! kill -0 "$VLLM_PID" 2>/dev/null; then
      echo "vLLM exited during startup. Log tail:" >&2
      tail -n 40 "$LOG_FILE" >&2 || true
      return 1
    fi
    sleep 2
  done
  echo "Timed out waiting for Qwen on ${API_BASE} (${STARTUP_TIMEOUT_SEC}s)." >&2
  tail -n 40 "$LOG_FILE" >&2 || true
  return 1
}

STARTED=0
VLLM_PID=""

stop_ephemeral_vllm() {
  if [[ "$STARTED" != "1" || -z "$VLLM_PID" ]]; then
    return 0
  fi
  if [[ "$KEEP" == "1" ]]; then
    echo "Leaving vLLM running (pid $VLLM_PID, log $LOG_FILE)."
    return 0
  fi
  echo "Stopping ephemeral vLLM (pid $VLLM_PID)..."
  kill "$VLLM_PID" 2>/dev/null || true
  local j
  for j in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$VLLM_PID" 2>/dev/null || break
    sleep 2
  done
  if kill -0 "$VLLM_PID" 2>/dev/null; then
    kill -9 "$VLLM_PID" 2>/dev/null || true
  fi
  pkill -P "$VLLM_PID" 2>/dev/null || true
  # vLLM engine workers sometimes outlive the parent
  pkill -f "vllm serve ${MODEL}.*--port ${PORT}" 2>/dev/null || true
  echo "vLLM stopped. If GPU memory is still full: nvidia-smi && pkill -f 'vllm serve'"
}

cleanup() {
  local code=$?
  stop_ephemeral_vllm
  exit "$code"
}
trap cleanup EXIT INT TERM

stop_foreign_vllm_on_port

if server_has_qwen && server_suitable_for_pipeline; then
  echo "Using existing Qwen vLLM @ ${API_BASE}"
  STARTED=0
elif [[ "$REUSE" == "1" ]]; then
  echo "No suitable Qwen on ${API_BASE} and --reuse set; refusing to start a new server." >&2
  exit 1
else
  if [[ ! -f "$CONDA_SH" ]]; then
    echo "Conda not found at $CONDA_SH (set CONDA_SH for vLLM env)." >&2
    exit 1
  fi
  if [[ "$MODEL" == *"-VL-"* || "$MODEL" == *"Qwen3-VL"* ]]; then
    echo "ERROR: QWEN_MODEL is a vision model ($MODEL). Use a text model (run.sh sets Qwen/Qwen3.5-27B)." >&2
    exit 1
  fi
  : >"$LOG_FILE"
  started_ok=0
  for attempt in 1 2 3; do
    VLLM_UTIL="$(compute_vllm_gpu_util)"
    if [[ "$attempt" -gt 1 ]]; then
      VLLM_UTIL="$(python3 -c "print(max(0.35, float('${VLLM_UTIL}') * 0.88))")"
      echo "vLLM startup retry ${attempt}/3 (gpu-memory-utilization=${VLLM_UTIL})..."
    else
      echo "Starting ephemeral vLLM: ${MODEL} on port ${PORT}, GPU ${VLLM_GPU_ID}, util ${VLLM_UTIL} (log: ${LOG_FILE})"
    fi
    (
      # shellcheck disable=SC1090
      source "$CONDA_SH"
      conda activate "$VLLM_CONDA_ENV"
      export HF_HOME="${HF_HOME:-/workspace/teja/models/hub}"
      export TORCH_HOME="${TORCH_HOME:-/workspace/torch-cache}"
      export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME}"
      export CUDA_VISIBLE_DEVICES="$VLLM_GPU_ID"
      exec vllm serve "$MODEL" \
        --host 0.0.0.0 \
        --port "$PORT" \
        --dtype bfloat16 \
        --max-model-len 32768 \
        --max-num-seqs 64 \
        --gpu-memory-utilization "$VLLM_UTIL" \
        >>"$LOG_FILE" 2>&1
    ) &
    VLLM_PID=$!
    STARTED=1
    if wait_for_server; then
      started_ok=1
      break
    fi
    kill "$VLLM_PID" 2>/dev/null || true
    pkill -P "$VLLM_PID" 2>/dev/null || true
    STARTED=0
    VLLM_PID=""
    sleep 3
  done
  if [[ "$started_ok" != "1" ]]; then
    echo "Failed to start vLLM after 3 attempts. See ${LOG_FILE}" >&2
    exit 1
  fi
fi

export OPENAI_API_BASE="${API_BASE}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-local}"
export QWEN_MODEL="$MODEL"

cd "$ROOT"
echo "Running: ${ARGS[*]}"
"${ARGS[@]}"
CMD_EXIT=$?

# Normal exit: cleanup trap runs with this exit code if we exit here
exit "$CMD_EXIT"
