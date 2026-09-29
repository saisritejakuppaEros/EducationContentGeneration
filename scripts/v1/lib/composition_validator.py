"""Pre-render validation for storyboard vs on-disk production assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from media_probe import probe_duration, probe_video_size
from scene_ids import scene_id_aliases


MATH_TYPES = {"MATH INSERT", "CONCEPT"}


def resolve_shot_video(
    *,
    scene_id: str,
    shot_num: int,
    cinematic_dir: Path,
) -> Path | None:
    for sid in scene_id_aliases(scene_id):
        tag = f"{sid}_shot{shot_num:02d}"
        candidates = [
            cinematic_dir / sid / f"{tag}.mp4",
            cinematic_dir / sid / f"{tag}_take02.mp4",
            cinematic_dir / sid / f"{tag}_take01.mp4",
            cinematic_dir / sid / f"{tag}_best.mp4",
            cinematic_dir / f"{tag}.mp4",
        ]
        for path in candidates:
            if path.is_file():
                return path
    return None


def validate_production(
    *,
    storyboard: dict,
    assets_root: Path,
    enable_manim: bool = False,
    duration_tolerance: float = 2.5,
) -> dict[str, Any]:
    cinematic_dir = assets_root / "cinematic_videos"
    if not cinematic_dir.is_dir():
        legacy = assets_root / "ltx_videos"
        if legacy.is_dir():
            cinematic_dir = legacy

    manim_dir = assets_root / "manim_videos"
    flux_dir = assets_root / "storyboard"
    if not any(flux_dir.rglob("*.png")):
        legacy_flux = assets_root / "flux_images"
        if legacy_flux.is_dir():
            flux_dir = legacy_flux

    issues: list[dict] = []
    shots_checked = 0
    shots_ok = 0

    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        for shot in scene.get("shots", []):
            shot_num = int(shot.get("shot") or 0)
            shot_type = (shot.get("type") or "").upper()
            expected = float(shot.get("duration_seconds") or 5.0)
            shots_checked += 1

            if enable_manim and shot_type in MATH_TYPES:
                tag = f"{scene_id}_shot{shot_num:02d}"
                manim = manim_dir / scene_id / f"{tag}.mp4"
                if manim.is_file():
                    shots_ok += 1
                    continue
                issues.append(
                    {"level": "error", "scene_id": scene_id, "shot": shot_num, "code": "missing_manim"}
                )
                continue

            video = resolve_shot_video(scene_id=scene_id, shot_num=shot_num, cinematic_dir=cinematic_dir)
            keyframe_rel = shot.get("keyframe_image")
            keyframe = None
            if keyframe_rel:
                keyframe = Path(keyframe_rel)
                if not keyframe.is_absolute():
                    from paths import PROJECT_ROOT

                    keyframe = PROJECT_ROOT / keyframe_rel

            if video is None:
                if keyframe and keyframe.is_file():
                    issues.append(
                        {
                            "level": "warning",
                            "scene_id": scene_id,
                            "shot": shot_num,
                            "code": "missing_video_has_keyframe",
                        }
                    )
                else:
                    issues.append(
                        {"level": "error", "scene_id": scene_id, "shot": shot_num, "code": "missing_asset"}
                    )
                continue

            actual = probe_duration(video)
            size = probe_video_size(video)
            if actual is None:
                issues.append(
                    {"level": "error", "scene_id": scene_id, "shot": shot_num, "code": "unreadable_video"}
                )
                continue

            if abs(actual - expected) > duration_tolerance:
                issues.append(
                    {
                        "level": "warning",
                        "scene_id": scene_id,
                        "shot": shot_num,
                        "code": "duration_mismatch",
                        "expected_seconds": expected,
                        "actual_seconds": round(actual, 2),
                    }
                )

            if size and (size[0] < 640 or size[1] < 360):
                issues.append(
                    {
                        "level": "warning",
                        "scene_id": scene_id,
                        "shot": shot_num,
                        "code": "low_resolution",
                        "width": size[0],
                        "height": size[1],
                    }
                )

            shots_ok += 1

    errors = [i for i in issues if i["level"] == "error"]
    return {
        "passed": len(errors) == 0,
        "shots_checked": shots_checked,
        "shots_ok": shots_ok,
        "error_count": len(errors),
        "warning_count": len([i for i in issues if i["level"] == "warning"]),
        "issues": issues,
    }
