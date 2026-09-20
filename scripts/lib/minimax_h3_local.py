"""Local MiniMax-H3 via ComfyUI (open weights + exported API workflow)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from comfyui_client import ComfyUIClient, ComfyUIError, load_workflow, patch_workflow


def _config_paths() -> tuple[Path, Path, str]:
    workflow = os.environ.get("MINIMAX_H3_I2V_WORKFLOW", "").strip()
    patch = os.environ.get("MINIMAX_H3_I2V_PATCH", "").strip()
    output_node = os.environ.get("MINIMAX_H3_OUTPUT_NODE", "").strip()
    if not workflow or not patch or not output_node:
        raise ComfyUIError(
            "Local MiniMax-H3 requires ComfyUI env config:\n"
            "  MINIMAX_H3_I2V_WORKFLOW  — API-format JSON exported from ComfyUI\n"
            "  MINIMAX_H3_I2V_PATCH     — patch spec JSON (see scripts/config/minimax_h3_i2v.patch.json.example)\n"
            "  MINIMAX_H3_OUTPUT_NODE   — SaveVideo / output node id in that workflow\n"
            "  COMFYUI_SERVER_URL or COMFYUI_VIDEO_SERVER_URL (default http://127.0.0.1:8188)\n"
            "Weights: https://huggingface.co/Comfy-Org/MiniMax-H3\n"
            "Template: https://github.com/Comfy-Org/workflow_templates (video_minimax_h3_*)\n"
            "Or use --video-backend ltx for local LTX 2.3 in gsplat_env."
        )
    return Path(workflow), Path(patch), output_node


def generate_i2v_clip(
    *,
    prompt: str,
    first_frame: Path,
    output_path: Path,
    seed: int,
    timeout_seconds: float = 1200,
) -> dict:
    wf_path, patch_path, output_node = _config_paths()
    if not wf_path.is_file():
        raise ComfyUIError(f"Workflow not found: {wf_path}")
    if not patch_path.is_file():
        raise ComfyUIError(f"Patch spec not found: {patch_path}")
    if not first_frame.is_file():
        raise FileNotFoundError(first_frame)

    client = ComfyUIClient()
    if not client.is_available():
        raise ComfyUIError(
            f"ComfyUI not reachable at {client.server_url}. "
            "Start ComfyUI with MiniMax-H3 weights and the exported I2V workflow."
        )

    patch_spec = json.loads(patch_path.read_text(encoding="utf-8"))
    image_name = client.upload_image(first_frame)
    workflow = patch_workflow(
        load_workflow(wf_path),
        patch_spec,
        prompt=prompt,
        image_filename=image_name,
        seed=seed,
    )
    out = client.generate_to_file(
        workflow,
        output_node=output_node,
        dest=output_path,
        timeout=timeout_seconds,
    )
    return {
        "provider": "comfyui",
        "model": "MiniMax-H3-local",
        "output": str(out),
        "workflow": str(wf_path),
    }
