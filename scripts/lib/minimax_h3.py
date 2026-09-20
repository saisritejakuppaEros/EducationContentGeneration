"""MiniMax-H3 image-to-video via official v2 API (cloud)."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests

REGION_BASE_URLS = {
    "global": "https://api.minimax.io",
    "cn": "https://api.minimaxi.com",
}
DEFAULT_MODEL = "MiniMax-H3"
_V2_IN_PROGRESS = {"queued", "running"}
_V2_SUCCESS = "succeeded"
_V2_FAILURES = {"failed", "cancelled"}


def _api_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "MINIMAX_API_KEY is not set. Get a key at https://platform.minimax.io/"
        )
    return key


def _base_url() -> str:
    override = os.environ.get("MINIMAX_BASE_URL", "").strip()
    if override:
        return override.rstrip("/")
    region = os.environ.get("MINIMAX_REGION", "global").strip().lower()
    if region in {"cn", "cn_zh"}:
        return REGION_BASE_URLS["cn"]
    return REGION_BASE_URLS["global"]


def local_image_to_url(path: Path) -> str:
    """Public HTTPS URL or data URI for MiniMax content[].image_url."""
    url_override = os.environ.get("MINIMAX_IMAGE_URL")
    if url_override:
        return url_override
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def clamp_duration(seconds: float) -> int:
    return max(4, min(15, int(round(seconds))))


def prompt_from_shot(shot: dict) -> str:
    raw = (shot.get("ltx_prompt") or "").strip()
    if raw:
        return raw[:7000]
    structured = shot.get("ltx_prompt_structured") or {}
    visual = (structured.get("visual") or "").strip()
    sounds = (structured.get("sounds") or "").strip()
    speech = (structured.get("speech") or "").strip()
    parts = [visual] if visual else []
    if speech:
        parts.append(f"Dialogue: {speech}")
    if sounds:
        parts.append(f"Sound: {sounds}")
    text = ". ".join(p for p in parts if p)
    if not text:
        text = "Smooth cinematic motion, educational cartoon scene, subtle camera movement."
    return text[:7000]


def generate_image_to_video(
    *,
    prompt: str,
    first_frame: Path,
    output_path: Path,
    duration_seconds: int,
    ratio: str = "16:9",
    timeout_seconds: float = 900,
    poll_interval: float = 5.0,
) -> dict[str, Any]:
    """Submit MiniMax-H3 i2v, poll, download MP4 to output_path."""
    api_key = _api_key()
    base = _base_url()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    image_url = local_image_to_url(first_frame)
    payload = {
        "model": DEFAULT_MODEL,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}, "role": "first_frame"},
        ],
        "resolution": "2K",
        "duration": duration_seconds,
        "ratio": ratio,
    }

    submit = requests.post(
        f"{base}/v2/video_generation",
        headers=headers,
        json=payload,
        timeout=60,
    )
    submit.raise_for_status()
    submit_data = submit.json()
    task_id = submit_data.get("task_id")
    if not task_id:
        raise RuntimeError(f"MiniMax did not return task_id: {submit_data}")

    deadline = time.monotonic() + timeout_seconds
    download_url: str | None = None
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        status_resp = requests.get(
            f"{base}/v2/query/video_generation/{task_id}",
            headers=headers,
            timeout=30,
        )
        status_resp.raise_for_status()
        task = status_resp.json().get("task") or {}
        status = task.get("status")
        if status == _V2_SUCCESS:
            download_url = (task.get("content") or {}).get("url")
            break
        if status in _V2_FAILURES:
            raise RuntimeError(f"MiniMax-H3 failed ({status}): {task.get('error')}")

    if not download_url:
        raise TimeoutError(f"MiniMax-H3 timed out after {timeout_seconds}s (task_id={task_id})")

    video_resp = requests.get(download_url, timeout=180)
    video_resp.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(video_resp.content)

    return {
        "provider": "minimax",
        "model": DEFAULT_MODEL,
        "task_id": task_id,
        "output": str(output_path),
        "duration_seconds": duration_seconds,
        "ratio": ratio,
    }
