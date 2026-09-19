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

# Use a free port (8000 is often Daydream Scope on this machine).
# Qwen3.5 is Mamba/hybrid: max_num_seqs must be <= available Mamba cache blocks.
vllm serve Qwen/Qwen3.5-27B \
  --host 0.0.0.0 \
  --port 8007 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --gpu-memory-utilization 0.86
```

**Startup errors**

| Error | Fix |
|-------|-----|
| `max_num_seqs exceeds available Mamba cache blocks` | Already fixed by `--max-num-seqs 64`; try `32` if it still fails |
| `Free memory ... is less than desired GPU memory utilization` | Another process is using VRAM (~12 GiB in your log). Run `nvidia-smi` and stop stale jobs, **or** lower `--gpu-memory-utilization` to `0.86` (free ÷ total, e.g. 82.44 / 94.97) |

After a failed vLLM run, orphaned engine processes may still hold GPU memory. Kill them before restarting:

```bash
nvidia-smi
# then: kill <pid> for stale python/vllm processes, or:
pkill -f "vllm serve"
```

### 2. Work terminal env

```bash
cd /devwork/teja/EducationContentGeneration
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export OPENAI_API_BASE=http://localhost:8007/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL=Qwen/Qwen3.5-27B
```

Verify: `curl http://localhost:8007/v1/models`

---

## Pipeline (Qwen for all text/LLM stages)

Layout and stage order: [scripts/README.md](scripts/README.md) (`lib/`, `stages/`, `knowledge/`, `legacy/`).

```bash
# Preview stages
python3 scripts/run_pipeline.py --dry-run

# Text stages (Qwen)
python3 scripts/run_pipeline.py --from-stage 1 --to-stage 4

# Or step by step
python3 scripts/stages/generate_math_bible.py --input scripts/samples/input_docs.md
python3 scripts/stages/generate_screenplay.py
python3 scripts/stages/generate_series_bible.py
python3 scripts/stages/build_reference_bank.py --copy-only
python3 scripts/stages/generate_storyboard.py

# GPU pixel stages (Flux / LTX / Manim — prompts still Qwen)
python3 scripts/stages/generate_storyboard_keyframes.py --skip-existing
python3 scripts/stages/generate_cinematic_videos.py --skip-existing
source .venv/bin/activate && python3 scripts/stages/generate_manim_videos.py --skip-existing

# Audio + final cut
python3 scripts/stages/generate_audio.py
python3 scripts/stages/assemble_final_cut.py
```

`run_pipeline.py` automatically passes `--backend qwen` to every LLM stage.

---

## Outputs

Default root: `output/` (override with `--output-root output/run_name` on any script or orchestrator).

| Stage | Output |
|-------|--------|
| 1 | `<root>/math_bible/math_bible.json` |
| 2 | `<root>/screenplay/screenplay.json` |
| 3 | `<root>/series_bible/series_bible.json` |
| 4 | `<root>/storyboard/storyboard.json` |
| 4b | `<root>/storyboard/*.png` |
| 5a | `<root>/cinematic_videos/` |
| 5b | `<root>/manim_videos/` |
| 6 | `<root>/audio/` |
| 7 | `<root>/final_cut/` |

Compare two runs:

```bash
python3 scripts/run_pipeline.py --output-root output/run_a --from-stage 1 --to-stage 4 --force
python3 scripts/run_pipeline.py --output-root output/run_b --from-stage 1 --to-stage 4 --force
diff -ru output/run_a/screenplay output/run_b/screenplay
```

See `plan.md` for full architecture.





(gsplat_env) parth_h200@ai-core-team-3:/devwork/teja/EducationContentGeneration$ vllm serve Qwen/Qwen3.5-27B   --host 0.0.0.0--port 8000   --dtype bfloat16   --max-model-len 32768   --max-num-seqs 64   --gpu-memory-utilization 0.90