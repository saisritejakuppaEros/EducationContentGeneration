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
STARTUP_TIMEOUT_SEC="${VLLM_STARTUP_TIMEOUT_SEC:-300}"
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

if server_has_qwen; then
  echo "Using existing Qwen vLLM @ ${API_BASE}"
  STARTED=0
elif [[ "$REUSE" == "1" ]]; then
  echo "No Qwen on ${API_BASE} and --reuse set; refusing to start a new server." >&2
  exit 1
else
  if [[ ! -f "$CONDA_SH" ]]; then
    echo "Conda not found at $CONDA_SH (set CONDA_SH for vLLM env)." >&2
    exit 1
  fi
  echo "Starting ephemeral vLLM: ${MODEL} on port ${PORT} (log: ${LOG_FILE})"
  : >"$LOG_FILE"
  # Start vLLM in an isolated subshell so conda activate does not override the caller's .venv.
  (
    # shellcheck disable=SC1090
    source "$CONDA_SH"
    conda activate "$VLLM_CONDA_ENV"
    export HF_HOME="${HF_HOME:-/workspace/teja/models/hub}"
    export TORCH_HOME="${TORCH_HOME:-/workspace/torch-cache}"
    export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME}"
    exec vllm serve "$MODEL" \
      --host 0.0.0.0 \
      --port "$PORT" \
      --dtype bfloat16 \
      --max-model-len 32768 \
      --max-num-seqs 64 \
      --gpu-memory-utilization "${VLLM_GPU_UTIL:-0.86}" \
      >>"$LOG_FILE" 2>&1
  ) &
  VLLM_PID=$!
  STARTED=1
  wait_for_server
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
