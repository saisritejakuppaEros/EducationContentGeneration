# assemble_final_cut

Assembles cinematic clips, Manim inserts, and audio into final MP4(s) per language.

## Purpose

Stage 7 — Editor Agent. Deterministic ffmpeg concat + audio mux + EDL export.

## Inputs

- `output/storyboard/storyboard.json`
- `output/cinematic_videos/` MP4s
- `output/manim_videos/` MP4s
- `output/audio/` WAVs and subtitles

## Outputs

- `output/final_cut/<chapter_slug>_<lang>.mp4`
- `output/final_cut/<chapter_slug>.edl`
- `output/final_cut/manifest.json`

## Usage

```bash
python scripts/assemble_final_cut.py --chapter-slug complex_numbers
python scripts/assemble_final_cut.py --languages en,hi
```

Requires `ffmpeg` on PATH.
