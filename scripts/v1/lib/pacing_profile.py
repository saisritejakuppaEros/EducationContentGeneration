"""Reference pacing analysis and storyboard retiming."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 5.0
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    return ordered[max(0, min(idx, len(ordered) - 1))]


def build_pacing_profile(
    *,
    source: str,
    duration_seconds: float,
    scenes: list[dict],
) -> dict[str, Any]:
    durations = [float(s["duration_seconds"]) for s in scenes if s.get("duration_seconds")]
    if not durations:
        durations = [5.0]

    hook_end = min(30.0, duration_seconds)
    hook_durs = [
        float(s["duration_seconds"])
        for s in scenes
        if float(s.get("start_seconds", 0)) < hook_end
    ]
    if not hook_durs:
        hook_durs = durations[: max(1, len(durations) // 5)]

    median = statistics.median(durations)
    total_minutes = max(duration_seconds / 60.0, 0.01)
    cuts_per_minute = len(durations) / total_minutes

    return {
        "source": source,
        "duration_seconds": round(duration_seconds, 2),
        "scene_count": len(scenes),
        "median_shot_seconds": round(median, 2),
        "p25_shot_seconds": round(_percentile(durations, 25), 2),
        "p75_shot_seconds": round(_percentile(durations, 75), 2),
        "cuts_per_minute": round(cuts_per_minute, 2),
        "hook_window_seconds": hook_end,
        "hook_median_shot_seconds": round(statistics.median(hook_durs), 2),
        "scenes": scenes,
        "recommended": {
            "default_shot_seconds": round(min(8.0, max(3.0, median)), 1),
            "min_shot_seconds": round(max(2.0, _percentile(durations, 25) * 0.85), 1),
            "max_shot_seconds": round(min(12.0, _percentile(durations, 75) * 1.15), 1),
            "hook_shot_seconds": round(min(6.0, max(2.5, statistics.median(hook_durs))), 1),
            "turn_interval_seconds": 45 if cuts_per_minute < 14 else 40,
        },
    }


def apply_pacing_to_storyboard(storyboard: dict, profile: dict) -> tuple[dict, list[dict]]:
    """Rescale shot durations toward reference median while preserving scene totals ratio."""
    rec = profile.get("recommended") or {}
    target_median = float(rec.get("default_shot_seconds") or 5.0)
    min_shot = float(rec.get("min_shot_seconds") or 3.0)
    max_shot = float(rec.get("max_shot_seconds") or 9.0)
    hook_shot = float(rec.get("hook_shot_seconds") or target_median)
    hook_window = float(profile.get("hook_window_seconds") or 30.0)

    changes: list[dict] = []
    elapsed = 0.0
    out = dict(storyboard)
    scenes_out = []

    for scene in storyboard.get("scenes", []):
        scene_copy = dict(scene)
        shots_out = []
        for shot in scene.get("shots", []):
            shot_copy = dict(shot)
            old = float(shot.get("duration_seconds") or 5.0)
            in_hook = elapsed < hook_window
            desired = hook_shot if in_hook else target_median
            # Blend current timing with reference (keep some storyboard intent).
            new = old * 0.45 + desired * 0.55
            new = max(min_shot, min(max_shot, new))
            new = round(new, 1)
            if abs(new - old) > 0.05:
                changes.append(
                    {
                        "scene_id": scene["scene_id"],
                        "shot": shot.get("shot"),
                        "old_seconds": old,
                        "new_seconds": new,
                        "in_hook": in_hook,
                    }
                )
            shot_copy["duration_seconds"] = new
            elapsed += new
            shots_out.append(shot_copy)
        scene_copy["shots"] = shots_out
        scene_copy["duration_seconds"] = round(sum(s["duration_seconds"] for s in shots_out), 1)
        scenes_out.append(scene_copy)

    out["scenes"] = scenes_out
    runtime_target = storyboard.get("total_runtime_target")
    total = sum(s["duration_seconds"] for s in scenes_out)
    out["pacing_applied_from"] = profile.get("source")
    out["total_shot_seconds"] = round(total, 1)
    if runtime_target:
        out["total_runtime_target"] = runtime_target
    return out, changes
