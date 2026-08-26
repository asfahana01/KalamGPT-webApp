#!/usr/bin/env python3
"""Prepare a versioned KalamGPT corpus from the extracted source catalog.

Expected layout (default):
    data/kalam/catalog/dataset_catalog.csv
    data/kalam/extracted/extracted_text/<files listed by the catalog>

The script preserves provenance and never modifies raw extracted files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def clean_text(text: str) -> str:
    """Normalize extracted text while preserving Unicode and paragraph boundaries."""
    text = text.replace("\x00", "")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?im)^\s*(?:page|p\.)\s*\d+\s*$", "", text)
    text = re.sub(r"(?im)^\s*chapter\s+\d+\s*$", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = re.sub(r"\s*\n\s*", " ", paragraph).strip()
        if len(paragraph.split()) >= 4:
            paragraphs.append(paragraph)
    return "\n\n".join(paragraphs).strip()


def truthy(value: str) -> bool:
    return value.strip().lower() in {"yes", "true", "1", "y"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=None, help="Path to data/kalam")
    parser.add_argument("--version", default="v1", help="Corpus version, for example v1")
    parser.add_argument("--min-words", type=int, default=80)
    parser.add_argument("--include-needs-review", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    data_root = (args.data_root or repo_root / "data" / "kalam").resolve()
    catalog_path = data_root / "catalog" / "dataset_catalog.csv"
    extracted_root = data_root / "extracted"
    output_root = data_root / "processed" / args.version
    text_root = output_root / "documents"
    output_root.mkdir(parents=True, exist_ok=True)
    text_root.mkdir(parents=True, exist_ok=True)
    if not catalog_path.is_file():
        raise SystemExit(f"Catalog not found: {catalog_path}")

    rows = list(csv.DictReader(catalog_path.open(encoding="utf-8", newline="")))
    accepted, rejected = [], Counter()
    seen_hashes: set[str] = set()
    for row in rows:
        if row.get("text_quality", "").strip().lower() != "good":
            rejected["text_quality"] += 1
            continue
        if not args.include_needs_review and truthy(row.get("needs_review", "")):
            rejected["needs_review"] += 1
            continue
        if row.get("duplicate_status", "").strip().lower() not in {"", "unique"}:
            rejected["duplicate"] += 1
            continue
        relative = row.get("extracted_text_path", "").strip()
        source_path = extracted_root / relative
        if not relative or not source_path.is_file():
            rejected["missing_text"] += 1
            continue
        raw = source_path.read_text(encoding="utf-8", errors="replace")
        cleaned = clean_text(raw)
        word_count = len(cleaned.split())
        if word_count < args.min_words:
            rejected["too_short_after_cleaning"] += 1
            continue
        content_hash = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
        if content_hash in seen_hashes:
            rejected["cleaned_duplicate"] += 1
            continue
        seen_hashes.add(content_hash)
        document_id = row.get("sha256", "")[:16] or content_hash[:16]
        output_path = text_root / f"{document_id}.txt"
        output_path.write_text(cleaned + "\n", encoding="utf-8")
        accepted.append({
            "document_id": document_id,
            "text_path": str(output_path.relative_to(output_root)),
            "source_id": row.get("sha256", ""),
            "source_title": row.get("metadata_title", "") or row.get("filename", ""),
            "source_type": row.get("source_type", "unknown"),
            "source_url": row.get("source_url", ""),
            "original_path": row.get("relative_path", ""),
            "extracted_text_path": relative,
            "word_count": word_count,
            "character_count": len(cleaned),
            "cleaned_sha256": content_hash,
            "language": "en",
            "corpus_version": args.version,
        })

    manifest = {
        "corpus_version": args.version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "catalog_path": str(catalog_path),
        "source_count": len(rows),
        "accepted_documents": len(accepted),
        "rejected_documents": dict(rejected),
        "accepted_words": sum(item["word_count"] for item in accepted),
        "accepted_characters": sum(item["character_count"] for item in accepted),
        "source_type_counts": dict(Counter(item["source_type"] for item in accepted)),
        "documents": accepted,
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in manifest if k != "documents"}, indent=2))
    print(f"Processed corpus written to: {output_root}")


if __name__ == "__main__":
    main()
