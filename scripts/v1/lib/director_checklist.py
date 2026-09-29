"""Storyboard / screenplay checks derived from director_skill.md."""

from __future__ import annotations

from typing import Any


def validate_storyboard_director(storyboard: dict, *, runtime_min: int = 480, runtime_max: int = 900) -> dict[str, Any]:
    issues: list[dict] = []
    scenes = storyboard.get("scenes") or []
    if not scenes:
        issues.append({"level": "error", "code": "empty_storyboard"})

    total = sum(float(s.get("duration_seconds") or 0) for s in scenes)
    if total < runtime_min:
        issues.append(
            {"level": "warning", "code": "runtime_short", "total_seconds": round(total, 1), "min": runtime_min}
        )
    if total > runtime_max:
        issues.append(
            {"level": "warning", "code": "runtime_long", "total_seconds": round(total, 1), "max": runtime_max}
        )

    hook_shots = []
    elapsed = 0.0
    for scene in scenes:
        for shot in scene.get("shots", []):
            if elapsed < 30:
                hook_shots.append(shot)
            elapsed += float(shot.get("duration_seconds") or 0)

    if hook_shots and not any(shot.get("dialogue") or shot.get("narration_line") for shot in hook_shots):
        issues.append({"level": "warning", "code": "hook_no_spoken_line_in_first_30s"})

    long_shots = []
    for scene in scenes:
        for shot in scene.get("shots", []):
            dur = float(shot.get("duration_seconds") or 0)
            if dur > 12:
                long_shots.append((scene["scene_id"], shot.get("shot"), dur))
    if long_shots:
        issues.append({"level": "warning", "code": "shots_over_12s", "examples": long_shots[:5]})

    errors = [i for i in issues if i["level"] == "error"]
    return {
        "passed": not errors,
        "total_runtime_seconds": round(total, 1),
        "scene_count": len(scenes),
        "issues": issues,
    }
