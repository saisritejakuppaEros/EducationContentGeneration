#!/usr/bin/env python3
import argparse
import json
import math
import wave
from pathlib import Path

from gemma_utils import fill_user_prompt, load_prompt_template
from paths import DEFAULT_LLM_BACKEND, PROMPTS_DIR, output_dir
from pipeline_utils import run_llm_json, write_json

SUB_MODULE = "audio"
DEFAULT_SCREENPLAY = output_dir("screenplay") / "screenplay.json"
DEFAULT_SERIES_BIBLE = output_dir("series_bible") / "series_bible.json"
DEFAULT_STORYBOARD = output_dir("storyboard") / "storyboard.json"
DEFAULT_DUB_PROMPT = PROMPTS_DIR / "audio_dubbing.md"

DEFAULT_LANGUAGES = ["en", "hi", "ta"]
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}
DEFAULT_WPM = 150


def words_per_minute_for_character(series_bible: dict, character: str) -> float:
    pace = (
        series_bible.get("cast", {})
        .get(character, {})
        .get("voice_profile", {})
        .get("pace", "normal")
    )
    pace_map = {"slow": 120, "measured": 130, "normal": 150, "brisk": 170, "fast": 190}
    if isinstance(pace, (int, float)):
        return float(pace)
    return pace_map.get(str(pace).lower(), DEFAULT_WPM)


def estimate_line_duration(line: str, wpm: float) -> float:
    words = max(1, len(line.split()))
    return max(1.0, (words / wpm) * 60.0)


def collect_dialogue_lines(screenplay: dict, series_bible: dict) -> list[dict]:
    lines: list[dict] = []
    for scene in screenplay.get("scenes", []):
        scene_id = scene["scene_id"]
        for entry in scene.get("dialogue", []):
            character = entry.get("character", "Y")
            line = entry.get("line", "")
            wpm = words_per_minute_for_character(series_bible, character)
            duration = estimate_line_duration(line, wpm)
            lines.append(
                {
                    "scene_id": scene_id,
                    "character": character,
                    "line": line,
                    "estimated_duration_seconds": round(duration, 2),
                    "wpm": wpm,
                }
            )
    return lines


def reconcile_shot_durations(storyboard: dict, lines: list[dict]) -> list[dict]:
    by_scene: dict[str, list[dict]] = {}
    for line in lines:
        by_scene.setdefault(line["scene_id"], []).append(line)

    adjustments: list[dict] = []
    for scene in storyboard.get("scenes", []):
        scene_id = scene["scene_id"]
        scene_lines = by_scene.get(scene_id, [])
        line_total = sum(l["estimated_duration_seconds"] for l in scene_lines)
        shot_total = sum(s.get("duration_seconds") or 0 for s in scene.get("shots", []))
        if shot_total and line_total > shot_total:
            adjustments.append(
                {
                    "scene_id": scene_id,
                    "line_total_seconds": round(line_total, 2),
                    "shot_total_seconds": round(shot_total, 2),
                    "action": "extend_shots_or_trim_dialogue",
                }
            )
    return adjustments


def write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * num_frames)


def synthesize_with_edge_tts(text: str, output_path: Path, voice: str) -> bool:
    try:
        import asyncio
        import edge_tts
    except ImportError:
        return False

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))

    try:
        asyncio.run(_run())
        return output_path.is_file()
    except Exception:
        return False


def default_voice_for_character(series_bible: dict, character: str, lang: str) -> str:
    accent = (
        series_bible.get("cast", {})
        .get(character, {})
        .get("voice_profile", {})
        .get("accent", "")
    )
    if lang == "en":
        if "indian" in str(accent).lower():
            return "en-IN-NeerjaNeural"
        return "en-US-AriaNeural"
    if lang == "hi":
        return "hi-IN-SwaraNeural"
    if lang == "ta":
        return "ta-IN-PallaviNeural"
    return "en-US-AriaNeural"


def localize_language(
    *,
    screenplay: dict,
    language: str,
    timing_budget: str,
    prompt_path: Path,
    backend: str,
    model_path: Path,
) -> dict:
    system_prompt, user_template = load_prompt_template(prompt_path)

    def validate(data: dict) -> None:
        if data.get("language") != language or "lines" not in data:
            raise ValueError("Invalid localization response")

    return run_llm_json(
        backend=backend,
        system_prompt=system_prompt,
        user_prompt=fill_user_prompt(
            user_template,
            screenplay=json.dumps(screenplay, indent=2, ensure_ascii=False),
            language_code=language,
            language_name=LANGUAGE_NAMES.get(language, language),
            timing_budget=timing_budget,
        ),
        validate=validate,
        model_path=model_path,
        max_tokens=8192,
    )


def generate(
    *,
    screenplay_path: Path,
    series_bible_path: Path,
    storyboard_path: Path,
    languages: list[str],
    dub_prompt_path: Path,
    backend: str,
    model_path: Path,
    synthesize: bool,
    skip_dub: bool,
) -> dict:
    screenplay = json.loads(screenplay_path.read_text(encoding="utf-8"))
    series_bible = (
        json.loads(series_bible_path.read_text(encoding="utf-8"))
        if series_bible_path.is_file()
        else {"cast": {}}
    )
    storyboard = (
        json.loads(storyboard_path.read_text(encoding="utf-8"))
        if storyboard_path.is_file()
        else {"scenes": []}
    )

    out_dir = output_dir(SUB_MODULE)
    lines = collect_dialogue_lines(screenplay, series_bible)
    adjustments = reconcile_shot_durations(storyboard, lines)

    source_files: list[dict] = []
    for idx, line in enumerate(lines):
        rel = out_dir / "source" / f"{line['scene_id']}_{idx:03d}_{line['character']}.wav"
        if synthesize:
            voice = default_voice_for_character(series_bible, line["character"], "en")
            ok = synthesize_with_edge_tts(line["line"], rel, voice)
            if not ok:
                write_silent_wav(rel, line["estimated_duration_seconds"])
        else:
            write_silent_wav(rel, line["estimated_duration_seconds"])
        source_files.append({**line, "path": str(rel.relative_to(out_dir.parent.parent)).replace("\\", "/")})

    sfx_dir = out_dir / "sfx"
    sfx_dir.mkdir(parents=True, exist_ok=True)
    for scene in storyboard.get("scenes", []):
        duration = scene.get("duration_seconds") or 30
        sfx_path = sfx_dir / f"{scene['scene_id']}.wav"
        if not sfx_path.is_file():
            write_silent_wav(sfx_path, duration)

    score_path = out_dir / "score" / "chapter_cue01.wav"
    if not score_path.is_file():
        write_silent_wav(score_path, 60.0)

    dub_manifest: dict[str, list] = {}
    if not skip_dub:
        timing_budget = json.dumps(adjustments, indent=2)
        for lang in languages:
            if lang == "en":
                dub_manifest[lang] = [{"original": l["line"], "localized": l["line"], **l} for l in lines]
                continue
            localized = localize_language(
                screenplay=screenplay,
                language=lang,
                timing_budget=timing_budget,
                prompt_path=dub_prompt_path,
                backend=backend,
                model_path=model_path,
            )
            dub_manifest[lang] = localized.get("lines", [])
            dub_dir = out_dir / "dub" / lang
            dub_dir.mkdir(parents=True, exist_ok=True)
            for idx, entry in enumerate(dub_manifest[lang]):
                text = entry.get("localized") or entry.get("line", "")
                character = entry.get("character", "Y")
                wav_path = dub_dir / f"{entry.get('scene_id', 'SC')}_{idx:03d}_{character}.wav"
                duration = entry.get("target_duration_seconds") or lines[idx]["estimated_duration_seconds"]
                if synthesize:
                    voice = default_voice_for_character(series_bible, character, lang)
                    if not synthesize_with_edge_tts(text, wav_path, voice):
                        write_silent_wav(wav_path, duration)
                else:
                    write_silent_wav(wav_path, duration)

    subtitles_dir = out_dir / "subtitles"
    subtitles_dir.mkdir(parents=True, exist_ok=True)
    for lang, entries in dub_manifest.items():
        srt_path = subtitles_dir / lang / f"{screenplay.get('chapter', 'chapter')}.srt"
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_lines = []
        t = 0.0
        for idx, entry in enumerate(entries, start=1):
            dur = lines[idx - 1]["estimated_duration_seconds"] if idx - 1 < len(lines) else 3.0
            start = t
            end = t + dur
            text = entry.get("localized") or entry.get("line", "")
            srt_lines.append(f"{idx}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n")
            t = end
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    plan = {
        "chapter": screenplay.get("chapter"),
        "languages": languages,
        "dialogue_lines": source_files,
        "timing_adjustments": adjustments,
        "dub": dub_manifest,
        "synthesize": synthesize,
    }
    return plan


def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - math.floor(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan and generate audio assets (timing, voice, dub, subtitles).")
    parser.add_argument("--screenplay", type=Path, default=DEFAULT_SCREENPLAY)
    parser.add_argument("--series-bible", type=Path, default=DEFAULT_SERIES_BIBLE)
    parser.add_argument("--storyboard", type=Path, default=DEFAULT_STORYBOARD)
    parser.add_argument("--languages", default=",".join(DEFAULT_LANGUAGES))
    parser.add_argument("--dub-prompt", type=Path, default=DEFAULT_DUB_PROMPT)
    parser.add_argument("--backend", choices=["gemma", "qwen"], default=DEFAULT_LLM_BACKEND)
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--synthesize", action="store_true", help="Use edge-tts when installed.")
    parser.add_argument("--skip-dub", action="store_true")
    args = parser.parse_args()

    from paths import DEFAULT_GEMMA_MODEL

    if not args.screenplay.is_file():
        raise FileNotFoundError(f"screenplay not found: {args.screenplay}")

    languages = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    model_path = args.model_path or DEFAULT_GEMMA_MODEL

    plan = generate(
        screenplay_path=args.screenplay,
        series_bible_path=args.series_bible,
        storyboard_path=args.storyboard,
        languages=languages,
        dub_prompt_path=args.dub_prompt,
        backend=args.backend,
        model_path=model_path,
        synthesize=args.synthesize,
        skip_dub=args.skip_dub,
    )

    out_path = output_dir(SUB_MODULE) / "audio_plan.json"
    write_json(out_path, plan)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
