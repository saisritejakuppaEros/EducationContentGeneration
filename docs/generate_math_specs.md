# generate_topic_specs

Extracts sub-topics, equations, and Manim scope from chapter text.

## Purpose

Stage 1 — Mathematician Agent. Locks `core_visual_idea` and `explicitly_excluded` per topic before any visuals run.

## Inputs

- `scripts/samples/input_docs.md` — chapter TOC/text (default)
- `scripts/prompts/math_specs.md`
- `scripts/samples/math_specs.json` — schema reference

## Outputs

- `output/topic_specs/math_specs.json`
- `output/pipeline/gates/math_specs.json`

## Usage

```bash
python scripts/stages/generate_math_specs.py --input scripts/samples/input_docs.md
python scripts/stages/generate_math_specs.py --backend qwen --skip-gate
```
