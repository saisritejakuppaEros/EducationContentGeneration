#!/usr/bin/env python3
"""Flux keyframes + LTX clips for a textbook video unit (from shot_decomposition.json)."""
import _bootstrap  # noqa: F401

import argparse
import os
import sys
from pathlib import Path

from paths import (
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    project_rel,
)
from pipeline_utils import run_script, write_json
from pixels_storyboard import write_pixels_storyboard


def book_video_root(book_id: str, video_id: str) -> Path:
    return get_output_root() / "textbooks" / book_id / "videos" / video_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate keyframe images and LTX video clips for one textbook unit.")
    parser.add_argument("--book-id", type=str, required=True)
    parser.add_argument("--video-id", type=str, required=True)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--keyframes-only", action="store_true")
    parser.add_argument("--videos-only", action="store_true", help="Skip Flux; run LTX from existing keyframes.")
    parser.add_argument("--prompts-only", action="store_true", help="Build cinematic_prompts.json only.")
    parser.add_argument("--scene", action="append", dest="scene_ids", help="Limit to director scene id (e.g. S01).")
    parser.add_argument(
        "--gpu",
        type=int,
        default=None,
        help="Physical GPU index (sets CUDA_VISIBLE_DEVICES so models use cuda:0 on that GPU). Example: --gpu 1",
    )
    parser.add_argument(
        "--video-backend",
        choices=("minimax", "ltx"),
        default="minimax",
        help="Cinematic clips: minimax (MiniMax-H3 API) or ltx (local GPU).",
    )
    add_output_root_argument(parser)
    args = parser.parse_args()

    if args.gpu is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)
        print(f"CUDA_VISIBLE_DEVICES={args.gpu} (process sees a single GPU as cuda:0)")

    configure_output_root(args.output_root)
    video_root = book_video_root(args.book_id, args.video_id)
    if not video_root.is_dir():
        raise FileNotFoundError(f"Video folder not found: {video_root}")

    decomp_path = video_root / "shots" / "shot_decomposition.json"
    if not decomp_path.is_file():
        raise FileNotFoundError(f"Run shot decomposition first: {decomp_path}")

    series_bible = get_output_root() / "textbooks" / args.book_id / "series_bible" / "series_bible.json"
    if not series_bible.is_file():
        raise FileNotFoundError(series_bible)

    pixels_board = video_root / "shots" / "pixels_storyboard.json"
    keyframes_prefix = project_rel(video_root / "shots" / "keyframes")
    write_pixels_storyboard(decomp_path, pixels_board, keyframes_rel_prefix=keyframes_prefix)
    print(f"Wrote {project_rel(pixels_board)}")

    out_flag = str(video_root)
    manifest_path = video_root / "shots" / "keyframes" / "keyframes_manifest.json"

    if not args.videos_only and not args.prompts_only:
        kf_args = [
            "--storyboard",
            str(pixels_board),
            "--series-bible",
            str(series_bible),
            "--keyframes-subdir",
            "shots/keyframes",
            "--shot-decomposition",
            str(decomp_path),
            "--output-root",
            out_flag,
            "--include-math-inserts",
        ]
        if args.skip_existing:
            kf_args.append("--skip-existing")
        if args.scene_ids:
            for sid in args.scene_ids:
                kf_args.extend(["--scene", sid])
        print("\n=== Flux keyframes ===")
        rc = run_script("generate_storyboard_keyframes.py", kf_args)
        if rc != 0:
            sys.exit(rc)

    if args.keyframes_only:
        print("\nKeyframes-only; done.")
        return

    cin_args = [
        "--storyboard",
        str(pixels_board),
        "--series-bible",
        str(series_bible),
        "--deterministic-prompts",
        "--output-root",
        out_flag,
        "--include-math-inserts",
        "--video-backend",
        args.video_backend,
    ]
    if args.skip_existing:
        cin_args.append("--skip-existing")
    if args.prompts_only:
        cin_args.append("--prompts-only")
    if args.scene_ids:
        for sid in args.scene_ids:
            cin_args.extend(["--scene", sid])

    print("\n=== LTX cinematic prompts + clips ===")
    rc = run_script("generate_cinematic_videos.py", cin_args)
    if rc != 0:
        sys.exit(rc)

    write_json(
        video_root / "pixels_manifest.json",
        {
            "video_id": args.video_id,
            "pixels_storyboard": project_rel(pixels_board),
            "shot_decomposition": project_rel(decomp_path),
            "keyframes_manifest": project_rel(manifest_path),
            "cinematic_prompts": project_rel(video_root / "cinematic_videos" / "cinematic_prompts.json"),
            "ltx_manifest": project_rel(video_root / "cinematic_videos" / "manifest.json"),
        },
    )
    print(f"\nPixel pipeline complete for {args.video_id}")


if __name__ == "__main__":
    main()
