#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from paths import DEFAULT_LLM_BACKEND, DEFAULT_QWEN_API_BASE, DEFAULT_QWEN_API_KEY, DEFAULT_QWEN_MODEL, PROJECT_ROOT, SAMPLES_DIR, output_dir
from pipeline_utils import STAGES, gate_passed, run_script, stage_by_id, write_json

PIPELINE_SUB_MODULE = "pipeline"

# Default CLI args per stage when orchestrating (all LLM stages use Qwen via vLLM).
STAGE_DEFAULT_ARGS: dict[str, list[str]] = {
    "1": ["--backend", DEFAULT_LLM_BACKEND, "--input", str(SAMPLES_DIR / "input_docs.md")],
    "2": ["--backend", DEFAULT_LLM_BACKEND],
    "3": ["--backend", DEFAULT_LLM_BACKEND],
    "3b": ["--backend", DEFAULT_LLM_BACKEND, "--copy-only"],
    "4": ["--backend", DEFAULT_LLM_BACKEND],
    "5a": ["--backend", DEFAULT_LLM_BACKEND],
    "5b": [
        "--manim-model", os.environ.get("QWEN_MODEL", DEFAULT_QWEN_MODEL),
        "--review-model", os.environ.get("QWEN_MODEL", DEFAULT_QWEN_MODEL),
    ],
    "6": ["--backend", DEFAULT_LLM_BACKEND],
    "7": [],
}


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


def script_args_for_stage(stage_id: str, passthrough: list[str]) -> list[str]:
    if passthrough:
        return passthrough
    return STAGE_DEFAULT_ARGS.get(stage_id, ["--backend", DEFAULT_LLM_BACKEND])


def dry_run_report() -> None:
    print("Chapter-to-Movie Pipeline — stage I/O")
    print(f"LLM backend: {DEFAULT_LLM_BACKEND} (vLLM @ {DEFAULT_QWEN_API_BASE})")
    print(f"Model: {os.environ.get('QWEN_MODEL', DEFAULT_QWEN_MODEL)}\n")
    for stage in STAGES:
        if stage.id == "0":
            continue
        defaults = " ".join(STAGE_DEFAULT_ARGS.get(stage.id, []))
        print(f"[{stage.id}] {stage.name}")
        print(f"  script:  scripts/{stage.script}")
        print(f"  output:  {stage.primary_output}")
        print(f"  gate:    {stage.gate}")
        if defaults:
            print(f"  defaults: {defaults}")
        print()


def update_state(*, current_stage: str, status: str, notes: str = "") -> None:
    state_path = output_dir(PIPELINE_SUB_MODULE) / "state.json"
    state = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    state.update(
        {
            "current_stage": current_stage,
            "status": status,
            "notes": notes,
            "llm_backend": DEFAULT_LLM_BACKEND,
            "qwen_model": os.environ.get("QWEN_MODEL", DEFAULT_QWEN_MODEL),
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
    parser.add_argument("passthrough", nargs="*", help="Extra args forwarded to each stage script.")
    args = parser.parse_args()

    ensure_qwen_env()

    if args.dry_run:
        dry_run_report()
        return

    stages = stage_range(args.from_stage, args.to_stage)
    if not stages:
        print("No stages selected.")
        return

    gate_map = {
        "1": None,
        "2": "math_bible",
        "3": "screenplay",
        "3b": "series_bible",
        "4": "reference_bank",
        "4b": "storyboard",
        "5a": "storyboard",
        "5b": "math_bible",
        "6": "storyboard",
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

        print(f"\n=== Stage {stage.id}: {stage.name} ===")
        update_state(current_stage=stage.id, status="running")
        rc = run_script(stage.script, script_args_for_stage(stage.id, args.passthrough))
        if rc != 0:
            update_state(current_stage=stage.id, status="failed", notes=f"exit code {rc}")
            sys.exit(rc)
        update_state(current_stage=stage.id, status="completed")

    update_state(current_stage=args.to_stage, status="done")
    print("\nPipeline run complete.")


if __name__ == "__main__":
    main()
