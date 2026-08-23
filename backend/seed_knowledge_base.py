"""Seed KalamGPT's persistent retrieval memory from the uploaded dataset.

Run from the backend directory:
    python seed_knowledge_base.py

By default this reads the extracted files copied into:
    ../data/kalam/extracted/extracted_text/

You can also provide another folder:
    python seed_knowledge_base.py --source-dir ./knowledge_sources
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from knowledge.rag_engine import rag_engine


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCES_DIR = BACKEND_DIR.parent / "data" / "kalam" / "extracted" / "extracted_text"


def infer_source_type(filename: str) -> str:
    lowered = filename.lower()
    if "speech" in lowered or "address" in lowered or "lecture" in lowered:
        return "speech"
    if "interview" in lowered:
        return "interview"
    if "article" in lowered or "essay" in lowered:
        return "article"
    return "book_or_document"


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Kalam source text into persistent Chroma memory")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCES_DIR))
    args = parser.parse_args()

    sources_dir = Path(args.source_dir).expanduser().resolve()
    if not sources_dir.exists():
        print(f"No source directory found: {sources_dir}")
        print("Upload/copy the extracted Kalam files first, or pass --source-dir.")
        return

    txt_files = sorted(sources_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {sources_dir}")
        return

    print(f"Found {len(txt_files)} source file(s) in {sources_dir}")
    total_chunks = 0
    skipped = 0

    for file_path in txt_files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"SKIP {file_path.name}: {exc}")
            skipped += 1
            continue

        if len(text.split()) < 20:
            print(f"SKIP {file_path.name}: too short")
            skipped += 1
            continue

        title = file_path.stem
        source_type = infer_source_type(file_path.name)
        chunk_count = rag_engine.index_document(text, title, source_type=source_type)
        total_chunks += chunk_count
        print(f"OK   {title}: {chunk_count} chunks [{source_type}]")

    print("-" * 60)
    print(f"Knowledge-base seeding complete: {total_chunks} chunks")
    print(f"Skipped files: {skipped}")
    print(f"Vector database: {rag_engine.get_stats()}")


if __name__ == "__main__":
    main()
