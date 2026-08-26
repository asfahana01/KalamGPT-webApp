#!/usr/bin/env python3
"""Create deterministic document-level train/validation/test datasets."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=None, help="Path to data/kalam")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--train-ratio", type=float, default=0.85)
    parser.add_argument("--validation-ratio", type=float, default=0.10)
    parser.add_argument("--seed", default="kalam-gpt-v1")
    return parser.parse_args()


def assignment(document_id: str, seed: str, train_ratio: float, validation_ratio: float) -> str:
    digest = hashlib.sha256(f"{seed}:{document_id}".encode("utf-8")).hexdigest()
    bucket = int(digest[:12], 16) / float(16**12)
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + validation_ratio:
        return "validation"
    return "test"


def main() -> None:
    args = parse_args()
    if not 0 < args.train_ratio < 1 or not 0 < args.validation_ratio < 1 or args.train_ratio + args.validation_ratio >= 1:
        raise SystemExit("train-ratio and validation-ratio must be positive and leave room for test data")
    repo_root = Path(__file__).resolve().parents[1]
    data_root = (args.data_root or repo_root / "data" / "kalam").resolve()
    prepared_root = data_root / "processed" / args.version
    manifest_path = prepared_root / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Prepared manifest not found: {manifest_path}. Run prepare_dataset.py first.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_root = data_root / "datasets" / args.version
    output_root.mkdir(parents=True, exist_ok=True)
    records = []
    for item in manifest["documents"]:
        split = assignment(item["document_id"], args.seed, args.train_ratio, args.validation_ratio)
        record = dict(item)
        record["split"] = split
        records.append(record)

    split_counts = Counter(record["split"] for record in records)
    for split in ("train", "validation", "test"):
        split_records = [record for record in records if record["split"] == split]
        text_parts = []
        metadata_path = output_root / f"{split}.jsonl"
        for record in split_records:
            source_file = prepared_root / record["text_path"]
            text_parts.append(source_file.read_text(encoding="utf-8").strip())
        (output_root / f"{split}.txt").write_text("\n\n".join(text_parts) + ("\n" if text_parts else ""), encoding="utf-8")
        with metadata_path.open("w", encoding="utf-8") as handle:
            for record in split_records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    split_manifest = {
        "dataset_version": args.version,
        "seed": args.seed,
        "ratios_requested": {"train": args.train_ratio, "validation": args.validation_ratio, "test": 1 - args.train_ratio - args.validation_ratio},
        "document_count": len(records),
        "split_counts": dict(split_counts),
        "split_word_counts": {
            split: sum(record["word_count"] for record in records if record["split"] == split)
            for split in ("train", "validation", "test")
        },
        "files": {split: {"text": f"{split}.txt", "metadata": f"{split}.jsonl"} for split in ("train", "validation", "test")},
    }
    (output_root / "split_manifest.json").write_text(json.dumps(split_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(split_manifest, indent=2))
    print(f"Datasets written to: {output_root}")


if __name__ == "__main__":
    main()
