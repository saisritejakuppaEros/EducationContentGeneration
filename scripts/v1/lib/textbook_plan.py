"""Heuristic video plan when LLM is unavailable."""

from __future__ import annotations

from typing import Any

from textbook_pdf import section_markdown


def heuristic_video_plan(manifest: dict[str, Any]) -> dict[str, Any]:
    meta = manifest.get("metadata") or {}
    sections = manifest.get("sections") or []
    videos = []
    prev_id: str | None = None
    for i, sec in enumerate(sections):
        sid = sec.get("section_id") or f"section_{i+1}"
        video_id = f"v{i+1:02d}_{sid}"
        title = (sec.get("title") or sid)[:100]
        videos.append(
            {
                "video_id": video_id,
                "title": title,
                "section_ids": [sid],
                "continuation_group": manifest.get("book_id"),
                "continues_from": prev_id,
                "continues_to": None,
                "runtime_minutes": 10,
                "narration_language": "en",
                "hook_angle": f"Why does {title[:60]} matter for Assam?",
            }
        )
        if prev_id and videos:
            videos[-2]["continues_to"] = video_id
        prev_id = video_id

    if not videos:
        videos.append(
            {
                "video_id": "v01_full_lesson",
                "title": meta.get("lesson_title") or "Full lesson",
                "section_ids": [s.get("section_id") for s in sections if s.get("section_id")],
                "continuation_group": manifest.get("book_id"),
                "continues_from": None,
                "continues_to": None,
                "runtime_minutes": 12,
                "narration_language": "en",
                "hook_angle": "What will we learn in this lesson?",
            }
        )

    plan = {
        "textbook_title": meta.get("lesson_title") or meta.get("textbook_title") or manifest.get("book_id"),
        "class_level": meta.get("class_level"),
        "subject": meta.get("subject"),
        "planning_rationale": "Heuristic: one video per extracted section (RF / outcome block).",
        "videos": videos,
        "book_id": manifest.get("book_id"),
    }
    for video in plan["videos"]:
        video["chapter_markdown"] = section_markdown(manifest, video.get("section_ids") or [])
    return plan
