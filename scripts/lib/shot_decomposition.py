"""Build second-accurate shot lists from directing_package.json (Flux + VO + BGM)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def parse_timestamp(ts: str | float | int) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts).strip()
    if not s:
        return 0.0
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    parts = s.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"Bad timestamp: {ts!r}")


def format_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m = int(seconds // 60)
    s = int(round(seconds - m * 60))
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"


def format_shot_time(start: float, end: float) -> str:
    return f"{int(round(start))}–{int(round(end))}s"


def _index_image_prompts(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows or []:
        sid = row.get("scene_id")
        if sid:
            out[sid] = row
    return out


def _fallback_flux_prompt(scene: dict, style: str) -> str:
    mode = scene.get("visual_mode") or "illustrated"
    text = scene.get("on_screen_text") or scene.get("vo_excerpt") or ""
    motion = scene.get("motion") or "gentle hold"
    anchor = "The friendly Guide mascot is on screen left." if scene.get("anchor_present") else "No characters; full-frame graphic."
    return (
        f"{style} Bright flat 2D cartoon educational frame, visual mode {mode}. "
        f"{anchor} {motion}. Large readable sans-serif on-screen label: \"{text}\". "
        "High contrast, classroom-friendly, Assam geography lesson."
    )


def _beat_vo_chunks(script: list[dict], scene_table: list[dict]) -> dict[str, str]:
    """Map each scene_id to narration text (full beat VO split by scene duration)."""
    if not script:
        return {s["scene_id"]: (s.get("vo_excerpt") or "") for s in scene_table}

    scenes_by_beat: dict[int, list[dict]] = {}
    for sc in scene_table:
        t = parse_timestamp(sc.get("time_start", "0:00"))
        beat_idx = 0
        for i, row in enumerate(script):
            bs = parse_timestamp(row.get("time_start", "0:00"))
            be = parse_timestamp(row.get("time_end", "0:00"))
            if bs <= t < be or (i == len(script) - 1 and t >= bs):
                beat_idx = i
                break
        scenes_by_beat.setdefault(beat_idx, []).append(sc)

    vo_map: dict[str, str] = {}
    for beat_idx, group in scenes_by_beat.items():
        row = script[beat_idx]
        vo = (row.get("vo") or "").strip()
        if not vo:
            for sc in group:
                vo_map[sc["scene_id"]] = sc.get("vo_excerpt") or ""
            continue
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", vo) if s.strip()]
        if not sentences:
            sentences = [vo]
        total_dur = sum(int(sc.get("duration_seconds") or 15) for sc in group) or 1
        sent_cursor = 0
        for j, sc in enumerate(group):
            excerpt = (sc.get("vo_excerpt") or "").strip()
            if excerpt and len(group) == 1:
                vo_map[sc["scene_id"]] = excerpt
                continue
            dur = int(sc.get("duration_seconds") or 15)
            if j == len(group) - 1:
                chunk = " ".join(sentences[sent_cursor:])
            else:
                n_sents = max(1, round(len(sentences) * (dur / total_dur)))
                chunk = " ".join(sentences[sent_cursor : sent_cursor + n_sents])
                sent_cursor += n_sents
            vo_map[sc["scene_id"]] = chunk.strip() or excerpt
    return vo_map


def _scale_durations(scene_table: list[dict], target_seconds: float) -> list[int]:
    raw = [max(1, int(s.get("duration_seconds") or 15)) for s in scene_table]
    total = sum(raw) or 1
    scaled = [max(1, int(round(d * target_seconds / total))) for d in raw]
    drift = int(round(target_seconds)) - sum(scaled)
    if drift != 0 and scaled:
        scaled[-1] = max(1, scaled[-1] + drift)
    return scaled


def _shots_for_scene(
    *,
    scene: dict,
    flux_prompt: str,
    narration: str,
    duration: int,
    style: str,
) -> list[dict]:
    mode = (scene.get("visual_mode") or "illustrated").lower()
    on_screen = scene.get("on_screen_text") or ""
    motion = scene.get("motion") or "hold"
    anchor = bool(scene.get("anchor_present"))

    def base_shot(shot_num: int, stype: str, dur: int, dialogue: str | None, flux: str) -> dict:
        return {
            "shot": shot_num,
            "duration_seconds": dur,
            "type": stype,
            "flux_frame": flux.strip(),
            "image_caption": flux.strip(),
            "wan_motion": motion if shot_num == 1 else "subtle hold, minimal camera move",
            "dialogue": dialogue,
            "narration_line": dialogue,
            "on_screen_text": on_screen if stype in {"TEXT", "INSERT", "MATH INSERT"} else None,
            "characters_in_frame": ["Y"] if anchor and stype == "WIDE" else [],
            "sfx_note": scene.get("sfx_note") or "",
            "music_cue": scene.get("music_cue") or "",
        }

    d = duration
    if anchor and d >= 12:
        w1 = max(4, int(round(d * 0.3)))
        w2 = max(5, int(round(d * 0.45)))
        w3 = max(3, d - w1 - w2)
        guide = (
            f"{style} WIDE shot. Friendly Guide mascot (flat 2D cartoon) faces camera, "
            f"classroom map studio background. {motion}. "
        )
        return [
            base_shot(1, "WIDE", w1, None, guide + f"Teaser label: \"{on_screen or 'Assam'}\"."),
            base_shot(2, "INSERT" if mode == "map" else "MEDIUM", w2, narration or None, flux_prompt),
            base_shot(
                3,
                "TEXT",
                w3,
                None,
                f"{style} Clean text card, large sans-serif: \"{on_screen}\". Soft gradient background.",
            ),
        ]
    if d >= 10:
        w1 = max(4, int(round(d * 0.4)))
        w2 = d - w1
        return [
            base_shot(1, "WIDE" if mode == "map" else "INSERT", w1, None, flux_prompt),
            base_shot(2, "MEDIUM", w2, narration or None, flux_prompt),
        ]
    return [base_shot(1, "INSERT", d, narration or None, flux_prompt)]


def build_shot_decomposition(
    package: dict,
    *,
    target_runtime_seconds: int | None = None,
    series_profile: dict | None = None,
) -> dict:
    scene_table = list(package.get("scene_table") or [])
    if not scene_table:
        raise ValueError("directing package has empty scene_table")

    target = int(
        target_runtime_seconds
        if target_runtime_seconds is not None
        else package.get("runtime_target_seconds")
        or 600
    )
    style = (package.get("style_guide") or "Bright flat 2D cartoon explainer.").strip()
    prompts = _index_image_prompts(package.get("image_prompts") or [])
    vo_map = _beat_vo_chunks(package.get("script") or [], scene_table)
    scaled_durs = _scale_durations(scene_table, float(target))

    visual_style_guide: dict[str, Any] = {"style_summary": style[:500]}
    if series_profile:
        visual_style_guide["cast"] = series_profile.get("cast") or {}
        visual_style_guide["reference_root"] = series_profile.get("reference_photos_root")

    scenes_out: list[dict] = []
    narration_timeline: list[dict] = []
    global_start = 0.0
    shot_index = 0

    for idx, scene in enumerate(scene_table):
        sid = scene.get("scene_id") or f"S{idx+1:02d}"
        dur = scaled_durs[idx]
        prompt_row = prompts.get(sid)
        flux = (prompt_row.get("prompt") if prompt_row else None) or _fallback_flux_prompt(scene, style)
        narration = vo_map.get(sid) or scene.get("vo_excerpt") or ""

        scene_start = global_start
        shots = _shots_for_scene(
            scene=scene,
            flux_prompt=flux,
            narration=narration,
            duration=dur,
            style=style,
        )

        shot_cursor = scene_start
        for sh in shots:
            shot_index += 1
            sd = int(sh["duration_seconds"])
            sh["time"] = format_shot_time(shot_cursor, shot_cursor + sd)
            sh["time_start_seconds"] = round(shot_cursor, 2)
            sh["time_end_seconds"] = round(shot_cursor + sd, 2)
            sh["global_shot_index"] = shot_index
            if sh.get("narration_line"):
                narration_timeline.append(
                    {
                        "shot_index": shot_index,
                        "scene_id": sid,
                        "time_start": format_timestamp(shot_cursor),
                        "time_end": format_timestamp(shot_cursor + sd),
                        "text": sh["narration_line"],
                    }
                )
            shot_cursor += sd

        scenes_out.append(
            {
                "scene_id": sid,
                "director_scene_id": sid,
                "time_start": format_timestamp(scene_start),
                "duration_seconds": dur,
                "beat": scene.get("vo_excerpt") or narration[:120],
                "visual_mode": scene.get("visual_mode"),
                "on_screen_text": scene.get("on_screen_text"),
                "render_type": "wan",
                "topic_ids": [],
                "shots": shots,
            }
        )
        global_start += dur

    total_runtime = round(global_start, 1)
    title = package.get("recommended_title") or package.get("title") or "Untitled"

    audio_cues = list(package.get("audio_cue_sheet") or [])
    if audio_cues:
        last = audio_cues[-1]
        end_ts = format_timestamp(total_runtime)
        if parse_timestamp(last.get("time_end", "0:00")) < total_runtime - 1:
            last = {**last, "time_end": end_ts}
            audio_cues[-1] = last

    return {
        "story_title": title,
        "chapter": package.get("chapter"),
        "tone_target": style[:200],
        "total_runtime_target_seconds": target,
        "total_runtime_seconds": total_runtime,
        "total_runtime_target": format_timestamp(total_runtime),
        "visual_style_guide": visual_style_guide,
        "audio_cue_sheet": audio_cues,
        "narration_timeline": narration_timeline,
        "scenes": scenes_out,
        "stats": {
            "scene_count": len(scenes_out),
            "shot_count": shot_index,
            "narration_lines": len(narration_timeline),
        },
    }


def render_shots_md(decomp: dict) -> str:
    lines = [
        f"# Shot decomposition: {decomp.get('story_title')}",
        "",
        f"- Chapter: {decomp.get('chapter', '—')}",
        f"- Runtime: **{decomp.get('total_runtime_target')}** ({decomp.get('total_runtime_seconds')} s)",
        f"- Scenes: {decomp['stats']['scene_count']} | Shots: {decomp['stats']['shot_count']} | VO lines: {decomp['stats']['narration_lines']}",
        "",
        "## Narration (ready for TTS)",
        "",
    ]
    for row in decomp.get("narration_timeline") or []:
        lines.append(
            f"- **{row['time_start']}–{row['time_end']}** ({row['scene_id']}, shot {row['shot_index']}): {row['text']}"
        )
    lines.extend(["", "## Shots by scene", ""])
    for scene in decomp.get("scenes") or []:
        lines.append(f"### {scene['scene_id']} @ {scene['time_start']} ({scene['duration_seconds']}s)")
        if scene.get("on_screen_text"):
            lines.append(f"*On screen:* {scene['on_screen_text']}")
        lines.append("")
        for sh in scene.get("shots") or []:
            lines.append(f"#### Shot {sh['shot']} — {sh['type']} ({sh['duration_seconds']}s, {sh['time']})")
            if sh.get("narration_line"):
                lines.append(f"**Say:** {sh['narration_line']}")
            lines.append("")
            lines.append("**Image caption (Flux):**")
            lines.append("")
            lines.append(sh.get("image_caption") or sh.get("flux_frame") or "")
            lines.append("")
            if sh.get("music_cue") or sh.get("sfx_note"):
                lines.append(f"*BGM cue:* {sh.get('music_cue') or '—'} | *SFX:* {sh.get('sfx_note') or '—'}")
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_shot_decomposition(
    package_path: Path,
    out_dir: Path,
    *,
    target_runtime_seconds: int | None = None,
    series_profile_path: Path | None = None,
) -> Path:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    series_profile = None
    if series_profile_path and series_profile_path.is_file():
        series_profile = json.loads(series_profile_path.read_text(encoding="utf-8"))
    decomp = build_shot_decomposition(
        package,
        target_runtime_seconds=target_runtime_seconds,
        series_profile=series_profile,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "shot_decomposition.json"
    json_path.write_text(json.dumps(decomp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "shots.md").write_text(render_shots_md(decomp), encoding="utf-8")
    (out_dir / "narration_manifest.json").write_text(
        json.dumps({"lines": decomp.get("narration_timeline") or []}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return json_path
