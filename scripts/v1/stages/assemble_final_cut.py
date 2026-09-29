#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json
import re
import tempfile
from pathlib import Path

from audio_timeline import build_voice_timeline
from scene_ids import scene_id_aliases
from cinematic_ffmpeg import cinematic_video_filter, concat_audio_cues, mix_voice_and_bgm, overlay_lower_third, run_ffmpeg
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


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "final_cut"


def scale_filter_base() -> str:
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
        path = PROJECT_ROOT / rel if not str(rel).startswith("/") else Path(rel)
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
    html_dir: Path,
    flux_dir: Path,
    enable_manim: bool = False,
    enable_html_inserts: bool = False,
) -> Path | None:
    if shot_type.upper() in MATH_TYPES:
        if enable_html_inserts:
            for sid in scene_id_aliases(scene_id):
                shot_tag = f"{sid}_shot{shot_num:02d}"
                html_clip = html_dir / sid / f"{shot_tag}.mp4"
                if html_clip.is_file():
                    return html_clip
        if enable_manim:
            for sid in scene_id_aliases(scene_id):
                shot_tag = f"{sid}_shot{shot_num:02d}"
                manim_clip = manim_dir / sid / f"{shot_tag}.mp4"
                if manim_clip.is_file():
                    return manim_clip
                manim_final = manim_dir / sid / shot_tag / "final_video.mp4"
                if manim_final.is_file():
                    return manim_final

    for sid in scene_id_aliases(scene_id):
        shot_tag = f"{sid}_shot{shot_num:02d}"
        candidates = [
            ltx_dir / sid / f"{shot_tag}.mp4",
            ltx_dir / sid / f"{shot_tag}_take02.mp4",
            ltx_dir / sid / f"{shot_tag}_take01.mp4",
            ltx_dir / sid / f"{shot_tag}_best.mp4",
            ltx_dir / f"{shot_tag}.mp4",
            flux_dir / sid / f"{shot_tag}.png",
            flux_dir / scene_id / f"{scene_id}_shot{shot_num:02d}.png",
        ]
        for path in candidates:
            if path.is_file():
                return path
    return None


def _dialogue_label(dialogue) -> str | None:
    if not dialogue:
        return None
    if isinstance(dialogue, dict):
        line = dialogue.get("line") or ""
    else:
        text = str(dialogue).strip()
        match = re.match(r"^[MFY]:\s*(.+)$", text)
        line = match.group(1).strip('"') if match else text
    line = line.strip()
    return line[:100] if line else None


def normalize_clip(
    source: Path,
    duration: float,
    output: Path,
    *,
    narration_audio: Path | None = None,
    lower_third: str | None = None,
    cinematic: bool = True,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    base = scale_filter_base()
    vf = cinematic_video_filter(base, duration=duration) if cinematic else base
    vf = overlay_lower_third(vf, lower_third)

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


def load_bgm_cues(assets_root: Path) -> list[Path]:
    manifest_path = assets_root / "background_audio" / "manifest.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cues: list[Path] = []
    for cue in manifest.get("cues") or []:
        rel = cue.get("path")
        if not rel:
            continue
        p = assets_root / rel if not Path(rel).is_absolute() else Path(rel)
        if not p.is_file():
            p = PROJECT_ROOT / rel
        if p.is_file():
            cues.append(p)
    return cues


def find_subtitles(assets_root: Path, chapter: str) -> Path | None:
    subs_dir = assets_root / "audio" / "subtitles" / "en"
    if not subs_dir.is_dir():
        return None
    candidates = list(subs_dir.glob("*.srt"))
    if not candidates:
        return None
    slug = slugify(chapter)
    for c in candidates:
        if slug in slugify(c.stem):
            return c
    return candidates[0]


def collect_clips(
    storyboard: dict,
    ltx_dir: Path,
    manim_dir: Path,
    html_dir: Path,
    flux_dir: Path,
    *,
    enable_manim: bool = False,
    enable_html_inserts: bool = False,
    max_clips: int | None = None,
) -> list[dict]:
    clips: list[dict] = []
    shot_lookup: dict[tuple[str, int], dict] = {}
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        for shot in scene.get("shots", []):
            shot_num = shot["shot"]
            shot_lookup[(scene_id, shot_num)] = shot

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
                html_dir=html_dir,
                flux_dir=flux_dir,
                enable_manim=enable_manim,
                enable_html_inserts=enable_html_inserts,
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
                    "lower_third": _dialogue_label(shot.get("dialogue")),
                }
            )
            if max_clips is not None and len(clips) >= max_clips:
                return clips
    return clips


def assemble(
    *,
    storyboard_path: Path,
    assets_root: Path,
    audio_plan_path: Path,
    output_name: str,
    enable_manim: bool = False,
    enable_html_inserts: bool = False,
    cinematic: bool = True,
    mix_audio: bool = True,
    bgm_volume: float = 0.22,
    max_clips: int | None = None,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    ltx_dir = assets_root / "cinematic_videos"
    if not ltx_dir.is_dir() or not any(ltx_dir.rglob("*.mp4")):
        legacy_ltx = assets_root / "ltx_videos"
        if legacy_ltx.is_dir():
            ltx_dir = legacy_ltx

    manim_dir = assets_root / "manim_videos"
    html_dir = assets_root / "html_inserts"
    flux_dir = assets_root / "storyboard"
    if not any(flux_dir.rglob("*.png")):
        legacy_flux = assets_root / "flux_images"
        if legacy_flux.is_dir():
            flux_dir = legacy_flux

    math_narration = load_math_narration_map(audio_plan_path)
    clip_plan = collect_clips(
        storyboard,
        ltx_dir,
        manim_dir,
        html_dir,
        flux_dir,
        enable_manim=enable_manim,
        enable_html_inserts=enable_html_inserts,
        max_clips=max_clips,
    )
    if not clip_plan:
        raise RuntimeError("No clips found to assemble.")

    out_dir = output_dir(SUB_MODULE)
    final_path = out_dir / f"{output_name}_en.mp4"
    silent_concat = out_dir / f"{output_name}_picture_en.mp4"

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
                lower_third=clip.get("lower_third"),
                cinematic=cinematic,
            )
            normalized.append(normalized_path)
            clip["normalized"] = normalized_path.name
            if narration:
                clip["math_narration"] = str(narration.relative_to(PROJECT_ROOT))

        concat_clips(normalized, silent_concat)

    voice_wav = None
    voice_events: list[dict] = []
    if mix_audio:
        voice_wav, voice_events = build_voice_timeline(
            storyboard=storyboard,
            audio_plan_path=audio_plan_path,
        )

    bgm_wav = None
    cue_paths = load_bgm_cues(assets_root)
    if mix_audio and cue_paths:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_bgm:
            bgm_wav = Path(tmp_bgm.name)
        try:
            concat_audio_cues(cue_paths, bgm_wav)
        except RuntimeError:
            bgm_wav.unlink(missing_ok=True)
            bgm_wav = None

    chapter = storyboard.get("story_title") or storyboard.get("chapter") or output_name
    srt = find_subtitles(assets_root, str(chapter))

    if mix_audio and (voice_wav or bgm_wav or srt):
        mix_voice_and_bgm(
            video_in=silent_concat,
            voice_wav=voice_wav,
            bgm_wav=bgm_wav,
            srt_path=srt,
            output_mp4=final_path,
            bgm_volume=bgm_volume,
        )
        if voice_wav and voice_wav.is_file():
            voice_wav.unlink(missing_ok=True)
        if bgm_wav and bgm_wav.is_file():
            bgm_wav.unlink(missing_ok=True)
    else:
        if srt and srt.is_file():
            run_ffmpeg(
                [
                    "-i",
                    str(silent_concat),
                    "-vf",
                    f"subtitles={srt}:force_style='FontSize=22,PrimaryColour=&HFFFFFF&,Outline=2'",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    str(final_path),
                ]
            )
        else:
            silent_concat.rename(final_path)

    manifest = {
        "title": chapter,
        "output": str(final_path.relative_to(PROJECT_ROOT)),
        "picture_output": str(silent_concat.relative_to(PROJECT_ROOT)) if silent_concat.is_file() else None,
        "clip_count": len(clip_plan),
        "assets_root": str(assets_root.relative_to(PROJECT_ROOT)),
        "ltx_dir": str(ltx_dir.relative_to(PROJECT_ROOT)),
        "flux_dir": str(flux_dir.relative_to(PROJECT_ROOT)),
        "voice_events": voice_events,
        "bgm_cues": len(cue_paths),
        "subtitles": str(srt.relative_to(PROJECT_ROOT)) if srt else None,
        "clips": clip_plan,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble cinematic final cut with VO, BGM, and captions.")
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
    parser.add_argument(
        "--enable-html-inserts",
        action="store_true",
        help="Prefer HTML-rendered MP4s (stage 5h) for insert shots when present.",
    )
    parser.add_argument("--no-cinematic-grade", action="store_true", help="Disable color grade and shot fades.")
    parser.add_argument("--no-audio-mix", action="store_true", help="Skip VO/BGM mux (video concat only).")
    parser.add_argument("--bgm-volume", type=float, default=0.22)
    parser.add_argument("--max-clips", type=int, default=None, help="Assemble only the first N resolved clips (smoke test).")
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
        enable_html_inserts=args.enable_html_inserts,
        cinematic=not args.no_cinematic_grade,
        mix_audio=not args.no_audio_mix,
        bgm_volume=args.bgm_volume,
        max_clips=args.max_clips,
    )
    print(f"Wrote {manifest['output']} ({manifest['clip_count']} clips)")


if __name__ == "__main__":
    main()
