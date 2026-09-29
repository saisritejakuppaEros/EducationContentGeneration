"""Lightweight automated checks on generated shot clips."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

from media_probe import has_audio_stream, probe_duration, probe_video_size


def _frame_mean_luma(video: Path, timestamp: float) -> float | None:
    with tempfile.TemporaryDirectory() as tmp:
        frame = Path(tmp) / "frame.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(max(0.0, timestamp)),
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(frame),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not frame.is_file():
            return None
        cmd2 = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(frame),
            "-vf",
            "format=gray,scale=32:32,stats",
            "-f",
            "null",
            "-",
        ]
        result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
        for line in result2.stderr.splitlines():
            if "mean:" in line:
                try:
                    return float(line.split("mean:")[1].split()[0])
                except (IndexError, ValueError):
                    pass
    return None


def score_shot_video(path: Path, *, expected_duration: float | None = None) -> dict[str, Any]:
    """Return qc score 0-100 and reasons."""
    reasons: list[str] = []
    score = 100.0

    if not path.is_file():
        return {"path": str(path), "score": 0, "reasons": ["missing_file"], "passed": False}

    duration = probe_duration(path)
    size = probe_video_size(path)
    if duration is None:
        return {"path": str(path), "score": 0, "reasons": ["ffprobe_failed"], "passed": False}

    if expected_duration is not None and abs(duration - expected_duration) > 3.0:
        score -= 15
        reasons.append("duration_drift")

    if size:
        w, h = size
        if w < 1280 or h < 720:
            score -= 20
            reasons.append("resolution_below_720p")
    else:
        score -= 25
        reasons.append("no_video_stream")

    luma = _frame_mean_luma(path, duration * 0.5)
    if luma is not None:
        if luma < 25:
            score -= 15
            reasons.append("very_dark")
        elif luma > 240:
            score -= 10
            reasons.append("very_bright")

    if not has_audio_stream(path):
        score -= 5
        reasons.append("silent_clip")

    score = max(0.0, min(100.0, score))
    return {
        "path": str(path),
        "duration_seconds": round(duration, 2),
        "width": size[0] if size else None,
        "height": size[1] if size else None,
        "score": round(score, 1),
        "reasons": reasons,
        "passed": score >= 60,
    }
