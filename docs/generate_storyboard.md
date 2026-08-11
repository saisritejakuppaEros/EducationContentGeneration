# generate_storyboard

Breaks screenplay scenes into fully specified shots (text only).

## Purpose

Stage 4a — Storyboard Agent shot breakdown with lens, scale, blocking, and Flux prompts.

## Inputs

- `output/screenplay/screenplay.json`
- `output/series_bible/series_bible.json`
- `scripts/prompts/storyboard.md`

## Outputs

- `output/storyboard/storyboard.json`

## Usage

```bash
python scripts/generate_storyboard.py --scene SC01
python scripts/generate_storyboard.py --backend qwen
```
