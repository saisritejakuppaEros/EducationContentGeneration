#!/usr/bin/env python3
"""Apply reference pacing profile to storyboard shot durations."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import shutil

from pacing_profile import apply_pacing_to_storyboard
from paths import add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel
from pipeline_utils import write_json

SUB_MODULE = "storyboard"


def main() -> None:
    parser = argparse.ArgumentParser(description="Retime storyboard shots using reference_pacing_profile.json.")
    parser.add_argument("--storyboard", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    storyboard_path = args.storyboard or output_dir(SUB_MODULE) / "storyboard.json"
    profile_path = args.profile or (get_output_root() / "pipeline" / "reference_pacing_profile.json")

    if not profile_path.is_file():
        raise FileNotFoundError(f"Pacing profile not found: {profile_path} (run stage ref first)")
    if not storyboard_path.is_file():
        raise FileNotFoundError(f"Storyboard not found: {storyboard_path}")

    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    updated, changes = apply_pacing_to_storyboard(storyboard, profile)

    print(f"Pacing from: {profile.get('source')}")
    print(f"Shot retimes: {len(changes)}")
    if args.dry_run:
        for c in changes[:10]:
            print(f"  {c['scene_id']} shot {c['shot']}: {c['old_seconds']}s -> {c['new_seconds']}s")
        return

    backup = storyboard_path.with_suffix(".pre_pacing.json")
    if not backup.is_file():
        shutil.copy2(storyboard_path, backup)
    write_json(storyboard_path, updated)
    log_path = output_dir("pipeline") / "pacing_apply_log.json"
    write_json(log_path, {"changes": changes, "profile_source": profile.get("source")})
    print(f"Updated {project_rel(storyboard_path)} (backup {project_rel(backup)})")


if __name__ == "__main__":
    main()
