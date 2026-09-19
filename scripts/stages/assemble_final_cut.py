#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from paths import (
    PROJECT_ROOT,
    add_output_root_argument,
    configure_output_root,
    get_output_root,
    output_dir,
    project_rel,
    resolve_project_path,
)

SUB_MODULE = "final_cut"

WIDTH = 1920
HEIGHT = 1080
FPS = 24
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
MATH_TYPES = {"MATH INSERT", "CONCEPT"}


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "final_cut"


def scale_filter() -> str:
    return (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}"
    )


def load_math_narration_map(audio_plan_path: Path) -> dict[tuple[str, int], Path]:
    if not audio_plan_path.is_file():
        return {}
    plan = json.loads(audio_plan_path.read_text(encoding="utf-8"))
    mapping: dict[tuple[str, int], Path] = {}
    for entry in plan.get("math_narration", []):
        rel = entry.get("path")
        if not rel:
            continue
        path = PROJECT_ROOT / rel
        if path.is_file():
            mapping[(entry["scene_id"], int(entry["shot"]))] = path
    return mapping


def resolve_shot_asset(
    *,
    scene_id: str,
    shot_num: int,
    shot_type: str,
    ltx_dir: Path,
    manim_dir: Path,
    flux_dir: Path,
    enable_manim: bool = False,
) -> Path | None:
    shot_tag = f"{scene_id}_shot{shot_num:02d}"
    if enable_manim and shot_type.upper() in MATH_TYPES:
        manim_clip = manim_dir / scene_id / f"{shot_tag}.mp4"
        if manim_clip.is_file():
            return manim_clip
        manim_final = manim_dir / scene_id / shot_tag / "final_video.mp4"
        if manim_final.is_file():
            return manim_final

    ltx_clip = ltx_dir / scene_id / f"{shot_tag}.mp4"
    if ltx_clip.is_file():
        return ltx_clip

    flux_still = flux_dir / scene_id / f"{shot_tag}.png"
    if flux_still.is_file():
        return flux_still
    return None


def normalize_clip(
    source: Path,
    duration: float,
    output: Path,
    *,
    narration_audio: Path | None = None,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    vf = scale_filter()

    if source.suffix.lower() in IMAGE_EXT:
        audio_input = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        if narration_audio and narration_audio.is_file():
            audio_input = ["-i", str(narration_audio)]
        run_ffmpeg(
            [
                "-loop",
                "1",
                "-i",
                str(source),
                *audio_input,
                "-t",
                str(duration),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(output),
            ]
        )
        return

    if narration_audio and narration_audio.is_file():
        run_ffmpeg(
            [
                "-i",
                str(source),
                "-i",
                str(narration_audio),
                "-t",
                str(duration),
                "-vf",
                vf,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-shortest",
                str(output),
            ]
        )
        return

    run_ffmpeg(
        [
            "-i",
            str(source),
            "-t",
            str(duration),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(output),
        ]
    )


def concat_clips(clips: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        for clip in clips:
            tmp.write(f"file '{clip.resolve()}'\n")
        list_path = tmp.name
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", str(output_path)])
    Path(list_path).unlink(missing_ok=True)


def collect_clips(
    storyboard: dict,
    ltx_dir: Path,
    manim_dir: Path,
    flux_dir: Path,
    *,
    enable_manim: bool = False,
) -> list[dict]:
    clips: list[dict] = []
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        for shot in scene.get("shots", []):
            shot_num = shot["shot"]
            shot_type = shot.get("type") or ""
            duration = float(shot.get("duration_seconds") or 5)
            source = resolve_shot_asset(
                scene_id=scene_id,
                shot_num=shot_num,
                shot_type=shot_type,
                ltx_dir=ltx_dir,
                manim_dir=manim_dir,
                flux_dir=flux_dir,
                enable_manim=enable_manim,
            )
            if source is None:
                print(f"skip missing: {scene_id} shot {shot_num}")
                continue
            clips.append(
                {
                    "scene_id": scene_id,
                    "shot": shot_num,
                    "type": shot_type,
                    "duration_seconds": duration,
                    "source": str(source.relative_to(PROJECT_ROOT)),
                }
            )
    return clips


def assemble(
    *,
    storyboard_path: Path,
    assets_root: Path,
    audio_plan_path: Path,
    output_name: str,
    enable_manim: bool = False,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    ltx_dir = assets_root / "cinematic_videos"
    if not ltx_dir.is_dir() or not any(ltx_dir.rglob("*.mp4")):
        legacy_ltx = assets_root / "ltx_videos"
        if legacy_ltx.is_dir():
            ltx_dir = legacy_ltx

    manim_dir = assets_root / "manim_videos"
    flux_dir = assets_root / "storyboard"
    if not any(flux_dir.rglob("*.png")):
        legacy_flux = assets_root / "flux_images"
        if legacy_flux.is_dir():
            flux_dir = legacy_flux

    math_narration = load_math_narration_map(audio_plan_path)
    clip_plan = collect_clips(storyboard, ltx_dir, manim_dir, flux_dir, enable_manim=enable_manim)
    if not clip_plan:
        raise RuntimeError("No clips found to assemble.")

    out_dir = output_dir(SUB_MODULE)
    final_path = out_dir / f"{output_name}_en.mp4"

    with tempfile.TemporaryDirectory(prefix="final_cut_") as tmp:
        work_dir = Path(tmp)
        normalized: list[Path] = []
        for idx, clip in enumerate(clip_plan):
            source = resolve_project_path(clip["source"])
            normalized_path = work_dir / f"clip_{idx:04d}.mp4"
            narration = None
            if clip["type"].upper() in MATH_TYPES:
                narration = math_narration.get((clip["scene_id"], clip["shot"]))
            normalize_clip(
                source,
                clip["duration_seconds"],
                normalized_path,
                narration_audio=narration,
            )
            normalized.append(normalized_path)
            clip["normalized"] = normalized_path.name
            if narration:
                clip["math_narration"] = str(narration.relative_to(PROJECT_ROOT))

        concat_clips(normalized, final_path)

    manifest = {
        "title": storyboard.get("story_title") or storyboard.get("chapter"),
        "output": str(final_path.relative_to(PROJECT_ROOT)),
        "clip_count": len(clip_plan),
        "assets_root": str(assets_root.relative_to(PROJECT_ROOT)),
        "ltx_dir": str(ltx_dir.relative_to(PROJECT_ROOT)),
        "flux_dir": str(flux_dir.relative_to(PROJECT_ROOT)),
        "clips": clip_plan,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Concatenate storyboard clips into one English final cut.")
    add_output_root_argument(parser)
    parser.add_argument("--storyboard", type=Path, default=None)
    parser.add_argument("--assets-root", type=Path, default=None)
    parser.add_argument("--audio-plan", type=Path, default=None)
    parser.add_argument("--output-name", default=None, help="Output base name (default: slug from story title).")
    parser.add_argument(
        "--enable-manim",
        action="store_true",
        help="Prefer Manim MP4s for MATH INSERT / CONCEPT shots when present.",
    )
    args = parser.parse_args()

    configure_output_root(args.output_root)
    assets_root = args.assets_root or get_output_root()
    print(f"Output root: {project_rel(assets_root)}/")
    storyboard_path = args.storyboard or assets_root / "storyboard" / "storyboard.json"
    audio_plan_path = args.audio_plan or assets_root / "audio" / "audio_plan.json"

    if not storyboard_path.is_file():
        raise FileNotFoundError(f"storyboard not found: {storyboard_path}")

    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    output_name = args.output_name or slugify(
        storyboard.get("story_title") or storyboard.get("chapter") or "final_cut"
    )

    manifest = assemble(
        storyboard_path=storyboard_path,
        assets_root=assets_root,
        audio_plan_path=audio_plan_path,
        output_name=output_name,
        enable_manim=args.enable_manim,
    )
    print(f"Wrote {manifest['output']} ({manifest['clip_count']} clips)")


if __name__ == "__main__":
    main()
