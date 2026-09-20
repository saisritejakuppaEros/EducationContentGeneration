# generate_screenplay

Turns `math_specs.json` into a scene-by-scene screenplay with dialogue.

## Purpose

Stage 2 — Screenwriter Agent. Produces JSON + human-readable Markdown review copy.

## Inputs

- `output/topic_specs/math_specs.json`
- `output/series_profile/series_profile.json` (optional)
- `scripts/prompts/screenplay.md`

## Outputs

- `output/screenplay/screenplay.json`
- `output/screenplay/screenplay.md`

## Usage

```bash
python scripts/stages/generate_screenplay.py --topic-specs output/topic_specs/math_specs.json
```
