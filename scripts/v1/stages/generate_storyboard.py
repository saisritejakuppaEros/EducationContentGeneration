#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
from pathlib import Path

from dialogue_utils import split_storyboard_shots
from gemma_utils import fill_user_prompt, load_prompt_template
from paths import (
    DEFAULT_LLM_BACKEND,
    PROMPTS_DIR,
    SAMPLES_DIR,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
    resolve_topic_specs_json,
)
from pipeline_utils import run_llm_json, write_gate, write_json

SUB_MODULE = "storyboard"
DEFAULT_SERIES_PROFILE = output_dir("series_profile") / "series_profile.json"
DEFAULT_REFERENCE = SAMPLES_DIR / "storyboard.json"
DEFAULT_PROMPT = PROMPTS_DIR / "storyboard.md"

REQUIRED_SHOT_KEYS = {
    "shot",
    "type",
    "lens_mm",
    "subject_scale_pct",
    "camera_move",
    "characters_in_frame",
    "reference_tags_used",
    "environment_detail",
    "blocking",
    "dialogue",
    "duration_seconds",
    "flux_prompt",
}


def validate_scene_shots(data: dict) -> None:
    if "scene_id" not in data or "shots" not in data:
        raise ValueError("Scene response must have scene_id and shots")
    shots = data["shots"]
    if not isinstance(shots, list) or not shots:
        raise ValueError("shots must be a non-empty list")
    for shot in shots:
        missing = REQUIRED_SHOT_KEYS - shot.keys()
        if missing:
            raise ValueError(f"Shot {shot.get('shot', '?')} missing keys: {sorted(missing)}")


def validate_storyboard(data: dict) -> None:
    if "scenes" not in data:
        raise ValueError("storyboard must have scenes")
    if not isinstance(data["scenes"], list) or not data["scenes"]:
        raise ValueError("scenes must be a non-empty list")


def gate_check_wide_coverage(storyboard: dict) -> tuple[bool, str]:
    failures: list[str] = []
    for scene in storyboard.get("scenes", []):
        scene_id = scene.get("scene_id", "?")
        shots = scene.get("shots") or []
        if not shots:
            failures.append(f"{scene_id}: no shots")
            continue
        has_wide = any(
            (s.get("type") or "").upper() in {"WIDE", "EXTREME WIDE"}
            and (s.get("subject_scale_pct") or 100) <= 30
            for s in shots
        )
        if not has_wide:
            failures.append(f"{scene_id}: missing true WIDE (subject_scale_pct <= 30)")
    if failures:
        return False, "; ".join(failures)
    return True, "Wide coverage rule satisfied"


def build_visual_style_guide(series_profile: dict) -> dict:
    return {
        "cast": series_profile.get("cast", {}),
        "sets": series_profile.get("world", {}).get("sets", []),
        "camera_grammar": series_profile.get("visual_grammar", {}).get("camera_rules", []),
        "grade": series_profile.get("visual_grammar", {}).get("grade", ""),
        "golden_rule": series_profile.get("visual_grammar", {}).get(
            "screen_direction_rules", "One speaking character per shot"
        ),
    }


def generate_scene_shots(
    *,
    scene: dict,
    series_profile: dict,
    previous_last_shot: str,
    next_scene_first_beat: str,
    reference_path: Path,
    prompt_path: Path,
    backend: str,
    model_path: Path,
    max_new_tokens: int,
    max_tokens: int,
    enable_thinking: bool,
) -> dict:
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        scene_json=json.dumps(scene, indent=2, ensure_ascii=False),
        series_profile=json.dumps(series_profile, indent=2, ensure_ascii=False),
        previous_last_shot=previous_last_shot or "None — first scene",
        next_scene_first_beat=next_scene_first_beat or "None — last scene",
        reference_output=reference_output,
    )
    result = run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        validate=validate_scene_shots,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        max_tokens=max_tokens,
        enable_thinking=enable_thinking,
    )
    result["scene_id"] = scene["scene_id"]
    return result


def attach_keyframe_paths(scene_payload: dict, out_dir: Path) -> dict:
    from paths import PROJECT_ROOT

    scene_id = scene_payload["scene_id"]
    for shot in scene_payload.get("shots", []):
        shot_num = shot["shot"]
        rel = out_dir / scene_id / f"{scene_id}_shot{shot_num:02d}.png"
        shot["keyframe_image"] = str(rel.relative_to(PROJECT_ROOT)).replace("\\", "/")
        shot["qc_status"] = shot.get("qc_status", "pending")
    return scene_payload


def generate(
    *,
    screenplay_path: Path,
    series_profile_path: Path,
    topic_specs_path: Path,
    reference_path: Path,
    prompt_path: Path,
    scene_ids: list[str] | None,
    backend: str,
    model_path: Path,
    max_new_tokens: int,
    max_tokens: int,
    enable_thinking: bool,
    skip_gate: bool,
) -> dict:
    screenplay = json.loads(screenplay_path.read_text(encoding="utf-8"))
    series_profile = json.loads(series_profile_path.read_text(encoding="utf-8"))
    topic_specs = json.loads(topic_specs_path.read_text(encoding="utf-8")) if topic_specs_path.is_file() else {}

    scenes_in = screenplay.get("scenes", [])
    if scene_ids:
        scenes_in = [s for s in scenes_in if s["scene_id"] in scene_ids]

    storyboard_scenes: list[dict] = []
    previous_last_shot = ""

    for idx, scene in enumerate(scenes_in):
        next_beat = ""
        if idx + 1 < len(scenes_in):
            next_beat = scenes_in[idx + 1].get("action", "")

        scene_payload = generate_scene_shots(
            scene=scene,
            series_profile=series_profile,
            previous_last_shot=previous_last_shot,
            next_scene_first_beat=next_beat,
            reference_path=reference_path,
            prompt_path=prompt_path,
            backend=backend,
            model_path=model_path,
            max_new_tokens=max_new_tokens,
            max_tokens=max_tokens,
            enable_thinking=enable_thinking,
        )
        if scene_payload.get("shots"):
            scene_payload["shots"] = split_storyboard_shots(scene_payload["shots"])

        if scene_payload.get("shots"):
            last = scene_payload["shots"][-1]
            previous_last_shot = json.dumps(
                {
                    "type": last.get("type"),
                    "blocking": last.get("blocking"),
                    "camera_move": last.get("camera_move"),
                },
                ensure_ascii=False,
            )

        storyboard_scenes.append(
            {
                "scene_id": scene["scene_id"],
                "screenplay_type": scene.get("type"),
                "topic_ids": scene.get("topic_ids", []),
                "title": scene.get("location", scene["scene_id"]),
                "duration_seconds": scene.get("target_duration_seconds"),
                "shots": scene_payload.get("shots", []),
            }
        )

    total_seconds = sum(s.get("duration_seconds") or 0 for s in storyboard_scenes)
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)

    storyboard = {
        "chapter": screenplay.get("chapter") or topic_specs.get("chapter", ""),
        "tone_target": series_profile.get("target_tone", ""),
        "total_runtime_target": f"{minutes}:{seconds:02d}",
        "visual_style_guide": build_visual_style_guide(series_profile),
        "scenes": storyboard_scenes,
    }

    out_dir = output_dir(SUB_MODULE)
    for scene in storyboard["scenes"]:
        attach_keyframe_paths(scene, out_dir)

    validate_storyboard(storyboard)

    if skip_gate:
        write_gate(SUB_MODULE, passed=True, notes="Gate skipped via --skip-gate")
    else:
        passed, notes = gate_check_wide_coverage(storyboard)
        write_gate(SUB_MODULE, passed=passed, notes=notes)
        print(f"Gate {'PASSED' if passed else 'FAILED'}: {notes}")

    return storyboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate storyboard.json from screenplay.")
    parser.add_argument("--screenplay", type=Path, default=None)
    parser.add_argument("--series-profile", type=Path, default=DEFAULT_SERIES_PROFILE)
    parser.add_argument("--topic-specs", type=Path, default=None)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--scene", action="append", dest="scene_ids")
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--disable-thinking", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    parser.add_argument(
        "--fix-dialogue",
        action="store_true",
        help="Split long dialogue in an existing storyboard.json (no LLM).",
    )
    add_output_root_argument(parser)
    args = parser.parse_args()

    from paths import DEFAULT_GEMMA_MODEL

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    screenplay_path = args.screenplay or (output_dir("screenplay") / "screenplay.json")
    topic_specs_path = resolve_topic_specs_json(args.topic_specs)

    out_path = output_dir(SUB_MODULE) / "storyboard.json"

    if args.fix_dialogue:
        if not out_path.is_file():
            raise FileNotFoundError(f"storyboard not found: {out_path}")
        storyboard = json.loads(out_path.read_text(encoding="utf-8"))
        out_dir = output_dir(SUB_MODULE)
        for scene in storyboard.get("scenes", []):
            scene["shots"] = split_storyboard_shots(scene.get("shots", []))
            attach_keyframe_paths(scene, out_dir)
        write_json(out_path, storyboard)
        print(f"Fixed dialogue splits in {out_path}")
        return

    for path in (screenplay_path, args.series_profile):
        if not path.is_file():
            raise FileNotFoundError(f"Required input not found: {path}")

    model_path = args.model_path or DEFAULT_GEMMA_MODEL

    result = generate(
        screenplay_path=screenplay_path,
        series_profile_path=args.series_profile,
        topic_specs_path=topic_specs_path,
        reference_path=args.reference,
        prompt_path=args.prompt,
        scene_ids=args.scene_ids,
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
