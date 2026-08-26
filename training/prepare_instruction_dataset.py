#!/usr/bin/env python3
"""Build an instruction-tuning dataset from reviewed KalamGPT candidates.

Only records with review_status=approved are included. Pending candidates are
reported but never silently used for training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=None, help="Path to data/kalam")
    parser.add_argument("--input", type=Path, default=None, help="Pilot candidates JSONL")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--validation-ratio", type=float, default=0.20)
    parser.add_argument("--allow-empty", action="store_true", help="Write empty outputs instead of failing when no candidates are approved")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    data_root = (args.data_root or repo_root / "data" / "kalam").resolve()
    input_path = (args.input or data_root / "datasets" / "pilot_candidates.jsonl").resolve()
    output_root = data_root / "datasets" / "instruction" / args.version
    output_root.mkdir(parents=True, exist_ok=True)
    if not input_path.is_file():
        raise SystemExit(f"Pilot candidates not found: {input_path}")

    status_counts = Counter()
    layer_counts = Counter()
    approved = []
    with input_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON on line {line_number}: {exc}") from exc
            status = str(record.get("review_status", "missing")).strip().lower()
            status_counts[status] += 1
            if status != "approved":
                continue
            messages = record.get("messages")
            if not isinstance(messages, list) or len(messages) < 2:
                raise SystemExit(f"Approved record {record.get('id', line_number)} has invalid messages")
            user = next((m.get("content", "").strip() for m in messages if m.get("role") == "user"), "")
            assistant = next((m.get("content", "").strip() for m in messages if m.get("role") == "assistant"), "")
            if not user or not assistant:
                raise SystemExit(f"Approved record {record.get('id', line_number)} has an empty user or assistant message")
            if record.get("is_direct_kalam_quote") is True and not record.get("source_refs"):
                raise SystemExit(f"Approved direct quote {record.get('id', line_number)} has no source references")
            item = {
                "id": record.get("id", f"candidate_{line_number}"),
                "layer": record.get("layer", "unknown"),
                "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}],
                "source_refs": record.get("source_refs", []),
                "is_direct_kalam_quote": bool(record.get("is_direct_kalam_quote", False)),
                "is_synthetic_demonstration": bool(record.get("is_synthetic_demonstration", False)),
                "review_status": "approved",
                "language": record.get("language", "en"),
                "dataset_version": args.version,
            }
            approved.append(item)
            layer_counts[item["layer"]] += 1

    if not 0 < args.validation_ratio < 1:
        raise SystemExit("--validation-ratio must be between 0 and 1")
    if len(approved) < 2 and not args.allow_empty:
        raise SystemExit("At least 2 approved candidates are required to create instruction train/validation splits")
    if not approved and not args.allow_empty:
        raise SystemExit(
            f"No approved candidates found in {input_path}. Statuses: {dict(status_counts)}. "
            "Review candidates and set review_status to approved before training, or use --allow-empty for a report."
        )

    # Deterministic document/example-level split. Keep the complete file for
    # auditability, but train and evaluate on disjoint examples.
    ordered = sorted(approved, key=lambda item: hashlib.sha256(f"{args.version}:{item['id']}".encode()).hexdigest())
    validation_count = max(1, round(len(ordered) * args.validation_ratio)) if ordered else 0
    validation = ordered[:validation_count]
    train = ordered[validation_count:]
    if not train and validation:
        train, validation = validation[:-1], validation[-1:]

    def write_jsonl(path: Path, items: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    def write_text(path: Path, items: list[dict]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                user = item["messages"][0]["content"]
                assistant = item["messages"][1]["content"]
                handle.write(f"User: {user}\nAssistant: {assistant}\n\n")

    write_jsonl(output_root / "instruction.jsonl", ordered)
    write_jsonl(output_root / "train.jsonl", train)
    write_jsonl(output_root / "validation.jsonl", validation)
    write_text(output_root / "instruction.txt", ordered)
    write_text(output_root / "train.txt", train)
    write_text(output_root / "validation.txt", validation)

    manifest = {
        "dataset_version": args.version,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "approved_examples": len(approved),
        "train_examples": len(train),
        "validation_examples": len(validation),
        "validation_ratio": args.validation_ratio,
        "status_counts": dict(status_counts),
        "layer_counts": dict(layer_counts),
        "files": {
            "all_jsonl": "instruction.jsonl",
            "all_text": "instruction.txt",
            "train_jsonl": "train.jsonl",
            "train_text": "train.txt",
            "validation_jsonl": "validation.jsonl",
            "validation_text": "validation.txt",
        },
        "training_policy": "Only human-approved candidates are included.",
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(f"Instruction dataset written to: {output_root}")


if __name__ == "__main__":
    main()
