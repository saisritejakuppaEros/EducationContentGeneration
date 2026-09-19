#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import DEFAULT_LLM_BACKEND, PROMPTS_DIR, SAMPLES_DIR, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "series_bible"
DEFAULT_REFERENCE = SAMPLES_DIR / "series_bible.json"
DEFAULT_PROMPT = PROMPTS_DIR / "series_bible.md"
DEFAULT_SCREENPLAY = output_dir("screenplay") / "screenplay.json"
DEFAULT_TEXTBOOK = "Intermediate Mathematics"
DEFAULT_TONE = "Interstellar-adjacent grounded sci-fi"

REFERENCE_TAGS = [
    "front_neutral",
    "three_quarter_left",
    "three_quarter_right",
    "profile",
    "close_up_neutral",
    "close_up_expression_concerned",
    "close_up_expression_curious",
    "wide_full_body_neutral_pose",
]


def validate_series_bible(data: dict) -> None:
    for key in ("textbook_title", "target_tone", "cast", "world", "visual_grammar", "chapters_so_far"):
        if key not in data:
            raise ValueError(f"series_bible missing '{key}'")
    for cast_key in ("M", "F", "Y"):
        if cast_key not in data["cast"]:
            raise ValueError(f"cast missing '{cast_key}'")


def ensure_reference_photo_placeholders(bible: dict) -> dict:
    for cast_key, info in bible.get("cast", {}).items():
        photos = info.get("reference_photos") or []
        existing_tags = {p.get("tag") for p in photos}
        for tag in REFERENCE_TAGS:
            if tag in existing_tags:
                continue
            photos.append(
                {
                    "tag": tag,
                    "path": f"output/series_bible/reference_photos/{cast_key}/{tag}.png",
                    "source": "pending",
                }
            )
        info["reference_photos"] = photos
    return bible


def generate(
    *,
    textbook_title: str,
    target_tone: str,
    existing_bible_path: Path | None,
    screenplay_path: Path | None,
    reference_path: Path,
    prompt_path: Path,
    backend: str,
    model_path: Path,
    max_new_tokens: int,
    max_tokens: int,
    enable_thinking: bool,
) -> dict:
    existing = (
        existing_bible_path.read_text(encoding="utf-8")
        if existing_bible_path and existing_bible_path.is_file()
        else "{}"
    )
    screenplay = (
        screenplay_path.read_text(encoding="utf-8")
        if screenplay_path and screenplay_path.is_file()
        else "{}"
    )
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        textbook_title=textbook_title,
        target_tone=target_tone,
        existing_series_bible=existing,
        new_chapter_screenplay=screenplay,
        reference_output=reference_output,
    )

    result = run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        validate=validate_series_bible,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )
    return ensure_reference_photo_placeholders(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate or update series_bible.json.")
    parser.add_argument("--textbook-title", default=DEFAULT_TEXTBOOK)
    parser.add_argument("--target-tone", default=DEFAULT_TONE)
    parser.add_argument("--existing", type=Path, default=None, help="Existing series_bible.json to update.")
    parser.add_argument("--screenplay", type=Path, default=DEFAULT_SCREENPLAY)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--disable-thinking", action="store_true")
    add_output_root_argument(parser)
    args = parser.parse_args()

    from paths import DEFAULT_GEMMA_MODEL

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    model_path = args.model_path or DEFAULT_GEMMA_MODEL
    out_dir = output_dir(SUB_MODULE)
    out_path = out_dir / "series_bible.json"

    existing_path = args.existing or (out_path if out_path.is_file() else None)

    result = generate(
        textbook_title=args.textbook_title,
        target_tone=args.target_tone,
        existing_bible_path=existing_path,
        screenplay_path=args.screenplay if args.screenplay.is_file() else None,
        reference_path=args.reference,
        prompt_path=args.prompt,
        backend=args.backend,
        model_path=model_path,
        max_new_tokens=args.max_new_tokens,
        max_tokens=args.max_tokens,
        enable_thinking=not args.disable_thinking,
    )

    write_json(out_path, result)
    write_gate(SUB_MODULE, passed=True, notes="Manual review recommended for reference photo bank")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
