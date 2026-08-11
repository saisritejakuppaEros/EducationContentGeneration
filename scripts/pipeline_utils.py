#!/usr/bin/env python3
"""Shared helpers for the chapter-to-movie pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from gemma_utils import load_gemma_model, run_gemma_json_with_model
from paths import DEFAULT_GEMMA_MODEL, DEFAULT_LLM_BACKEND, PROJECT_ROOT, output_dir

PIPELINE_SUB_MODULE = "pipeline"


@dataclass(frozen=True)
class Stage:
    id: str
    name: str
    script: str
    primary_output: str
    gate: str  # "none" | "qwen" | "gemma" | "manual"


STAGES: tuple[Stage, ...] = (
    Stage("0", "pipeline", "run_pipeline.py", "output/pipeline/state.json", "none"),
    Stage("1", "math_bible", "generate_math_bible.py", "output/math_bible/math_bible.json", "qwen"),
    Stage("2", "screenplay", "generate_screenplay.py", "output/screenplay/screenplay.json", "qwen"),
    Stage("3", "series_bible", "generate_series_bible.py", "output/series_bible/series_bible.json", "manual"),
    Stage("3b", "reference_bank", "build_reference_bank.py", "output/series_bible/reference_photos/", "manual"),
    Stage("4", "storyboard", "generate_storyboard.py", "output/storyboard/storyboard.json", "qwen"),
    Stage("4b", "storyboard_keyframes", "generate_storyboard_keyframes.py", "output/storyboard/", "manual"),
    Stage("5a", "cinematic_videos", "generate_cinematic_videos.py", "output/cinematic_videos/manifest.json", "manual"),
    Stage("5b", "manim_videos", "generate_manim_videos.py", "output/manim_videos/manifest.json", "manual"),
    Stage("6", "audio", "generate_audio.py", "output/audio/audio_plan.json", "manual"),
    Stage("7", "final_cut", "assemble_final_cut.py", "output/final_cut/", "manual"),
)


def stage_by_id(stage_id: str) -> Stage | None:
    for stage in STAGES:
        if stage.id == stage_id:
            return stage
    return None


def gate_path(stage_name: str) -> Path:
    return output_dir(PIPELINE_SUB_MODULE) / "gates" / f"{stage_name}.json"


def write_gate(stage_name: str, *, passed: bool, notes: str = "", details: dict | None = None) -> Path:
    path = gate_path(stage_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage_name,
        "passed": passed,
        "notes": notes,
        "details": details or {},
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def read_gate(stage_name: str) -> dict | None:
    path = gate_path(stage_name)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def gate_passed(stage_name: str) -> bool:
    gate = read_gate(stage_name)
    return bool(gate and gate.get("passed"))


def run_llm_json(
    *,
    backend: str = DEFAULT_LLM_BACKEND,
    system_prompt: str,
    user_prompt: str,
    validate: Callable[[dict], None],
    model_path: Path = DEFAULT_GEMMA_MODEL,
    max_new_tokens: int = 8192,
    max_tokens: int = 8192,
    temperature: float = 0.6,
    enable_thinking: bool = False,
    qwen_model: str | None = None,
) -> dict:
    if backend == "gemma":
        processor, model = load_gemma_model(model_path)
        return run_gemma_json_with_model(
            processor=processor,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
            validate=validate,
        )
    if backend == "qwen":
        from qwen_utils import run_qwen_json

        return run_qwen_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=qwen_model,
            max_tokens=max_tokens,
            temperature=temperature,
            validate=validate,
        )
    raise ValueError(f"Unknown backend: {backend}. Use 'gemma' or 'qwen'.")


def run_script(script_name: str, extra_args: list[str] | None = None) -> int:
    script_path = PROJECT_ROOT / "scripts" / script_name
    if not script_path.is_file():
        raise FileNotFoundError(f"Pipeline script not found: {script_path}")
    cmd = [sys.executable, str(script_path), *(extra_args or [])]
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)
