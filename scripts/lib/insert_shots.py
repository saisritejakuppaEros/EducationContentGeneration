"""Shared helpers for diagram / math-insert shots (Manim, HTML, or LTX fallback)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

# Shot types that can use a dedicated insert renderer instead of generic I2V.
INSERT_SHOT_TYPES = frozenset({"MATH INSERT", "CONCEPT", "INSERT"})

# scene_table visual_mode values that benefit from HTML/diagram renders (textbook path).
DIAGRAM_VISUAL_MODES = frozenset(
    {"map", "mechanism", "diagram", "timeline", "chart", "flow", "compare"}
)


def shot_tag(scene_id: str, shot_num: int) -> str:
    return f"{scene_id}_shot{shot_num:02d}"


def iter_storyboard_insert_shots(storyboard: dict) -> list[tuple[dict, dict]]:
    """Same selection rules as legacy Manim stage (storyboard-driven chapter pipeline)."""
    shots: list[tuple[dict, dict]] = []
    for scene in storyboard.get("scenes", []):
        scene_type = (scene.get("screenplay_type") or scene.get("render_type") or "").upper()
        for shot in scene.get("shots", []):
            shot_type = (shot.get("type") or "").upper()
            if shot_type == "MATH INSERT":
                shots.append((scene, shot))
            elif scene_type in {"CONCEPT", "HYBRID"} and shot_type == "MATH INSERT":
                shots.append((scene, shot))
            elif scene_type == "CONCEPT" and shot_type in INSERT_SHOT_TYPES:
                shots.append((scene, shot))
            elif shot_type in {"MATH INSERT", "CONCEPT"}:
                shots.append((scene, shot))
    return shots


def iter_decomposition_insert_shots(decomposition: dict) -> list[tuple[dict, dict]]:
    """Textbook shot_decomposition.json — diagram/map/mechanism scenes."""
    out: list[tuple[dict, dict]] = []
    for scene in decomposition.get("scenes", []):
        mode = (scene.get("visual_mode") or "").lower()
        scene_id = scene.get("scene_id") or scene.get("id")
        if not scene_id:
            continue
        scene_wrap = {"scene_id": scene_id, "visual_mode": mode, **scene}
        for shot in scene.get("shots", []):
            stype = (shot.get("type") or "").upper()
            if stype in INSERT_SHOT_TYPES or mode in DIAGRAM_VISUAL_MODES:
                out.append((scene_wrap, shot))
    return out


def merge_insert_shots(
    storyboard: dict | None,
    decomposition: dict | None,
) -> list[tuple[dict, dict]]:
    """De-dupe by (scene_id, shot number); decomposition fills gaps for textbook runs."""
    seen: set[tuple[str, int]] = set()
    merged: list[tuple[dict, dict]] = []

    def add(pairs: list[tuple[dict, dict]]) -> None:
        for scene, shot in pairs:
            sid = scene.get("scene_id") or ""
            num = int(shot.get("shot") or 0)
            key = (sid, num)
            if not sid or key in seen:
                continue
            seen.add(key)
            merged.append((scene, shot))

    if storyboard:
        add(iter_storyboard_insert_shots(storyboard))
    if decomposition:
        add(iter_decomposition_insert_shots(decomposition))
    return merged


def insert_mp4_path(root: Path, scene_id: str, shot_num: int) -> Path:
    tag = shot_tag(scene_id, shot_num)
    return root / scene_id / f"{tag}.mp4"


def insert_html_dir(root: Path, scene_id: str, shot_num: int) -> Path:
    return root / scene_id / shot_tag(scene_id, shot_num)
