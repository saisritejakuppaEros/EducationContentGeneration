# generate_series_profile

Creates or updates cast, world, and visual grammar for the series.

## Purpose

Stage 3 — Character & Series Profile Agent. Seeds reference photo placeholders for M/F/Y.

## Inputs

- `scripts/prompts/series_profile.md`
- Optional existing `output/series_profile/series_profile.json`
- Optional `output/screenplay/screenplay.json` for chapter updates

## Outputs

- `output/series_profile/series_profile.json`

## Usage

```bash
python scripts/stages/generate_series_profile.py
python scripts/stages/generate_series_profile.py --existing output/series_profile/series_profile.json
```
