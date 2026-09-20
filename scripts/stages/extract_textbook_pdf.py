#!/usr/bin/env python3
"""Extract text + section structure from a textbook or DIKSHA lesson PDF."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import _bootstrap  # noqa: F401

import argparse
import json

from paths import PROJECT_ROOT, add_output_root_argument, configure_output_root, get_output_root, project_rel
from pipeline_utils import write_json
from textbook_pdf import book_id_from_pdf, build_manifest, read_pdf_pages


def textbook_root(book_id: str, output_root: Path) -> Path:
    root = output_root / "textbooks" / book_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract NCERT/DIKSHA PDF → textbook manifest.")
    parser.add_argument("--pdf", type=Path, required=True, help="Path to textbook or lesson PDF.")
    parser.add_argument("--book-id", type=str, default=None, help="Override output folder id.")
    add_output_root_argument(parser)
    args = parser.parse_args()

    configure_output_root(args.output_root)
    pdf_path = args.pdf if args.pdf.is_absolute() else PROJECT_ROOT / args.pdf
    book_id = args.book_id or book_id_from_pdf(pdf_path)
    book_root = textbook_root(book_id, get_output_root())

    full_text, pages = read_pdf_pages(pdf_path)
    extracted_dir = book_root / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    (extracted_dir / "full_text.txt").write_text(full_text, encoding="utf-8")

    manifest = build_manifest(pdf_path=pdf_path, full_text=full_text, pages=pages)
    manifest_path = book_root / "manifest.json"
    write_json(manifest_path, manifest)

    chapters_json = book_root / "extracted" / "chapters.json"
    chapters_md = book_root / "extracted" / "chapters.md"
    hierarchy_payload = {
        "document_type": manifest.get("document_type"),
        "chapter_count": manifest.get("chapter_count"),
        "subchapter_count": manifest.get("subchapter_count"),
        "chapters": manifest.get("chapters"),
    }
    write_json(chapters_json, hierarchy_payload)
    chapters_md.write_text(manifest.get("chapters_markdown") or "", encoding="utf-8")

    print(f"Book id:     {book_id}")
    print(f"Output root: {project_rel(book_root)}/")
    print(f"Pages:       {len(pages)}")
    print(f"Type:        {manifest.get('document_type')}")
    print(f"Chapters:    {manifest.get('chapter_count')} (subchapters total: {manifest.get('subchapter_count')})")
    print(f"Video units: {len(manifest.get('sections', []))} teaching blocks in `sections`")
    print(f"Wrote {manifest_path}")
    print(f"Wrote {chapters_json}")
    print(f"Wrote {chapters_md}")


if __name__ == "__main__":
    main()
