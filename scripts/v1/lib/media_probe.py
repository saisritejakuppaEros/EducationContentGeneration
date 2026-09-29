"""FFprobe helpers for pipeline validation and assembly."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def ffprobe_path() -> str | None:
    return shutil.which("ffprobe")


def probe_media(path: Path) -> dict[str, Any] | None:
    ffprobe = ffprobe_path()
    if not ffprobe or not path.is_file():
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return None


def probe_duration(path: Path) -> float | None:
    data = probe_media(path)
    if not data:
        return None
    try:
        return float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        return None


def probe_video_size(path: Path) -> tuple[int, int] | None:
    data = probe_media(path)
    if not data:
        return None
    for stream in data.get("streams") or []:
        if stream.get("codec_type") != "video":
            continue
        w = stream.get("width")
        h = stream.get("height")
        if w and h:
            return int(w), int(h)
    return None


def has_audio_stream(path: Path) -> bool:
    data = probe_media(path)
    if not data:
        return False
    return any(s.get("codec_type") == "audio" for s in data.get("streams") or [])
