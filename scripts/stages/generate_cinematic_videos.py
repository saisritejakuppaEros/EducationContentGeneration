#!/usr/bin/env python3
"""Generate cinematic video prompts from storyboard and run LTX 2.3 I2V inference."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401


import argparse
import json
import re
from pathlib import Path

from dialogue_utils import strip_on_screen_text, truncate_speech_for_ltx
from gemma_utils import fill_user_prompt, load_gemma_model, load_prompt_template, run_gemma_json_with_model
from paths import DEFAULT_LLM_BACKEND, PROJECT_ROOT, PROMPTS_DIR, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel, resolve_project_path
from pipeline_utils import write_json
from qwen_utils import run_qwen_json

SUB_MODULE = "cinematic_videos"
DEFAULT_STORYBOARD = output_dir("storyboard") / "storyboard.json"
DEFAULT_SERIES_BIBLE = output_dir("series_bible") / "series_bible.json"
DEFAULT_PROMPT = PROMPTS_DIR / "cinematic_video.md"

HUMAN_SHOT_TYPES = {"INT WIDE", "WIDE", "OTS", "TWO-SHOT", "REACTION", "Y-POV", "OTS Y→M", "OTS Y→F"}
DEFAULT_NEGATIVE = (
    "music, silent or muted audio, distorted voice, off-sync lips, background music, "
    "washed out contrast, deformed facial features, blurry, low quality, "
    "text, subtitles, captions, letters, words on screen, title cards, watermarks"
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


def infer_ltx_mode(shot: dict, scene_type: str, *, include_math_inserts: bool = False) -> str:
    shot_type = (shot.get("type") or "").upper()
    if not include_math_inserts and (shot_type == "MATH INSERT" or scene_type == "CONCEPT"):
        return "skip"
    dialogue = shot.get("dialogue")
    if dialogue and parse_speaker(dialogue if isinstance(dialogue, str) else f"{dialogue.get('character')}: {dialogue.get('line')}"):
        if shot_type in HUMAN_SHOT_TYPES or "OTS" in shot_type or "TWO" in shot_type:
            return "talking_head"
    return "cinematic"


def keyframe_path(shot: dict) -> str:
    path = shot.get("keyframe_image")
    if not path:
        return ""
    candidate = resolve_project_path(path)
    if candidate.is_file():
        return project_rel(candidate)
    rel = Path(path)
    alt = output_dir("storyboard") / rel.parent.name / rel.name
    if alt.is_file():
        return project_rel(alt)
    alt_flat = output_dir("storyboard") / rel.name
    if alt_flat.is_file():
        return project_rel(alt_flat)
    return path


def default_ambient_sound(scene: dict) -> str:
    title = scene.get("title") or scene.get("scene_id") or "control room"
    return f"ambient {title}, subtle mechanical hum, room tone"


def build_deterministic_structured(shot: dict, scene: dict) -> dict:
    raw_visual = shot.get("flux_prompt") or shot.get("blocking") or "cinematic sci-fi shot"
    visual = strip_on_screen_text(raw_visual)
    speech = truncate_speech_for_ltx(extract_speech(shot.get("dialogue")))
    return {
        "visual": visual,
        "speech": speech,
        "sounds": default_ambient_sound(scene),
    }


def build_ltx_prompt(structured: dict, *, mode: str) -> str | None:
    if mode == "skip":
        return None
    visual = strip_on_screen_text((structured.get("visual") or "").strip())
    speech = truncate_speech_for_ltx(structured.get("speech"))
    sounds = (structured.get("sounds") or "").strip() or "ambient room tone, subtle mechanical hum"
    if not visual:
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


def build_prompts_manifest_deterministic(
    *,
    storyboard_path: Path,
    scene_ids: list[str] | None,
    include_math_inserts: bool = False,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    scenes_out = []

    for scene in storyboard.get("scenes", []):
        if scene_ids and scene["scene_id"] not in scene_ids:
            continue
        scene_type = scene.get("screenplay_type", "STORY")
        shots_out = []
        for shot in scene.get("shots", []):
            mode = infer_ltx_mode(shot, scene_type, include_math_inserts=include_math_inserts)
            structured = build_deterministic_structured(shot, scene)
            ltx_prompt = build_ltx_prompt(structured, mode=mode)
            init_image = keyframe_path(shot)
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
        scenes_out.append({**scene, "shots": shots_out})

    return {
        "chapter": storyboard.get("chapter"),
        "story_title": storyboard.get("chapter"),
        "scenes": scenes_out,
    }


def build_prompts_manifest(
    *,
    storyboard_path: Path,
    series_bible_path: Path,
    prompt_path: Path,
    scene_ids: list[str] | None,
    backend: str,
    model_path: Path,
    max_tokens: int,
    include_math_inserts: bool = False,
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
            mode = llm_shot.get("ltx_mode") or infer_ltx_mode(
                shot, scene_type, include_math_inserts=include_math_inserts
            )
            structured = llm_shot.get("ltx_prompt_structured") or build_deterministic_structured(shot, scene)
            if structured.get("visual"):
                structured["visual"] = strip_on_screen_text(structured["visual"])
            if structured.get("speech"):
                structured["speech"] = truncate_speech_for_ltx(structured["speech"])
            if not structured.get("sounds"):
                structured["sounds"] = default_ambient_sound(scene)
            ltx_prompt = llm_shot.get("ltx_prompt") or build_ltx_prompt(structured, mode=mode)
            init_image = llm_shot.get("init_image") or keyframe_path(shot)
            init_path = resolve_project_path(init_image) if init_image else None
            if mode != "skip" and init_path and not init_path.is_file():
                print(f"Warning: missing keyframe for {scene['scene_id']} shot {shot.get('shot')}: {init_image}")
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
        "--output-root",
        str(get_output_root()),
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
    parser.add_argument(
        "--deterministic-prompts",
        action="store_true",
        help="Build LTX prompts from storyboard without LLM (faster, no text-in-video).",
    )
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument(
        "--include-math-inserts",
        action="store_true",
        help="Generate LTX clips for MATH INSERT / CONCEPT shots (use when Manim is disabled).",
    )
    add_output_root_argument(parser)
    args, extra = parser.parse_known_args()

    from paths import DEFAULT_GEMMA_MODEL

    configure_output_root(args.output_root)
    print(f"Output root: {project_rel(get_output_root())}/")

    out_dir = output_dir(SUB_MODULE)
    prompts_path = out_dir / "cinematic_prompts.json"

    if not args.skip_prompts:
        if not args.storyboard.is_file():
            raise FileNotFoundError(f"storyboard not found: {args.storyboard}")
        if args.deterministic_prompts:
            manifest = build_prompts_manifest_deterministic(
                storyboard_path=args.storyboard,
                scene_ids=args.scene_ids,
                include_math_inserts=args.include_math_inserts,
            )
        else:
            model_path = args.model_path or DEFAULT_GEMMA_MODEL
            manifest = build_prompts_manifest(
                storyboard_path=args.storyboard,
                series_bible_path=args.series_bible if args.series_bible.is_file() else args.series_bible,
                prompt_path=args.prompt,
                scene_ids=args.scene_ids,
                backend=args.backend,
                model_path=model_path,
                max_tokens=args.max_tokens,
                include_math_inserts=args.include_math_inserts,
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
