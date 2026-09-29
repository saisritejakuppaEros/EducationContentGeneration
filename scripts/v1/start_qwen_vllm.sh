#!/usr/bin/env bash
# Start Qwen 3.5 for director / story layout (OpenAI-compatible vLLM on port 8007).
set -euo pipefail

PORT="${VLLM_PORT:-8007}"
MODEL="${QWEN_MODEL:-Qwen/Qwen3.5-27B}"

source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME="${HF_HOME:-/workspace/teja/models/hub}"
export TORCH_HOME="${TORCH_HOME:-/workspace/torch-cache}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME}"

echo "Starting vLLM: $MODEL on 0.0.0.0:$PORT"
echo "In another terminal:"
echo "  export OPENAI_API_BASE=http://localhost:$PORT/v1"
echo "  export QWEN_MODEL=$MODEL"
echo "  curl -s \$OPENAI_API_BASE/models | head"
echo

exec vllm serve "$MODEL" \
  --host 0.0.0.0 \
  --port "$PORT" \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --gpu-memory-utilization 0.86
