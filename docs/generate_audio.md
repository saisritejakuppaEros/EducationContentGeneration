# generate_audio

Plans dialogue timing, generates source/dub WAVs, SFX beds, and subtitles.

## Purpose

Stage 6 — **human voice** only. Timing pass (WPM), optional edge-tts synthesis, multilingual dubbing via Gemma/Qwen.

Background music and score beds are **not** generated here — use stage **6b** (`generate_background_audio.py`).

## Inputs

- `output/screenplay/screenplay.json`
- `output/series_bible/series_bible.json`
- `output/storyboard/storyboard.json`
- `output/math_bible/math_bible.json`

## Outputs

```
output/audio/
  audio_plan.json
  source/*.wav
  math_narration/<scene>_shot##.wav
  sfx/<scene_id>.wav          (legacy placeholder; omitted with --voice-only)
  score/chapter_cue01.wav     (legacy placeholder; omitted with --voice-only)
  dub/<lang>/*.wav
  subtitles/<lang>/<chapter>.srt
```

Math narration WAVs are muxed onto Manim clips during final assembly when `--synthesize` is used.

## Usage

```bash
python scripts/stages/generate_audio.py
python scripts/stages/generate_audio.py --synthesize --languages en,hi,ta
python scripts/stages/generate_audio.py --skip-dub
python scripts/stages/generate_audio.py --synthesize --voice-only
```

Install optional TTS: `pip install edge-tts`
