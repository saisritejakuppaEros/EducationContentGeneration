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

SUB_MODULE = "math_specs"
DEFAULT_INPUT = SAMPLES_DIR / "input_docs.md"
DEFAULT_REFERENCE = SAMPLES_DIR / "math_specs.json"
DEFAULT_PROMPT = PROMPTS_DIR / "math_specs.md"
DEFAULT_OUTPUT_FILE = "math_specs.json"
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


def validate_topic_specs(data: dict) -> None:
    if "chapter" not in data or "topics" not in data:
        raise ValueError("topic_specs must have 'chapter' and 'topics'")
    topics = data["topics"]
    if not isinstance(topics, list) or not topics:
        raise ValueError("'topics' must be a non-empty list")
    for topic in topics:
        missing = REQUIRED_TOPIC_KEYS - topic.keys()
        if missing:
            raise ValueError(f"Topic {topic.get('id', '?')} missing keys: {sorted(missing)}")


def validate_verification(data: dict) -> None:
    if "passed" not in data or "failed_topics" not in data:
        raise ValueError("verification must have 'passed' and 'failed_topics'")
    if not isinstance(data["failed_topics"], list):
        raise ValueError("'failed_topics' must be a list")


def run_verification_gate(
    *,
    topic_specs: dict,
    backend: str,
    model_path: Path,
    max_tokens: int,
) -> dict:
    system = (
        "You are a mathematics professor grading a math specs. "
        "Re-verify every equation independently. "
        "Output ONLY JSON: {\"passed\": bool, \"failed_topics\": [{\"id\": \"1.1\", \"error\": \"...\"}]}"
    )
    user = json.dumps(topic_specs, indent=2, ensure_ascii=False)
    return run_llm_json(
        backend=backend,
        system_prompt=system,
        user_prompt=user,
        validate=validate_verification,
        model_path=model_path,
        max_tokens=max_tokens,
    )


def generate(
    *,
    input_path: Path,
    reference_path: Path,
    prompt_path: Path,
    math_history: str,
    backend: str,
    model_path: Path,
    max_new_tokens: int,
    max_tokens: int,
    enable_thinking: bool,
    skip_gate: bool,
) -> dict:
    chapter_text = input_path.read_text(encoding="utf-8")
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        chapter_text=chapter_text,
        series_profile_math_history=math_history,
        reference_output=reference_output,
    )

    result = run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        validate=validate_topic_specs,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )

    if skip_gate:
        write_gate(SUB_MODULE, passed=True, notes="Gate skipped via --skip-gate")
        return result

    verification = run_verification_gate(
        topic_specs=result,
        backend=backend,
        model_path=model_path,
        max_tokens=max_tokens,
    )
    failed = verification.get("failed_topics") or []
    if failed:
        failed_ids = {item["id"] for item in failed if item.get("id")}
        notes = "; ".join(f"{item.get('id')}: {item.get('error', '')}" for item in failed)
        write_gate(SUB_MODULE, passed=False, notes=notes, details={"failed_topics": failed})
        print(f"Gate FAILED for topics: {sorted(failed_ids)}")
    else:
        write_gate(SUB_MODULE, passed=True, notes="All equations verified")
        print("Gate PASSED")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate math_specs.json from chapter text.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--math-history", default=DEFAULT_MATH_HISTORY)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    add_output_root_argument(parser)
    args = parser.parse_args()

    from paths import DEFAULT_GEMMA_MODEL

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    model_path = args.model_path or DEFAULT_GEMMA_MODEL
    out_path = output_dir(SUB_MODULE) / args.output_file

    result = generate(
        input_path=args.input,
        reference_path=args.reference,
        prompt_path=args.prompt,
        math_history=args.math_history,
        backend=args.backend,
        model_path=model_path,
        max_new_tokens=args.max_new_tokens,
        max_tokens=args.max_tokens,
        enable_thinking=not args.disable_thinking,
        skip_gate=args.skip_gate,
    )

    write_json(out_path, result)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
