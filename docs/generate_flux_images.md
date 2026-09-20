# generate_flux_images

Runs local FLUX 2.0 inference using **person reference photos** + **flux_prompts.json** to render still frames.

## Purpose

Stage 5 of the pipeline: for each shot in `flux_prompts.json`, generate a PNG. Character shots also pass the matching person photo(s) into FLUX 2.0 as image input.

## Inputs

1. **Person photos** (`person/` by default)
   - `person/friend.png` → cast **F** (Friend)
   - `person/ramanujan.jpeg` → cast **M** (Mathematician)

2. **Prompts JSON** (`output/flux_prompts/flux_prompts.json` by default)
   - One `flux_prompt` per shot
   - Cast keys **M** / **F** from `visual_style_guide.cast` decide which person photo(s) to attach

3. **Model weights** — `/workspace/parth/models/hub/models--black-forest-labs--FLUX.2-dev`

## Outputs

All artifacts go under `output/flux_images/`:

- `S0/S0_shot01.png`, … — one PNG per shot
- `manifest.json` — which person photos and prompts were used per shot

Math-only shots (no characters) use the text prompt only.

## Usage

```bash
source /devwork/MiniConda/miniconda3/etc/profile.d/conda.sh
conda activate gsplat_env

python scripts/legacy/generate_flux_images.py --skip-existing
```

Explicit inputs:

```bash
python scripts/legacy/generate_flux_images.py \
  --person-dir person \
  --prompts output/flux_prompts/flux_prompts.json \
  --skip-existing
```

Optional flags: `--scene`, `--shot`, `--seed`, `--num-inference-steps`, `--guidance-scale`, `--width`, `--height`, `--no-cpu-offload`, `--skip-existing`.
