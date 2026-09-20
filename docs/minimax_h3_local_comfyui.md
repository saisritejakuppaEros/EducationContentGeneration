# Local MiniMax-H3 video (ComfyUI)

MiniMax-H3 is **not** a diffusers script in this repo. Local generation uses **ComfyUI** + open weights from [Comfy-Org/MiniMax-H3 on Hugging Face](https://huggingface.co/Comfy-Org/MiniMax-H3), same stack described in OpenMontage (`minimax_h3_local`) and DramaClaw (`MiniMax-H3-local`).

## Models (typical stack)

| File | Folder under ComfyUI |
|------|----------------------|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `models/diffusion_models/` |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `models/text_encoders/` |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae/` |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` |

Load the official template from [Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates) (search `video_minimax_h3`), then **Export (API format)** and note node ids for prompt, Load Image, seed, and Save Video.

## Pipeline env

```bash
export COMFYUI_SERVER_URL=http://127.0.0.1:8188   # or COMFYUI_VIDEO_SERVER_URL
export MINIMAX_H3_I2V_WORKFLOW=/path/to/exported_api.json
export MINIMAX_H3_I2V_PATCH=/path/to/minimax_h3_i2v.patch.json
export MINIMAX_H3_OUTPUT_NODE=42                    # your SaveVideo / output node id
```

Copy [scripts/config/minimax_h3_i2v.patch.json.example](../scripts/config/minimax_h3_i2v.patch.json.example) and fill node ids from your export.

## Run

```bash
python3 scripts/run_textbook_pixels.py \
  --book-id ... --video-id ... \
  --video-backend minimax_h3 \
  --output-root output
```

Fallback without ComfyUI: `--video-backend ltx` (local LTX 2.3 in `gsplat_env`).

Cloud API (if you prefer): `--video-backend minimax_api` and `MINIMAX_API_KEY`.

## QC scores after generation

Stage **5c** still runs `validate_production_assets.py` → `pipeline/qc_report.json` (per-shot score 0–100) and `contact_sheet.html`.
