# generate_flux_prompts

Enhances raw `flux_frame` shot descriptions into production-grade Flux 2.0 prompts.

## Purpose

Stage 4 of the pipeline: take shot breakdowns and produce detailed, camera-specific Flux 2.0 still-frame prompts for each shot.

## Inputs

- `output/image_video_generation/image_video_generation.json` — shot breakdown (default)
- `prompts/flux_prompt_enhancement.md` — enhancement prompt template
- `samples/flux_prompts.json` — reference quality/schema
- `gemma4_model/` — local Gemma 4 weights

## Outputs

All artifacts go under `output/flux_prompts/`:

- `flux_prompts.json` — scenes with enhanced `flux_prompt` and `flux_prompt_structured` per shot

## JSON shape

Each shot keeps original fields plus:

- `flux_prompt` — 80–200 word Flux 2.0 prose prompt (SASC framework)
- `flux_prompt_structured` — subject, action, environment, lighting, camera, lens, composition, color_grade, mood, style_reference

MATH INSERT shots use graphic/educational style; WAN shots use cinematic photorealism with camera specs.

## Usage

```bash
python scripts/generate_flux_prompts.py
```

Process specific scenes only:

```bash
python scripts/generate_flux_prompts.py --scene S0 --scene S1
```

Optional flags: `--input`, `--reference`, `--prompt`, `--model-path`, `--output-file`, `--max-new-tokens`, `--disable-thinking`.
