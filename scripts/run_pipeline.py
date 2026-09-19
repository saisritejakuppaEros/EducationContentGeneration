#!/usr/bin/env python3
import _bootstrap  # noqa: F401 — adds scripts/lib to sys.path

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from paths import (
    DEFAULT_LLM_BACKEND,
    DEFAULT_QWEN_API_BASE,
    DEFAULT_QWEN_API_KEY,
    DEFAULT_QWEN_MODEL,
    PROJECT_ROOT,
    SAMPLES_DIR,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
)
from pipeline_utils import STAGES, gate_passed, run_script, stage_by_id, write_json

PIPELINE_SUB_MODULE = "pipeline"

# Default CLI args per stage when orchestrating (all LLM stages use Qwen via vLLM).
STAGE_DEFAULT_ARGS: dict[str, list[str]] = {
    "dir": ["--backend", DEFAULT_LLM_BACKEND, "--input", str(SAMPLES_DIR / "input_docs.md")],
    "1": ["--backend", DEFAULT_LLM_BACKEND, "--input", str(SAMPLES_DIR / "input_docs.md")],
    "2": ["--backend", DEFAULT_LLM_BACKEND],
    "3": ["--backend", DEFAULT_LLM_BACKEND],
    "3b": ["--backend", DEFAULT_LLM_BACKEND, "--copy-only"],
    "4": ["--backend", DEFAULT_LLM_BACKEND],
    "4b": [],
    "5a": ["--deterministic-prompts"],
    "5b": [
        "--manim-model", os.environ.get("QWEN_MODEL", DEFAULT_QWEN_MODEL),
        "--review-model", os.environ.get("QWEN_MODEL", DEFAULT_QWEN_MODEL),
    ],
    "6": ["--synthesize", "--voice-only"],
    "6b": ["--directing-package"],
    "7": [],
}

# Stages skipped when custom cast / reference photos are deferred.
REFERENCE_BANK_STAGE_ID = "3b"


def ensure_qwen_env() -> None:
    os.environ.setdefault("OPENAI_API_BASE", DEFAULT_QWEN_API_BASE)
    os.environ.setdefault("OPENAI_API_KEY", DEFAULT_QWEN_API_KEY)
    os.environ.setdefault("QWEN_MODEL", DEFAULT_QWEN_MODEL)


def stage_range(from_stage: str | None, to_stage: str | None) -> list:
    ids = [s.id for s in STAGES if s.id not in {"0"}]
    if from_stage:
        if from_stage not in ids:
            raise ValueError(f"Unknown from-stage: {from_stage}")
        ids = ids[ids.index(from_stage) :]
    if to_stage:
        if to_stage not in ids:
            raise ValueError(f"Unknown to-stage: {to_stage}")
        ids = ids[: ids.index(to_stage) + 1]
    return [stage_by_id(sid) for sid in ids if stage_by_id(sid)]


def script_args_for_stage(
    stage_id: str,
    passthrough: list[str],
    output_root: Path | None,
    *,
    enable_manim: bool,
) -> list[str]:
    if passthrough:
        args = list(passthrough)
    elif stage_id == "4b":
        args = list(STAGE_DEFAULT_ARGS.get(stage_id, []))
        if not enable_manim:
            args.append("--include-math-inserts")
    elif stage_id == "5a":
        args = list(STAGE_DEFAULT_ARGS.get(stage_id, []))
        if not enable_manim:
            args.append("--include-math-inserts")
    elif stage_id == "7" and enable_manim:
        args = ["--enable-manim"]
    else:
        args = list(STAGE_DEFAULT_ARGS.get(stage_id, ["--backend", DEFAULT_LLM_BACKEND]))
    if output_root is not None:
        flag = str(output_root)
        if "--output-root" not in args:
            args.extend(["--output-root", flag])
    return args


def dry_run_report(
    output_root: Path,
    *,
    enable_manim: bool,
    skip_reference_bank: bool,
) -> None:
    print("Chapter-to-Movie Pipeline — stage I/O")
    print(f"Output root: {project_rel(output_root)}/")
    print(f"LLM backend: {DEFAULT_LLM_BACKEND} (vLLM @ {DEFAULT_QWEN_API_BASE})")
    print(f"Model: {os.environ.get('QWEN_MODEL', DEFAULT_QWEN_MODEL)}")
    print(f"Manim (stage 5b): {'enabled' if enable_manim else 'disabled — math inserts via cinematic LTX'}")
    print(f"Reference bank (3b): {'skipped' if skip_reference_bank else 'enabled'}\n")
    for stage in STAGES:
        if stage.id == "0":
            continue
        rel_output = stage.primary_output.replace("output/", f"{project_rel(output_root)}/", 1)
        print(f"[{stage.id}] {stage.name}")
        print(f"  script:  scripts/stages/{stage.script}")
        print(f"  output:  {rel_output}")
        print(f"  gate:    {stage.gate}")
        if stage.id == "5b" and not enable_manim:
            print("  skipped: Manim disabled (use --enable-manim to run stage 5b)")
        elif stage.id == REFERENCE_BANK_STAGE_ID and skip_reference_bank:
            print("  skipped: custom avatars deferred (omit --skip-reference-bank to run)")
        else:
            stage_defaults = script_args_for_stage(stage.id, [], None, enable_manim=enable_manim)
            if stage_defaults:
                print(f"  defaults: {' '.join(stage_defaults)}")
        print()


def update_state(*, current_stage: str, status: str, notes: str = "", enable_manim: bool = False) -> None:
    state_path = output_dir(PIPELINE_SUB_MODULE) / "state.json"
    state = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "current_stage": current_stage,
            "status": status,
            "notes": notes,
            "output_root": project_rel(get_output_root()),
            "llm_backend": DEFAULT_LLM_BACKEND,
            "qwen_model": os.environ.get("QWEN_MODEL", DEFAULT_QWEN_MODEL),
            "enable_manim": enable_manim,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_json(state_path, state)


def main() -> None:
    parser = argparse.ArgumentParser(description="Orchestrate the chapter-to-movie pipeline (Qwen via vLLM).")
    parser.add_argument("--dry-run", action="store_true", help="List stages and expected I/O paths.")
    parser.add_argument("--from-stage", default="1", help="First stage id to run (default: 1).")
    parser.add_argument("--to-stage", default="7", help="Last stage id to run (default: 7).")
    parser.add_argument("--force", action="store_true", help="Run even if upstream gate failed.")
    parser.add_argument(
        "--enable-manim",
        action="store_true",
        help="Run stage 5b (Manim math inserts). When off, MATH INSERT shots use cinematic LTX instead.",
    )
    parser.add_argument(
        "--skip-reference-bank",
        action="store_true",
        help="Skip stage 3b (cast reference photos) until custom avatars are ready.",
    )
    parser.add_argument(
        "--generation-only",
        action="store_true",
        help="Timeline + pixels first: director (dir) through cinematic video (5a); no final cut.",
    )
    add_output_root_argument(parser)
    parser.add_argument("passthrough", nargs="*", help="Extra args forwarded to each stage script.")
    args = parser.parse_args()

    ensure_qwen_env()
    output_root = configure_output_root(args.output_root)

    skip_reference_bank = args.skip_reference_bank or args.generation_only

    if args.generation_only:
        if args.from_stage == "1":
            args.from_stage = "dir"
        if args.to_stage == "7":
            args.to_stage = "5a"

    if args.dry_run:
        dry_run_report(
            output_root,
            enable_manim=args.enable_manim,
            skip_reference_bank=skip_reference_bank,
        )
        return

    stages = stage_range(args.from_stage, args.to_stage)
    if not stages:
        print("No stages selected.")
        return

    gate_map = {
        "dir": None,
        "1": None,
        "2": "math_bible",
        "3": "screenplay",
        "3b": "series_bible",
        "4": "reference_bank" if not skip_reference_bank else "series_bible",
        "4b": "storyboard",
        "5a": "storyboard",
        "5b": "math_bible",
        "6": "storyboard",
        "6b": "directing_package",
        "7": "audio",
    }

    for stage in stages:
        required_gate = gate_map.get(stage.id)
        if required_gate and not args.force and not gate_passed(required_gate):
            print(f"Blocked at stage {stage.id}: gate '{required_gate}' not passed. Use --force to override.")
            update_state(current_stage=stage.id, status="blocked", notes=f"gate {required_gate} failed")
            sys.exit(1)

        if stage.id == "0":
            continue

        if stage.id == "5b" and not args.enable_manim:
            print(f"\n=== Stage {stage.id}: {stage.name} (skipped — Manim disabled) ===")
            update_state(
                current_stage=stage.id,
                status="skipped",
                notes="Manim disabled; math inserts handled in stages 4b/5a",
                enable_manim=args.enable_manim,
            )
            continue

        if stage.id == REFERENCE_BANK_STAGE_ID and skip_reference_bank:
            print(f"\n=== Stage {stage.id}: {stage.name} (skipped — avatars/reference bank deferred) ===")
            update_state(
                current_stage=stage.id,
                status="skipped",
                notes="Reference bank deferred; use placeholder anchor in directing package",
                enable_manim=args.enable_manim,
            )
            continue

        print(f"\n=== Stage {stage.id}: {stage.name} ===")
        print(f"Output root: {project_rel(output_root)}/")
        update_state(current_stage=stage.id, status="running", enable_manim=args.enable_manim)
        rc = run_script(
            stage.script,
            script_args_for_stage(stage.id, args.passthrough, output_root, enable_manim=args.enable_manim),
        )
        if rc != 0:
            update_state(
                current_stage=stage.id,
                status="failed",
                notes=f"exit code {rc}",
                enable_manim=args.enable_manim,
            )
            sys.exit(rc)
        update_state(current_stage=stage.id, status="completed", enable_manim=args.enable_manim)

    update_state(current_stage=args.to_stage, status="done", enable_manim=args.enable_manim)
    print("\nPipeline run complete.")


if __name__ == "__main__":
    main()
