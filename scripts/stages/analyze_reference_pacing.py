#!/usr/bin/env python3
"""Analyze a reference video's cut pacing for storyboard retiming."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import shutil
import subprocess
import tempfile

from media_probe import probe_duration
from pacing_profile import build_pacing_profile
from paths import PROJECT_ROOT, add_output_root_argument, configure_output_root, output_dir, project_rel
from pipeline_utils import write_json
from scene_detect import detect_scene_cuts

SUB_MODULE = "pipeline"
PROFILE_NAME = "reference_pacing_profile.json"


def download_url(url: str, dest: Path) -> Path:
    yt_dlp = shutil.which("yt-dlp")
    if not yt_dlp:
        raise RuntimeError("yt-dlp not found on PATH; pass a local --input video file instead.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [yt_dlp, "-f", "mp4/best", "-o", str(dest), url]
    subprocess.run(cmd, check=True)
    matches = list(dest.parent.glob(f"{dest.stem}*"))
    if matches:
        return matches[0]
    if dest.is_file():
        return dest
    raise FileNotFoundError(f"Download failed for {url}")


def resolve_input(path_or_url: str) -> tuple[Path, str, bool]:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        tmp = Path(tempfile.mkdtemp(prefix="ref_pacing_"))
        local = download_url(path_or_url, tmp / "reference.mp4")
        return local, path_or_url, True
    p = Path(path_or_url)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.is_file():
        raise FileNotFoundError(p)
    return p, str(p), False


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract pacing profile from a reference video.")
    parser.add_argument("--input", required=True, help="Local video path or http(s) URL")
    parser.add_argument("--threshold", type=float, default=0.35, help="Scene-cut sensitivity")
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    video_path, source_label, is_temp = resolve_input(args.input)
    duration = probe_duration(video_path) or 0.0
    scenes = detect_scene_cuts(video_path, threshold=args.threshold)
    profile = build_pacing_profile(source=source_label, duration_seconds=duration, scenes=scenes)

    out_path = output_dir(SUB_MODULE) / PROFILE_NAME
    write_json(out_path, profile)
    print(f"Wrote {project_rel(out_path)}")
    print(
        f"median shot {profile['median_shot_seconds']}s, "
        f"cuts/min {profile['cuts_per_minute']}, "
        f"hook median {profile['hook_median_shot_seconds']}s"
    )

    if is_temp:
        shutil.rmtree(video_path.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
