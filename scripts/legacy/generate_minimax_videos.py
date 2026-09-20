#!/usr/bin/env python3
"""Render cinematic_prompts.json clips with MiniMax-H3 (cloud I2V)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from minimax_h3 import clamp_duration, generate_image_to_video, prompt_from_shot


def iter_renderable_shots(data: dict):
    for scene in data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("ltx_mode") == "skip":
                continue
            if not shot.get("ltx_prompt") and not shot.get("ltx_prompt_structured"):
                continue
            yield scene, shot
from paths import PROJECT_ROOT, add_output_root_argument, configure_output_root, get_output_root, output_dir, project_rel, resolve_project_path
from pipeline_utils import write_json

SUB_MODULE = "cinematic_videos"


def generate(
    *,
    prompts_path: Path,
    sub_module: str,
    scene_ids: list[str] | None,
    shot_numbers: list[int] | None,
    skip_existing: bool,
    ratio: str,
    timeout_seconds: float,
) -> dict:
    data = json.loads(prompts_path.read_text(encoding="utf-8"))
    out_dir = output_dir(sub_module)
    manifest_path = out_dir / "manifest.json"
    manifest: dict = {
        "story_title": data.get("story_title"),
        "prompts": str(prompts_path.relative_to(PROJECT_ROOT)),
        "video_backend": "minimax-h3",
        "shots": [],
    }
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["video_backend"] = "minimax-h3"

    pending: list[tuple[dict, dict, Path, Path]] = []
    for scene, shot in iter_renderable_shots(data):
        if scene_ids and scene["scene_id"] not in scene_ids:
            continue
        if shot_numbers and shot["shot"] not in shot_numbers:
            continue
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]
        output_path = out_dir / scene_id / f"{scene_id}_shot{shot_num:02d}.mp4"
        if skip_existing and output_path.is_file():
            print(f"Skipping existing {output_path.name}")
            continue
        init_rel = shot.get("init_image")
        if not init_rel:
            raise ValueError(f"{scene_id} shot {shot_num}: missing init_image")
        init_path = resolve_project_path(init_rel)
        pending.append((scene, shot, init_path, output_path))

    if not pending:
        print("Nothing to generate.")
        return manifest

    print(f"{len(pending)} MiniMax-H3 shot(s) pending from {prompts_path.name}")
    for scene, shot, init_path, output_path in pending:
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]
        duration = clamp_duration(float(shot.get("duration_seconds") or 5.0))
        prompt = prompt_from_shot(shot)
        print(f"MiniMax-H3 {scene_id} shot {shot_num} ({duration}s) …")
        meta = generate_image_to_video(
            prompt=prompt,
            first_frame=init_path,
            output_path=output_path,
            duration_seconds=duration,
            ratio=ratio,
            timeout_seconds=timeout_seconds,
        )
        entry = {
            "scene_id": scene_id,
            "shot": shot_num,
            "type": shot.get("type"),
            "ltx_mode": shot.get("ltx_mode"),
            "init_image": str(init_path.relative_to(PROJECT_ROOT)),
            "output": str(output_path.relative_to(PROJECT_ROOT)),
            "duration_seconds": duration,
            "minimax_task_id": meta.get("task_id"),
            "prompt": prompt[:500],
        }
        manifest.setdefault("shots", []).append(entry)
        write_json(manifest_path, manifest)
        print(f"Wrote {project_rel(output_path)}")

    write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate shot videos with MiniMax-H3 I2V.")
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--output-sub-module", type=str, default=SUB_MODULE)
    parser.add_argument("--scene", action="append", dest="scene_ids")
    parser.add_argument("--shot", action="append", dest="shot_numbers", type=int)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--ratio", type=str, default="16:9")
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    generate(
        prompts_path=args.prompts,
        sub_module=args.output_sub_module,
        scene_ids=args.scene_ids,
        shot_numbers=args.shot_numbers,
        skip_existing=args.skip_existing,
        ratio=args.ratio,
        timeout_seconds=args.timeout_seconds,
    )


if __name__ == "__main__":
    main()
