# Audio director (VO separate from video)

## Principle

**Narration is never trusted from the video model.** All spoken lines go through stage **6** (`generate_audio.py`) and mux in stage **7**.

## Series profile

Set once per book in `series_profile.json`:

```json
"narration_voice": {
  "engine": "edge_tts",
  "voice_id": "en-IN-NeerjaNeural",
  "language": "en",
  "speed": 1.0
},
"character_voices": { "M": true, "F": true, "Y": true }
```

When `character_voices.*` is `true`, that role uses **`narration_voice`** (one consistent narrator). Set to `false` and add `cast.M.voice_profile.edge_voice` only if you need a second distinct role.

## Engines (`scripts/lib/voice_synthesis.py`)

| Engine | When |
|--------|------|
| `edge_tts` | Default local, no API |
| `xai_tts` | Set `NARRATION_TTS_ENGINE=xai_tts`, `OPENAI_API_BASE`, `NARRATION_VOICE_ID=leo` (Atlas/xAI) |
| `seed_audio` | Clone from `narration_voice.clone_ref` (Vox-style) |

Override without editing JSON: `NARRATION_VOICE_ID`, `NARRATION_TTS_ENGINE`.

## Mix

BGM from stage **6b**; duck under VO in `assemble_final_cut.py`. LTX/MiniMax negative prompts should still discourage in-clip speech when using external TTS.
