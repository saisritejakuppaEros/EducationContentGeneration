#!/usr/bin/env python3
"""Render cinematic_prompts.json with local MiniMax-H3 via ComfyUI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from minimax_h3_local import generate_i2v_clip


def iter_renderable_shots(data: dict):
    for scene in data.get("scenes", []):
        for shot in scene.get("shots", []):
            if shot.get("ltx_mode") == "skip":
                continue
            if not shot.get("ltx_prompt") and not shot.get("ltx_prompt_structured"):
                continue
            yield scene, shot


def prompt_from_shot(shot: dict) -> str:
    raw = (shot.get("ltx_prompt") or "").strip()
    if raw:
        return raw[:7000]
    structured = shot.get("ltx_prompt_structured") or {}
    visual = (structured.get("visual") or "").strip()
    sounds = (structured.get("sounds") or "").strip()
    speech = (structured.get("speech") or "").strip()
    parts = [visual] if visual else []
    if speech:
        parts.append(f"Dialogue: {speech}")
    if sounds:
        parts.append(f"Sound: {sounds}")
    text = ". ".join(p for p in parts if p)
    return (text or "Smooth cinematic motion, educational scene.")[:7000]
from paths import PROJECT_ROOT, add_output_root_argument, configure_output_root, output_dir, project_rel, resolve_project_path
from pipeline_utils import write_json

SUB_MODULE = "cinematic_videos"


def clamp_duration(seconds: float) -> int:
    return max(4, min(15, int(round(seconds))))


def generate(
    *,
    prompts_path: Path,
    sub_module: str,
    scene_ids: list[str] | None,
    shot_numbers: list[int] | None,
    skip_existing: bool,
    timeout_seconds: float,
    seed_base: int,
) -> dict:
    data = json.loads(prompts_path.read_text(encoding="utf-8"))
    out_dir = output_dir(sub_module)
    manifest_path = out_dir / "manifest.json"
    manifest: dict = {
        "story_title": data.get("story_title"),
        "prompts": str(prompts_path.relative_to(PROJECT_ROOT)),
        "video_backend": "minimax-h3-local-comfyui",
        "shots": [],
    }
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["video_backend"] = "minimax-h3-local-comfyui"

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

    print(f"{len(pending)} local MiniMax-H3 (ComfyUI) shot(s) from {prompts_path.name}")
    for scene, shot, init_path, output_path in pending:
        scene_id = scene["scene_id"]
        shot_num = shot["shot"]
        prompt = prompt_from_shot(shot)
        seed = seed_base + shot_num + int(scene_id[1:]) * 100
        print(f"ComfyUI MiniMax-H3 {scene_id} shot {shot_num} …")
        meta = generate_i2v_clip(
            prompt=prompt,
            first_frame=init_path,
            output_path=output_path,
            seed=seed,
            timeout_seconds=timeout_seconds,
        )
        entry = {
            "scene_id": scene_id,
            "shot": shot_num,
            "init_image": str(init_path.relative_to(PROJECT_ROOT)),
            "output": str(output_path.relative_to(PROJECT_ROOT)),
            "seed": seed,
            "comfy_workflow": meta.get("workflow"),
        }
        manifest.setdefault("shots", []).append(entry)
        write_json(manifest_path, manifest)
        print(f"Wrote {project_rel(output_path)}")

    write_json(manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Local MiniMax-H3 I2V via ComfyUI.")
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--output-sub-module", type=str, default=SUB_MODULE)
    parser.add_argument("--scene", action="append", dest="scene_ids")
    parser.add_argument("--shot", action="append", dest="shot_numbers", type=int)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--seed", type=int, default=42)
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    generate(
        prompts_path=args.prompts,
        sub_module=args.output_sub_module,
        scene_ids=args.scene_ids,
        shot_numbers=args.shot_numbers,
        skip_existing=args.skip_existing,
        timeout_seconds=args.timeout_seconds,
        seed_base=args.seed,
    )


if __name__ == "__main__":
    main()
