#!/usr/bin/env python3
"""Consolidate instruction candidates and create a human-review report.

This tool never auto-approves content. It preserves existing statuses, assigns
unique IDs across input files, flags exact duplicate questions, and writes a
single reviewable JSONL plus a compact report.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def normalized(text: str) -> str:
    text = text.casefold().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def message_content(record: dict[str, Any], role: str) -> str:
    for message in record.get("messages", []):
        if message.get("role") == role:
            return str(message.get("content", ""))
    return ""


def unique_id(base: str, source_stem: str, used: set[str]) -> str:
    candidate = base or f"candidate_{len(used) + 1:04d}"
    if candidate not in used:
        used.add(candidate)
        return candidate
    prefix = re.sub(r"[^a-zA-Z0-9_-]+", "_", source_stem).strip("_") or "batch"
    index = 1
    while f"{candidate}__{prefix}_{index:02d}" in used:
        index += 1
    candidate = f"{candidate}__{prefix}_{index:02d}"
    used.add(candidate)
    return candidate


def main() -> None:
    args = parse_args()
    records: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    question_owner: dict[str, int] = {}
    duplicate_count = 0

    for input_path in args.inputs:
        if not input_path.is_file():
            raise SystemExit(f"Input file not found: {input_path}")
        with input_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"Invalid JSON in {input_path}:{line_number}: {exc}") from exc
                if not isinstance(record, dict):
                    raise SystemExit(f"Expected JSON object in {input_path}:{line_number}")

                record = dict(record)
                record["id"] = unique_id(str(record.get("id", "")), input_path.stem, used_ids)
                record.setdefault("review_status", "pending")
                flags = set(record.get("auto_flags") or [])
                question = message_content(record, "user")
                answer = message_content(record, "assistant")
                question_key = normalized(question)

                if question_key and question_key in question_owner:
                    flags.add("duplicate_question_exact")
                    if record["review_status"] == "approved":
                        record["review_status"] = "needs_revision"
                    duplicate_count += 1
                elif question_key:
                    question_owner[question_key] = len(records)

                if not question.strip() or not answer.strip():
                    flags.add("empty_content")
                record["is_direct_kalam_quote"] = bool(record.get("is_direct_kalam_quote", False))
                record["is_synthetic_demonstration"] = bool(record.get("is_synthetic_demonstration", True))
                record["auto_flags"] = sorted(flags)
                records.append(record)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    statuses = Counter(str(record.get("review_status", "pending")) for record in records)
    layers = Counter(str(record.get("layer", "unknown")) for record in records)
    flagged = sum(bool(record.get("auto_flags")) for record in records)
    report = {
        "records": len(records),
        "unique_ids": len({record["id"] for record in records}),
        "duplicate_questions_exact": duplicate_count,
        "flagged_records": flagged,
        "status_counts": dict(sorted(statuses.items())),
        "layer_counts": dict(sorted(layers.items())),
        "approved_records": sum(record.get("review_status") == "approved" for record in records),
        "policy": "Human approval is required; this tool never auto-approves candidates.",
        "output": str(args.output),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

