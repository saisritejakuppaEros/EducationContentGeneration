# generate_storyboard_keyframes

Renders storyboard keyframe PNGs with FLUX.2-dev multi-reference + optional mask retry.

## Purpose

Stage 4b — pixel generation for cinematic video init frames.

## Inputs

- `output/storyboard/storyboard.json`
- `output/series_profile/series_profile.json`
- Reference photos from `output/series_profile/reference_photos/`
- Fallback source photos from `assets/images/` (`ramanujan.jpeg` for M, `friend.png` for F/Y)

Cast references are inferred from `flux_prompt` when `characters_in_frame` is empty. See `keyframes_manifest.json` → `reference_details` for per-shot audit.

## Outputs

- `output/storyboard/<scene_id>/<scene_id>_shot##.png`
- `output/storyboard/keyframes_manifest.json`

## Usage

```bash
python scripts/stages/generate_storyboard_keyframes.py --skip-existing
python scripts/stages/generate_storyboard_keyframes.py --scene SC01 --mask-retry
```
