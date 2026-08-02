#!/usr/bin/env bash
# Generate all MATH INSERT Manim videos using local Qwen 3.5 via vLLM.
#
# Terminal 1 (keep running):
#   source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
#   conda activate gsplat_env
#   vllm serve Qwen/Qwen3.5-27B --host 0.0.0.0 --port 8000 \
#     --dtype bfloat16 --max-model-len 32768 --max-num-seqs 64 \
#     --gpu-memory-utilization 0.90
#
# Terminal 2:
#   bash scripts/run_all_manim_videos.sh
#   bash scripts/run_all_manim_videos.sh --render-only   # MP4 only, no LLM

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

source .venv/bin/activate

export OPENAI_API_BASE="${OPENAI_API_BASE:-http://localhost:8000/v1}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-local}"
export QWEN_MODEL="${QWEN_MODEL:-openai/Qwen/Qwen3.5-27B}"

REVIEW_CYCLES="${REVIEW_CYCLES:-3}"
MAX_TOKENS="${MAX_TOKENS:-8192}"
TEMPERATURE="${TEMPERATURE:-0.6}"

# All MATH INSERT shots in the storyboard (shot 2 in each mixed scene)
SCENES=(S2 S4 S6 S8 S10 S12 S14 S16)

MODE=(--skip-existing)
if [[ "${1:-}" == "--render-only" ]]; then
  MODE=(--render-only --skip-existing)
  shift
fi

echo "Using model: $QWEN_MODEL"
echo "API base:    $OPENAI_API_BASE"
echo "Mode:        ${MODE[*]}"
echo

if [[ "${MODE[*]}" != *render-only* ]]; then
  curl -sf "$OPENAI_API_BASE/models" >/dev/null || {
    echo "ERROR: vLLM not reachable at $OPENAI_API_BASE"
    echo "Start the Qwen server first (see script header)."
    exit 1
  }
fi

for scene in "${SCENES[@]}"; do
  echo "========== $scene shot 2 =========="
  python scripts/generate_manim_videos.py \
    --scene "$scene" \
    --shot 2 \
    --manim-model "$QWEN_MODEL" \
    --review-model "$QWEN_MODEL" \
    --review-cycles "$REVIEW_CYCLES" \
    --temperature "$TEMPERATURE" \
    --max-tokens "$MAX_TOKENS" \
    "${MODE[@]}"
  echo
done

echo "All done. Videos and manifest:"
echo "  output/manim_videos/manifest.json"
echo "  output/manim_videos/S*/S*_shot02.mp4"
