#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template, run_gemma_json_generation
from paths import PROJECT_ROOT, output_dir

SUB_MODULE = "problem_statement_buildup"
DEFAULT_INPUT = PROJECT_ROOT / "samples" / "input_docs.md"
DEFAULT_REFERENCE = PROJECT_ROOT / "samples" / "problem_statement_buildup.json"
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "problem_statement_buildup.md"
DEFAULT_MODEL = PROJECT_ROOT / "gemma4_model"
DEFAULT_OUTPUT_FILE = "problem_statement_buildup.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "story_title",
    "course_flow",
    "overarching_problem",
    "chapters",
    "story_resolution",
}


def validate_output(data: dict) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS - data.keys()
    if missing:
        raise ValueError(f"Missing required top-level keys: {sorted(missing)}")

    if not isinstance(data["course_flow"], list) or not data["course_flow"]:
        raise ValueError("'course_flow' must be a non-empty list")

    problem = data["overarching_problem"]
    if not isinstance(problem, dict):
        raise ValueError("'overarching_problem' must be an object")
    for key in ("summary", "chapter_missions"):
        if key not in problem:
            raise ValueError(f"'overarching_problem' missing '{key}'")

    chapters = data["chapters"]
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("'chapters' must be a non-empty list")

    for chapter in chapters:
        for key in ("number", "name", "subtitle", "topics", "chapter_close"):
            if key not in chapter:
                raise ValueError(f"Chapter {chapter.get('number', '?')} missing '{key}'")
        for topic in chapter["topics"]:
            for key in ("id", "topic", "story_beat", "why_in_story"):
                if key not in topic:
                    raise ValueError(f"Topic in chapter {chapter['number']} missing '{key}'")


def generate(
    input_path: Path,
    reference_path: Path,
    prompt_path: Path,
    model_path: Path,
    max_new_tokens: int,
    enable_thinking: bool,
) -> dict:
    input_docs = input_path.read_text(encoding="utf-8")
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        input_docs=input_docs,
        reference_output=reference_output,
    )

    return run_gemma_json_generation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        enable_thinking=enable_thinking,
        validate=validate_output,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate problem_statement_buildup JSON from textbook input using Gemma 4."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Filename written inside output/{SUB_MODULE}/",
    )
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--disable-thinking", action="store_true")
    args = parser.parse_args()

    enable_thinking = not args.disable_thinking
    out_dir = output_dir(SUB_MODULE)
    out_path = out_dir / args.output_file

    result = generate(
        input_path=args.input,
        reference_path=args.reference,
        prompt_path=args.prompt,
        model_path=args.model_path,
        max_new_tokens=args.max_new_tokens,
        enable_thinking=enable_thinking,
    )

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
