#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path

from gemma_utils import (
    fill_user_prompt,
    load_gemma_model,
    load_prompt_template,
    run_gemma_json_with_model,
)
from paths import PROJECT_ROOT, output_dir

SUB_MODULE = "flux_prompts"
DEFAULT_INPUT = PROJECT_ROOT / "output" / "image_video_generation" / "image_video_generation.json"
DEFAULT_REFERENCE = PROJECT_ROOT / "samples" / "flux_prompts.json"
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "flux_prompt_enhancement.md"
DEFAULT_MODEL = PROJECT_ROOT / "gemma4_model"
DEFAULT_OUTPUT_FILE = "flux_prompts.json"


def validate_scene_response(data: dict, scene: dict) -> None:
    if data.get("scene_id") != scene["scene_id"]:
        raise ValueError(
            f"Expected scene_id {scene['scene_id']}, got {data.get('scene_id')}"
        )

    shots = data.get("shots")
    if not isinstance(shots, list) or len(shots) != len(scene["shots"]):
        raise ValueError(
            f"Scene {scene['scene_id']}: expected {len(scene['shots'])} shots, got {len(shots or [])}"
        )

    expected_numbers = {s["shot"] for s in scene["shots"]}
    returned_numbers = {s.get("shot") for s in shots}
    if expected_numbers != returned_numbers:
        raise ValueError(
            f"Scene {scene['scene_id']}: shot number mismatch {expected_numbers} vs {returned_numbers}"
        )

    for shot in shots:
        if not shot.get("flux_prompt"):
            raise ValueError(f"Scene {scene['scene_id']} shot {shot.get('shot')}: missing flux_prompt")
        structured = shot.get("flux_prompt_structured")
        if not isinstance(structured, dict):
            raise ValueError(
                f"Scene {scene['scene_id']} shot {shot.get('shot')}: missing flux_prompt_structured"
            )
        for key in (
            "subject",
            "action",
            "environment",
            "lighting",
            "camera",
            "lens",
            "composition",
            "color_grade",
            "mood",
            "style_reference",
        ):
            if key not in structured:
                raise ValueError(
                    f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                    f"flux_prompt_structured missing '{key}'"
                )


def merge_enhancements(scene: dict, enhanced: dict) -> list[dict]:
    enhancement_by_shot = {s["shot"]: s for s in enhanced["shots"]}
    merged_shots = []
    for shot in scene["shots"]:
        merged = copy.deepcopy(shot)
        extra = enhancement_by_shot[shot["shot"]]
        merged["flux_prompt"] = extra["flux_prompt"]
        merged["flux_prompt_structured"] = extra["flux_prompt_structured"]
        merged_shots.append(merged)
    return merged_shots


def enhance_scene(
    *,
    scene: dict,
    visual_style_bible: dict,
    tone_target: str,
    system_prompt: str,
    user_template: str,
    reference_output: str,
    processor,
    model,
    max_new_tokens: int,
    enable_thinking: bool,
) -> list[dict]:
    scene_payload = {
        "scene_id": scene["scene_id"],
        "chapter": scene["chapter"],
        "chapter_subtitle": scene.get("chapter_subtitle"),
        "title": scene.get("title"),
        "render_type": scene["render_type"],
        "beat": scene["beat"],
        "shots": scene["shots"],
    }

    user_prompt = fill_user_prompt(
        user_template,
        visual_style_bible=json.dumps(visual_style_bible, indent=2),
        tone_target=tone_target,
        scene_json=json.dumps(scene_payload, indent=2),
        reference_output=reference_output,
    )

    def validate(data: dict) -> None:
        validate_scene_response(data, scene)

    enhanced = run_gemma_json_with_model(
        processor=processor,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_new_tokens=max_new_tokens,
        enable_thinking=enable_thinking,
        validate=validate,
    )
    return merge_enhancements(scene, enhanced)


def generate(
    input_path: Path,
    reference_path: Path,
    prompt_path: Path,
    model_path: Path,
    max_new_tokens: int,
    enable_thinking: bool,
    scene_ids: list[str] | None = None,
) -> dict:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)

    processor, model = load_gemma_model(model_path)

    output = {
        "story_title": source["story_title"],
        "source": str(input_path.relative_to(PROJECT_ROOT)),
        "model_target": "flux-2",
        "prompt_framework": "SASC — Subject, Action, Style, Context",
        "tone_target": source.get("tone_target", ""),
        "visual_style_bible": source["visual_style_bible"],
        "scenes": [],
    }

    scenes = source["scenes"]
    if scene_ids:
        scenes = [s for s in scenes if s["scene_id"] in scene_ids]
        if not scenes:
            raise ValueError(f"No scenes matched: {scene_ids}")

    for scene in scenes:
        print(f"Enhancing {scene['scene_id']} ({len(scene['shots'])} shots)...")
        merged_shots = enhance_scene(
            scene=scene,
            visual_style_bible=source["visual_style_bible"],
            tone_target=source.get("tone_target", ""),
            system_prompt=system_prompt,
            user_template=user_template,
            reference_output=reference_output,
            processor=processor,
            model=model,
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
        )
        output["scenes"].append(
            {
                "scene_id": scene["scene_id"],
                "chapter": scene["chapter"],
                "chapter_subtitle": scene.get("chapter_subtitle"),
                "title": scene.get("title"),
                "render_type": scene["render_type"],
                "topic_ids": scene.get("topic_ids", []),
                "time_start": scene.get("time_start"),
                "duration_seconds": scene.get("duration_seconds"),
                "cumulative_time": scene.get("cumulative_time"),
                "beat": scene.get("beat"),
                "shots": merged_shots,
            }
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enhance flux_frame descriptions into Flux 2.0 production prompts."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Filename written inside output/{SUB_MODULE}/",
    )
    parser.add_argument(
        "--scene",
        action="append",
        dest="scene_ids",
        help="Process only these scene ids (e.g. S0 S1). Repeatable.",
    )
    parser.add_argument("--max-new-tokens", type=int, default=4096)
    parser.add_argument("--disable-thinking", action="store_true")
    args = parser.parse_args()

    enable_thinking = not args.disable_thinking
    out_dir = output_dir(SUB_MODULE)
    out_path = out_dir / args.output_file

    result = generate(
        input_path=args.input,
        reference_path=args.reference,
        prompt_path=args.prompt,
        model_path=args.model_path,
        max_new_tokens=args.max_new_tokens,
        enable_thinking=enable_thinking,
        scene_ids=args.scene_ids,
    )

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    total_shots = sum(len(s["shots"]) for s in result["scenes"])
    print(f"Wrote {out_path} ({len(result['scenes'])} scenes, {total_shots} enhanced shots)")


if __name__ == "__main__":
    main()
