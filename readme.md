# Education Content Generation

Textbook chapter → sci-fi educational film pipeline.

All **LLM tasks use Qwen via vLLM** (local OpenAI-compatible API). Per-module details in `docs/`.

---

## Prerequisites

### 1. Start Qwen vLLM (keep running)

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME=/workspace/teja/models/hub
export TORCH_HOME=/workspace/torch-cache
export HF_HUB_CACHE=$HF_HOME

vllm serve Qwen/Qwen3.5-27B \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.90
```

### 2. Work terminal env

```bash
cd /devwork/teja/EducationContentGeneration
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=Qwen/Qwen3.5-27B
```

Verify: `curl http://localhost:8000/v1/models`

---

## Pipeline (Qwen for all text/LLM stages)

```bash
# Preview stages
python3 scripts/run_pipeline.py --dry-run

# Text stages (Qwen)
python3 scripts/run_pipeline.py --from-stage 1 --to-stage 4

# Or step by step
python3 scripts/generate_math_bible.py --input scripts/samples/input_docs.md
python3 scripts/generate_screenplay.py
python3 scripts/generate_series_bible.py
python3 scripts/build_reference_bank.py --copy-only
python3 scripts/generate_storyboard.py

# GPU pixel stages (Flux / LTX / Manim — prompts still Qwen)
python3 scripts/generate_storyboard_keyframes.py --skip-existing
python3 scripts/generate_cinematic_videos.py --skip-existing
source .venv/bin/activate && python3 scripts/generate_manim_videos.py --skip-existing

# Audio + final cut
python3 scripts/generate_audio.py
python3 scripts/assemble_final_cut.py --chapter-slug complex_numbers
```

`run_pipeline.py` automatically passes `--backend qwen` to every LLM stage.

---

## Outputs

| Stage | Output |
|-------|--------|
| 1 | `output/math_bible/math_bible.json` |
| 2 | `output/screenplay/screenplay.json` |
| 3 | `output/series_bible/series_bible.json` |
| 4 | `output/storyboard/storyboard.json` |
| 4b | `output/storyboard/*.png` |
| 5a | `output/cinematic_videos/` |
| 5b | `output/manim_videos/` |
| 6 | `output/audio/` |
| 7 | `output/final_cut/` |

See `plan.md` for full architecture.





(gsplat_env) parth_h200@ai-core-team-3:/devwork/teja/EducationContentGeneration$ vllm serve Qwen/Qwen3.5-27B   --host 0.0.0.0--port 8000   --dtype bfloat16   --max-model-len 32768   --max-num-seqs 64   --gpu-memory-utilization 0.90