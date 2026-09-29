"""Minimal ComfyUI REST client for local video workflows."""

from __future__ import annotations

import copy
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import requests


class ComfyUIError(RuntimeError):
    def __init__(self, message: str, *, prompt_id: str | None = None) -> None:
        super().__init__(message)
        self.prompt_id = prompt_id


class ComfyUIClient:
    def __init__(self, server_url: str | None = None) -> None:
        resolved = (
            server_url
            or os.environ.get("COMFYUI_VIDEO_SERVER_URL")
            or os.environ.get("COMFYUI_SERVER_URL")
            or "http://127.0.0.1:8188"
        )
        self.server_url = resolved.rstrip("/")
        self.client_id = str(uuid.uuid4())

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.server_url}/system_stats", timeout=5)
            return r.status_code == 200
        except OSError:
            return False

    def submit(self, workflow: dict[str, Any]) -> str:
        payload = {"prompt": workflow, "client_id": self.client_id}
        r = requests.post(f"{self.server_url}/prompt", json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI /prompt returned no prompt_id: {data}")
        return prompt_id

    def poll(self, prompt_id: str, *, timeout: float = 1200, interval: float = 5) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.get(f"{self.server_url}/history/{prompt_id}", timeout=15)
            r.raise_for_status()
            entry = r.json().get(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise ComfyUIError(
                        f"ComfyUI execution error: {status.get('messages')}",
                        prompt_id=prompt_id,
                    )
                return entry
            time.sleep(interval)
        raise ComfyUIError(
            f"ComfyUI prompt {prompt_id} did not finish within {timeout}s",
            prompt_id=prompt_id,
        )

    def upload_image(self, local_path: Path) -> str:
        with local_path.open("rb") as f:
            r = requests.post(
                f"{self.server_url}/upload/image",
                files={"image": (local_path.name, f, "image/png")},
                timeout=120,
            )
        r.raise_for_status()
        return r.json()["name"]

    def download_artifact(self, item: dict, dest: Path) -> Path:
        r = requests.get(
            f"{self.server_url}/view",
            params={
                "filename": item["filename"],
                "subfolder": item.get("subfolder", ""),
                "type": item.get("type", "output"),
            },
            timeout=180,
        )
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest

    def generate_to_file(
        self,
        workflow: dict[str, Any],
        *,
        output_node: str,
        dest: Path,
        timeout: float = 1200,
    ) -> Path:
        prompt_id = self.submit(workflow)
        entry = self.poll(prompt_id, timeout=timeout)
        outputs = entry.get("outputs", {})
        node_out = outputs.get(output_node, {})
        items = (
            node_out.get("images")
            or node_out.get("gifs")
            or node_out.get("videos")
            or node_out.get("video")
            or []
        )
        if not items:
            raise ComfyUIError(
                f"No artifacts on output node {output_node}; nodes={list(outputs.keys())}",
                prompt_id=prompt_id,
            )
        item = items[0]
        suffix = Path(item["filename"]).suffix or dest.suffix or ".mp4"
        target = dest if dest.suffix else dest.with_suffix(suffix)
        return self.download_artifact(item, target)


def load_workflow(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def patch_workflow(
    workflow: dict[str, Any],
    patch_spec: dict[str, Any],
    *,
    prompt: str,
    image_filename: str | None,
    seed: int,
) -> dict[str, Any]:
    """Apply MINIMAX_H3 patch spec (see scripts/config/minimax_h3_i2v.patch.json.example)."""
    wf = copy.deepcopy(workflow)
    p = patch_spec.get("prompt") or {}
    if p.get("node") and p.get("input"):
        wf[str(p["node"])]["inputs"][p["input"]] = prompt
    img = patch_spec.get("image") or {}
    if image_filename and img.get("node") and img.get("input"):
        wf[str(img["node"])]["inputs"][img["input"]] = image_filename
    sd = patch_spec.get("seed") or {}
    if sd.get("node") and sd.get("input"):
        wf[str(sd["node"])]["inputs"][sd["input"]] = seed
    return wf
