#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from paths import PROJECT_ROOT, output_dir

SUB_MODULE = "final_cut"
DEFAULT_STORYBOARD = output_dir("storyboard") / "storyboard.json"
DEFAULT_CINEMATIC = output_dir("cinematic_videos")
DEFAULT_MANIM = output_dir("manim_videos")
DEFAULT_AUDIO = output_dir("audio")
DEFAULT_SERIES_BIBLE = output_dir("series_bible") / "series_bible.json"


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def video_for_shot(
    *,
    scene: dict,
    shot: dict,
    cinematic_dir: Path,
    manim_dir: Path,
) -> Path | None:
    scene_id = scene["scene_id"]
    shot_num = shot["shot"]
    shot_type = (shot.get("type") or "").upper()
    if shot_type == "MATH INSERT":
        topic_ids = scene.get("topic_ids") or []
        if topic_ids:
            topic_path = manim_dir / f"{topic_ids[0]}.mp4"
            if topic_path.is_file():
                return topic_path
        manim_shot = manim_dir / scene_id / f"{scene_id}_shot{shot_num:02d}.mp4"
        if manim_shot.is_file():
            return manim_shot
        return None

    cinematic = cinematic_dir / scene_id / f"{scene_id}_shot{shot_num:02d}.mp4"
    if cinematic.is_file():
        return cinematic

    keyframe = shot.get("keyframe_image")
    if keyframe:
        png = PROJECT_ROOT / keyframe
        if png.is_file():
            return png
    return None


def concat_videos(video_paths: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        for path in video_paths:
            tmp.write(f"file '{path.resolve()}'\n")
        list_path = tmp.name

    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            str(output_path),
        ]
    )
    Path(list_path).unlink(missing_ok=True)


def mux_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    run_ffmpeg(
        [
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
            str(output_path),
        ]
    )


def build_audio_bed(audio_dir: Path, scene_ids: list[str], out_wav: Path) -> Path | None:
    sfx_files = [audio_dir / "sfx" / f"{scene_id}.wav" for scene_id in scene_ids]
    existing = [p for p in sfx_files if p.is_file()]
    if not existing:
        score = audio_dir / "score" / "chapter_cue01.wav"
        return score if score.is_file() else None

    if len(existing) == 1:
        return existing[0]

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    inputs: list[str] = []
    for path in existing:
        inputs.extend(["-i", str(path)])
    run_ffmpeg([*inputs, "-filter_complex", f"concat=n={len(existing)}:v=0:a=1", str(out_wav)])
    return out_wav


def collect_ordered_videos(
    storyboard: dict,
    cinematic_dir: Path,
    manim_dir: Path,
) -> list[tuple[dict, dict, Path]]:
    clips: list[tuple[dict, dict, Path]] = []
    for scene in storyboard.get("scenes", []):
        for shot in scene.get("shots", []):
            path = video_for_shot(
                scene=scene,
                shot=shot,
                cinematic_dir=cinematic_dir,
                manim_dir=manim_dir,
            )
            if path is None:
                print(f"Warning: missing video for {scene['scene_id']} shot {shot['shot']}")
                continue
            if path.suffix.lower() == ".png":
                print(f"Warning: using still image fallback for {path.name}")
            clips.append((scene, shot, path))
    return clips


def write_edl(storyboard: dict, clip_entries: list[tuple[dict, dict, Path]], edl_path: Path) -> None:
    lines = ["TITLE: Chapter Final Cut", "FCM: NON-DROP FRAME", ""]
    record_in = 0.0
    for idx, (scene, shot, path) in enumerate(clip_entries, start=1):
        duration = shot.get("duration_seconds") or 5
        record_out = record_in + duration
        lines.append(
            f"{idx:03d}  AX       V     C        {record_in:06.2f} {record_out:06.2f} "
            f"{record_in:06.2f} {record_out:06.2f}"
        )
        lines.append(f"* FROM CLIP NAME: {path.name} ({scene['scene_id']} shot {shot['shot']})")
        record_in = record_out
    edl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def assemble(
    *,
    storyboard_path: Path,
    cinematic_dir: Path,
    manim_dir: Path,
    audio_dir: Path,
    languages: list[str],
    chapter_slug: str,
) -> dict:
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
    out_dir = output_dir(SUB_MODULE)
    clip_entries = collect_ordered_videos(storyboard, cinematic_dir, manim_dir)
    if not clip_entries:
        raise RuntimeError("No video clips found to assemble")

    video_paths = [entry[2] for entry in clip_entries]
    video_only = out_dir / f"{chapter_slug}_video_only.mp4"
    concat_videos(video_paths, video_only)

    scene_ids = [s["scene_id"] for s in storyboard.get("scenes", [])]
    audio_bed = build_audio_bed(audio_dir, scene_ids, out_dir / "sfx_bed.wav")

    outputs: dict[str, str] = {"video_only": str(video_only.relative_to(PROJECT_ROOT))}
    for lang in languages:
        final_path = out_dir / f"{chapter_slug}_{lang}.mp4"
        if lang == "en":
            source_files = sorted((audio_dir / "source").glob("*.wav")) if (audio_dir / "source").is_dir() else []
            if source_files:
                mux_audio(video_only, source_files[0], final_path)
            elif audio_bed:
                mux_audio(video_only, audio_bed, final_path)
            else:
                final_path.write_bytes(video_only.read_bytes())
        else:
            dub_files = sorted((audio_dir / "dub" / lang).glob("*.wav")) if (audio_dir / "dub" / lang).is_dir() else []
            if dub_files:
                mux_audio(video_only, dub_files[0], final_path)
            elif audio_bed:
                mux_audio(video_only, audio_bed, final_path)
            else:
                final_path.write_bytes(video_only.read_bytes())
        outputs[lang] = str(final_path.relative_to(PROJECT_ROOT))

    edl_path = out_dir / f"{chapter_slug}.edl"
    write_edl(storyboard, clip_entries, edl_path)
    outputs["edl"] = str(edl_path.relative_to(PROJECT_ROOT))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble final cut MP4(s) from storyboard + generated assets.")
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--cinematic-dir", type=Path, default=DEFAULT_CINEMATIC)
    parser.add_argument("--manim-dir", type=Path, default=DEFAULT_MANIM)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO)
    parser.add_argument("--languages", default="en,hi,ta")
    parser.add_argument("--chapter-slug", default="chapter")
    args = parser.parse_args()

    if not args.storyboard.is_file():
        raise FileNotFoundError(f"storyboard not found: {args.storyboard}")

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    outputs = assemble(
        storyboard_path=args.storyboard,
        cinematic_dir=args.cinematic_dir,
        manim_dir=args.manim_dir,
        audio_dir=args.audio_dir,
        languages=languages,
        chapter_slug=args.chapter_slug,
    )

    manifest_path = output_dir(SUB_MODULE) / "manifest.json"
    manifest_path.write_text(json.dumps(outputs, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {manifest_path}")
    for lang, path in outputs.items():
        if lang != "edl":
            print(f"  {lang}: {path}")


if __name__ == "__main__":
    main()
