#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import copy
import json
import re
from pathlib import Path

from gemma_utils import (
    fill_user_prompt,
    load_gemma_model,
    load_prompt_template,
    run_gemma_json_with_model,
)
from paths import PROJECT_ROOT, output_dir
from qwen_utils import DEFAULT_API_BASE, DEFAULT_MODEL, run_qwen_json

SUB_MODULE = "ltx_prompts"
DEFAULT_INPUT = PROJECT_ROOT / "output" / "flux_prompts" / "flux_prompts.json"
DEFAULT_REFERENCE = PROJECT_ROOT / "samples" / "ltx_prompts.json"
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "ltx_prompt_enhancement.md"
DEFAULT_GEMMA_MODEL = PROJECT_ROOT / "gemma4_model"
DEFAULT_OUTPUT_FILE = "ltx_prompts.json"
DEFAULT_FLUX_IMAGES = PROJECT_ROOT / "output" / "flux_images"

DEFAULT_NEGATIVE = (
    "music, silent or muted audio, distorted voice, off-sync lips, "
    "background music, washed out contrast, deformed facial features, "
    "out of focus face, unnatural skin tones"
)

HUMAN_SHOT_TYPES = {
    "INT WIDE",
    "WIDE",
    "OTS Y→M",
    "OTS Y→F",
    "TWO-SHOT",
    "REACTION",
    "Y-POV",
}


def parse_speaker(dialogue: str | None) -> str | None:
    if not dialogue:
        return None
    match = re.match(r"^([MFY]):\s*", dialogue.strip())
    return match.group(1) if match else None


def extract_speech(dialogue: str | None) -> str | None:
    if not dialogue:
        return None
    match = re.match(r"^[MFY]:\s*\"(.+)\"$", dialogue.strip())
    if match:
        return match.group(1)
    match = re.match(r"^[MFY]:\s*(.+)$", dialogue.strip())
    return match.group(1).strip('"') if match else None


def infer_ltx_mode(shot: dict) -> str:
    shot_type = (shot.get("type") or "").upper()
    if shot_type == "MATH INSERT":
        return "skip"
    if shot.get("dialogue") and parse_speaker(shot.get("dialogue")):
        if shot_type in HUMAN_SHOT_TYPES:
            return "talking_head"
    return "cinematic"


def flux_image_path(scene_id: str, shot_number: int, flux_images_dir: Path) -> str:
    rel = flux_images_dir.relative_to(PROJECT_ROOT)
    return str(rel / scene_id / f"{scene_id}_shot{shot_number:02d}.png")


def build_ltx_prompt(structured: dict, *, mode: str) -> str | None:
    if mode == "skip":
        return None
    visual = (structured.get("visual") or "").strip()
    speech = (structured.get("speech") or "").strip()
    sounds = (structured.get("sounds") or "").strip()
    if not visual or not sounds:
        return None
    parts = [f"[VISUAL]:{visual}"]
    if mode == "talking_head" and speech:
        parts.append(f"[SPEECH]:{speech}")
    parts.append(f"[SOUNDS]:{sounds}")
    return " ".join(parts)


def normalize_scene_response(data: dict, scene: dict) -> dict:
    scene_id = scene["scene_id"]

    if data.get("scene_id") == scene_id and isinstance(data.get("shots"), list):
        return data

    scenes = data.get("scenes")
    if isinstance(scenes, list):
        for entry in scenes:
            if entry.get("scene_id") == scene_id and isinstance(entry.get("shots"), list):
                return {"scene_id": scene_id, "shots": entry["shots"]}

    shots = data.get("shots")
    if isinstance(shots, list):
        return {"scene_id": scene_id, "shots": shots}

    raise ValueError(
        f"Could not find scene {scene_id} in model output keys: {sorted(data.keys())}"
    )


def validate_scene_response(data: dict, scene: dict) -> None:
    if data.get("scene_id") != scene["scene_id"]:
        raise ValueError(
            f"Expected scene_id {scene['scene_id']}, got {data.get('scene_id')}"
        )

    shots = data.get("shots")
    if not isinstance(shots, list) or len(shots) != len(scene["shots"]):
        raise ValueError(
            f"Scene {scene['scene_id']}: expected {len(scene['shots'])} shots, "
            f"got {len(shots or [])}"
        )

    expected_numbers = {s["shot"] for s in scene["shots"]}
    returned_numbers = {s.get("shot") for s in shots}
    if expected_numbers != returned_numbers:
        raise ValueError(
            f"Scene {scene['scene_id']}: shot number mismatch "
            f"{expected_numbers} vs {returned_numbers}"
        )

    for shot, source_shot in zip(shots, scene["shots"], strict=True):
        mode = shot.get("ltx_mode")
        if mode not in {"talking_head", "cinematic", "skip"}:
            raise ValueError(
                f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                f"invalid ltx_mode {mode!r}"
            )

        if "use_talking_head_lora" not in shot:
            raise ValueError(
                f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                "missing use_talking_head_lora"
            )

        structured = shot.get("ltx_prompt_structured")
        if not isinstance(structured, dict):
            raise ValueError(
                f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                "missing ltx_prompt_structured"
            )

        if mode == "skip":
            continue

        for key in ("visual", "sounds"):
            if not structured.get(key):
                raise ValueError(
                    f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                    f"ltx_prompt_structured missing '{key}'"
                )

        if mode == "talking_head":
            if not structured.get("speech"):
                raise ValueError(
                    f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                    "talking_head mode requires speech"
                )
            if not shot.get("ltx_prompt"):
                raise ValueError(
                    f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                    "missing ltx_prompt"
                )

        if source_shot.get("dialogue") and mode == "talking_head":
            expected_speaker = parse_speaker(source_shot["dialogue"])
            if shot.get("speaker") != expected_speaker:
                raise ValueError(
                    f"Scene {scene['scene_id']} shot {shot.get('shot')}: "
                    f"speaker mismatch expected {expected_speaker}, "
                    f"got {shot.get('speaker')}"
                )


def merge_enhancements(
    scene: dict,
    enhanced: dict,
    *,
    flux_images_dir: Path,
) -> list[dict]:
    enhancement_by_shot = {s["shot"]: s for s in enhanced["shots"]}
    merged_shots = []
    for shot in scene["shots"]:
        merged = copy.deepcopy(shot)
        extra = enhancement_by_shot[shot["shot"]]
        mode = extra.get("ltx_mode") or infer_ltx_mode(shot)

        merged["ltx_mode"] = mode
        merged["use_talking_head_lora"] = bool(extra.get("use_talking_head_lora"))
        merged["speaker"] = extra.get("speaker") or parse_speaker(shot.get("dialogue"))
        merged["motion_summary"] = extra.get("motion_summary") or shot.get("wan_motion")
        merged["init_image"] = flux_image_path(
            scene["scene_id"], shot["shot"], flux_images_dir
        )

        structured = extra.get("ltx_prompt_structured") or {}
        merged["ltx_prompt_structured"] = structured
        merged["ltx_prompt"] = extra.get("ltx_prompt") or build_ltx_prompt(
            structured, mode=mode
        )
        merged["negative_prompt"] = (
            None if mode == "skip" else extra.get("negative_prompt") or DEFAULT_NEGATIVE
        )
        merged_shots.append(merged)
    return merged_shots


def enhance_scene(
    *,
    scene: dict,
    visual_style_guide: dict,
    tone_target: str,
    system_prompt: str,
    user_template: str,
    reference_output: str,
    backend: str,
    processor,
    model,
    qwen_model: str,
    api_base: str,
    max_new_tokens: int,
    temperature: float,
    enable_thinking: bool,
    flux_images_dir: Path,
) -> list[dict]:
    scene_payload = {
        "scene_id": scene["scene_id"],
        "chapter": scene["chapter"],
        "chapter_subtitle": scene.get("chapter_subtitle"),
        "title": scene.get("title"),
        "render_type": scene["render_type"],
        "beat": scene["beat"],
        "shots": [
            {
                "shot": s["shot"],
                "time": s.get("time"),
                "duration_seconds": s.get("duration_seconds"),
                "type": s.get("type"),
                "flux_frame": s.get("flux_frame"),
                "wan_motion": s.get("wan_motion"),
                "dialogue": s.get("dialogue"),
                "flux_prompt": s.get("flux_prompt"),
                "flux_prompt_structured": s.get("flux_prompt_structured"),
            }
            for s in scene["shots"]
        ],
    }

    user_prompt = fill_user_prompt(
        user_template,
        visual_style_guide=json.dumps(visual_style_guide, indent=2),
        tone_target=tone_target,
        scene_json=json.dumps(scene_payload, indent=2),
        reference_output=reference_output,
    )

    def validate(data: dict) -> None:
        validate_scene_response(normalize_scene_response(data, scene), scene)

    if backend == "qwen":
        enhanced = normalize_scene_response(
            run_qwen_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=qwen_model,
                api_base=api_base,
                max_tokens=max_new_tokens,
                temperature=temperature,
                validate=validate,
            ),
            scene,
        )
    else:
        enhanced = run_gemma_json_with_model(
            processor=processor,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_new_tokens=max_new_tokens,
            enable_thinking=enable_thinking,
            validate=validate,
        )
    return merge_enhancements(scene, enhanced, flux_images_dir=flux_images_dir)


def generate(
    input_path: Path,
    reference_path: Path,
    prompt_path: Path,
    backend: str,
    gemma_model_path: Path,
    qwen_model: str,
    api_base: str,
    flux_images_dir: Path,
    max_new_tokens: int,
    temperature: float,
    enable_thinking: bool,
    scene_ids: list[str] | None = None,
) -> dict:
    source = json.loads(input_path.read_text(encoding="utf-8"))
    reference_output = reference_path.read_text(encoding="utf-8")
    system_prompt, user_template = load_prompt_template(prompt_path)

    processor = model = None
    if backend == "gemma":
        processor, model = load_gemma_model(gemma_model_path)

    output = {
        "story_title": source["story_title"],
        "source": str(input_path.relative_to(PROJECT_ROOT)),
        "model_target": "ltx-2.3",
        "prompt_framework": "LTX AV — [VISUAL] [SPEECH] [SOUNDS]",
        "tone_target": source.get("tone_target", ""),
        "visual_style_guide": source["visual_style_guide"],
        "scenes": [],
    }

    scenes = source["scenes"]
    if scene_ids:
        scenes = [s for s in scenes if s["scene_id"] in scene_ids]
        if not scenes:
            raise ValueError(f"No scenes matched: {scene_ids}")

    for scene in scenes:
        print(f"Writing LTX prompts for {scene['scene_id']} ({len(scene['shots'])} shots)...")
        merged_shots = enhance_scene(
            scene=scene,
            visual_style_guide=source["visual_style_guide"],
            tone_target=source.get("tone_target", ""),
            system_prompt=system_prompt,
            user_template=user_template,
            reference_output=reference_output,
            backend=backend,
            processor=processor,
            model=model,
            qwen_model=qwen_model,
            api_base=api_base,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            enable_thinking=enable_thinking,
            flux_images_dir=flux_images_dir,
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
        description="Generate LTX 2.3 audio-video prompts from flux_prompts.json."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument(
        "--backend",
        choices=("qwen", "gemma"),
        default="qwen",
        help="LLM backend: qwen (vLLM OpenAI API, default) or gemma (local weights).",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_GEMMA_MODEL,
        help="Local Gemma weights path (only when --backend gemma).",
    )
    parser.add_argument(
        "--qwen-model",
        default=DEFAULT_MODEL,
        help="LiteLLM model id for vLLM (default: openai/Qwen/Qwen3.5-27B).",
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help="OpenAI-compatible vLLM base URL (default: http://localhost:8000/v1).",
    )
    parser.add_argument(
        "--flux-images-dir",
        type=Path,
        default=DEFAULT_FLUX_IMAGES,
        help="Directory containing Flux PNG init frames.",
    )
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
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="Disable Gemma thinking mode (ignored for --backend qwen).",
    )
    args = parser.parse_args()

    enable_thinking = not args.disable_thinking
    if args.backend == "qwen":
        print(f"Using Qwen via {args.api_base} model={args.qwen_model}")
    else:
        print(f"Using Gemma from {args.model_path}")
    out_dir = output_dir(SUB_MODULE)
    out_path = out_dir / args.output_file

    result = generate(
        input_path=args.input,
        reference_path=args.reference,
        prompt_path=args.prompt,
        backend=args.backend,
        gemma_model_path=args.model_path,
        qwen_model=args.qwen_model,
        api_base=args.api_base,
        flux_images_dir=args.flux_images_dir,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        enable_thinking=enable_thinking,
        scene_ids=args.scene_ids,
    )

    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    total = sum(len(s["shots"]) for s in result["scenes"])
    talking = sum(
        1
        for s in result["scenes"]
        for shot in s["shots"]
        if shot.get("ltx_mode") == "talking_head"
    )
    cinematic = sum(
        1
        for s in result["scenes"]
        for shot in s["shots"]
        if shot.get("ltx_mode") == "cinematic"
    )
    skipped = sum(
        1
        for s in result["scenes"]
        for shot in s["shots"]
        if shot.get("ltx_mode") == "skip"
    )
    print(
        f"Wrote {out_path} ({len(result['scenes'])} scenes, {total} shots: "
        f"{talking} talking_head, {cinematic} cinematic, {skipped} skip)"
    )


if __name__ == "__main__":
    main()
