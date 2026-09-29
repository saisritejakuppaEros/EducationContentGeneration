"""Cinematic FFmpeg filters, overlays, and audio mixing."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


def run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def escape_drawtext(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())[:120]
    return (
        cleaned.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
    )


def cinematic_video_filter(base_scale: str, *, fade_in: float = 0.25, fade_out: float = 0.25, duration: float) -> str:
    """Scale/pad + subtle grade + shot fades."""
    fade_out_start = max(0.0, duration - fade_out)
    grade = "eq=contrast=1.06:saturation=1.07:brightness=0.01"
    fades = f"fade=t=in:st=0:d={fade_in},fade=t=out:st={fade_out_start}:d={fade_out}"
    return f"{base_scale},{grade},{fades}"


def overlay_lower_third(base_vf: str, label: str | None) -> str:
    if not label:
        return base_vf
    text = escape_drawtext(label)
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    font_part = f"fontfile={font}:" if font.is_file() else ""
    draw = (
        f"drawtext={font_part}"
        f"text='{text}':fontsize=36:fontcolor=white:borderw=3:bordercolor=black@0.6:"
        f"x=(w-text_w)/2:y=h*0.82"
    )
    return f"{base_vf},{draw}"


def concat_audio_cues(cue_paths: list[Path], output_wav: Path, sample_rate: int = 48000) -> None:
    if not cue_paths:
        raise ValueError("No BGM cues")
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    if len(cue_paths) == 1:
        run_ffmpeg(["-i", str(cue_paths[0]), "-ar", str(sample_rate), "-ac", "2", str(output_wav)])
        return

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tmp:
        for p in cue_paths:
            tmp.write(f"file '{p.resolve()}'\n")
        list_path = tmp.name
    run_ffmpeg(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-ar",
            str(sample_rate),
            "-ac",
            "2",
            str(output_wav),
        ]
    )
    Path(list_path).unlink(missing_ok=True)


def mix_voice_and_bgm(
    *,
    video_in: Path,
    voice_wav: Path | None,
    bgm_wav: Path | None,
    srt_path: Path | None,
    output_mp4: Path,
    bgm_volume: float = 0.22,
) -> None:
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    inputs = ["-i", str(video_in)]
    filter_parts: list[str] = []
    audio_maps: list[str] = []

    if voice_wav and voice_wav.is_file():
        inputs.extend(["-i", str(voice_wav)])
        filter_parts.append("[1:a]volume=1.0[voice]")
        audio_maps.append("[voice]")

    if bgm_wav and bgm_wav.is_file():
        idx = 2 if voice_wav and voice_wav.is_file() else 1
        inputs.extend(["-i", str(bgm_wav)])
        filter_parts.append(f"[{idx}:a]volume={bgm_volume},afade=t=in:st=0:d=2,afade=t=out:st=0:d=3[bgm]")
        audio_maps.append("[bgm]")

    vf = "copy"
    if srt_path and srt_path.is_file():
        vf = f"subtitles={srt_path}:force_style='FontSize=22,PrimaryColour=&HFFFFFF&,Outline=2'"

    if filter_parts:
        if len(audio_maps) == 2:
            filter_parts.append(f"{audio_maps[0]}{audio_maps[1]}amix=inputs=2:duration=first:dropout_transition=2[aout]")
            audio_label = "[aout]"
        else:
            audio_label = audio_maps[0]
        fc = ";".join(filter_parts)
        run_ffmpeg(
            [
                *inputs,
                "-filter_complex",
                fc,
                "-map",
                "0:v:0",
                "-map",
                audio_label,
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(output_mp4),
            ]
        )
        return

    if vf != "copy":
        run_ffmpeg(
            [
                "-i",
                str(video_in),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                str(output_mp4),
            ]
        )
    else:
        run_ffmpeg(["-i", str(video_in), "-c", "copy", str(output_mp4)])
