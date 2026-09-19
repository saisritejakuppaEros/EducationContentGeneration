# generate_background_audio

Generates **background music and ambience** with [Stable Audio 3](https://github.com/Stability-AI/stable-audio-3) on **CPU** via LiteRT/TFLite. Weights come from [stabilityai/stable-audio-3-optimized](https://huggingface.co/stabilityai/stable-audio-3-optimized) on Hugging Face (lazy download on first generation).

## Purpose

Complements stage 6 (`generate_audio.py`): that script plans dialogue, dubbing, and placeholder SFX beds. This script produces real **instrumental BGM** for scenes or chapter cues.

## Prerequisites

```bash
cd /devwork/teja/EducationContentGeneration

export HF_HOME=/workspace/teja/models/hub
export HF_HUB_CACHE=$HF_HOME

bash scripts/setup_stable_audio.sh
```

`setup_stable_audio.sh` sparse-clones the TFLite runtime into `.stable-audio-tflite/` (gitignored) and pre-downloads the `sm-music` bundle (~2 GB). Add `sm-sfx` or `medium` with:

```bash
bash scripts/setup_stable_audio.sh --download sm-music,sm-sfx
```

No NVIDIA GPU is required. For GPU TensorRT builds, use the upstream [optimized/tensorRT](https://github.com/Stability-AI/stable-audio-3/tree/main/optimized/tensorRT) docs instead.

## Outputs

```
output/background_audio/
  samples/edu_bgm_sample.wav    # --sample
  samples/edu_bgm_sample.json   # prompt metadata
  scenes/<scene_id>_bgm.wav     # --storyboard
  manifest.json                 # scene batch
```

Wire scene files into `output/audio/score/` or mux in `assemble_final_cut.py` when you are ready.

## Usage

Demo clip (educational bed, 30 s):

```bash
python3 scripts/stages/generate_background_audio.py --sample
```

Custom prompt:

```bash
python3 scripts/stages/generate_background_audio.py --sample \
  --prompt "Light orchestral curiosity, documentary style, no vocals" \
  --seconds 45
```

Per-scene beds from storyboard:

```bash
python3 scripts/stages/generate_background_audio.py --storyboard output/storyboard/storyboard.json
python3 scripts/stages/generate_background_audio.py --directing-package
```

`--directing-package` reads `audio_cue_sheet` from the director package (M1–M8 cues with `stable_audio_prompt` per cue).

Sound effects preset:

```bash
python3 scripts/stages/generate_background_audio.py --sample --kind sfx \
  --prompt "Soft classroom ambience, quiet HVAC, distant pencil sounds"
```

## License

Stable Audio weights use the [Stability AI Community License](https://stability.ai/license). Review terms before commercial use.
