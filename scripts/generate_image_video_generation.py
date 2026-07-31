#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template, run_gemma_json_generation
from paths import PROJECT_ROOT, output_dir

SUB_MODULE = "image_video_generation"
DEFAULT_PROBLEM_STATEMENT = (
    PROJECT_ROOT / "output" / "problem_statement_buildup" / "problem_statement_buildup.json"
)
DEFAULT_MATH_LINKUP = PROJECT_ROOT / "output" / "ps_math_linkup" / "ps_math_linkup.json"
DEFAULT_REFERENCE = PROJECT_ROOT / "samples" / "image_video_generation.json"
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "image_video_generation.md"
DEFAULT_MODEL = PROJECT_ROOT / "gemma4_model"
DEFAULT_OUTPUT_FILE = "image_video_generation.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "story_title",
    "tone_target",
    "total_runtime_target",
    "visual_style_bible",
    "scenes",
}

REQUIRED_BIBLE_KEYS = {"cast", "sets", "camera_grammar", "grade", "golden_rule"}
REQUIRED_SCENE_KEYS = {
    "scene_id",
    "chapter",
    "chapter_subtitle",
    "title",
    "render_type",
    "topic_ids",
    "time_start",
    "duration_seconds",
    "cumulative_time",
    "beat",
    "shots",
}
REQUIRED_SHOT_KEYS = {
    "shot",
    "time",
    "duration_seconds",
    "type",
    "flux_frame",
    "wan_motion",
    "dialogue",
}


def validate_output(data: dict) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS - data.keys()
    if missing:
        raise ValueError(f"Missing required top-level keys: {sorted(missing)}")

    bible = data["visual_style_bible"]
    if not isinstance(bible, dict):
        raise ValueError("'visual_style_bible' must be an object")
    missing_bible = REQUIRED_BIBLE_KEYS - bible.keys()
    if missing_bible:
        raise ValueError(f"'visual_style_bible' missing keys: {sorted(missing_bible)}")

    scenes = data["scenes"]
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("'scenes' must be a non-empty list")

    for scene in scenes:
        missing_scene = REQUIRED_SCENE_KEYS - scene.keys()
        if missing_scene:
            raise ValueError(f"Scene {scene.get('scene_id', '?')} missing keys: {sorted(missing_scene)}")
        if not isinstance(scene["shots"], list) or not scene["shots"]:
            raise ValueError(f"Scene {scene['scene_id']} must have at least one shot")
        for shot in scene["shots"]:
            missing_shot = REQUIRED_SHOT_KEYS - shot.keys()
            if missing_shot:
                raise ValueError(
                    f"Shot {shot.get('shot', '?')} in {scene['scene_id']} missing keys: {sorted(missing_shot)}"
                )


def generate(
    problem_statement_path: Path,
    math_linkup_path: Path,
    reference_path: Path,
    prompt_path: Path,
    model_path: Path,
    max_new_tokens: int,
    enable_thinking: bool,
) -> dict:
    problem_statement = problem_statement_path.read_text(encoding="utf-8")
    math_linkup = math_linkup_path.read_text(encoding="utf-8")
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        problem_statement_buildup=problem_statement,
        ps_math_linkup=math_linkup,
        reference_output=reference_output,
    )

    return run_gemma_json_generation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        enable_thinking=enable_thinking,
        validate=validate_output,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate image_video_generation JSON (shot decomposition) using Gemma 4."
    )
    parser.add_argument("--problem-statement", type=Path, default=DEFAULT_PROBLEM_STATEMENT)
    parser.add_argument("--math-linkup", type=Path, default=DEFAULT_MATH_LINKUP)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--output-file",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Filename written inside output/{SUB_MODULE}/",
    )
    parser.add_argument("--max-new-tokens", type=int, default=16384)
    parser.add_argument("--disable-thinking", action="store_true")
    args = parser.parse_args()

    enable_thinking = not args.disable_thinking
    out_dir = output_dir(SUB_MODULE)
    out_path = out_dir / args.output_file

    result = generate(
        problem_statement_path=args.problem_statement,
        math_linkup_path=args.math_linkup,
        reference_path=args.reference,
        prompt_path=args.prompt,
        model_path=args.model_path,
        max_new_tokens=args.max_new_tokens,
        enable_thinking=enable_thinking,
    )

    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
