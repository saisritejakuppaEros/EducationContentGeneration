"""Build LLM director briefs from textbook manifest + video plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paths import KNOWLEDGE_DIR, PROJECT_ROOT


def _index_subchapters(manifest: dict[str, Any]) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for ch in manifest.get("chapters") or []:
        for sub in ch.get("subchapters") or []:
            sid = sub.get("subchapter_id") or sub.get("section_id")
            if sid:
                by_id[sid] = {**sub, "chapter_id": ch.get("chapter_id"), "chapter_title": ch.get("title")}
    return by_id


def _section_rows(manifest: dict[str, Any], section_ids: list[str]) -> list[dict]:
    by_id = {s["section_id"]: s for s in manifest.get("sections") or []}
    return [by_id[sid] for sid in section_ids if sid in by_id]


def _playbook_excerpt(max_chars: int = 3500) -> str:
    path = KNOWLEDGE_DIR / "context.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    return text[:max_chars].strip()


def _series_bible_summary(series_bible_path: Path | None) -> str:
    if not series_bible_path or not series_bible_path.is_file():
        return "(Series bible not loaded.)"
    bible = json.loads(series_bible_path.read_text(encoding="utf-8"))
    lines = [
        f"- Textbook tone: {bible.get('target_tone', '—')}",
        f"- World premise: {bible.get('world', {}).get('premise', '—')}",
        "- Cast: same cartoon guide for M, F, Y (assets/cartoon/image.png)",
    ]
    for key, info in (bible.get("cast") or {}).items():
        lines.append(f"  - {key}: {info.get('role', 'Guide')} — {info.get('description', '')[:120]}")
    vg = bible.get("visual_grammar") or {}
    if vg.get("grade"):
        lines.append(f"- Visual grade: {vg['grade']}")
    return "\n".join(lines)


def build_director_brief(
    *,
    manifest: dict[str, Any],
    video: dict[str, Any],
    plan: dict[str, Any],
    series_bible_path: Path | None = None,
    include_playbook: bool = True,
) -> str:
    meta = manifest.get("metadata") or {}
    sub_by_id = _index_subchapters(manifest)
    sections = _section_rows(manifest, video.get("section_ids") or [])

    lines = [
        "# Director brief — textbook video unit",
        "",
        "## Textbook context",
        f"- Book id: `{manifest.get('book_id')}`",
        f"- Subject: {meta.get('subject', plan.get('subject', '—'))}",
        f"- Class: {meta.get('class_level', plan.get('class_level', '—'))}",
        f"- Textbook: {meta.get('textbook_name') or meta.get('textbook_title', '—')}",
        f"- Lesson: {meta.get('lesson_number', '—')} — {meta.get('lesson_title', '—')}",
        "",
        "## This video unit",
        f"- Video id: `{video.get('video_id')}`",
        f"- Title: {video.get('title', '—')}",
        f"- Target runtime: ~{video.get('runtime_minutes', 8)} minutes",
        f"- Narration language: **English only** (all VO, titles, on-screen labels — translate syllabus faithfully from source)",
        f"- Hook angle: {video.get('hook_angle', '—')}",
        "",
        "### Continuation (same textbook series)",
        f"- Group: {video.get('continuation_group') or plan.get('book_id')}",
        f"- Previous: {video.get('continues_from') or 'none — open with lesson context'}",
        f"- Next: {video.get('continues_to') or 'none — close with recap + teaser if applicable'}",
        "",
        "## Series / cast (director)",
        _series_bible_summary(series_bible_path),
        "",
    ]

    for sec in sections:
        sid = sec.get("section_id")
        block = sub_by_id.get(sec.get("subchapter_id") or sid) or {}
        topic = sub_by_id.get(block.get("linked_topic_id", ""), {})
        lo = sub_by_id.get(block.get("linked_learning_outcome_id", ""), {})

        lines.extend(
            [
                f"## Teaching block `{sid}`",
                "",
                f"**Topic outline:** {topic.get('title') or topic.get('summary') or '—'}",
                f"**Learning outcome:** {lo.get('title') or lo.get('summary') or '—'}",
                "",
                "### Lesson plan source (DIKSHA / NCERT — ground truth)",
                "",
                (sec.get("body") or sec.get("summary") or "").strip(),
                "",
            ]
        )

    ch = (manifest.get("chapters") or [None])[0]
    if ch and ch.get("vocabulary"):
        lines.extend(["## Key vocabulary", "", ", ".join(ch["vocabulary"]), ""])

    if include_playbook:
        excerpt = _playbook_excerpt()
        if excerpt:
            lines.extend(
                [
                    "## Explainer patterns (reference — do not quote verbatim)",
                    "",
                    excerpt,
                    "",
                ]
            )

    lines.extend(
        [
            "## Director instructions",
            "",
            "- Turn this **syllabus-accurate** lesson block into a single explainer **story** with hook, turns, and payoff.",
            "- **English only:** every `vo`, `script`, `on_screen`, `on_screen_text`, `title`, `recommended_title`, and `image_prompts` string must be **English** (Latin script). Source text may be Assamese — translate; do not output Assamese/Bengali in those fields.",
            "- Use the **cartoon guide** (M/F/Y same design) as host; maps/diagrams for geography concepts.",
            "- Timeline-first: beats + VO script + scene_table + image_prompts + audio_cue_sheet.",
            "- Stay within NCERT/DIKSHA content; mark uncertain claims in qa_notes.",
            "",
        ]
    )
    return "\n".join(lines)
