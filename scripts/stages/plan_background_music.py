#!/usr/bin/env python3
"""LLM: full-timeline background music cue sheet from directing + shot timeline."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import (
    DEFAULT_LLM_BACKEND,
    PROMPTS_DIR,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
    resolve_project_path,
)
from pipeline_utils import run_llm_json, write_json
from shot_decomposition import format_timestamp, parse_timestamp

SUB_MODULE = "background_audio"
DEFAULT_PROMPT = PROMPTS_DIR / "audio_cue_sheet_plan.md"
REQUIRED_CUE_KEYS = {
    "cue_id",
    "time_start",
    "time_end",
    "mood",
    "instruments",
    "intensity",
    "mix_notes",
    "stable_audio_prompt",
}


def validate_plan(data: dict, *, target_seconds: float) -> None:
    if "audio_cue_sheet" not in data or not isinstance(data["audio_cue_sheet"], list):
        raise ValueError("response must include non-empty audio_cue_sheet")
    cues = data["audio_cue_sheet"]
    if len(cues) < 4:
        raise ValueError("expected at least 4 cues for a long-form lesson")
    prev_end = 0.0
    for i, cue in enumerate(cues):
        missing = REQUIRED_CUE_KEYS - cue.keys()
        if missing:
            raise ValueError(f"cue {cue.get('cue_id', i)} missing keys: {sorted(missing)}")
        start = parse_timestamp(cue["time_start"])
        end = parse_timestamp(cue["time_end"])
        if end <= start:
            raise ValueError(f"cue {cue['cue_id']}: time_end must be after time_start")
        if start < prev_end - 2.0:
            raise ValueError(f"cue {cue['cue_id']}: overlaps previous cue (starts {start}, prev end {prev_end})")
        prev_end = end
    last_end = parse_timestamp(cues[-1]["time_end"])
    if last_end < target_seconds - 45:
        raise ValueError(
            f"last cue ends at {last_end}s but target runtime is {target_seconds}s — cover full timeline"
        )


def build_scene_timeline(package: dict, decomp: dict | None) -> list[dict]:
    if decomp and decomp.get("scenes"):
        rows = []
        for sc in decomp["scenes"]:
            rows.append(
                {
                    "scene_id": sc.get("scene_id"),
                    "time_start": sc.get("time_start"),
                    "duration_seconds": sc.get("duration_seconds"),
                    "visual_mode": sc.get("visual_mode"),
                    "on_screen_text": sc.get("on_screen_text"),
                }
            )
        return rows[:40]
    rows = []
    for sc in package.get("scene_table") or []:
        rows.append(
            {
                "scene_id": sc.get("scene_id"),
                "time_start": sc.get("time_start"),
                "duration_seconds": sc.get("duration_seconds"),
                "music_cue": sc.get("music_cue"),
                "visual_mode": sc.get("visual_mode"),
            }
        )
    return rows


def resolve_target_seconds(package: dict, decomp: dict | None, override: int | None) -> float:
    if override is not None:
        return float(override)
    if decomp:
        return float(decomp.get("total_runtime_seconds") or decomp.get("total_runtime_target_seconds") or 0)
    return float(package.get("runtime_target_seconds") or 480)


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM plan: full-timeline audio_cue_sheet JSON.")
    parser.add_argument(
        "--directing-package",
        type=Path,
        required=True,
        help="directing/directing_package.json",
    )
    parser.add_argument(
        "--shot-decomposition",
        type=Path,
        default=None,
        help="shots/shot_decomposition.json for 10:00 timeline (recommended)",
    )
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument(
        "--runtime-seconds",
        type=int,
        default=None,
        help="Override total runtime (default: from shot_decomposition or directing package)",
    )
    parser.add_argument(
        "--and-generate",
        action="store_true",
        help="After planning, run generate_background_audio on the new cue sheet.",
    )
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    pkg_path = resolve_project_path(args.directing_package)
    if not pkg_path.is_file():
        raise FileNotFoundError(pkg_path)
    package = json.loads(pkg_path.read_text(encoding="utf-8"))

    decomp = None
    decomp_path: Path | None = None
    if args.shot_decomposition:
        decomp_path = resolve_project_path(args.shot_decomposition)
        if decomp_path.is_file():
            decomp = json.loads(decomp_path.read_text(encoding="utf-8"))

    target_seconds = resolve_target_seconds(package, decomp, args.runtime_seconds)
    if target_seconds <= 0:
        target_seconds = 600.0
    total_runtime = format_timestamp(target_seconds)

    system_prompt, user_template = load_prompt_template(args.prompt)
    result = run_llm_json(
        backend=args.backend,
        system_prompt=system_prompt,
        user_prompt=fill_user_prompt(
            user_template,
            title=package.get("recommended_title") or package.get("title") or "Lesson",
            chapter=package.get("chapter") or "",
            total_runtime=total_runtime,
            total_runtime_seconds=str(int(round(target_seconds))),
            style_bible_excerpt=(package.get("style_bible") or "")[:900],
            beat_sheet_json=json.dumps(package.get("beat_sheet") or [], indent=2, ensure_ascii=False),
            script_json=json.dumps(package.get("script") or [], indent=2, ensure_ascii=False),
            scene_timeline_json=json.dumps(
                build_scene_timeline(package, decomp), indent=2, ensure_ascii=False
            ),
            previous_cue_sheet_json=json.dumps(
                package.get("audio_cue_sheet") or [], indent=2, ensure_ascii=False
            ),
        ),
        validate=lambda d: validate_plan(d, target_seconds=target_seconds),
        max_tokens=args.max_tokens,
        json_retries=3,
    )

    out = {
        "title": package.get("title"),
        "chapter": package.get("chapter"),
        "total_runtime_seconds": target_seconds,
        "total_runtime": total_runtime,
        "planning_rationale": result.get("planning_rationale") or "",
        "source_directing_package": project_rel(pkg_path.resolve()),
        "source_shot_decomposition": project_rel(decomp_path.resolve())
        if decomp_path and decomp_path.is_file()
        else None,
        "audio_cue_sheet": result["audio_cue_sheet"],
    }
    out_dir = output_dir(SUB_MODULE)
    sheet_path = out_dir / "music_cue_sheet.json"
    write_json(sheet_path, out)
    print(f"Wrote {project_rel(sheet_path)} ({len(out['audio_cue_sheet'])} cues → {total_runtime})")

    if args.and_generate:
        from pipeline_utils import run_script

        rc = run_script(
            "generate_background_audio.py",
            [
                "--cue-sheet",
                str(sheet_path),
                "--output-root",
                str(get_output_root()),
            ],
        )
        if rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
