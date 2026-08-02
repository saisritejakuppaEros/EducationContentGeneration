# Education Content Generation

Textbook-to-movie pipeline: narrative framework → math linkup → storyboard → Flux stills → LTX video → Manim math inserts.

Per-module details live in `docs/`.

---

## Prerequisites

### Conda + cache paths

Use this for Gemma, Flux, and LTX inference (`gsplat_env`):

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME=/workspace/teja/models/hub
export TORCH_HOME=/workspace/torch-cache
export PIP_CACHE_DIR=/workspace/users/$USER/.pip-cache
export HF_HUB_CACHE=$HF_HOME
```

### Project root

```bash
cd /devwork/teja/EducationContentGeneration
```

### One-time LTX setup (before stage 7)

```bash
pip install 'diffusers>=0.39.0'
```

---

## Pipeline overview

| Step | Script | Env | Needs vLLM? |
|------|--------|-----|-------------|
| 1 | `generate_problem_statement_buildup.py` | `gsplat_env` | No (local Gemma) |
| 2 | `generate_ps_math_linkup.py` | `gsplat_env` | No |
| 3 | `generate_image_video_generation.py` | `gsplat_env` | No |
| 4 | `generate_flux_prompts.py` | `gsplat_env` | No |
| 5 | `generate_flux_images.py` | `gsplat_env` | No |
| 6 | `generate_ltx_prompts.py` | `gsplat_env` | Yes (Qwen default) |
| 7 | `generate_ltx_videos.py` | `gsplat_env` | No |
| 8 | `generate_manim_videos.py` | `.venv` | Yes |

---

## Terminal layout

```text
Terminal A (keep running):  vLLM Qwen on :8000
Terminal B (work):          gsplat_env → stages 1–5, 7
                            .venv      → stage 8 (Manim)
```

---

## Step 1 — Start Qwen vLLM (stages 6 & 8)

**Terminal A** — keep this running:

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME=/workspace/teja/models/hub
export TORCH_HOME=/workspace/torch-cache
export PIP_CACHE_DIR=/workspace/users/$USER/.pip-cache
export HF_HUB_CACHE=$HF_HOME

vllm serve Qwen/Qwen3.5-27B \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype bfloat16 \
  --max-model-len 32768 \
  --max-num-seqs 64 \
  --gpu-memory-utilization 0.90
```

**Terminal B** — verify the server is up:

```bash
curl http://localhost:8000/v1/models
```

---

## Step 2 — Story framework (Gemma, stages 1–4)

**Terminal B** — `gsplat_env`:

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env
cd /devwork/teja/EducationContentGeneration
```

### 2a. Problem statement → sci-fi narrative

```bash
python scripts/generate_problem_statement_buildup.py
```

Output: `output/problem_statement_buildup/problem_statement_buildup.json`

### 2b. Map story beats to math equations

```bash
python scripts/generate_ps_math_linkup.py
```

Output: `output/ps_math_linkup/ps_math_linkup.json`

### 2c. Shot-level storyboard

```bash
python scripts/generate_image_video_generation.py
```

Output: `output/image_video_generation/image_video_generation.json`

### 2d. Enhance Flux still-frame prompts

```bash
python scripts/generate_flux_prompts.py
```

Specific scenes only:

```bash
python scripts/generate_flux_prompts.py --scene S0 --scene S1
```

Output: `output/flux_prompts/flux_prompts.json`

---

## Step 3 — Flux still images (stage 5)

Still in **`gsplat_env`**:

```bash
python scripts/generate_flux_images.py --skip-existing
```

Explicit paths:

```bash
python scripts/generate_flux_images.py \
  --person-dir person \
  --prompts output/flux_prompts/flux_prompts.json \
  --skip-existing
```

Output: `output/flux_images/S*/S*_shot*.png`

---

## Step 4 — LTX prompt generation (stage 6)

Requires **vLLM running** (Step 1).

```bash
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL="openai/Qwen/Qwen3.5-27B"

python scripts/generate_ltx_prompts.py --scene S0
```

All scenes:

```bash
python scripts/generate_ltx_prompts.py
```

Use local Gemma instead of Qwen (no vLLM needed):

```bash
python scripts/generate_ltx_prompts.py --backend gemma
```

Output: `output/ltx_prompts/ltx_prompts.json`

---

## Step 5 — LTX video generation (stage 7)

**`gsplat_env`** — LTX weights use `HF_HOME`, not `TORCH_HOME`:

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env
cd /devwork/teja/EducationContentGeneration

export HF_HOME=/workspace/teja/models/hub
export HF_HUB_CACHE=$HF_HOME
unset TORCH_HOME
```

One scene:

```bash
python scripts/generate_ltx_videos.py --scene S0 --skip-existing
```

All scenes (batch script):

```bash
bash scripts/run_all_ltx_videos.sh
```

After models are cached locally:

```bash
python scripts/generate_ltx_videos.py --local-files-only --skip-existing
```

Output: `output/ltx_videos/S*/S*_shot*.mp4`

---

## Step 6 — Manim math inserts (stage 8)

Requires **vLLM running** (Step 1).

**Terminal B** — project venv:

```bash
cd /devwork/teja/EducationContentGeneration
source .venv/bin/activate

export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=sk-local
export QWEN_MODEL="openai/Qwen/Qwen3.5-27B"
```

Preview prompts only (no LLM call):

```bash
python scripts/generate_manim_videos.py --dry-run
```

Single shot:

```bash
python scripts/generate_manim_videos.py \
  --scene S2 --shot 2 \
  --manim-model "$QWEN_MODEL" \
  --review-model "$QWEN_MODEL" \
  --review-cycles 3 \
  --temperature 0.6 \
  --max-tokens 8192
```

All MATH INSERT shots (S2, S4, S6, S8, S10, S12, S14, S16 — shot 2 each):

```bash
bash scripts/run_all_manim_videos.sh
```

Re-render MP4s from existing code (no LLM):

```bash
bash scripts/run_all_manim_videos.sh --render-only
```

Output: `output/manim_videos/S*/S*_shot02.mp4`

---

## Outputs checklist

| Stage | Key output |
|-------|------------|
| 1 | `output/problem_statement_buildup/problem_statement_buildup.json` |
| 2 | `output/ps_math_linkup/ps_math_linkup.json` |
| 3 | `output/image_video_generation/image_video_generation.json` |
| 4 | `output/flux_prompts/flux_prompts.json` |
| 5 | `output/flux_images/` |
| 6 | `output/ltx_prompts/ltx_prompts.json` |
| 7 | `output/ltx_videos/manifest.json` |
| 8 | `output/manim_videos/manifest.json` |
