# generate_manim_videos

Generates Manim math-insert videos for **MATH INSERT** shots using the `manim-generator` LLM workflow.

## Purpose

Pipeline stage for animated math screen inserts. Reads the storyboard and math linkup JSON, builds a focused Manim prompt per shot, runs code generation + review cycles, and renders an MP4.

Replaces Flux 2.0 still generation for shots where `type` is `MATH INSERT`.

## Inputs

1. **Storyboard** — `output/image_video_generation/image_video_generation.json` (default)
   - Scenes with `render_type: "mixed"` contain MATH INSERT shots
   - Uses `flux_frame`, `wan_motion`, and `duration_seconds` from each shot

2. **Math linkup** — `output/ps_math_linkup/ps_math_linkup.json` (default)
   - Equations, problems, and explanations keyed by `topic_ids` on each scene

3. **manim-generator** — installed in the project venv; calls `ManimWorkflow` programmatically

## Outputs

All artifacts go under `output/manim_videos/`:

- `S2/S2_shot02.mp4` — final rendered math insert per shot
- `S2/S2_shot02/` — full workflow run (code, steps, intermediate renders)
- `manifest.json` — success status, paths, token cost per shot

## Usage

Preview prompts without calling the LLM:

```bash
python scripts/generate_manim_videos.py --dry-run
```

Generate one shot:

```bash
python scripts/generate_manim_videos.py --scene S2 --shot 2
```

Generate all MATH INSERT shots, skipping completed ones:

```bash
bash scripts/run_all_manim_videos.sh
```

Render MP4s from existing generated code (no LLM), e.g. after a failed run:

```bash
bash scripts/run_all_manim_videos.sh --render-only
```

Or recover a single shot:

```bash
python scripts/generate_manim_videos.py --scene S2 --shot 2 --render-only
```

Optional flags: `--storyboard`, `--math-linkup`, `--manim-model`, `--review-model`, `--review-cycles`, `--temperature`, `--max-tokens`, `--scene-timeout`, `--render-only`, `--no-render`.
