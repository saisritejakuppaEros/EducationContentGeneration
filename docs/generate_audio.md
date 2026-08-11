# generate_audio

Plans dialogue timing, generates source/dub WAVs, SFX beds, and subtitles.

## Purpose

Stage 6 — Audio Agent. Timing pass (WPM), optional edge-tts synthesis, multilingual dubbing via Gemma/Qwen.

## Inputs

- `output/screenplay/screenplay.json`
- `output/series_bible/series_bible.json`
- `output/storyboard/storyboard.json`

## Outputs

```
output/audio/
  audio_plan.json
  source/*.wav
  sfx/<scene_id>.wav
  score/chapter_cue01.wav
  dub/<lang>/*.wav
  subtitles/<lang>/<chapter>.srt
```

## Usage

```bash
python scripts/generate_audio.py
python scripts/generate_audio.py --synthesize --languages en,hi,ta
python scripts/generate_audio.py --skip-dub
```

Install optional TTS: `pip install edge-tts`
