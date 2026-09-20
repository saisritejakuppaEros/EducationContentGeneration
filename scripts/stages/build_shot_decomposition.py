#!/usr/bin/env python3
"""Expand directing_package into per-shot Flux captions + full narration timeline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from paths import add_output_root_argument, configure_output_root, output_dir, project_rel
from pipeline_utils import write_json
from shot_decomposition import write_shot_decomposition

SUB_MODULE = "shots"
DEFAULT_DIRECTING = output_dir("directing") / "directing_package.json"
DEFAULT_SERIES = output_dir("series_bible") / "series_bible.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build shot decomposition (image captions + VO lines) from directing_package.json."
    )
    parser.add_argument(
        "--directing-package",
        type=Path,
        default=DEFAULT_DIRECTING,
        help="Path to directing_package.json",
    )
    parser.add_argument(
        "--series-bible",
        type=Path,
        default=DEFAULT_SERIES,
        help="Optional series bible for cast reference paths",
    )
    parser.add_argument(
        "--runtime-seconds",
        type=int,
        default=None,
        help="Stretch timeline to this length (default: package runtime_target_seconds or 600)",
    )
    add_output_root_argument(parser)
    args = parser.parse_args()
    configure_output_root(args.output_root)

    directing = args.directing_package
    if not directing.is_file():
        raise FileNotFoundError(directing)

    out_dir = output_dir(SUB_MODULE)

    json_path = write_shot_decomposition(
        directing,
        out_dir,
        target_runtime_seconds=args.runtime_seconds,
        series_bible_path=args.series_bible if args.series_bible.is_file() else None,
    )
    write_json(
        out_dir / "manifest.json",
        {
            "shot_decomposition": project_rel(json_path),
            "shots_md": project_rel(out_dir / "shots.md"),
            "narration_manifest": project_rel(out_dir / "narration_manifest.json"),
        },
    )
    data = json.loads(json_path.read_text(encoding="utf-8"))
    print(
        f"Wrote {project_rel(json_path)} — "
        f"{data['stats']['shot_count']} shots, {data['total_runtime_seconds']}s, "
        f"{data['stats']['narration_lines']} narration lines"
    )


if __name__ == "__main__":
    main()
