"""Scene / cut detection for reference pacing (FFmpeg fallback, no PySceneDetect required)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _escape_lavfi_movie_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if "'" in normalized:
        raise ValueError("Paths containing single quotes are unsupported for lavfi movie=")
    escaped = []
    for char in normalized:
        if char in "\\:,[];":
            escaped.append("\\" + char)
        else:
            escaped.append(char)
    return "".join(escaped)


def detect_scene_cuts(
    input_path: Path,
    *,
    threshold: float = 0.35,
    min_scene_length_seconds: float = 0.8,
) -> list[dict]:
    """Return list of {start_seconds, end_seconds, duration_seconds}."""
    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    escaped = _escape_lavfi_movie_path(str(input_path.resolve()))
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vf",
        f"select='gt(scene,{threshold})',showinfo",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    cut_times: list[float] = [0.0]
    for line in result.stderr.splitlines():
        match = re.search(r"pts_time:([0-9.]+)", line)
        if match:
            cut_times.append(float(match.group(1)))

    from media_probe import probe_duration

    total = probe_duration(input_path) or cut_times[-1] if cut_times else 0.0
    if total <= 0:
        return [{"start_seconds": 0.0, "end_seconds": 0.0, "duration_seconds": 0.0}]

    cut_times = sorted(set(cut_times))
    if cut_times[-1] < total - 0.05:
        cut_times.append(total)

    scenes: list[dict] = []
    for i in range(len(cut_times) - 1):
        start = cut_times[i]
        end = cut_times[i + 1]
        dur = end - start
        if dur < min_scene_length_seconds:
            continue
        scenes.append(
            {
                "index": len(scenes),
                "start_seconds": round(start, 3),
                "end_seconds": round(end, 3),
                "duration_seconds": round(dur, 3),
            }
        )

    if not scenes:
        scenes.append(
            {
                "index": 0,
                "start_seconds": 0.0,
                "end_seconds": round(total, 3),
                "duration_seconds": round(total, 3),
            }
        )
    return scenes
