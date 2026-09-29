"""Consistent narration / character TTS (separate from in-clip LTX speech)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceSpec:
    engine: str
    voice_id: str
    language: str
    speed: float = 1.0
    clone_ref: Path | None = None
    persona: str | None = None


DEFAULT_NARRATION = VoiceSpec(
    engine="edge_tts",
    voice_id="en-IN-NeerjaNeural",
    language="en",
    speed=1.0,
)

EDGE_VOICE_BY_LANG = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
}


def _narration_block(series_profile: dict) -> dict:
    return series_profile.get("narration_voice") or {}


def resolve_narration_voice(series_profile: dict, lang: str = "en") -> VoiceSpec:
    block = _narration_block(series_profile)
    engine = (block.get("engine") or os.environ.get("NARRATION_TTS_ENGINE") or "edge_tts").strip()
    voice_id = (
        block.get("voice_id")
        or os.environ.get("NARRATION_VOICE_ID")
        or EDGE_VOICE_BY_LANG.get(lang, DEFAULT_NARRATION.voice_id)
    )
    language = block.get("language") or lang
    speed = float(block.get("speed") or 1.0)
    clone = block.get("clone_ref")
    clone_path = Path(clone) if clone else None
    if clone_path and not clone_path.is_file():
        clone_path = None
    persona = block.get("persona")
    return VoiceSpec(
        engine=engine,
        voice_id=str(voice_id),
        language=str(language),
        speed=speed,
        clone_ref=clone_path,
        persona=persona,
    )


def resolve_voice_for_line(
    series_profile: dict,
    character: str | None,
    lang: str = "en",
) -> VoiceSpec:
    """One stable narrator by default; optional per-character overrides in series profile."""
    narration = resolve_narration_voice(series_profile, lang)
    cast = series_profile.get("cast", {})
    char_key = (character or "Y").strip()
    profile = cast.get(char_key, {}).get("voice_profile") or {}
    overrides = series_profile.get("character_voices") or {}

    use_narrator = profile.get("use_narrator_voice")
    if use_narrator is None and char_key in ("M", "F", "Y"):
        use_narrator = overrides.get(char_key, True)
    if use_narrator is True or use_narrator is None:
        if char_key == "Y" or not profile.get("edge_voice"):
            return narration

    engine = profile.get("engine") or narration.engine
    voice_id = profile.get("edge_voice") or profile.get("voice_id") or narration.voice_id
    if lang != "en" and not profile.get("edge_voice"):
        voice_id = EDGE_VOICE_BY_LANG.get(lang, voice_id)
    speed = float(profile.get("speed") or narration.speed)
    return VoiceSpec(
        engine=str(engine),
        voice_id=str(voice_id),
        language=lang if lang != "en" else narration.language,
        speed=speed,
        clone_ref=narration.clone_ref,
        persona=profile.get("persona") or narration.persona,
    )


def synthesize_to_file(text: str, output_path: Path, spec: VoiceSpec) -> bool:
    text = (text or "").strip()
    if not text:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if spec.engine == "edge_tts":
        return _synthesize_edge_tts(text, output_path, spec)
    if spec.engine in ("xai_tts", "xai/tts-v1", "openai_compatible"):
        return _synthesize_openai_compatible(text, output_path, spec)
    if spec.engine in ("seed_audio", "bytedance/seed-audio-1.0") and spec.clone_ref:
        return _synthesize_seed_audio_clone(text, output_path, spec)
    return _synthesize_edge_tts(text, output_path, spec)


def _synthesize_edge_tts(text: str, output_path: Path, spec: VoiceSpec) -> bool:
    try:
        import edge_tts
    except ImportError:
        return False

    rate_pct = int(round((spec.speed - 1.0) * 100))
    rate = f"{rate_pct:+d}%" if rate_pct else "+0%"

    async def _run() -> None:
        communicate = edge_tts.Communicate(text, spec.voice_id, rate=rate)
        await communicate.save(str(output_path))

    try:
        asyncio.run(_run())
        return output_path.is_file() and output_path.stat().st_size > 0
    except Exception:
        return False


def _openai_tts_config() -> tuple[str, str, str]:
    base = (
        os.environ.get("OPENAI_API_BASE")
        or os.environ.get("NARRATION_TTS_API_BASE")
        or ""
    ).rstrip("/")
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("NARRATION_TTS_API_KEY") or ""
    model = os.environ.get("NARRATION_TTS_MODEL") or "xai/tts-v1"
    return base, key, model


def _synthesize_openai_compatible(text: str, output_path: Path, spec: VoiceSpec) -> bool:
    base, key, model = _openai_tts_config()
    if not base or not key:
        return False
    url = f"{base}/audio/speech"
    payload = {
        "model": model,
        "input": text,
        "voice": spec.voice_id,
        "language": spec.language,
        "speed": spec.speed,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            output_path.write_bytes(resp.read())
        return output_path.is_file() and output_path.stat().st_size > 0
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _synthesize_seed_audio_clone(text: str, output_path: Path, spec: VoiceSpec) -> bool:
    base, key, _model = _openai_tts_config()
    if not base or not key or not spec.clone_ref or not spec.clone_ref.is_file():
        return False
    ref_b64 = base64.b64encode(spec.clone_ref.read_bytes()).decode("ascii")
    persona = spec.persona or "YouTube tutorial creator"
    prompt = (
        f"**Speaker A** @audio1 keeps their own vocal timbre and speaks fluent natural "
        f"{spec.language}. Persona: {persona}. Text: {text}"
    )
    payload = {
        "model": "bytedance/seed-audio-1.0",
        "input": prompt,
        "references": [{"audio_data": ref_b64}],
    }
    url = f"{base}/audio/speech"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            output_path.write_bytes(resp.read())
        return output_path.is_file() and output_path.stat().st_size > 0
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
