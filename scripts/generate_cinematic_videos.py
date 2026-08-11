#!/usr/bin/env python3
"""Generate cinematic video prompts from storyboard and run LTX 2.3 I2V inference."""

import argparse
import json
import re
from pathlib import Path

from gemma_utils import fill_user_prompt, load_gemma_model, load_prompt_template, run_gemma_json_with_model
from paths import DEFAULT_LLM_BACKEND, PROJECT_ROOT, PROMPTS_DIR, output_dir
from pipeline_utils import write_json
from qwen_utils import run_qwen_json

SUB_MODULE = "cinematic_videos"
DEFAULT_STORYBOARD = output_dir("storyboard") / "storyboard.json"
DEFAULT_SERIES_BIBLE = output_dir("series_bible") / "series_bible.json"
DEFAULT_PROMPT = PROMPTS_DIR / "cinematic_video.md"

HUMAN_SHOT_TYPES = {"INT WIDE", "WIDE", "OTS", "TWO-SHOT", "REACTION", "Y-POV", "OTS Y→M", "OTS Y→F"}
DEFAULT_NEGATIVE = (
    "music, silent or muted audio, distorted voice, off-sync lips, background music, "
    "washed out contrast, deformed facial features, blurry, low quality"
)


def parse_speaker(dialogue: str | None) -> str | None:
    if not dialogue:
        return None
    if isinstance(dialogue, dict):
        return dialogue.get("character")
    match = re.match(r"^([MFY]):\s*", str(dialogue).strip())
    return match.group(1) if match else None


def extract_speech(dialogue) -> str | None:
    if not dialogue:
        return None
    if isinstance(dialogue, dict):
        return dialogue.get("line")
    text = str(dialogue).strip()
    match = re.match(r"^[MFY]:\s*\"(.+)\"$", text)
    if match:
        return match.group(1)
    match = re.match(r"^[MFY]:\s*(.+)$", text)
    return match.group(1).strip('"') if match else None


def infer_ltx_mode(shot: dict, scene_type: str) -> str:
    shot_type = (shot.get("type") or "").upper()
    if shot_type == "MATH INSERT" or scene_type == "CONCEPT":
        return "skip"
    dialogue = shot.get("dialogue")
    if dialogue and parse_speaker(dialogue if isinstance(dialogue, str) else f"{dialogue.get('character')}: {dialogue.get('line')}"):
        if shot_type in HUMAN_SHOT_TYPES or "OTS" in shot_type or "TWO" in shot_type:
            return "talking_head"
    return "cinematic"


def keyframe_path(shot: dict) -> str:
    path = shot.get("keyframe_image")
    if path:
        return path
    return ""


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


def validate_scene_prompts(data: dict) -> None:
    if "scene_id" not in data or "shots" not in data:
        raise ValueError("Expected scene_id and shots")


def generate_scene_prompts(
    *,
    scene: dict,
    series_bible: dict,
    previous_motion: str,
    prompt_path: Path,
    backend: str,
    model_path: Path,
    max_tokens: int,
) -> dict:
    system_prompt, user_template = load_prompt_template(prompt_path)
    user_prompt = fill_user_prompt(
        user_template,
        scene_shots=json.dumps(scene, indent=2, ensure_ascii=False),
        series_bible=json.dumps(series_bible, indent=2, ensure_ascii=False),
        previous_shot_motion=previous_motion or "None",
    )

    if backend == "gemma":
        processor, model = load_gemma_model(model_path)
        return run_gemma_json_with_model(
            processor=processor,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_new_tokens=max_tokens,
            enable_thinking=False,
            validate=validate_scene_prompts,
        )

    return run_qwen_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        validate=validate_scene_prompts,
    )


def build_prompts_manifest(
    *,
    storyboard_path: Path,
    series_bible_path: Path,
    prompt_path: Path,
    scene_ids: list[str] | None,
    backend: str,
    model_path: Path,
    max_tokens: int,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    series_bible = json.loads(series_bible_path.read_text(encoding="utf-8"))
    scenes_out = []
    previous_motion = ""

    for scene in storyboard.get("scenes", []):
        if scene_ids and scene["scene_id"] not in scene_ids:
            continue
        scene_type = scene.get("screenplay_type", "STORY")
        llm_scene = generate_scene_prompts(
            scene=scene,
            series_bible=series_bible,
            previous_motion=previous_motion,
            prompt_path=prompt_path,
            backend=backend,
            model_path=model_path,
            max_tokens=max_tokens,
        )

        shots_out = []
        for shot in scene.get("shots", []):
            llm_shot = next((s for s in llm_scene.get("shots", []) if s.get("shot") == shot.get("shot")), {})
            mode = llm_shot.get("ltx_mode") or infer_ltx_mode(shot, scene_type)
            structured = llm_shot.get("ltx_prompt_structured") or {
                "visual": shot.get("flux_prompt", "")[:200],
                "speech": extract_speech(shot.get("dialogue")) or "",
                "sounds": f"ambient {scene.get('title', 'control room')}, subtle mechanical hum",
            }
            ltx_prompt = llm_shot.get("ltx_prompt") or build_ltx_prompt(structured, mode=mode)
            init_image = llm_shot.get("init_image") or keyframe_path(shot)
            shots_out.append(
                {
                    **shot,
                    "ltx_mode": mode,
                    "ltx_prompt": ltx_prompt,
                    "ltx_prompt_structured": structured,
                    "init_image": init_image,
                    "use_talking_head_lora": mode == "talking_head",
                    "negative_prompt": DEFAULT_NEGATIVE,
                }
            )
            if shot.get("camera_move"):
                previous_motion = shot["camera_move"]

        scenes_out.append({**scene, "shots": shots_out})

    return {
        "chapter": storyboard.get("chapter"),
        "story_title": storyboard.get("chapter"),
        "scenes": scenes_out,
    }


def run_video_generation(prompts_path: Path, extra_args: list[str]) -> int:
    import subprocess
    import sys

    script = PROJECT_ROOT / "scripts" / "generate_ltx_videos.py"
    cmd = [
        sys.executable,
        str(script),
        "--prompts",
        str(prompts_path),
        "--output-sub-module",
        SUB_MODULE,
        *extra_args,
    ]
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cinematic prompts and LTX videos from storyboard.")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--series-bible", type=Path, default=DEFAULT_SERIES_BIBLE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--scene", action="append", dest="scene_ids")
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--prompts-only", action="store_true")
    parser.add_argument("--skip-prompts", action="store_true", help="Use existing cinematic_prompts.json")
    parser.add_argument("--skip-existing", action="store_true")
    args, extra = parser.parse_known_args()

    from paths import DEFAULT_GEMMA_MODEL

    out_dir = output_dir(SUB_MODULE)
    prompts_path = out_dir / "cinematic_prompts.json"

    if not args.skip_prompts:
        if not args.storyboard.is_file():
            raise FileNotFoundError(f"storyboard not found: {args.storyboard}")
        model_path = args.model_path or DEFAULT_GEMMA_MODEL
        manifest = build_prompts_manifest(
            storyboard_path=args.storyboard,
            series_bible_path=args.series_bible if args.series_bible.is_file() else args.series_bible,
            prompt_path=args.prompt,
            scene_ids=args.scene_ids,
            backend=args.backend,
            model_path=model_path,
            max_tokens=args.max_tokens,
        )
        write_json(prompts_path, manifest)
        print(f"Wrote {prompts_path}")

    if args.prompts_only:
        return

    if not prompts_path.is_file():
        raise FileNotFoundError(f"Prompts not found: {prompts_path}")

    video_args = list(extra)
    if args.skip_existing:
        video_args.append("--skip-existing")
    if args.scene_ids:
        for scene_id in args.scene_ids:
            video_args.extend(["--scene", scene_id])

    raise SystemExit(run_video_generation(prompts_path, video_args))


if __name__ == "__main__":
    main()
