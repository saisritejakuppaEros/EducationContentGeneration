# generate_storyboard_keyframes

Renders storyboard keyframe PNGs with FLUX.2-dev multi-reference + optional mask retry.

## Purpose

Stage 4b — pixel generation for cinematic video init frames.

## Inputs

- `output/storyboard/storyboard.json`
- `output/series_bible/series_bible.json`
- Reference photos from `output/series_bible/reference_photos/`

## Outputs

- `output/storyboard/<scene_id>/<scene_id>_shot##.png`
- `output/storyboard/keyframes_manifest.json`

## Usage

```bash
python scripts/generate_storyboard_keyframes.py --skip-existing
python scripts/generate_storyboard_keyframes.py --scene SC01 --mask-retry
```
