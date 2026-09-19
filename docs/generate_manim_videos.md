# generate_manim_videos

Generates Manim math-insert videos for **MATH INSERT** / **CONCEPT** shots using the `manim-generator` LLM workflow.

## Purpose

Stage 5b — Math Insert Agent. Visualizes only `core_visual_idea` from the math bible (no full derivations).

## Inputs

1. **Storyboard** — `output/storyboard/storyboard.json` (default)
2. **Math bible** — `output/math_bible/math_bible.json` (default)
   - Legacy: `--math-linkup output/ps_math_linkup/ps_math_linkup.json`
3. **manim-generator** — project venv; calls `ManimWorkflow` programmatically

## Outputs

All artifacts under `output/manim_videos/`:

- `<scene_id>/<scene_id>_shot##.mp4` — final rendered insert
- `<topic_id>.mp4` — when keyed by topic
- `manifest.json` — success status, paths, token cost

## Usage

```bash
source .venv/bin/activate
export OPENAI_API_BASE=http://localhost:8000/v1

python scripts/stages/generate_manim_videos.py \
  --storyboard output/storyboard/storyboard.json \
  --math-bible output/math_bible/math_bible.json \
  --scene SC02 --skip-existing
```
