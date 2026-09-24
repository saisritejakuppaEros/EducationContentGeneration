#!/usr/bin/env bash
# Pick NVIDIA GPU index with the most free VRAM (for run.sh / with_qwen_vllm).
# Usage: eval "$(bash scripts/gpu_autopick.sh export VLLM_GPU_ID)"
set -euo pipefail

pick_gpu_most_free() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "0"
    return 0
  fi
  python3 - <<'PY'
import subprocess
import sys

try:
    out = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-gpu=index,memory.free",
            "--format=csv,noheader,nounits",
        ],
        text=True,
    )
except (subprocess.CalledProcessError, FileNotFoundError):
    print("0")
    sys.exit(0)

best_i, best_free = 0, -1.0
for line in out.strip().splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) != 2:
        continue
    idx, free = int(parts[0]), float(parts[1])
    if free > best_free:
        best_i, best_free = idx, free

print(best_i)
PY
}

gpu_free_mib() {
  local idx="${1:-0}"
  nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i "$idx" 2>/dev/null | tr -d ' ' || echo "0"
}

log_gpu_table() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "[gpu] nvidia-smi not available"
    return 0
  fi
  echo "[gpu] free VRAM (MiB) per device:"
  nvidia-smi --query-gpu=index,memory.free,memory.total --format=csv,noheader | sed 's/^/[gpu]   /'
}

case "${1:-pick}" in
  pick)
    pick_gpu_most_free
    ;;
  log)
    log_gpu_table
    ;;
  export)
    # shellcheck disable=SC2034
    var="${2:-GPU}"
    idx="$(pick_gpu_most_free)"
    echo "export ${var}=${idx}"
    ;;
  *)
    echo "Usage: $0 [pick|log|export VAR_NAME]" >&2
    exit 2
    ;;
esac
