"""Shared dialogue length helpers for screenplay and storyboard stages."""

from __future__ import annotations

import copy
import re

MAX_DIALOGUE_WORDS = 15

SPEAKER_PREFIX = re.compile(r"^([MFY]):\s*")


def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def parse_dialogue_line(dialogue: str | dict | None) -> dict | None:
    if not dialogue:
        return None
    if isinstance(dialogue, dict):
        character = dialogue.get("character")
        line = (dialogue.get("line") or "").strip()
        if not line:
            return None
        return {"character": character, "line": line}

    text = str(dialogue).strip()
    match = SPEAKER_PREFIX.match(text)
    if match:
        character = match.group(1)
        line = text[match.end() :].strip().strip('"')
        return {"character": character, "line": line}
    return {"character": None, "line": text}


def format_dialogue(entry: dict | None) -> str | None:
    if not entry:
        return None
    character = entry.get("character")
    line = entry.get("line", "")
    if character:
        return f'{character}: "{line}"'
    return line


def split_line_at_natural_break(line: str, max_words: int = MAX_DIALOGUE_WORDS) -> list[str]:
    words = line.split()
    if len(words) <= max_words:
        return [line.strip()]

    target = len(words) // 2
    best_idx: int | None = None
    best_distance = len(words)

    for idx in range(2, len(words) - 1):
        if words[idx - 1].endswith((",", ";", ":", "—", "-")):
            distance = abs(idx - target)
            if distance < best_distance:
                best_distance = distance
                best_idx = idx

    conjunctions = {"and", "but", "so", "because", "then", "while", "when", "or"}
    for idx in range(2, len(words) - 1):
        if words[idx].lower() in conjunctions:
            distance = abs(idx - target)
            if distance < best_distance:
                best_distance = distance
                best_idx = idx

    if best_idx is None:
        best_idx = target

    first = " ".join(words[:best_idx]).strip()
    second = " ".join(words[best_idx:]).strip()
    if not first or not second:
        return [line.strip()]
    return [first, second]


def split_dialogue_entry(entry: dict, max_words: int = MAX_DIALOGUE_WORDS) -> list[dict]:
    parts = split_line_at_natural_break(entry["line"], max_words)
    character = entry.get("character")
    return [{"character": character, "line": part} for part in parts]


def split_screenplay_dialogue(screenplay: dict, max_words: int = MAX_DIALOGUE_WORDS) -> dict:
    result = copy.deepcopy(screenplay)
    for scene in result.get("scenes", []):
        expanded: list[dict] = []
        for entry in scene.get("dialogue", []):
            parsed = parse_dialogue_line(entry)
            if not parsed:
                continue
            if word_count(parsed["line"]) <= max_words:
                expanded.append(parsed)
            else:
                expanded.extend(split_dialogue_entry(parsed, max_words))
        scene["dialogue"] = expanded
    return result


def split_storyboard_shots(shots: list[dict], max_words: int = MAX_DIALOGUE_WORDS) -> list[dict]:
    expanded: list[dict] = []
    for shot in shots:
        parsed = parse_dialogue_line(shot.get("dialogue"))
        if not parsed or word_count(parsed["line"]) <= max_words:
            expanded.append(shot)
            continue

        parts = split_dialogue_entry(parsed, max_words)
        total_words = max(1, word_count(parsed["line"]))
        base_duration = float(shot.get("duration_seconds") or 6.0)

        for idx, part in enumerate(parts):
            new_shot = copy.deepcopy(shot)
            part_words = max(1, word_count(part["line"]))
            new_shot["dialogue"] = format_dialogue(part)
            new_shot["duration_seconds"] = round(base_duration * (part_words / total_words), 1)
            if idx > 0 and new_shot.get("type") not in {"MATH INSERT", "INSERT", "TITLE"}:
                new_shot["type"] = "REACTION"
            expanded.append(new_shot)

    for idx, shot in enumerate(expanded, start=1):
        shot["shot"] = idx
    return expanded


def truncate_speech_for_ltx(speech: str | None, max_words: int = MAX_DIALOGUE_WORDS) -> str:
    if not speech:
        return ""
    words = speech.split()
    if len(words) <= max_words:
        return speech.strip()
    return " ".join(words[:max_words]).strip()


def strip_on_screen_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"floating (white )?text reads '[^']*'", "glowing abstract symbol", cleaned, flags=re.I)
    cleaned = re.sub(r"text reads '[^']*'", "glowing abstract symbol", cleaned, flags=re.I)
    cleaned = re.sub(r"floating text [^.]*\.", "glowing abstract symbols.", cleaned, flags=re.I)
    cleaned = re.sub(r"text appears[^.]*\.", "abstract glowing symbols appear.", cleaned, flags=re.I)
    cleaned = re.sub(r"labeled '[^']*'", "with glowing markers", cleaned, flags=re.I)
    cleaned = re.sub(r"reads '[^']*'", "shows abstract glyphs", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\b(subtitles?|captions?|on-screen text|title card text|letters|words on screen|sans-serif font)\b",
        "abstract glow",
        cleaned,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", cleaned).strip()
