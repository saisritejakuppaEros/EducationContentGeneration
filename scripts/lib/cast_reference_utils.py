"""Cast photo resolution for Flux keyframe generation."""

from __future__ import annotations

import re
from pathlib import Path

from paths import DEFAULT_CARTOON_CAST_IMAGE, DEFAULT_PERSON_DIR, PROJECT_ROOT

DEFAULT_CAST_PHOTOS = {
    "M": "ramanujan.jpeg",
    "F": "friend.png",
    "Y": "friend.png",
}


def default_cast_image_path() -> Path | None:
    if DEFAULT_CARTOON_CAST_IMAGE.is_file():
        return DEFAULT_CARTOON_CAST_IMAGE
    return None

NO_CHARACTER_HINTS = re.compile(
    r"no characters|no environment|math visualization|pure black|educational math|abstract mathematical",
    re.IGNORECASE,
)


def cast_match_patterns(cast_key: str, role: str) -> re.Pattern:
    if cast_key == "M":
        return re.compile(
            r"\bmathematician\b|\bcommander\b|\(\s*m\s*\)|\bm\b|\bm—|\bm'|\bm,|\bm and|\band m\b",
            re.IGNORECASE,
        )
    if cast_key == "F":
        return re.compile(
            r"\bfriend\b|\bengineer\b|\(\s*f\s*\)|\bf—|\bf'|\bf,|\bf and|\band f\b",
            re.IGNORECASE,
        )
    if cast_key == "Y":
        return re.compile(
            r"\bcadet\b|\bviewer\b|\bguide\b|\bmascot\b|\(\s*y\s*\)|\by—|\by'|\by,|\by and|\band y\b",
            re.IGNORECASE,
        )
    role_pat = re.escape(role) if role else ""
    parts = [rf"\(\s*{cast_key.lower()}\s*\)", rf"\b{re.escape(cast_key)}\b"]
    if role_pat:
        parts.append(rf"\b{role_pat}\b")
    return re.compile("|".join(parts), re.IGNORECASE)


def infer_characters_in_frame(shot: dict, cast: dict) -> list[str]:
    declared = shot.get("characters_in_frame") or []
    if declared:
        return list(declared)

    shot_type = (shot.get("type") or "").upper()
    if shot_type == "MATH INSERT":
        return []

    text = " ".join(
        [
            str(shot.get("flux_prompt") or ""),
            str(shot.get("blocking") or ""),
            str(shot.get("environment_detail") or ""),
        ]
    )
    if NO_CHARACTER_HINTS.search(text):
        return []

    keys: list[str] = []
    for cast_key, info in cast.items():
        if cast_key not in DEFAULT_CAST_PHOTOS:
            continue
        role = (info.get("role") or "").strip()
        if cast_match_patterns(cast_key, role).search(text):
            keys.append(cast_key)
    return keys


def source_photo_path(cast_key: str, source_dir: Path | None = None) -> Path | None:
    unified = default_cast_image_path()
    if unified:
        return unified
    root = source_dir or DEFAULT_PERSON_DIR
    filename = DEFAULT_CAST_PHOTOS.get(cast_key)
    if not filename:
        return None
    path = root / filename
    return path if path.is_file() else None


def resolve_cast_reference(
    *,
    series_bible: dict,
    cast_key: str,
    tag: str,
    bank_lookup,
    source_dir: Path | None = None,
) -> tuple[Path | None, str]:
    ref_path = bank_lookup(series_bible, cast_key, tag)
    if ref_path:
        return ref_path, "reference_bank"

    ref_path = bank_lookup(series_bible, cast_key, "front_neutral")
    if ref_path:
        return ref_path, "reference_bank_front_neutral"

    source = source_photo_path(cast_key, source_dir)
    if source:
        return source, "source_photo"
    return None, "missing"
