"""Cast photo resolution and reference tagging for Flux keyframe generation."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from paths import DEFAULT_CARTOON_CAST_IMAGE, DEFAULT_PERSON_DIR, PROJECT_ROOT

DEFAULT_CAST_PHOTOS = {
    "M": "ramanujan.jpeg",
    "F": "friend.png",
    "Y": "friend.png",
}

REFERENCE_TAG_PRIORITY = [
    "close_up_neutral",
    "close_up_expression_curious",
    "close_up_expression_concerned",
    "three_quarter_left",
    "three_quarter_right",
    "front_neutral",
    "wide_full_body_neutral_pose",
    "profile",
]

NO_CHARACTER_HINTS = re.compile(
    r"no characters|no environment|math visualization|pure black|educational math|abstract mathematical",
    re.IGNORECASE,
)


def default_cast_image_path() -> Path | None:
    if DEFAULT_CARTOON_CAST_IMAGE.is_file():
        return DEFAULT_CARTOON_CAST_IMAGE
    return None


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
        role = (info.get("role") or "").strip()
        if cast_match_patterns(cast_key, role).search(text):
            keys.append(cast_key)
    if not keys and cast:
        mode = (shot.get("ltx_mode") or "").lower()
        if mode == "talking_head" and "Y" in cast:
            return ["Y"]
    return keys


def profile_reference_path(series_profile: dict, cast_key: str, tag: str) -> Path | None:
    cast = series_profile.get("cast", {}).get(cast_key, {})
    for entry in cast.get("reference_photos") or []:
        if entry.get("tag") == tag:
            path = PROJECT_ROOT / entry["path"]
            if path.is_file():
                return path
    return None


def pick_reference_tag(shot: dict, cast_key: str, ref_tags: dict | None) -> str:
    ref_tags = ref_tags or {}
    if cast_key in ref_tags:
        return ref_tags[cast_key]

    shot_type = (shot.get("type") or "").upper()
    mode = (shot.get("ltx_mode") or "").lower()
    if shot_type in ("CLOSE", "CLOSEUP", "TALKING_HEAD") or mode == "talking_head":
        return "close_up_neutral"
    if shot_type == "WIDE":
        return "wide_full_body_neutral_pose"
    if shot_type == "INSERT":
        return "three_quarter_left"
    return "front_neutral"


def prepare_reference_image(image: Image.Image, tag: str) -> Image.Image:
    """Crop/resize refs so Flux gets a clear identity signal (especially faces)."""
    img = image.convert("RGB")
    w, h = img.size
    if w < 64 or h < 64:
        return img

    if "close" in tag or "profile" in tag:
        side = min(w, h)
        left = max(0, (w - side) // 2)
        top = max(0, int(h * 0.02))
        if top + side > h:
            top = max(0, h - side)
        img = img.crop((left, top, left + side, top + side))
    elif "wide" in tag and w / h < 1.2:
        target_h = int(w * 9 / 16)
        if target_h < h:
            top = (h - target_h) // 2
            img = img.crop((0, top, w, top + target_h))

    max_side = 1024
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def source_photo_path(
    cast_key: str,
    *,
    series_profile: dict | None = None,
    source_dir: Path | None = None,
) -> Path | None:
    if series_profile:
        for tag in ("front_neutral", *REFERENCE_TAG_PRIORITY):
            path = profile_reference_path(series_profile, cast_key, tag)
            if path:
                return path

    root = source_dir or DEFAULT_PERSON_DIR
    filename = DEFAULT_CAST_PHOTOS.get(cast_key)
    if filename:
        path = root / filename
        if path.is_file():
            return path

    if cast_key == "Y":
        unified = default_cast_image_path()
        if unified:
            return unified
    return None


def resolve_cast_reference(
    *,
    series_profile: dict,
    cast_key: str,
    tag: str,
    bank_lookup,
    source_dir: Path | None = None,
) -> tuple[Path | None, str]:
    for try_tag in (tag, *REFERENCE_TAG_PRIORITY):
        ref_path = bank_lookup(series_profile, cast_key, try_tag)
        if ref_path:
            return ref_path, f"reference_bank:{try_tag}"

    ref_path = profile_reference_path(series_profile, cast_key, tag)
    if ref_path:
        return ref_path, "series_profile"

    source = source_photo_path(cast_key, series_profile=series_profile, source_dir=source_dir)
    if source:
        return source, "source_photo"
    return None, "missing"
