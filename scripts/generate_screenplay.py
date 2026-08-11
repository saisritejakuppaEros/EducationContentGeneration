#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import DEFAULT_LLM_BACKEND, PROMPTS_DIR, SAMPLES_DIR, output_dir
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "screenplay"
DEFAULT_MATH_BIBLE = output_dir("math_bible") / "math_bible.json"
DEFAULT_SERIES_BIBLE = output_dir("series_bible") / "series_bible.json"
DEFAULT_REFERENCE = SAMPLES_DIR / "screenplay.json"
DEFAULT_PROMPT = PROMPTS_DIR / "screenplay.md"
DEFAULT_RUNTIME_MINUTES = 18
EMPTY_BIBLE = "{}"


def validate_screenplay(data: dict) -> None:
    if "chapter" not in data or "scenes" not in data:
        raise ValueError("screenplay must have 'chapter' and 'scenes'")
    scenes = data["scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("'scenes' must be a non-empty list")
    for scene in scenes:
        for key in (
            "scene_id",
            "type",
            "int_ext",
            "location",
            "time_of_day",
            "topic_ids",
            "action",
            "dialogue",
            "target_duration_seconds",
            "leads_to",
        ):
            if key not in scene:
                raise ValueError(f"Scene {scene.get('scene_id', '?')} missing '{key}'")
        if scene["type"] not in {"STORY", "CONCEPT", "HYBRID"}:
            raise ValueError(f"Scene {scene['scene_id']} has invalid type: {scene['type']}")
        if not isinstance(scene["dialogue"], list):
            raise ValueError(f"Scene {scene['scene_id']} dialogue must be a list")


def gate_check_screenplay(screenplay: dict, math_bible: dict) -> tuple[bool, str]:
    topic_ids = {t["id"] for t in math_bible.get("topics", [])}
    covered = set()
    for scene in screenplay.get("scenes", []):
        covered.update(scene.get("topic_ids") or [])

    missing = topic_ids - covered
    if missing:
        return False, f"math_bible topics not covered in screenplay: {sorted(missing)}"

    for scene in screenplay.get("scenes", []):
        words = sum(len(d.get("line", "").split()) for d in scene.get("dialogue", []))
        duration = scene.get("target_duration_seconds") or 1
        wpm = (words / duration) * 60
        if wpm > 220:
            return False, f"Scene {scene['scene_id']} dialogue too dense ({wpm:.0f} WPM)"

    return True, "All topics covered; dialogue pacing plausible"


def render_screenplay_md(screenplay: dict) -> str:
    lines = [f"# {screenplay.get('chapter', 'Chapter')}", ""]
    for scene in screenplay.get("scenes", []):
        lines.append(
            f"## {scene['scene_id']} — {scene['int_ext']}. {scene['location']} — {scene['time_of_day']}"
        )
        lines.append(f"**Type:** {scene['type']}  ")
        lines.append(f"**Topics:** {', '.join(scene.get('topic_ids') or []) or '—'}")
        lines.append("")
        lines.append(scene.get("action", ""))
        lines.append("")
        for entry in scene.get("dialogue", []):
            lines.append(f"**{entry.get('character', '?')}**")
            lines.append(entry.get("line", ""))
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def generate(
    *,
    math_bible_path: Path,
    series_bible_path: Path,
    reference_path: Path,
    prompt_path: Path,
    runtime_minutes: int,
    backend: str,
    model_path: Path,
    max_new_tokens: int,
    max_tokens: int,
    enable_thinking: bool,
    skip_gate: bool,
) -> dict:
    math_bible = json.loads(math_bible_path.read_text(encoding="utf-8"))
    series_bible = (
        series_bible_path.read_text(encoding="utf-8")
        if series_bible_path.is_file()
        else EMPTY_BIBLE
    )
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        math_bible=json.dumps(math_bible, indent=2, ensure_ascii=False),
        series_bible=series_bible,
        chapter_runtime_target_minutes=str(runtime_minutes),
        reference_output=reference_output,
    )

    result = run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        validate=validate_screenplay,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )

    if skip_gate:
        write_gate(SUB_MODULE, passed=True, notes="Gate skipped via --skip-gate")
        return result

    passed, notes = gate_check_screenplay(result, math_bible)
    write_gate(SUB_MODULE, passed=passed, notes=notes)
    print(f"Gate {'PASSED' if passed else 'FAILED'}: {notes}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate screenplay.json from math_bible.")
    parser.add_argument("--math-bible", type=Path, default=DEFAULT_MATH_BIBLE)
    parser.add_argument("--series-bible", type=Path, default=DEFAULT_SERIES_BIBLE)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--runtime-minutes", type=int, default=DEFAULT_RUNTIME_MINUTES)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    args = parser.parse_args()

    from paths import DEFAULT_GEMMA_MODEL

    if not args.math_bible.is_file():
        raise FileNotFoundError(f"math_bible not found: {args.math_bible}")

    model_path = args.model_path or DEFAULT_GEMMA_MODEL
    out_dir = output_dir(SUB_MODULE)

    result = generate(
        math_bible_path=args.math_bible,
        series_bible_path=args.series_bible,
        reference_path=args.reference,
        prompt_path=args.prompt,
        runtime_minutes=args.runtime_minutes,
        backend=args.backend,
        model_path=model_path,
        max_new_tokens=args.max_new_tokens,
        max_tokens=args.max_tokens,
        enable_thinking=not args.disable_thinking,
        skip_gate=args.skip_gate,
    )

    json_path = out_dir / "screenplay.json"
    md_path = out_dir / "screenplay.md"
    write_json(json_path, result)
    md_path.write_text(render_screenplay_md(result), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
