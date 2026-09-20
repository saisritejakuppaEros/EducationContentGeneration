# generate_cinematic_videos

Builds cinematic prompts from storyboard and renders MP4 clips (**MiniMax-H3** cloud I2V by default, or local **LTX 2.3**).

## Purpose

Stage 5a — Cinematic Video Agent. Wraps prompt generation + `generate_minimax_videos.py` (default) or `generate_ltx_videos.py`.

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
export MINIMAX_API_KEY=...   # required for default backend
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --prompts-only
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --scene SC01 --skip-existing

# Local GPU instead of MiniMax-H3:
python scripts/stages/generate_cinematic_videos.py --deterministic-prompts --video-backend ltx --scene SC01
```

## QC after clips exist

Stage **5c** (`validate_production_assets.py`) scores each shot MP4 (0–100) and writes:

- `output/.../pipeline/qc_report.json` — per-shot `score`, `reasons`, composition + director checklist
- `output/.../pipeline/contact_sheet.html` — visual review grid

Run via `run_pipeline.py --from-stage 5c` (see root `run.sh` after pixels).

Use `--deterministic-prompts` to build LTX prompts without an LLM. Visual prompts strip on-screen text; speech is capped at 15 words.
