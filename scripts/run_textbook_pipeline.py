#!/usr/bin/env python3
"""
Textbook → one explainer video per planned unit.

Phase 1 (default): extract PDF, plan videos, bootstrap cartoon cast, generate scripts per video.
Phase 2 (later): add --with-pixels to run image/video stages.
"""
import _bootstrap  # noqa: F401

import argparse
import json
import os
import sys
from pathlib import Path

from paths import (
    DEFAULT_CARTOON_CAST_IMAGE,
    DEFAULT_LLM_BACKEND,
    DEFAULT_QWEN_API_BASE,
    DEFAULT_QWEN_API_KEY,
    DEFAULT_QWEN_MODEL,
    PROJECT_ROOT,
    STAGES_DIR,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    project_rel,
)
from directing_exports import export_directing_artifacts
from pipeline_utils import run_script, write_json
from textbook_director_context import build_director_brief
from textbook_pdf import book_id_from_pdf
from textbook_plan import heuristic_video_plan

DEFAULT_PDF = Path(
    "/workspace/teja/ai_vidya/input/phaseII/assamese/pdfs/diksha/"
    "do_3129711180205834241569_ম_নৱ_স_ষ_ট_পৰ_ৱ_শ.pdf"
)

def ensure_qwen_env(*, require_qwen_server: bool = False) -> None:
    os.environ.setdefault("OPENAI_API_BASE", DEFAULT_QWEN_API_BASE)
    os.environ.setdefault("OPENAI_API_KEY", DEFAULT_QWEN_API_KEY)
    os.environ.setdefault("QWEN_MODEL", DEFAULT_QWEN_MODEL)
    if require_qwen_server:
        from qwen_utils import ensure_qwen_for_story_layout

        ensure_qwen_for_story_layout(strict=True)


def book_root(book_id: str) -> Path:
    return get_output_root() / "textbooks" / book_id


def run_stage(script: str, args: list[str]) -> None:
    rc = run_script(script, args)
    if rc != 0:
        sys.exit(rc)


def step_extract(pdf: Path, book_id: str | None, force: bool) -> str:
    bid = book_id or book_id_from_pdf(pdf)
    manifest_path = book_root(bid) / "manifest.json"
    if manifest_path.is_file() and not force:
        print(f"Skip extract — manifest exists: {manifest_path}")
        return bid
    flag = str(configure_output_root(None))
    run_stage(
        "extract_textbook_pdf.py",
        ["--pdf", str(pdf), "--book-id", bid, "--output-root", flag],
    )
    return bid


def step_plan(bid: str, *, use_llm: bool, force: bool) -> None:
    plan_path = book_root(bid) / "video_plan.json"
    if plan_path.is_file() and not force:
        print(f"Skip plan — {plan_path}")
        return
    if use_llm:
        flag = str(get_output_root())
        run_stage(
            "plan_textbook_videos.py",
            ["--book-id", bid, "--backend", DEFAULT_LLM_BACKEND, "--output-root", flag],
        )
        return
    manifest = json.loads((book_root(bid) / "manifest.json").read_text(encoding="utf-8"))
    plan = heuristic_video_plan(manifest)
    write_json(plan_path, plan)
    print(f"Heuristic plan: {len(plan['videos'])} video(s) → {plan_path}")


def step_cast(bid: str, cartoon: Path, force: bool) -> None:
    bible_path = book_root(bid) / "series_bible" / "series_bible.json"
    if bible_path.is_file() and not force:
        print(f"Skip cast bootstrap — {bible_path}")
        return
    run_stage(
        "bootstrap_textbook_cast.py",
        [
            "--book-id",
            bid,
            "--cartoon-image",
            str(cartoon),
            "--output-root",
            str(get_output_root()),
        ],
    )


def step_scripts_for_video(
    bid: str,
    video: dict,
    plan: dict,
    *,
    manifest: dict,
    series_bible: Path,
    runtime_minutes: int,
    skip_existing: bool,
    max_tokens: int,
) -> Path:
    vid = video["video_id"]
    video_root = book_root(bid) / "videos" / vid
    video_root.mkdir(parents=True, exist_ok=True)
    input_dir = video_root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    brief_path = input_dir / "director_brief.md"
    chapter_path = input_dir / "chapter.md"
    brief = build_director_brief(
        manifest=manifest,
        video=video,
        plan=plan,
        series_bible_path=series_bible,
    )
    brief_path.write_text(brief, encoding="utf-8")
    chapter_path.write_text(brief, encoding="utf-8")

    out_flag = str(video_root)
    directing_json = video_root / "directing" / "directing_package.json"
    bible_json = video_root / "math_bible" / "math_bible.json"
    screenplay_json = video_root / "screenplay" / "screenplay.json"
    storyboard_json = video_root / "storyboard" / "storyboard.json"

    runtime_seconds = int((video.get("runtime_minutes") or runtime_minutes) * 60)

    if not (skip_existing and directing_json.is_file()):
        print(f"\n--- [{vid}] directing package ---")
        run_stage(
            "generate_directing_package.py",
            [
                "--input",
                str(brief_path),
                "--backend",
                DEFAULT_LLM_BACKEND,
                "--runtime-seconds",
                str(runtime_seconds),
                "--max-tokens",
                str(max_tokens),
                "--output-root",
                out_flag,
            ],
        )
        if directing_json.is_file():
            export_directing_artifacts(directing_json, video_root / "directing")

    if not (skip_existing and bible_json.is_file()):
        print(f"\n--- [{vid}] topic bible ---")
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
        print(f"\n--- [{vid}] screenplay ---")
        run_stage(
            "generate_screenplay.py",
            [
                "--backend",
                DEFAULT_LLM_BACKEND,
                "--skip-gate",
                "--runtime-minutes",
                str(video.get("runtime_minutes") or runtime_minutes),
                "--series-bible",
                str(series_bible),
                "--output-root",
                out_flag,
            ],
        )

    if not (skip_existing and storyboard_json.is_file()):
        print(f"\n--- [{vid}] storyboard (script breakdown) ---")
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

    meta = {
        "video_id": vid,
        "title": video.get("title"),
        "output_root": project_rel(video_root),
        "chapter_input": project_rel(chapter_path),
    }
    write_json(video_root / "video_meta.json", meta)
    return video_root


def main() -> None:
    parser = argparse.ArgumentParser(description="NCERT textbook PDF → per-unit script pipeline.")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF, help="Textbook or DIKSHA lesson PDF.")
    parser.add_argument("--book-id", type=str, default=None)
    parser.add_argument(
        "--with-pixels",
        action="store_true",
        help="Also run pixel stages (keyframes, cinematic video) — default is script stages only.",
    )
    parser.add_argument(
        "--heuristic-plan",
        action="store_true",
        help="Skip LLM for video grouping (one video per extracted section).",
    )
    parser.add_argument("--force", action="store_true", help="Re-run extract/plan/cast even if outputs exist.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip per-video stages if outputs exist.")
    parser.add_argument("--runtime-minutes", type=int, default=8)
    parser.add_argument("--cartoon-image", type=Path, default=DEFAULT_CARTOON_CAST_IMAGE)
    parser.add_argument("--video-id", type=str, default=None, help="Only process one planned video id.")
    parser.add_argument(
        "--through",
        choices=("extract", "plan", "cast", "scripts"),
        default="scripts",
        help="Stop after this step (default: full script generation per video).",
    )
    parser.add_argument("--max-tokens", type=int, default=16384, help="LLM max tokens per stage call (director default 16384).")
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    ensure_qwen_env(require_qwen_server=args.through == "scripts")

    pdf = args.pdf if args.pdf.is_absolute() else PROJECT_ROOT / args.pdf
    if not pdf.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf}")

    print(f"PDF:         {pdf}")
    print(f"Output root: {project_rel(get_output_root())}/")
    print(f"Stages dir:  {project_rel(STAGES_DIR)}/")

    bid = step_extract(pdf, args.book_id, args.force)
    if args.through == "extract":
        print(f"\nStopped after extract. Book: {project_rel(book_root(bid))}/")
        return

    if args.through in ("plan", "scripts") and not args.heuristic_plan:
        ensure_qwen_env(require_qwen_server=True)

    step_plan(bid, use_llm=not args.heuristic_plan, force=args.force)
    if args.through == "plan":
        print(f"\nStopped after plan. See {project_rel(book_root(bid) / 'video_plan.json')}")
        return

    step_cast(bid, args.cartoon_image, args.force)
    if args.through == "cast":
        print(f"\nStopped after cast bootstrap.")
        return

    plan = json.loads((book_root(bid) / "video_plan.json").read_text(encoding="utf-8"))
    manifest = json.loads((book_root(bid) / "manifest.json").read_text(encoding="utf-8"))
    series_bible = book_root(bid) / "series_bible" / "series_bible.json"
    if not series_bible.is_file():
        raise FileNotFoundError(f"Missing series bible: {series_bible}")

    videos = plan.get("videos") or []
    if args.video_id:
        videos = [v for v in videos if v.get("video_id") == args.video_id]
        if not videos:
            raise ValueError(f"video_id not in plan: {args.video_id}")

    print(f"\nProcessing {len(videos)} video unit(s) for book {bid}")
    for video in videos:
        step_scripts_for_video(
            bid,
            video,
            plan,
            manifest=manifest,
            series_bible=series_bible,
            runtime_minutes=args.runtime_minutes,
            skip_existing=args.skip_existing,
            max_tokens=args.max_tokens,
        )

    if args.with_pixels:
        print("\nRun pixels per video unit, e.g.:")
        print(
            f"  python3 scripts/run_textbook_pixels.py --book-id {bid} --video-id <video_id> --output-root output"
        )

    print("\nTextbook script pipeline complete.")
    print(f"Book artifacts: {project_rel(book_root(bid))}/")


if __name__ == "__main__":
    main()
