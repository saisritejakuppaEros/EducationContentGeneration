# generate_screenplay

Turns `math_bible.json` into a scene-by-scene screenplay with dialogue.

## Purpose

Stage 2 — Screenwriter Agent. Produces JSON + human-readable Markdown review copy.

## Inputs

- `output/math_bible/math_bible.json`
- `output/series_bible/series_bible.json` (optional)
- `scripts/prompts/screenplay.md`

## Outputs

- `output/screenplay/screenplay.json`
- `output/screenplay/screenplay.md`

## Usage

```bash
python scripts/stages/generate_screenplay.py --math-bible output/math_bible/math_bible.json
```
