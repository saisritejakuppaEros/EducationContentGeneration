"""Extract and structure text from NCERT / DIKSHA lesson-plan PDFs."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None  # type: ignore


def read_pdf_pages(pdf_path: Path) -> tuple[str, list[str]]:
    if pymupdf is None:
        raise RuntimeError("pymupdf is required: pip install pymupdf")
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    doc = pymupdf.open(str(pdf_path))
    pages = [page.get_text() or "" for page in doc]
    doc.close()
    full = "\n\n".join(pages)
    return full, pages


def _bn_digits_to_int(value: str) -> int:
    table = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
    return int(value.translate(table))


def slugify(text: str, *, max_len: int = 48) -> str:
    s = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    s = re.sub(r"[-\s]+", "_", s.strip()).strip("_").lower()
    if not s:
        s = "textbook"
    return s[:max_len]


def book_id_from_pdf(pdf_path: Path) -> str:
    stem = pdf_path.stem
    m = re.match(r"(do_\d+)", stem)
    if m:
        return m.group(1)
    return slugify(stem, max_len=64)


def _first_match(pattern: str, text: str, flags: int = 0) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


# Assamese/Bengali avagraha / visarga often appear instead of ASCII colons in PDF text.
_INDIC_COLON = r"[∶:\u0983]\s*"


def parse_lesson_metadata(full_text: str) -> dict[str, Any]:
    """Best-effort metadata from DIKSHA-style lesson plan cover page."""
    meta: dict[str, Any] = {
        "class_level": _first_match(rf"শ্ৰ[\s]*ণ[^\n]*{_INDIC_COLON}(\S+)", full_text)
        or _first_match(r"Class\s*[∶:]\s*(.+)", full_text, re.I),
        "subject": _first_match(rf"ৰিষ[^\n]*{_INDIC_COLON}(.+)", full_text)
        or _first_match(r"Subject\s*[∶:]\s*(.+)", full_text, re.I),
        "textbook_name": _first_match(rf"পাঠ[^\n]*পু[^\n]*নাম[^\n]*{_INDIC_COLON}(.+)", full_text),
        "lesson_number": _first_match(rf"পাঠ\s*ন[^\n]*{_INDIC_COLON}([০-৯\d]+)", full_text),
        "lesson_title": _first_match(rf"পাঠ.{{0,4}}নাম[^\n]*{_INDIC_COLON}(.+)", full_text)
        or _first_match(r"Lesson\s*[title]*\s*[∶:]\s*(.+)", full_text, re.I),
    }
    if meta.get("lesson_title"):
        meta["textbook_title"] = meta["lesson_title"]
    elif meta.get("textbook_name"):
        meta["textbook_title"] = meta["textbook_name"]
    return {k: v for k, v in meta.items() if v}


def _split_learning_outcome_lines(full_text: str) -> list[str]:
    """Bullet lines under চ) শ্ৰেণী — often three Assam geography outcomes."""
    lines: list[str] = []
    in_block = False
    for raw in full_text.splitlines():
        line = raw.strip()
        if re.search(r"^চ\)", line):
            in_block = True
            continue
        if in_block and re.search(r"^ছ\)", line):
            break
        if not in_block:
            continue
        line = line.strip(" ৷.·\t ")
        if len(line) < 10:
            continue
        if line.startswith("অসম") or "অসম" in line[:20] or line.startswith("বান"):
            lines.append(line)
    return lines


def extract_rf_sections(full_text: str, pages: list[str]) -> list[dict[str, Any]]:
    """
    Split lesson plan by learning-outcome / RF blocks (ৰফিঃ ১, RF 2, …).
    Falls back to one section with full text.
    """
    sections: list[dict[str, Any]] = []
    header_pattern = re.compile(
        r"^[\s]*(?:"
        r"ৰ[^\n]{0,8}ঃ[\s]*ফ[^\n]{0,6}?[\s]*([০-৯\d]+)"
        r"|RF\s*([০-৯\d]+)"
        r")",
        re.IGNORECASE | re.MULTILINE,
    )

    markers: list[tuple[int, str, int]] = []
    for m in header_pattern.finditer(full_text):
        num_raw = m.group(1) or m.group(2)
        if not num_raw:
            continue
        num = _bn_digits_to_int(num_raw)
        markers.append((m.start(), f"rf{num}", num))

    markers.sort(key=lambda x: x[0])
    if not markers:
        outcome_lines = _split_learning_outcome_lines(full_text)
        if outcome_lines:
            for i, line in enumerate(outcome_lines, start=1):
                sections.append(
                    {
                        "section_id": f"outcome_{i}",
                        "index": i,
                        "title": line[:120],
                        "summary": line,
                        "source": "outline",
                    }
                )
        if not sections:
            sections.append(
                {
                    "section_id": "full_document",
                    "index": 1,
                    "title": "Full lesson",
                    "summary": full_text[:500],
                    "source": "full_text",
                }
            )
        return sections

    for i, (start, sid, num) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(full_text)
        chunk = full_text[start:end].strip()
        title_line = chunk.splitlines()[0][:160] if chunk else sid
        sections.append(
            {
                "section_id": sid,
                "index": num,
                "title": title_line,
                "body": chunk,
                "source": "rf_block",
            }
        )
    return sections


def build_manifest(*, pdf_path: Path, full_text: str, pages: list[str]) -> dict[str, Any]:
    from textbook_structure import (
        build_hierarchy,
        flatten_teaching_sections,
        render_chapters_markdown,
    )

    meta = parse_lesson_metadata(full_text)
    hierarchy = build_hierarchy(full_text=full_text, pages=pages, meta=meta)
    sections = flatten_teaching_sections(hierarchy)
    book_id = book_id_from_pdf(pdf_path)
    return {
        "book_id": book_id,
        "source_pdf": str(pdf_path.resolve()),
        "page_count": len(pages),
        "metadata": meta,
        "document_type": hierarchy.get("document_type"),
        "chapter_count": hierarchy.get("chapter_count"),
        "subchapter_count": hierarchy.get("subchapter_count"),
        "chapters": hierarchy.get("chapters"),
        "sections": sections,
        "chapters_markdown": render_chapters_markdown(hierarchy, meta),
        "extraction_notes": (
            "Chapters/subchapters in `chapters`; flat teaching units in `sections`. "
            "Re-run extract after PDF changes."
        ),
    }


def section_markdown(manifest: dict[str, Any], section_ids: list[str]) -> str:
    meta = manifest.get("metadata") or {}
    lines = [
        f"# {meta.get('lesson_title') or meta.get('textbook_title') or manifest.get('book_id')}",
        "",
        f"- Class: {meta.get('class_level', '—')}",
        f"- Subject: {meta.get('subject', '—')}",
        f"- Lesson no.: {meta.get('lesson_number', '—')}",
        "",
        "## Sections in this video unit",
        "",
    ]
    by_id = {s["section_id"]: s for s in manifest.get("sections", [])}
    for sid in section_ids:
        sec = by_id.get(sid)
        if not sec:
            continue
        ch_id = sec.get("chapter_id")
        if ch_id:
            lines.append(f"*(Chapter `{ch_id}` · subchapter `{sec.get('subchapter_id', sid)}`)*")
            lines.append("")
        lines.append(f"### {sec.get('title', sid)}")
        lines.append("")
        body = sec.get("body") or sec.get("summary") or ""
        lines.append(body.strip())
        lines.append("")
    return "\n".join(lines).strip() + "\n"
