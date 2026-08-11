# generate_cinematic_videos

Generates LTX 2.3 cinematic prompts from storyboard and renders MP4 clips.

## Purpose

Stage 5a — Cinematic Video Agent. Wraps prompt generation + `generate_ltx_videos.py`.

## Inputs

- `output/storyboard/storyboard.json`
- `output/series_bible/series_bible.json`
- Keyframe PNGs under `output/storyboard/`

## Outputs

- `output/cinematic_videos/cinematic_prompts.json`
- `output/cinematic_videos/<scene_id>/<scene_id>_shot##.mp4`
- `output/cinematic_videos/manifest.json`

## Usage

```bash
export OPENAI_API_BASE=http://localhost:8000/v1
python scripts/generate_cinematic_videos.py --prompts-only
python scripts/generate_cinematic_videos.py --scene SC01 --skip-existing
```
