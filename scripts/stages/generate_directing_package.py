#!/usr/bin/env python3
"""NCERT explainer directing package (timeline, script, scenes, BGM cues)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401


import argparse
import json
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import (
    DEFAULT_LLM_BACKEND,
    DIRECTOR_SKILL_PATH,
    PROMPTS_DIR,
    SAMPLES_DIR,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
)
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "directing"
DEFAULT_INPUT = SAMPLES_DIR / "input_docs.md"
DEFAULT_USER_PROMPT = PROMPTS_DIR / "directing_package.md"
DEFAULT_RUNTIME_SECONDS = 540


def load_director_system_prompt() -> str:
    if not DIRECTOR_SKILL_PATH.is_file():
        raise FileNotFoundError(f"Director skill not found: {DIRECTOR_SKILL_PATH}")
    return DIRECTOR_SKILL_PATH.read_text(encoding="utf-8")


def validate_package(data: dict) -> None:
    for key in ("title", "chapter", "runtime_target_seconds", "beat_sheet", "script", "scene_table"):
        if key not in data:
            raise ValueError(f"directing package missing '{key}'")
    if not isinstance(data["scene_table"], list) or not data["scene_table"]:
        raise ValueError("scene_table must be a non-empty list")
    if not isinstance(data.get("audio_cue_sheet"), list):
        raise ValueError("audio_cue_sheet must be a list (for background-audio agent)")


def render_timeline_md(package: dict) -> str:
    lines = [
        f"# {package.get('title', package.get('chapter', 'Directing package'))}",
        "",
        f"Runtime target: **{package.get('runtime_target_seconds', '?')} s**",
        "",
        "## Beat sheet",
        "",
        "| # | Time | Label | Turns | Music |",
        "|---|------|-------|-------|-------|",
    ]
    for row in package.get("beat_sheet", []):
        turns = ", ".join(row.get("turn_ids") or []) or "—"
        lines.append(
            f"| {row.get('beat_number', '?')} | "
            f"{row.get('time_start', '?')}–{row.get('time_end', '?')} | "
            f"{row.get('label', '?')} | {turns} | {row.get('music_intensity', '—')} |"
        )
    lines.extend(["", "## Scene timeline (first 20)", ""])
    for scene in package.get("scene_table", [])[:20]:
        lines.append(
            f"- **{scene.get('scene_id')}** @ {scene.get('time_start')} "
            f"({scene.get('duration_seconds')}s) — {scene.get('visual_mode')}: "
            f"{scene.get('vo_excerpt', '')[:60]}"
        )
    total = len(package.get("scene_table", []))
    if total > 20:
        lines.append(f"- … and {total - 20} more scenes")
    return "\n".join(lines) + "\n"


def generate(
    *,
    chapter_text: str,
    user_prompt_path: Path,
    backend: str,
    model_path: Path,
    runtime_seconds: int,
    max_tokens: int,
) -> dict:
    system_prompt = load_director_system_prompt()
    _, user_template = load_prompt_template(user_prompt_path)
    runtime_minutes = round(runtime_seconds / 60, 1)

    def validate(data: dict) -> None:
        validate_package(data)

    return run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=fill_user_prompt(
            user_template,
            chapter_text=chapter_text,
            runtime_seconds=str(runtime_seconds),
            runtime_minutes=str(runtime_minutes),
        ),
        validate=validate,
        model_path=model_path,
        max_tokens=max_tokens,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Director skill → timeline-first directing package (JSON + markdown)."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Chapter text (markdown/plain).")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_USER_PROMPT)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--runtime-seconds", type=int, default=DEFAULT_RUNTIME_SECONDS)
    parser.add_argument("--max-tokens", type=int, default=16384)
    add_output_root_argument(parser)
    args = parser.parse_args()

    from paths import DEFAULT_GEMMA_MODEL

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    if not args.input.is_file():
        raise FileNotFoundError(f"Input not found: {args.input}")

    chapter_text = args.input.read_text(encoding="utf-8")
    model_path = args.model_path or DEFAULT_GEMMA_MODEL

    package = generate(
        chapter_text=chapter_text,
        user_prompt_path=args.prompt,
        backend=args.backend,
        model_path=model_path,
        runtime_seconds=args.runtime_seconds,
        max_tokens=args.max_tokens,
    )

    out_dir = output_dir(SUB_MODULE)
    json_path = out_dir / "directing_package.json"
    md_path = out_dir / "directing_timeline.md"
    write_json(json_path, package)
    md_path.write_text(render_timeline_md(package), encoding="utf-8")

    scene_count = len(package.get("scene_table", []))
    cue_count = len(package.get("audio_cue_sheet", []))
    write_gate(
        "directing_package",
        passed=scene_count >= 10,
        notes=f"{scene_count} timed scenes, {cue_count} BGM cues",
        details={"scenes": scene_count, "bgm_cues": cue_count},
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")


if __name__ == "__main__":
    main()
