# assemble_final_cut

Concatenates LTX cinematic clips, Manim math inserts, and Flux keyframe stills into one English MP4 in storyboard order.

## Purpose

Stage 7 — stitch all generated video assets into a single flowing cut. Math inserts can receive TTS narration from stage 6.

## Inputs

- `output/storyboard/storyboard.json` — shot order and durations
- `output/cinematic_videos/` — LTX MP4s (preferred for non-math shots)
- `output/manim_videos/` — math insert MP4s
- `output/storyboard/` — Flux keyframe PNG fallback when LTX video is missing
- `output/audio/audio_plan.json` — optional math narration WAV paths

Legacy `output/ltx_videos/` and `output/flux_images/` are used automatically if the new folders are empty.

## Outputs

- `output/final_cut/<title_slug>_en.mp4`
- `output/final_cut/manifest.json`

## Usage

```bash
python scripts/stages/assemble_final_cut.py
python scripts/stages/assemble_final_cut.py --assets-root output --output-name complex_numbers
```

Requires `ffmpeg` on PATH.

## Clip resolution (per shot)

1. **MATH INSERT** → Manim MP4 (with math narration audio when available)
2. **Other shots** → LTX MP4 if present
3. **Fallback** → Flux PNG turned into a timed still clip

Missing shots are skipped with a warning.
