#!/usr/bin/env python3
"""Series bible + reference photos using the default cartoon cast image."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import shutil

from paths import (
    DEFAULT_CARTOON_CAST_IMAGE,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    project_rel,
)
from pipeline_utils import write_json


def build_series_bible(*, meta: dict, book_id: str, cartoon_rel: str) -> dict:
    title = meta.get("textbook_title") or meta.get("lesson_title") or book_id
    subject = meta.get("subject") or "NCERT"
    tone = (
        "Warm 2D cartoon explainer — consistent mascot, clear maps and diagrams, "
        "classroom-friendly pacing"
    )
    cast_entry = {
        "role": "Guide",
        "description": "Same cartoon character for all roles — consistent silhouette and colors",
        "voice_profile": {
            "pace": "measured",
            "register": "friendly teacher",
            "accent": "neutral Indian English",
            "tic": "uses everyday analogies",
        },
        "reference_photos": [
            {
                "tag": "front_neutral",
                "path": cartoon_rel,
                "source": "assets/cartoon/image.png",
            }
        ],
    }
    return {
        "textbook_title": title,
        "target_tone": tone,
        "cast": {"M": dict(cast_entry), "F": dict(cast_entry), "Y": dict(cast_entry)},
        "world": {
            "premise": f"NCERT {subject} explainer — {title}. Viewer learns with the cartoon guide.",
            "sets": [
                {
                    "name": "Classroom / map studio",
                    "description": "Simple animated backdrop; maps and charts when needed",
                    "reference_image": cartoon_rel,
                }
            ],
        },
        "visual_grammar": {
            "grade": "bright flat cartoon, high readability text overlays",
            "camera_rules": ["hold on diagrams", "cut on question beats"],
            "screen_direction_rules": "Guide screen-left when pointing at maps",
        },
        "chapters_so_far": [],
    }


def copy_cast_references(cartoon: Path, ref_root: Path) -> None:
    for key in ("M", "F", "Y"):
        dest_dir = ref_root / key
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / "front_neutral.png"
        shutil.copy2(cartoon, dest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap series bible with cartoon cast.")
    parser.add_argument("--book-id", type=str, required=True)
    parser.add_argument("--cartoon-image", type=Path, default=DEFAULT_CARTOON_CAST_IMAGE)
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    if not args.cartoon_image.is_file():
        raise FileNotFoundError(f"Cartoon cast image not found: {args.cartoon_image}")

    book_root = get_output_root() / "textbooks" / args.book_id
    manifest_path = book_root / "manifest.json"
    meta = {}
    if manifest_path.is_file():
        meta = json.loads(manifest_path.read_text(encoding="utf-8")).get("metadata") or {}

    series_dir = book_root / "series_bible"
    ref_root = series_dir / "reference_photos"
    copy_cast_references(args.cartoon_image, ref_root)

    rel_photo = project_rel(ref_root / "M" / "front_neutral.png")
    bible = build_series_bible(meta=meta, book_id=args.book_id, cartoon_rel=rel_photo)
    for key in bible["cast"]:
        bible["cast"][key]["reference_photos"][0]["path"] = project_rel(ref_root / key / "front_neutral.png")

    json_path = series_dir / "series_bible.json"
    write_json(json_path, bible)
    print(f"Wrote {json_path}")
    print(f"Cast image: {args.cartoon_image}")
    print(f"Book root: {project_rel(book_root)}/")


if __name__ == "__main__":
    main()
