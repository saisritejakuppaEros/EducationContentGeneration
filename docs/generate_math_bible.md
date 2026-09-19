# generate_math_bible

Extracts sub-topics, equations, and Manim scope from chapter text.

## Purpose

Stage 1 — Mathematician Agent. Locks `core_visual_idea` and `explicitly_excluded` per topic before any visuals run.

## Inputs

- `scripts/samples/input_docs.md` — chapter TOC/text (default)
- `scripts/prompts/math_bible.md`
- `scripts/samples/math_bible.json` — schema reference

## Outputs

- `output/math_bible/math_bible.json`
- `output/pipeline/gates/math_bible.json`

## Usage

```bash
python scripts/stages/generate_math_bible.py --input scripts/samples/input_docs.md
python scripts/stages/generate_math_bible.py --backend qwen --skip-gate
```
