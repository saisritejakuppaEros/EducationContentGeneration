# generate_series_bible

Creates or updates cast, world, and visual grammar for the series.

## Purpose

Stage 3 — Character & Story Bible Agent. Seeds reference photo placeholders for M/F/Y.

## Inputs

- `scripts/prompts/series_bible.md`
- Optional existing `output/series_bible/series_bible.json`
- Optional `output/screenplay/screenplay.json` for chapter updates

## Outputs

- `output/series_bible/series_bible.json`

## Usage

```bash
python scripts/stages/generate_series_bible.py
python scripts/stages/generate_series_bible.py --existing output/series_bible/series_bible.json
```
