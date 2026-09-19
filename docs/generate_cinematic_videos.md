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
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --prompts-only
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --scene SC01 --skip-existing
```

Use `--deterministic-prompts` to build LTX prompts without an LLM. Visual prompts strip on-screen text; speech is capped at 15 words.
