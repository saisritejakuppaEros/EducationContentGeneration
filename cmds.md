source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME=/workspace/teja/models/hub
export HF_HUB_CACHE=$HF_HOME

vllm serve Qwen/Qwen3.5-27B \
  --host 0.0.0.0 \
  --port 8009 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --gpu-memory-utilization 0.70


export OPENAI_API_BASE=http://localhost:8009/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=Qwen/Qwen3.5-27B
export RUN=output/debug_20260811_1012

curl -s $OPENAI_API_BASE/models | python3 -m json.tool

# Resume (series bible already exists — start at 3b or 4)
python3 scripts/run_pipeline.py \
  --output-root $RUN \
  --from-stage 1 \
  --to-stage 4 \
  --force


