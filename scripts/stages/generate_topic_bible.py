#!/usr/bin/env python3
"""Concept bible for social science / general lessons (writes math_bible.json schema)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import DEFAULT_LLM_BACKEND, PROMPTS_DIR, SAMPLES_DIR, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "math_bible"
DEFAULT_PROMPT = PROMPTS_DIR / "topic_bible.md"
DEFAULT_REFERENCE = SAMPLES_DIR / "math_bible.json"
DEFAULT_MATH_HISTORY = "[]"

REQUIRED_TOPIC_KEYS = {
    "id",
    "topic",
    "real_world_problem",
    "equation",
    "why_this_tool",
    "prerequisites",
    "core_visual_idea",
    "explicitly_excluded",
}


def validate_bible(data: dict) -> None:
    if "chapter" not in data or "topics" not in data:
        raise ValueError("bible must have 'chapter' and 'topics'")
    for topic in data["topics"]:
        missing = REQUIRED_TOPIC_KEYS - topic.keys()
        if missing:
            raise ValueError(f"Topic {topic.get('id', '?')} missing keys: {sorted(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate concept bible → math_bible/math_bible.json")
    parser.add_argument("--input", type=Path, required=True, help="Chapter markdown for this video unit.")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--skip-gate", action="store_true", default=True)
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    if not args.input.is_file():
        raise FileNotFoundError(args.input)

    chapter_text = args.input.read_text(encoding="utf-8")
    reference_output = DEFAULT_REFERENCE.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(args.prompt)

    result = run_llm_json(
        backend=args.backend,
        system_prompt=system_prompt,
        user_prompt=fill_user_prompt(
            user_template,
            chapter_text=chapter_text,
            series_bible_math_history=DEFAULT_MATH_HISTORY,
            reference_output=reference_output,
        ),
        validate=validate_bible,
        max_tokens=args.max_tokens,
    )

    out_dir = output_dir(SUB_MODULE)
    json_path = out_dir / "math_bible.json"
    write_json(json_path, result)
    write_gate("math_bible", passed=True, notes="topic bible (social science); verification skipped")
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()
