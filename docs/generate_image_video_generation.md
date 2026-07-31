# generate_image_video_generation

Shot-level breakdown for Flux still frames and WAN 2.2 motion generation.

## Purpose

Stage 3 of the textbook-to-movie pipeline: decompose the story and math into second-accurate scenes and shots.

## Inputs

- `output/problem_statement_buildup/problem_statement_buildup.json` — narrative framework
- `output/ps_math_linkup/ps_math_linkup.json` — equations per sub-topic
- `prompts/image_video_generation.md` — prompt template
- `samples/image_video_generation.json` — JSON schema reference
- `gemma4_model/` — local Gemma 4 weights

## Outputs

All artifacts go under `output/image_video_generation/`:

- `image_video_generation.json` — visual style bible + scenes + shots

## JSON shape

Top-level: `story_title`, `tone_target`, `total_runtime_target`, `visual_style_bible`, `scenes`.

Each scene: `scene_id`, `chapter`, `render_type` (wan/manim/mixed), `topic_ids`, timing, `beat`, `shots[]`.

Each shot: `shot`, `time`, `duration_seconds`, `type`, `flux_frame`, `wan_motion`, `dialogue`.

## Usage

```bash
python scripts/generate_image_video_generation.py
```

Optional flags: `--problem-statement`, `--math-linkup`, `--reference`, `--prompt`, `--model-path`, `--output-file`, `--max-new-tokens`, `--disable-thinking`.
