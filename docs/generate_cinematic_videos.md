# generate_cinematic_videos

Builds cinematic prompts from storyboard and renders MP4 clips (**local MiniMax-H3 via ComfyUI** by default, or local **LTX 2.3**, or optional cloud API).

## Purpose

Stage 5a — Cinematic Video Agent. Wraps prompt generation + `generate_minimax_h3_local_videos.py` (default), `generate_ltx_videos.py`, or `generate_minimax_videos.py` (API).

## Inputs

- `output/storyboard/storyboard.json`
- `output/series_profile/series_profile.json`
- Keyframe PNGs under `output/storyboard/`

## Outputs

- `output/cinematic_videos/cinematic_prompts.json`
- `output/cinematic_videos/<scene_id>/<scene_id>_shot##.mp4`
- `output/cinematic_videos/manifest.json`

## Usage

```bash
# See docs/minimax_h3_local_comfyui.md for ComfyUI + MINIMAX_H3_* env
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --prompts-only
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --scene SC01 --skip-existing

python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --video-backend ltx --scene SC01
```

## QC after clips exist

Stage **5c** (`validate_production_assets.py`) scores each shot MP4 (0–100) and writes:

- `output/.../pipeline/qc_report.json` — per-shot `score`, `reasons`, composition + director checklist
- `output/.../pipeline/contact_sheet.html` — visual review grid

Run via `run_pipeline.py --from-stage 5c` (see root `run.sh` after pixels).

Use `--deterministic-prompts` to build LTX prompts without an LLM. Visual prompts strip on-screen text; speech is capped at 15 words.
