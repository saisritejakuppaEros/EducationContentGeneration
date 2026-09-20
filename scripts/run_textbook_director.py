#!/usr/bin/env python3
"""
Run NCERT Explainer Director (LLM) per planned video unit.

Uses chapter + subchapter context → directing package (story, beats, scenes, image prompts, BGM cues)
→ topic bible → screenplay → storyboard.
"""
import _bootstrap  # noqa: F401

import argparse
import json
import os
import sys
from pathlib import Path

from directing_exports import export_directing_artifacts
from paths import (
    DEFAULT_LLM_BACKEND,
    DEFAULT_QWEN_API_BASE,
    DEFAULT_QWEN_API_KEY,
    DEFAULT_QWEN_MODEL,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    project_rel,
)
from pipeline_utils import run_script, write_json
from qwen_utils import ensure_qwen_for_story_layout
from textbook_director_context import build_director_brief


def ensure_qwen_env() -> None:
    os.environ.setdefault("OPENAI_API_BASE", DEFAULT_QWEN_API_BASE)
    os.environ.setdefault("OPENAI_API_KEY", DEFAULT_QWEN_API_KEY)
    os.environ.setdefault("QWEN_MODEL", DEFAULT_QWEN_MODEL)
    ensure_qwen_for_story_layout(strict=True)


def book_root(book_id: str) -> Path:
    return get_output_root() / "textbooks" / book_id


def run_stage(script: str, args: list[str]) -> None:
    rc = run_script(script, args)
    if rc != 0:
        sys.exit(rc)


def produce_video_unit(
    *,
    book_id: str,
    manifest: dict,
    plan: dict,
    video: dict,
    series_bible: Path,
    skip_existing: bool,
    max_tokens: int,
    director_only: bool,
) -> None:
    vid = video["video_id"]
    video_root = book_root(book_id) / "videos" / vid
    input_dir = video_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)

    brief_path = input_dir / "director_brief.md"
    brief_path.write_text(
        build_director_brief(
            manifest=manifest,
            video=video,
            plan=plan,
            series_bible_path=series_bible,
        ),
        encoding="utf-8",
    )
    # Legacy name for downstream tools
    (input_dir / "chapter.md").write_text(brief_path.read_text(encoding="utf-8"), encoding="utf-8")

    out_flag = str(video_root)
    directing_json = video_root / "directing" / "directing_package.json"

    if not (skip_existing and directing_json.is_file()):
        print(f"\n=== [{vid}] LLM Director → directing package ===")
        run_stage(
            "generate_directing_package.py",
            [
                "--input",
                str(brief_path),
                "--backend",
                DEFAULT_LLM_BACKEND,
                "--runtime-seconds",
                str(int((video.get("runtime_minutes") or 8) * 60)),
                "--max-tokens",
                str(max_tokens),
                "--output-root",
                out_flag,
            ],
        )
        export_directing_artifacts(directing_json, video_root / "directing")
        print(f"Wrote {video_root / 'directing' / 'story_overview.md'}")
        print(f"Wrote {video_root / 'directing' / 'vo_script.md'}")

    shots_json = video_root / "shots" / "shot_decomposition.json"
    runtime_sec = int((video.get("runtime_minutes") or 10) * 60)
    if directing_json.is_file() and not (skip_existing and shots_json.is_file()):
        print(f"\n=== [{vid}] Shot decomposition ({runtime_sec}s target) ===")
        run_stage(
            "build_shot_decomposition.py",
            [
                "--directing-package",
                str(directing_json),
                "--series-bible",
                str(series_bible),
                "--runtime-seconds",
                str(runtime_sec),
                "--output-root",
                out_flag,
            ],
        )

    if director_only:
        return

    bible_json = video_root / "math_bible" / "math_bible.json"
    screenplay_json = video_root / "screenplay" / "screenplay.json"
    storyboard_json = video_root / "storyboard" / "storyboard.json"

    if not (skip_existing and bible_json.is_file()):
        print(f"\n=== [{vid}] Concept bible (topics for screenplay) ===")
        run_stage(
            "generate_topic_bible.py",
            [
                "--input",
                str(brief_path),
                "--backend",
                DEFAULT_LLM_BACKEND,
                "--max-tokens",
                str(max_tokens),
                "--output-root",
                out_flag,
            ],
        )

    if not (skip_existing and screenplay_json.is_file()):
        print(f"\n=== [{vid}] Screenplay ===")
        run_stage(
            "generate_screenplay.py",
            [
                "--backend",
                DEFAULT_LLM_BACKEND,
                "--skip-gate",
                "--runtime-minutes",
                str(video.get("runtime_minutes") or 8),
                "--series-bible",
                str(series_bible),
                "--output-root",
                out_flag,
            ],
        )

    if not (skip_existing and storyboard_json.is_file()):
        print(f"\n=== [{vid}] Storyboard (shots for production) ===")
        run_stage(
            "generate_storyboard.py",
            [
                "--backend",
                DEFAULT_LLM_BACKEND,
                "--skip-gate",
                "--series-bible",
                str(series_bible),
                "--output-root",
                out_flag,
            ],
        )

    write_json(
        video_root / "video_production_package.json",
        {
            "video_id": vid,
            "title": video.get("title"),
            "director_brief": project_rel(brief_path),
            "directing_package": project_rel(directing_json),
            "story_overview": project_rel(video_root / "directing" / "story_overview.md"),
            "vo_script": project_rel(video_root / "directing" / "vo_script.md"),
            "math_bible": project_rel(bible_json),
            "screenplay": project_rel(screenplay_json),
            "storyboard": project_rel(storyboard_json),
            "shot_decomposition": project_rel(video_root / "shots" / "shot_decomposition.json"),
            "shots_md": project_rel(video_root / "shots" / "shots.md"),
            "narration_manifest": project_rel(video_root / "shots" / "narration_manifest.json"),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM Director: story + video prep from textbook chapters (per video_plan unit)."
    )
    parser.add_argument("--book-id", type=str, required=True)
    parser.add_argument("--video-id", type=str, default=None, help="Process one unit only.")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--director-only", action="store_true", help="Only run directing package + story exports.")
    parser.add_argument("--max-tokens", type=int, default=8192, help="Max tokens per director LLM call (staged = several calls).")
    add_output_root_argument(parser)
    args = parser.parse_args()

    ensure_qwen_env()
    configure_output_root(args.output_root)

    root = book_root(args.book_id)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    plan = json.loads((root / "video_plan.json").read_text(encoding="utf-8"))
    series_bible = root / "series_bible" / "series_bible.json"
    if not series_bible.is_file():
        raise FileNotFoundError(f"Run cast bootstrap first: {series_bible}")

    videos = plan.get("videos") or []
    if args.video_id:
        videos = [v for v in videos if v.get("video_id") == args.video_id]
        if not videos:
            raise ValueError(f"Unknown video_id: {args.video_id}")

    print(f"Book: {args.book_id} — {len(videos)} video unit(s)")
    print(f"LLM: {DEFAULT_LLM_BACKEND} / {os.environ.get('QWEN_MODEL', DEFAULT_QWEN_MODEL)}")
    print(f"Output: {project_rel(root)}/")

    for video in videos:
        produce_video_unit(
            book_id=args.book_id,
            manifest=manifest,
            plan=plan,
            video=video,
            series_bible=series_bible,
            skip_existing=args.skip_existing,
            max_tokens=args.max_tokens,
            director_only=args.director_only,
        )

    print("\nDirector run complete.")


if __name__ == "__main__":
    main()
