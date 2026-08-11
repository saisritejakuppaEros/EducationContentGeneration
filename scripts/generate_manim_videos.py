#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console

from manim_generator.utils.file import save_code_to_file
from manim_generator.utils.parsing import SceneParsingError, extract_scene_class_names, sanitize_manim_code
from manim_generator.utils.usage import format_duration, get_usage_totals
from manim_generator.utils.video import render_and_concat
from manim_generator.workflow import ManimWorkflow
from paths import DEFAULT_QWEN_MODEL, PROJECT_ROOT, output_dir

SUB_MODULE = "manim_videos"
MANIM_GENERATOR_ROOT = PROJECT_ROOT / "scripts" / "manim-generator"


@contextmanager
def manim_generator_cwd():
    """manim-generator resolves prompts/ relative to its project root."""
    previous = Path.cwd()
    os.chdir(MANIM_GENERATOR_ROOT)
    try:
        yield
    finally:
        os.chdir(previous)
DEFAULT_STORYBOARD = output_dir("storyboard") / "storyboard.json"
DEFAULT_MATH_BIBLE = output_dir("math_bible") / "math_bible.json"
DEFAULT_MATH_LINKUP = PROJECT_ROOT / "output" / "ps_math_linkup" / "ps_math_linkup.json"

DEFAULT_MANIM_MODEL = DEFAULT_QWEN_MODEL
DEFAULT_REVIEW_MODEL = DEFAULT_QWEN_MODEL
DEFAULT_REVIEW_CYCLES = 4


def load_math_topics(linkup_path: Path) -> dict[str, dict]:
    data = json.loads(linkup_path.read_text(encoding="utf-8"))
    topics: dict[str, dict] = {}
    if "topics" in data:
        for topic in data.get("topics", []):
            topics[topic["id"]] = {**topic, "chapter_name": data.get("chapter", "")}
        return topics
    for chapter in data.get("chapters", []):
        for topic in chapter.get("topics", []):
            topics[topic["id"]] = {
                **topic,
                "chapter_name": chapter.get("name"),
                "chapter_subtitle": chapter.get("subtitle"),
            }
    return topics


def math_insert_set_description(visual_style_bible: dict) -> str:
    for entry in visual_style_bible.get("sets", []):
        name = (entry.get("name") or "").lower()
        if "math" in name or "screen" in name:
            return entry.get("description", "")
    return "Pure black background, glowing cyan-white equations, no clutter."


def iter_math_insert_shots(storyboard: dict) -> list[tuple[dict, dict]]:
    shots: list[tuple[dict, dict]] = []
    for scene in storyboard.get("scenes", []):
        scene_type = (scene.get("screenplay_type") or scene.get("render_type") or "").upper()
        for shot in scene.get("shots", []):
            shot_type = (shot.get("type") or "").upper()
            if shot_type == "MATH INSERT" or scene_type in {"CONCEPT", "HYBRID"} and shot_type == "MATH INSERT":
                shots.append((scene, shot))
            elif scene_type == "CONCEPT" and shot_type in {"INSERT", "MATH INSERT", "CONCEPT"}:
                shots.append((scene, shot))
    return shots


def build_video_data_prompt(
    scene: dict,
    shot: dict,
    *,
    math_topics: dict[str, dict],
    visual_style_bible: dict,
) -> str:
    style_desc = math_insert_set_description(visual_style_bible)
    topic_lines: list[str] = []
    for topic_id in scene.get("topic_ids", []):
        topic = math_topics.get(topic_id)
        if not topic:
            continue
        topic_lines.append(
            f"- [{topic_id}] {topic['topic']}\n"
            f"  Problem: {topic.get('real_world_problem') or topic.get('problem', '')}\n"
            f"  Equation: {topic['equation']}\n"
            f"  Why: {topic.get('why_this_tool') or topic.get('why_equation', '')}\n"
            f"  Core visual (ONLY this): {topic.get('core_visual_idea', 'Show the main idea clearly')}\n"
            f"  Excluded: {', '.join(topic.get('explicitly_excluded') or [])}"
        )

    chapter = scene.get("chapter", "")
    subtitle = scene.get("chapter_subtitle") or ""
    title = scene.get("title") or f"{chapter} math insert"
    duration = shot.get("duration_seconds", 40)

    return f"""Title: {title} — Math Insert (Shot {shot['shot']})
Chapter: {chapter} / {subtitle}
Scene ID: {scene['scene_id']}
Scene beat: {scene.get('beat', '')}
Target duration: {duration} seconds

Visual style:
- {style_desc}
- Educational math visualization only — no characters, no environments, no UI chrome
- Locked-off camera, static framing, legibility over decoration

Animation description:
{shot.get('flux_frame', '')}

Motion and pacing:
{shot.get('wan_motion', '')}

Mathematical context:
{chr(10).join(topic_lines) if topic_lines else '- Use the animation description above as the primary math content.'}

Requirements:
- Visualize ONLY the core_visual_idea — no proofs, no edge cases, no multi-step derivations
- Create a single polished Manim animation suitable as a screen insert in a sci-fi film
- Reveal formulas and geometric constructions step by step
- Keep the background pure black with cyan/white glowing math typography
- Aim for approximately {duration} seconds total runtime
- Use Manim Community v0.20 API only: no glow_factor on Dot, use TEAL instead of CYAN, no external assets
"""


def build_manim_config(
    *,
    output_dir_path: Path,
    manim_model: str,
    review_model: str,
    review_cycles: int,
    temperature: float,
    max_tokens: int,
    scene_timeout: int | None,
) -> dict:
    return {
        "manim_model": manim_model,
        "review_model": review_model,
        "review_cycles": review_cycles,
        "output_dir": str(output_dir_path.resolve()),
        "manim_logs": False,
        "streaming": False,
        "temperature": temperature,
        "no_temperature": False,
        "vision_enabled": True,
        "reasoning": None,
        "provider": None,
        "success_threshold": 100,
        "frame_extraction_mode": "highest_density",
        "frame_count": 3,
        "headless": True,
        "scene_timeout": scene_timeout,
        "max_tokens": max_tokens,
    }


def run_shot_workflow(
    *,
    video_data: str,
    run_dir: Path,
    config: dict,
    console: Console,
    render_final: bool,
) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    os.makedirs(config["output_dir"], exist_ok=True)

    start_time = time.time()
    with manim_generator_cwd():
        workflow = ManimWorkflow(config, console)

        current_code, _ = workflow.generate_initial_code(video_data)
        success, last_frames, combined_logs, successful_scenes = workflow.execute_code(
            current_code, "Initial"
        )
        workflow.initial_success = success
        working_code = current_code if success else None

        current_code, new_working_code, combined_logs = workflow.review_and_update_code(
            current_code, combined_logs, last_frames, video_data, successful_scenes
        )
        working_code = new_working_code if new_working_code else working_code

        video_path = None
        code_path = None
        if working_code:
            code_path = save_code_to_file(working_code, filename=f"{config['output_dir']}/video.py")
            workflow.artifact_manager.save_step_artifacts("final", code=working_code)
            if render_final:
                video_path = render_and_concat(
                    code_path,
                    config["output_dir"],
                    "final_video.mp4",
                )
                if video_path:
                    video_path = os.path.abspath(video_path)

    duration_seconds = time.time() - start_time
    token_usage = workflow.usage_tracker.get_tracking_data()
    (
        total_prompt_tokens,
        total_completion_tokens,
        total_reasoning_tokens,
        total_answer_tokens,
    ) = get_usage_totals(token_usage)

    return {
        "success": working_code is not None,
        "video_path": video_path,
        "code_path": code_path,
        "duration_seconds": duration_seconds,
        "duration_human": format_duration(duration_seconds),
        "review_cycles": workflow.cycles_completed,
        "total_executions": workflow.execution_count,
        "successful_executions": workflow.successful_executions,
        "initial_success": workflow.initial_success,
        "total_cost": token_usage["total_cost"],
        "total_tokens": token_usage["total_tokens"],
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_answer_tokens": total_answer_tokens,
        "logs_tail": combined_logs[-2000:] if combined_logs else "",
    }


def find_runnable_code(run_dir: Path) -> str | None:
    candidates: list[Path] = []
    steps = run_dir / "steps"
    if steps.is_dir():
        candidates.extend(sorted(steps.glob("revision_*/code.py"), reverse=True))
        for name in ("final", "initial"):
            path = steps / name / "code.py"
            if path.is_file():
                candidates.append(path)
    video_py = run_dir / "video.py"
    if video_py.is_file():
        candidates.append(video_py)

    for path in candidates:
        sanitized = sanitize_manim_code(path.read_text(encoding="utf-8"))
        scene_names = extract_scene_class_names(sanitized)
        if isinstance(scene_names, SceneParsingError):
            continue
        if scene_names:
            return sanitized
    return None


def render_existing_shot(*, run_dir: Path, final_video: Path) -> dict:
    run_dir.mkdir(parents=True, exist_ok=True)
    code = find_runnable_code(run_dir)
    if not code:
        return {"success": False, "video_path": None, "error": "No runnable Manim code found"}

    code_path = save_code_to_file(code, filename=f"{run_dir.resolve()}/video.py")
    with manim_generator_cwd():
        video_path = render_and_concat(code_path, str(run_dir.resolve()), "final_video.mp4")

    if not video_path:
        return {"success": False, "video_path": None, "error": "Manim render failed"}

    final_video.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video_path, final_video)
    print(f"  Wrote {final_video}")
    return {"success": True, "video_path": str(final_video)}


def shot_output_paths(out_dir: Path, scene_id: str, shot_num: int) -> tuple[Path, Path, Path]:
    scene_dir = out_dir / scene_id
    run_dir = scene_dir / f"{scene_id}_shot{shot_num:02d}"
    final_video = scene_dir / f"{scene_id}_shot{shot_num:02d}.mp4"
    return scene_dir, run_dir, final_video


def generate(
    *,
    storyboard_path: Path,
    math_linkup_path: Path,
    scene_ids: list[str] | None,
    shot_numbers: list[int] | None,
    manim_model: str,
    review_model: str,
    review_cycles: int,
    temperature: float,
    max_tokens: int,
    scene_timeout: int | None,
    skip_existing: bool,
    render_final: bool,
    dry_run: bool,
    render_only: bool,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    math_topics = load_math_topics(math_linkup_path)
    visual_style_bible = storyboard.get("visual_style_bible", {})

    out_dir = output_dir(SUB_MODULE)
    manifest_path = out_dir / "manifest.json"
    manifest = {
        "story_title": storyboard.get("story_title"),
        "storyboard": str(storyboard_path.relative_to(PROJECT_ROOT)),
        "math_linkup": str(math_linkup_path.relative_to(PROJECT_ROOT)),
        "manim_model": manim_model,
        "review_model": review_model,
        "review_cycles": review_cycles,
        "shots": [],
    }
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    pending: list[tuple[dict, dict, Path, Path, str]] = []
    for scene, shot in iter_math_insert_shots(storyboard):
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]

        if scene_ids and scene_id not in scene_ids:
            continue
        if shot_numbers and shot_num not in shot_numbers:
            continue

        _, run_dir, final_video = shot_output_paths(out_dir, scene_id, shot_num)
        if skip_existing and final_video.is_file():
            print(f"Skipping existing {final_video.name}")
            continue

        if render_only:
            if not run_dir.is_dir():
                print(f"Skipping {scene_id} shot {shot_num} — no run dir at {run_dir}")
                continue
            pending.append((scene, shot, run_dir, final_video, ""))
            continue

        video_data = build_video_data_prompt(
            scene,
            shot,
            math_topics=math_topics,
            visual_style_bible=visual_style_bible,
        )
        pending.append((scene, shot, run_dir, final_video, video_data))

    if not pending:
        print("Nothing to generate.")
        return manifest

    print(
        f"{len(pending)} MATH INSERT shot(s) pending — "
        f"storyboard: {storyboard_path.name}, math linkup: {math_linkup_path.name}"
        + (" (render-only)" if render_only else "")
    )

    if dry_run:
        for scene, shot, run_dir, final_video, video_data in pending:
            print(f"\n--- {scene['scene_id']} shot {shot['shot']} -> {final_video} ---")
            if video_data:
                print(video_data)
            else:
                print(f"render-only from {run_dir}")
        return manifest

    if render_only:
        for scene, shot, run_dir, final_video, _ in pending:
            scene_id = scene["scene_id"]
            shot_num = shot["shot"]
            print(f"\nRendering existing Manim code for {scene_id} shot {shot_num}...")
            result = render_existing_shot(run_dir=run_dir, final_video=final_video)
            entry = {
                "scene_id": scene_id,
                "shot": shot_num,
                "type": shot.get("type"),
                "topic_ids": scene.get("topic_ids", []),
                "duration_seconds": shot.get("duration_seconds"),
                "run_dir": str(run_dir.relative_to(PROJECT_ROOT)),
                "output": str(final_video.relative_to(PROJECT_ROOT)) if result["success"] else None,
                "success": result["success"],
                "render_only": True,
            }
            if not result["success"]:
                print(f"  Failed — {result.get('error', 'unknown error')}")
            manifest["shots"] = [
                e
                for e in manifest.get("shots", [])
                if not (e["scene_id"] == scene_id and e["shot"] == shot_num)
            ]
            manifest["shots"].append(entry)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return manifest

    console = Console()
    for scene, shot, run_dir, final_video, video_data in pending:
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]
        print(f"\nGenerating Manim video for {scene_id} shot {shot_num}...")

        config = build_manim_config(
            output_dir_path=run_dir,
            manim_model=manim_model,
            review_model=review_model,
            review_cycles=review_cycles,
            temperature=temperature,
            max_tokens=max_tokens,
            scene_timeout=scene_timeout,
        )

        result = run_shot_workflow(
            video_data=video_data,
            run_dir=run_dir,
            config=config,
            console=console,
            render_final=render_final,
        )

        if result["success"] and result["video_path"] and render_final:
            final_video.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result["video_path"], final_video)
            print(f"  Wrote {final_video}")
        elif result["success"]:
            print(f"  Code saved under {run_dir} (render skipped)")
        else:
            print(f"  Failed — see artifacts in {run_dir}")

        entry = {
            "scene_id": scene_id,
            "shot": shot_num,
            "type": shot.get("type"),
            "topic_ids": scene.get("topic_ids", []),
            "duration_seconds": shot.get("duration_seconds"),
            "run_dir": str(run_dir.relative_to(PROJECT_ROOT)),
            "output": str(final_video.relative_to(PROJECT_ROOT)) if final_video.is_file() else None,
            "success": result["success"],
            "duration_human": result["duration_human"],
            "total_cost": result["total_cost"],
            "total_tokens": result["total_tokens"],
            "review_cycles": result["review_cycles"],
            "initial_success": result["initial_success"],
        }
        manifest["shots"] = [
            e
            for e in manifest.get("shots", [])
            if not (e["scene_id"] == scene_id and e["shot"] == shot_num)
        ]
        manifest["shots"].append(entry)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Manim math-insert videos from image_video_generation.json "
            "using the manim-generator workflow."
        )
    )
    parser.add_argument(
        "--storyboard",
        "--input",
        type=Path,
        default=DEFAULT_STORYBOARD,
        dest="storyboard",
        help=f"Storyboard JSON with MATH INSERT shots (default: {DEFAULT_STORYBOARD.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--math-bible",
        type=Path,
        default=DEFAULT_MATH_BIBLE,
        help=f"Math bible JSON (default: {DEFAULT_MATH_BIBLE.relative_to(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--math-linkup",
        type=Path,
        default=None,
        help="Legacy math linkup JSON (overrides --math-bible when set).",
    )
    parser.add_argument(
        "--scene",
        action="append",
        dest="scene_ids",
        help="Process only these scene ids (e.g. S2). Repeatable.",
    )
    parser.add_argument(
        "--shot",
        type=int,
        action="append",
        dest="shot_numbers",
        help="Process only these shot numbers within selected scenes. Repeatable.",
    )
    parser.add_argument("--manim-model", default=DEFAULT_MANIM_MODEL)
    parser.add_argument("--review-model", default=DEFAULT_REVIEW_MODEL)
    parser.add_argument("--review-cycles", type=int, default=DEFAULT_REVIEW_CYCLES)
    parser.add_argument("--temperature", type=float, default=0.4)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument(
        "--scene-timeout",
        type=int,
        default=400,
        help="Per-scene Manim render timeout in seconds (0 disables).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip shots whose final MP4 already exists.",
    )
    parser.add_argument(
        "--no-render",
        action="store_true",
        help="Generate and review Manim code only; skip final ffmpeg concat render.",
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Render MP4 from the best existing code in each run dir (no LLM calls).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print built video_data prompts without calling the LLM.",
    )
    args = parser.parse_args()

    math_path = args.math_linkup or args.math_bible
    if not args.storyboard.is_file():
        raise FileNotFoundError(f"Storyboard file not found: {args.storyboard}")
    if not math_path.is_file():
        raise FileNotFoundError(f"Math input not found: {math_path}")

    scene_timeout = None if args.scene_timeout == 0 else args.scene_timeout

    manifest = generate(
        storyboard_path=args.storyboard,
        math_linkup_path=math_path,
        scene_ids=args.scene_ids,
        shot_numbers=args.shot_numbers,
        manim_model=args.manim_model,
        review_model=args.review_model,
        review_cycles=args.review_cycles,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        scene_timeout=scene_timeout,
        skip_existing=args.skip_existing,
        render_final=not args.no_render,
        dry_run=args.dry_run,
        render_only=args.render_only,
    )

    if args.dry_run:
        print("\nDry run complete — no LLM calls made.")
        return

    ok = sum(1 for s in manifest.get("shots", []) if s.get("success"))
    print(f"\nDone. {ok