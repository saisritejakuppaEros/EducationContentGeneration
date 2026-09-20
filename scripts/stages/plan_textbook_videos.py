#!/usr/bin/env python3
"""LLM plan: group textbook sections into one video per coherent unit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import DEFAULT_LLM_BACKEND, PROMPTS_DIR, add_output_root_argument, configure_output_root, get_output_root, project_rel
from pipeline_utils import run_llm_json, write_json
from textbook_pdf import book_id_from_pdf, section_markdown


def validate_plan(data: dict) -> None:
    if "videos" not in data or not isinstance(data["videos"], list) or not data["videos"]:
        raise ValueError("plan must contain non-empty 'videos' list")
    for v in data["videos"]:
        for key in ("video_id", "title", "section_ids"):
            if key not in v:
                raise ValueError(f"video missing '{key}'")


def attach_chapter_markdown(plan: dict, manifest: dict) -> dict:
    for video in plan.get("videos", []):
        video["chapter_markdown"] = section_markdown(manifest, video.get("section_ids") or [])
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan per-chapter videos from textbook manifest.")
    parser.add_argument("--book-id", type=str, required=True)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--prompt", type=Path, default=PROMPTS_DIR / "textbook_video_plan.md")
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--max-tokens", type=int, default=8192)
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    book_root = get_output_root() / "textbooks" / args.book_id
    manifest_path = args.manifest or (book_root / "manifest.json")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Run extract_textbook_pdf first: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    system_prompt, user_template = load_prompt_template(args.prompt)

    def validate(data: dict) -> None:
        validate_plan(data)

    plan = run_llm_json(
        backend=args.backend,
        system_prompt=system_prompt,
        user_prompt=fill_user_prompt(
            user_template,
            manifest_json=json.dumps(manifest, indent=2, ensure_ascii=False),
        ),
        validate=validate,
        max_tokens=args.max_tokens,
    )
    plan = attach_chapter_markdown(plan, manifest)
    plan["book_id"] = args.book_id
    plan_path = book_root / "video_plan.json"
    write_json(plan_path, plan)
    print(f"Planned {len(plan['videos'])} video(s) → {plan_path}")
    print(f"Book root: {project_rel(book_root)}/")


if __name__ == "__main__":
    main()
