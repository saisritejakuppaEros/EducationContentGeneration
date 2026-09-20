"""Chapter / subchapter hierarchy from NCERT and DIKSHA PDFs."""

from __future__ import annotations

import re
from typing import Any

from textbook_pdf import (
    _bn_digits_to_int,
    _split_learning_outcome_lines,
    extract_rf_sections,
    parse_lesson_metadata,
)


def detect_document_type(full_text: str, page_count: int) -> str:
    head = full_text[:4000]
    if re.search(r"পাঠ\s*আদান|5E|DIKSHA|পৰিকল্পনা", head, re.I):
        return "diksha_lesson_plan"
    if page_count <= 15 and re.search(r"ৰ(?:ৰ)?(?:্ি)?(?:\:|\∶)?ফ", head):
        return "diksha_lesson_plan"
    return "textbook"


def _clean_line(line: str) -> str:
    return line.strip(" ৷.·\t ")


def parse_topic_outline_subchapters(full_text: str) -> list[dict[str, Any]]:
    """Section চ) — short topic bullets for the lesson."""
    topics: list[dict[str, Any]] = []
    for i, line in enumerate(_split_learning_outcome_lines(full_text), start=1):
        topics.append(
            {
                "subchapter_id": f"topic_{i}",
                "kind": "topic",
                "index": i,
                "title": _clean_line(line),
                "summary": _clean_line(line),
            }
        )
    return topics


def parse_formal_learning_outcomes(full_text: str) -> list[dict[str, Any]]:
    """Section ছ) — numbered learning outcomes."""
    outcomes: list[dict[str, Any]] = []
    block_started = False
    buf: list[str] = []

    def ingest_numbered(num: str, text: str) -> None:
        nonlocal buf
        if buf:
            outcomes.append(_flush_outcome(buf, len(outcomes) + 1))
            buf = []
        buf = [text.strip()]

    for raw in full_text.splitlines():
        line = raw.strip()
        if re.search(r"^ছ\)", line):
            block_started = True
            for m in re.finditer(r"([০-৯\d]+)\)\s*(.+?)(?=\s*[০-৯\d]+\)\s|$)", line):
                ingest_numbered(m.group(1), m.group(2))
            continue
        if block_started and re.search(r"^[য-হ]\)", line):
            break
        if not block_started:
            continue
        m = re.match(r"^([০-৯\d]+)\)\s*(.+)", line)
        if m:
            ingest_numbered(m.group(1), m.group(2))
        elif buf and line and not re.match(r"^Page\s*\|", line):
            buf.append(line)
    if buf:
        outcomes.append(_flush_outcome(buf, len(outcomes) + 1))
    return outcomes


def _flush_outcome(lines: list[str], n: int) -> dict[str, Any]:
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "subchapter_id": f"lo_{n}",
        "kind": "learning_outcome",
        "index": n,
        "title": text[:160],
        "summary": text,
    }


def parse_key_vocabulary(full_text: str) -> list[str]:
    terms: list[str] = []
    in_vocab = False
    for raw in full_text.splitlines():
        line = _clean_line(raw)
        if re.search(r"^য\)", line) or ("শব্দসূচ" in line and "য)" in line):
            in_vocab = True
            continue
        if in_vocab and re.search(r"^[ঝ-হ]\)", line):
            break
        if in_vocab and 2 < len(line) < 80 and not line.startswith("Page"):
            if not re.search(r"পাঠ|পৰিকল্পন|QR", line):
                terms.append(line)
    return terms


def _rf_display_title(body: str, rf_num: int) -> str:
    for line in body.splitlines()[1:8]:
        line = line.strip()
        if len(line) < 20:
            continue
        if re.search(r"শমশনট|Page\s*\|", line):
            continue
        if "ছাত্ৰ" in line or "students" in line.lower():
            return re.sub(r"\s+", " ", line)[:200]
    return f"Lesson block {rf_num}"


def enrich_rf_blocks(rf_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for sec in rf_sections:
        num = sec.get("index") or 0
        body = sec.get("body") or ""
        enriched.append(
            {
                **sec,
                "subchapter_id": sec.get("section_id") or f"rf{num}",
                "kind": "lesson_block",
                "title": _rf_display_title(body, num),
            }
        )
    return enriched


def parse_worksheets(full_text: str) -> list[dict[str, Any]]:
    worksheets: list[dict[str, Any]] = []
    pattern = re.compile(
        r"তাশলক[^\n]*ন[^\n]*[∶:\s]*([০-৯\d]+)([\s\S]*?)(?=তাশলক[^\n]*ন[^\n]*[∶:\s]*[০-৯\d]+|$)",
        re.MULTILINE,
    )
    for m in pattern.finditer(full_text):
        num = _bn_digits_to_int(m.group(1))
        body = m.group(2).strip()
        if len(body) < 5:
            continue
        worksheets.append(
            {
                "subchapter_id": f"worksheet_{num}",
                "kind": "worksheet",
                "index": num,
                "title": f"Worksheet {num}",
                "body": body[:8000],
            }
        )
    return worksheets


# Full textbook heading detection (English + Indic digits)
CHAPTER_LINE = re.compile(
    r"^(?:"
    r"(?:CHAPTER|Chapter|UNIT|Unit|LESSON|Lesson|Part)\s*[:\-\.]?\s*"
    r"([0-9]+|[০-৯]+)\s*[:\-\.]?\s*(.+)"
    r"|(?:পাঠ|অধ্যায়|অধ্যায়)\s*[:\-\.]?\s*"
    r"([0-9]+|[০-৯]+)\s*[:\-\.]?\s*(.+)"
    r"|([0-9]{1,2})\.\s+(.{8,120})"
    r")$",
    re.UNICODE,
)

SUBCHAPTER_LINE = re.compile(
    r"^(\d+\.\d+(?:\.\d+)?)\s+(.{5,200})$"
)


def extract_textbook_chapters_from_pages(pages: list[str]) -> list[dict[str, Any]]:
    """Scan page text for chapter / subchapter headings (full NCERT PDFs)."""
    chapters: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    page_num = 0

    def start_chapter(num: str, title: str, page: int) -> None:
        nonlocal current
        n = str(_bn_digits_to_int(num)) if num else str(len(chapters) + 1)
        cid = f"ch_{n.zfill(2)}"
        current = {
            "chapter_id": cid,
            "number": n,
            "title": title.strip(),
            "start_page": page,
            "subchapters": [],
            "body_parts": [],
        }
        chapters.append(current)

    for page_text in pages:
        page_num += 1
        for raw in page_text.splitlines():
            line = raw.strip()
            if len(line) < 4 or line.startswith("Page |"):
                continue

            sub_m = SUBCHAPTER_LINE.match(line)
            if sub_m and current:
                sid = sub_m.group(1).replace(".", "_")
                current["subchapters"].append(
                    {
                        "subchapter_id": f"{current['chapter_id']}.{sid}",
                        "kind": "section",
                        "index": len(current["subchapters"]) + 1,
                        "number": sub_m.group(1),
                        "title": sub_m.group(2).strip(),
                        "start_page": page_num,
                    }
                )
                continue

            ch_m = CHAPTER_LINE.match(line)
            if ch_m:
                g = ch_m.groups()
                num = g[0] or g[2] or g[4]
                title = g[1] or g[3] or g[5]
                if title and len(title) > 3:
                    start_chapter(num, title, page_num)
                    continue

            if current and len(line) > 30:
                current["body_parts"].append(line)

    for ch in chapters:
        ch["body"] = "\n".join(ch.pop("body_parts", []))[:50000]
        if not ch["subchapters"]:
            ch["subchapters"].append(
                {
                    "subchapter_id": f"{ch['chapter_id']}.1",
                    "kind": "section",
                    "index": 1,
                    "title": ch["title"],
                    "start_page": ch.get("start_page"),
                    "body": ch.get("body", "")[:12000],
                }
            )
    return chapters


def build_lesson_plan_hierarchy(
    *,
    full_text: str,
    pages: list[str],
    meta: dict[str, Any],
) -> dict[str, Any]:
    lesson_num = meta.get("lesson_number") or "1"
    try:
        ln = str(_bn_digits_to_int(str(lesson_num)))
    except ValueError:
        ln = str(lesson_num)
    title = (
        meta.get("lesson_title")
        or meta.get("textbook_title")
        or f"Lesson {ln}"
    )
    chapter_id = f"lesson_{ln}"

    topics = parse_topic_outline_subchapters(full_text)
    outcomes = parse_formal_learning_outcomes(full_text)
    rf_raw = extract_rf_sections(full_text, pages)
    lesson_blocks = enrich_rf_blocks(rf_raw)
    worksheets = parse_worksheets(full_text)
    vocabulary = parse_key_vocabulary(full_text)

    subchapters: list[dict[str, Any]] = []
    subchapters.extend(topics)
    subchapters.extend(outcomes)

    for i, block in enumerate(lesson_blocks):
        linked_topic = topics[i]["subchapter_id"] if i < len(topics) else None
        linked_lo = outcomes[i]["subchapter_id"] if i < len(outcomes) else None
        subchapters.append(
            {
                **block,
                "section_id": block.get("section_id") or block.get("subchapter_id"),
                "linked_topic_id": linked_topic,
                "linked_learning_outcome_id": linked_lo,
            }
        )

    subchapters.extend(worksheets)

    return {
        "document_type": "diksha_lesson_plan",
        "chapter_count": 1,
        "subchapter_count": len(subchapters),
        "chapters": [
            {
                "chapter_id": chapter_id,
                "number": ln,
                "title": title,
                "page_range": [1, len(pages)],
                "metadata": meta,
                "vocabulary": vocabulary,
                "subchapters": subchapters,
            }
        ],
    }


def build_textbook_hierarchy(*, full_text: str, pages: list[str], meta: dict[str, Any]) -> dict[str, Any]:
    chapters = extract_textbook_chapters_from_pages(pages)
    if len(chapters) < 2:
        # Likely not a multi-chapter scan — treat whole PDF as one chapter
        return build_lesson_plan_hierarchy(full_text=full_text, pages=pages, meta=meta)

    sub_count = sum(len(c.get("subchapters") or []) for c in chapters)
    return {
        "document_type": "textbook",
        "chapter_count": len(chapters),
        "subchapter_count": sub_count,
        "chapters": chapters,
    }


def build_hierarchy(*, full_text: str, pages: list[str], meta: dict[str, Any]) -> dict[str, Any]:
    doc_type = detect_document_type(full_text, len(pages))
    if doc_type == "diksha_lesson_plan":
        return build_lesson_plan_hierarchy(full_text=full_text, pages=pages, meta=meta)
    return build_textbook_hierarchy(full_text=full_text, pages=pages, meta=meta)


def flatten_teaching_sections(hierarchy: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat list for video planner — prefer lesson_block, else topic sections."""
    flat: list[dict[str, Any]] = []
    for ch in hierarchy.get("chapters") or []:
        cid = ch.get("chapter_id", "ch")
        blocks = [s for s in ch.get("subchapters") or [] if s.get("kind") == "lesson_block"]
        if blocks:
            for b in blocks:
                flat.append(
                    {
                        "section_id": b.get("section_id") or b.get("subchapter_id"),
                        "chapter_id": cid,
                        "subchapter_id": b.get("subchapter_id"),
                        "index": b.get("index"),
                        "title": b.get("title"),
                        "body": b.get("body"),
                        "kind": b.get("kind"),
                        "source": "lesson_block",
                    }
                )
        else:
            for b in ch.get("subchapters") or []:
                if b.get("kind") in ("topic", "section"):
                    flat.append(
                        {
                            "section_id": b.get("subchapter_id"),
                            "chapter_id": cid,
                            "subchapter_id": b.get("subchapter_id"),
                            "index": b.get("index"),
                            "title": b.get("title"),
                            "body": b.get("body") or b.get("summary"),
                            "kind": b.get("kind"),
                            "source": "subchapter",
                        }
                    )
    if not flat:
        flat.append(
            {
                "section_id": "full_document",
                "title": "Full document",
                "body": "",
                "kind": "full",
                "source": "fallback",
            }
        )
    return flat


def render_chapters_markdown(hierarchy: dict[str, Any], meta: dict[str, Any]) -> str:
    lines = [
        f"# Textbook structure: {meta.get('lesson_title') or meta.get('textbook_title') or 'PDF'}",
        "",
        f"- Document type: **{hierarchy.get('document_type')}**",
        f"- Chapters: **{hierarchy.get('chapter_count', 0)}**",
        f"- Subchapters (all kinds): **{hierarchy.get('subchapter_count', 0)}**",
        "",
    ]
    for ch in hierarchy.get("chapters") or []:
        lines.append(f"## Chapter {ch.get('number', '?')}: {ch.get('title', ch.get('chapter_id'))}")
        lines.append("")
        if ch.get("vocabulary"):
            lines.append("**Key terms:** " + ", ".join(ch["vocabulary"][:12]))
            lines.append("")
        for sub in ch.get("subchapters") or []:
            kind = sub.get("kind", "?")
            sid = sub.get("subchapter_id") or sub.get("section_id")
            title = sub.get("title", sid)
            lines.append(f"- `{sid}` ({kind}) — {title[:100]}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
