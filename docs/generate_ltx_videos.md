# generate_ltx_videos

Runs LTX 2.3 image-to-video inference with **native audio** from Flux init frames + `ltx_prompts.json`.

## Purpose

Stage 7 of the pipeline: turn each Flux PNG and tagged LTX prompt into an MP4 with synchronized sound. Skips `ltx_mode: skip` shots (Manim math inserts).

## Inputs

- `output/ltx_prompts/ltx_prompts.json` — tagged `[VISUAL]` / `[SPEECH]` / `[SOUNDS]` prompts per shot
- `output/flux_images/` — init frame PNGs referenced by `init_image`
- **Model:** `diffusers/LTX-2.3-Diffusers` (cached under `HF_HOME`, not `TORCH_HOME`)
- **Talking-head LoRA (optional):** `elix3r/LTX-2.3-22b-AV-LoRA-talking-head` for `use_talking_head_lora: true` shots

Requires `diffusers>=0.39` with LTX2 support in `gsplat_env`:

```bash
pip install 'diffusers>=0.39.0'
```

## Outputs

All artifacts go under `output/ltx_videos/`:

- `S0/S0_shot01.mp4`, … — one MP4 per renderable shot (video + audio)
- `manifest.json` — seeds, frame counts, init image paths

## Usage

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

export HF_HOME=/workspace/teja/models/hub
export HF_HUB_CACHE=$HF_HOME
unset TORCH_HOME

python scripts/generate_ltx_videos.py --scene S0 --skip-existing
```

Batch all shots:

```bash
bash scripts/run_all_ltx_videos.sh
```

First-time model download (omit `--local-files-only`). After cache is warm:

```bash
python scripts/generate_ltx_videos.py --local-files-only --skip-existing
```

Optional flags: `--prompts`, `--model`, `--hf-home`, `--scene`, `--shot`, `--seed`, `--width`, `--height`, `--num-inference-steps`, `--talking-head-strength`, `--sequential-offload`, `--no-cpu-offload`, `--skip-existing`.
