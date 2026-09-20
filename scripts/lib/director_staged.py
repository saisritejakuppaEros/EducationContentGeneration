"""Multi-pass director: story → scene batches → media cues (reliable JSON with Qwen)."""

from __future__ import annotations

import json
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import PROMPTS_DIR
from pipeline_utils import run_llm_json

PHASE1 = PROMPTS_DIR / "directing_phase1_story.md"
PHASE2 = PROMPTS_DIR / "directing_phase2_scenes.md"
PHASE3 = PROMPTS_DIR / "directing_phase3_media.md"

BATCH_SIZE = 14


def scene_budget(runtime_seconds: int) -> dict[str, str | int]:
    """Conservative scene count so each LLM call stays small."""
    max_scenes = max(20, min(28, runtime_seconds // 16))
    min_scenes = max(18, max_scenes - 4)
    image_max = max(10, min(18, max_scenes // 2))
    return {
        "scene_count_min": min_scenes,
        "scene_count_max": max_scenes,
        "scene_seconds_avg": round(runtime_seconds / max_scenes, 1),
        "image_prompt_max": image_max,
    }


def _validate_core(data: dict) -> None:
    for key in ("title", "chapter", "beat_sheet", "script", "runtime_target_seconds"):
        if key not in data:
            raise ValueError(f"phase1 missing '{key}'")
    if not data.get("beat_sheet") or not data.get("script"):
        raise ValueError("phase1 beat_sheet and script required")


def _validate_scene_batch(data: dict, expected: int) -> None:
    if "scene_table" not in data or not isinstance(data["scene_table"], list):
        raise ValueError("phase2 must return scene_table list")
    rows = data["scene_table"]
    if len(rows) < max(1, expected - 2):
        raise ValueError(f"phase2 expected ~{expected} scenes, got {len(rows)}")
    for row in rows:
        for key in ("scene_id", "time_start", "duration_seconds", "visual_mode", "vo_excerpt"):
            if key not in row:
                raise ValueError(f"scene missing {key}")


def _validate_media(data: dict) -> None:
    if "audio_cue_sheet" not in data or not isinstance(data["audio_cue_sheet"], list):
        raise ValueError("phase3 needs audio_cue_sheet")
    if "image_prompts" not in data or not isinstance(data["image_prompts"], list):
        raise ValueError("phase3 needs image_prompts")


def _scene_id(n: int) -> str:
    return f"S{n:02d}"


def generate_staged(
    *,
    chapter_text: str,
    runtime_seconds: int,
    backend: str,
    model_path: Path,
    max_tokens: int,
    out_dir: Path | None = None,
) -> dict:
    budget = scene_budget(runtime_seconds)
    max_scenes = int(budget["scene_count_max"])
    runtime_minutes = round(runtime_seconds / 60, 1)

    english_rule = (
        "OUTPUT LANGUAGE: English only for all narration, labels, titles, and prompts. "
        "Translate source material; do not use Assamese or other non-English scripts in JSON string values.\n\n"
    )

    print(f"Director staged: {max_scenes} scenes in batches of {BATCH_SIZE} …")

    sys1, user1 = load_prompt_template(PHASE1)
    sys1 = english_rule + sys1
    core = run_llm_json(
        backend=backend,
        system_prompt=sys1,
        user_prompt=fill_user_prompt(
            user1,
            chapter_text=chapter_text,
            runtime_seconds=str(runtime_seconds),
            runtime_minutes=str(runtime_minutes),
        ),
        validate=_validate_core,
        model_path=model_path,
        max_tokens=min(max_tokens, 8192),
        json_retries=3,
    )
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "phase1_core.json").write_text(json.dumps(core, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    sys2, user2 = load_prompt_template(PHASE2)
    sys2 = english_rule + sys2
    beat_json = json.dumps(core.get("beat_sheet", []), ensure_ascii=False)
    script_json = json.dumps(core.get("script", []), ensure_ascii=False)

    all_scenes: list[dict] = []
    scene_num = 1
    while scene_num <= max_scenes:
        batch_count = min(BATCH_SIZE, max_scenes - scene_num + 1)
        batch_start_id = _scene_id(scene_num)
        batch_end_id = _scene_id(scene_num + batch_count - 1)
        batch_seconds = int(round(runtime_seconds * batch_count / max_scenes))
        continuation = ""
        if all_scenes:
            last = all_scenes[-1]
            continuation = (
                f"Continue immediately after scene {last.get('scene_id')} "
                f"(ended ~{last.get('time_start')} + {last.get('duration_seconds')}s)."
            )

        def validate_batch(data: dict, *, expected=batch_count) -> None:
            _validate_scene_batch(data, expected)

        batch = run_llm_json(
            backend=backend,
            system_prompt=sys2,
            user_prompt=fill_user_prompt(
                user2,
                runtime_seconds=str(runtime_seconds),
                batch_start_id=batch_start_id,
                batch_end_id=batch_end_id,
                batch_count=str(batch_count),
                batch_seconds=str(batch_seconds),
                beat_sheet_json=beat_json,
                script_json=script_json,
                continuation_note=continuation,
            ),
            validate=validate_batch,
            model_path=model_path,
            max_tokens=min(max_tokens, 8192),
            json_retries=3,
        )
        rows = batch["scene_table"]
        for i, row in enumerate(rows):
            row["scene_id"] = _scene_id(scene_num + i)
        all_scenes.extend(rows)
        scene_num += batch_count

    if out_dir:
        (out_dir / "phase2_scenes.json").write_text(
            json.dumps({"scene_table": all_scenes}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    scene_summary = [
        {
            "scene_id": s.get("scene_id"),
            "visual_mode": s.get("visual_mode"),
            "anchor_present": s.get("anchor_present"),
            "on_screen_text": s.get("on_screen_text"),
            "duration_seconds": s.get("duration_seconds"),
        }
        for s in all_scenes
    ]

    sys3, user3 = load_prompt_template(PHASE3)
    sys3 = english_rule + sys3
    media = run_llm_json(
        backend=backend,
        system_prompt=sys3,
        user_prompt=fill_user_prompt(
            user3,
            title=core.get("recommended_title") or core.get("title", ""),
            style_guide_excerpt=(core.get("style_guide") or "")[:800],
            scene_summary_json=json.dumps(scene_summary, ensure_ascii=False),
            image_prompt_max=str(budget["image_prompt_max"]),
        ),
        validate=_validate_media,
        model_path=model_path,
        max_tokens=min(max_tokens, 6144),
        json_retries=3,
    )

    package = {
        **core,
        "runtime_target_seconds": runtime_seconds,
        "scene_table": all_scenes,
        "image_prompts": media.get("image_prompts", []),
        "audio_cue_sheet": media.get("audio_cue_sheet", []),
    }
    if out_dir:
        (out_dir / "phase3_media.json").write_text(json.dumps(media, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return package
