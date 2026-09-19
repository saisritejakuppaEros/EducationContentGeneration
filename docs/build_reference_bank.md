# build_reference_bank

Builds multi-angle reference photo banks for M/F/Y using FLUX.2-dev.

## Purpose

Stage 3b — expands single source photos into tagged reference sets for storyboard keyframes.

## Inputs

- `output/series_bible/series_bible.json`
- `assets/images/` source photos (`ramanujan.jpeg`, `friend.png`)
- `scripts/prompts/reference_bank.md`

## Outputs

- `output/series_bible/reference_photos/{M,F,Y}/*.png`
- `output/series_bible/reference_photos/manifest.json`

## Usage

```bash
python scripts/stages/build_reference_bank.py --copy-only
python scripts/stages/build_reference_bank.py --skip-existing
```

Use `--copy-only` to bootstrap without GPU. Remove it for Flux-generated angle variants.
