"""Convert shot_decomposition.json into storyboard-shaped JSON for Flux / LTX stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paths import project_rel


def _dialogue_from_shot(shot: dict) -> str | None:
    line = (shot.get("narration_line") or shot.get("dialogue") or "").strip()
    if not line:
        return None
    if isinstance(line, dict):
        return f"{line.get('character', 'Y')}: {line.get('line', '')}"
    if line.startswith(("M:", "F:", "Y:")):
        return line
    chars = shot.get("characters_in_frame") or []
    speaker = chars[0] if chars else "Y"
    return f"{speaker}: {line}"


def storyboard_from_decomposition(
    decomp: dict,
    *,
    keyframes_rel_prefix: str,
) -> dict:
    """Build storyboard JSON with flux_prompt + keyframe_image paths per shot."""
    scenes_out: list[dict] = []
    for scene in decomp.get("scenes") or []:
        sid = scene.get("scene_id") or "S00"
        shots_out: list[dict] = []
        for shot in scene.get("shots") or []:
            num = int(shot.get("shot") or 1)
            rel_img = f"{keyframes_rel_prefix.rstrip('/')}/{sid}/{sid}_shot{num:02d}.png"
            flux = (
                shot.get("flux_prompt")
                or shot.get("flux_frame")
                or shot.get("image_caption")
                or ""
            )
            shots_out.append(
                {
                    **shot,
                    "flux_prompt": flux,
                    "keyframe_image": rel_img,
                    "dialogue": _dialogue_from_shot(shot),
                    "camera_move": shot.get("wan_motion") or shot.get("camera_move") or "static",
                    "reference_tags_used": shot.get("reference_tags_used") or {},
                    "environment_detail": shot.get("environment_detail") or scene.get("on_screen_text") or "",
                    "blocking": shot.get("blocking") or "",
                }
            )
        scenes_out.append(
            {
                "scene_id": sid,
                "screenplay_type": "STORY",
                "title": scene.get("on_screen_text") or sid,
                "duration_seconds": scene.get("duration_seconds"),
                "time_start": scene.get("time_start"),
                "visual_mode": scene.get("visual_mode"),
                "shots": shots_out,
            }
        )

    return {
        "chapter": decomp.get("chapter"),
        "tone_target": decomp.get("tone_target"),
        "total_runtime_target": decomp.get("total_runtime_target"),
        "visual_style_guide": decomp.get("visual_style_guide") or {},
        "scenes": scenes_out,
        "source": "shot_decomposition",
    }


def write_pixels_storyboard(
    decomposition_path: Path,
    out_path: Path,
    *,
    keyframes_rel_prefix: str | None = None,
) -> dict:
    decomp = json.loads(decomposition_path.read_text(encoding="utf-8"))
    if keyframes_rel_prefix is None:
        video_root = decomposition_path.parent.parent
        keyframes_rel_prefix = project_rel(video_root / "shots" / "keyframes")
    board = storyboard_from_decomposition(decomp, keyframes_rel_prefix=keyframes_rel_prefix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return board


def apply_keyframes_to_decomposition(decomposition_path: Path, manifest_shots: list[dict]) -> None:
    """Copy generated keyframe paths back into shot_decomposition.json."""
    if not decomposition_path.is_file():
        return
    decomp = json.loads(decomposition_path.read_text(encoding="utf-8"))
    lookup = {(e["scene_id"], e["shot"]): e["output"] for e in manifest_shots}
    for scene in decomp.get("scenes") or []:
        sid = scene.get("scene_id")
        for shot in scene.get("shots") or []:
            key = (sid, shot.get("shot"))
            if key in lookup:
                shot["keyframe_image"] = lookup[key]
    decomposition_path.write_text(json.dumps(decomp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
