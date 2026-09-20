"""Build narration timeline aligned to storyboard shot order."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any


def _dialogue_text(dialogue: Any) -> tuple[str | None, str | None]:
    if not dialogue:
        return None, None
    if isinstance(dialogue, dict):
        return dialogue.get("character"), dialogue.get("line")
    text = str(dialogue).strip()
    match = re.match(r"^([MFY]):\s*(.+)$", text)
    if match:
        line = match.group(2).strip().strip('"')
        return match.group(1), line
    return None, text


def _wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "r") as wav:
            return wav.getnframes() / float(wav.getframerate())
    except wave.Error:
        return 0.0


def build_dialogue_lookup(audio_plan: dict) -> list[dict]:
    return list(audio_plan.get("dialogue_lines") or [])


def match_dialogue_wav(
    *,
    scene_id: str,
    character: str | None,
    line: str | None,
    dialogue_lines: list[dict],
    scene_line_index: dict[str, int],
) -> Path | None:
    if not line:
        return None
    norm = line.strip().lower()
    for entry in dialogue_lines:
        if entry.get("scene_id") != scene_id:
            continue
        eline = (entry.get("line") or "").strip().lower()
        if eline == norm or norm in eline or eline in norm:
            rel = entry.get("path")
            if rel:
                from paths import PROJECT_ROOT

                p = PROJECT_ROOT / rel if not str(rel).startswith("/") else Path(rel)
                if not p.is_file():
                    p = Path(rel)
                if p.is_file():
                    return p
    idx = scene_line_index.get(scene_id, 0)
    scene_entries = [e for e in dialogue_lines if e.get("scene_id") == scene_id]
    if idx < len(scene_entries):
        rel = scene_entries[idx].get("path")
        if rel:
            from paths import PROJECT_ROOT

            p = PROJECT_ROOT / rel
            if p.is_file():
                scene_line_index[scene_id] = idx + 1
                return p
    return None


def build_voice_timeline(
    *,
    storyboard: dict,
    audio_plan_path: Path,
    sample_rate: int = 48000,
) -> tuple[Path | None, list[dict]]:
    if not audio_plan_path.is_file():
        return None, []

    plan = json.loads(audio_plan_path.read_text(encoding="utf-8"))
    dialogue_lines = build_dialogue_lookup(plan)
    if not dialogue_lines:
        return None, []

    events: list[dict] = []
    timeline_cursor = 0.0
    scene_line_index: dict[str, int] = {}

    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        for shot in scene.get("shots", []):
            dur = float(shot.get("duration_seconds") or 5.0)
            character, line = _dialogue_text(shot.get("dialogue"))
            wav = match_dialogue_wav(
                scene_id=scene_id,
                character=character,
                line=line,
                dialogue_lines=dialogue_lines,
                scene_line_index=scene_line_index,
            )
            if wav:
                events.append(
                    {
                        "scene_id": scene_id,
                        "shot": shot.get("shot"),
                        "start_seconds": round(timeline_cursor, 3),
                        "path": str(wav),
                        "line": line,
                    }
                )
            timeline_cursor += dur

    if not events:
        return None, []

    total_duration = timeline_cursor
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out_path = Path(tmp.name)

    # Silent bed then overlay each line at its start.
    from cinematic_ffmpeg import run_ffmpeg

    run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=stereo",
            "-t",
            str(max(1.0, total_duration)),
            str(out_path),
        ]
    )

    for event in events:
        start = event["start_seconds"]
        merged = out_path.with_suffix(".merge.wav")
        run_ffmpeg(
            [
                "-i",
                str(out_path),
                "-i",
                str(event["path"]),
                "-filter_complex",
                f"[1:a]adelay={int(start * 1000)}|{int(start * 1000)}[d];[0:a][d]amix=inputs=2:duration=first:dropout_transition=0",
                str(merged),
            ]
        )
        out_path.unlink(missing_ok=True)
        merged.rename(out_path)

    return out_path, events
