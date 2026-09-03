#!/usr/bin/env python3
"""Generate reviewable KalamGPT instruction candidates in local batches.

This script calls an OpenAI-compatible chat model to create candidates, applies
cheap deterministic quality gates, removes duplicate questions, and appends only
pending records to a JSONL file. It never marks a generated record approved.

Example:
    python training/generate_candidates.py --layer reasoning --count 25
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BLUEPRINT: dict[str, list[str]] = {
    "personality": [
        "recovering after exam failure", "finding motivation", "choosing a career",
        "handling criticism", "discipline", "faith and science", "leadership",
        "ethical decision-making", "managing fear", "learning from mistakes",
    ],
    "reasoning": [
        "education reform", "innovation barriers", "India's brain drain",
        "urban flooding", "rural development", "poverty and technology",
        "climate adaptation", "public health", "scientific temper", "inclusive growth",
    ],
    "innovation": [
        "rural education", "village healthcare", "clean energy", "agriculture",
        "water management", "low-cost technology", "youth employment",
        "local manufacturing", "assistive technology", "disaster preparedness",
    ],
    "mixed": [
        "science and spirituality", "youth and national development",
        "technology and social justice", "energy independence",
        "education and entrepreneurship", "environment and economic growth",
        "space technology and society", "ethics of innovation", "digital inclusion",
        "community resilience",
    ],
}

QUESTION_FORMS = [
    "Why does this matter, and what practical steps should a young person take?",
    "How can this problem be approached using science, compassion, and evidence?",
    "What are the main trade-offs, and what would a realistic first-year plan look like?",
    "Design a low-cost, measurable pilot that a school, village, or district could try.",
    "What would you advise a student or young engineer who wants to work on this issue?",
]

SYSTEM_PROMPT = """You create high-quality synthetic instruction examples for KalamGPT.

Ground every answer in Dr. A.P.J. Abdul Kalam's documented public ideas,
writings, speeches, and broad themes. Write an original AI-generated answer;
do not imitate or claim to be Dr. Kalam. Never use first-person memories,
personal experiences, invented historical details, or fabricated quotations.
Do not place original wording inside quotation marks and attribute it to Kalam.
When a factual claim is supported by supplied source metadata, include the
relevant source in source_refs. If a claim cannot be supported, present it as a
clearly labeled suggestion or omit it. Mark every example as synthetic.

Use a warm, humble, scientific, hopeful, practical, teacher-like tone. Answer
the question directly in 140–220 words, with a clear structure and useful next
steps. Keep the JSON fields concise and return only the requested JSON object."""

SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "instruction_candidate",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "source_refs": {"type": "array", "items": {"type": "string"}},
                "is_direct_kalam_quote": {"type": "boolean"},
                "is_synthetic_demonstration": {"type": "boolean"},
            },
            "required": [
                "question", "answer", "source_refs",
                "is_direct_kalam_quote", "is_synthetic_demonstration",
            ],
            "additionalProperties": False,
        },
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", choices=sorted(BLUEPRINT), required=True)
    parser.add_argument("--count", type=int, default=25)
    parser.add_argument("--model", default="gpt-5-mini")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--examples", type=Path, default=None, help="Approved JSONL style examples")
    parser.add_argument("--source-catalog", type=Path, default=None, help="Optional catalog CSV or JSONL")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--seed", default="v0.2.0")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def load_sources(path: Path | None) -> list[dict[str, str]]:
    if not path or not path.is_file():
        return []
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    import csv
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_context(sources: list[dict[str, str]], limit: int = 12) -> str:
    lines = []
    for item in sources[:limit]:
        title = item.get("title") or item.get("name") or item.get("source_title") or "Kalam source"
        url = item.get("source_url") or item.get("url") or item.get("source_refs") or ""
        lines.append(f"- {title} {url}".strip())
    return "\n".join(lines) if lines else "No source metadata supplied; avoid factual claims and write a general proposal."


def style_context(examples: list[dict[str, Any]], limit: int = 4) -> str:
    selected = []
    for record in examples:
        messages = record.get("messages", [])
        user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        assistant = next((m.get("content", "") for m in messages if m.get("role") == "assistant"), "")
        if user and assistant:
            selected.append(f"EXAMPLE USER: {user}\nEXAMPLE ASSISTANT: {assistant}")
    return "\n\n".join(selected[:limit]) or "No approved style examples supplied."


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def quality_flags(question: str, answer: str, source_refs: list[str], direct_quote: bool) -> list[str]:
    flags: list[str] = []
    words = answer.split()
    lowered = answer.lower()
    if not question.strip() or not answer.strip():
        flags.append("empty_content")
    if len(words) < 80:
        flags.append("answer_too_short")
    if len(words) > 500:
        flags.append("answer_too_long")
    impersonation = [
        "i am dr. kalam", "i am abdul kalam", "when i was president",
        "when i met", "my childhood", "my speech",
    ]
    if any(term in lowered for term in impersonation):
        flags.append("possible_impersonation")
    if direct_quote or (answer.count('"') >= 2 and ("kalam" in lowered or "dr." in lowered)):
        flags.append("quote_review_required")
    if re.search(r"\b\d+(?:\.\d+)?\s*%", answer) or re.search(r"\b(?:19|20)\d{2}\b", answer):
        flags.append("numeric_or_date_claim_review")
    if not source_refs and ("according to" in lowered or "research shows" in lowered or "data shows" in lowered):
        flags.append("unsupported_attribution")
    generic_questions = {
        "why does this matter and what practical steps should a young person take",
        "how can this problem be approached using science compassion and evidence",
        "what are the main trade offs and what would a realistic first year plan look like",
    }
    if normalized(question) in generic_questions:
        flags.append("generic_question")
    sentences = re.split(r"[.!?]+", lowered)
    clean = [s.strip() for s in sentences if s.strip()]
    if len(clean) != len(set(clean)):
        flags.append("repeated_sentence")
    return sorted(set(flags))


def make_task(layer: str, index: int, style: str, sources: str) -> tuple[int, str]:
    topic = BLUEPRINT[layer][index % len(BLUEPRINT[layer])]
    form = QUESTION_FORMS[(index // len(BLUEPRINT[layer])) % len(QUESTION_FORMS)]
    prompt = f"""Create one original instruction example for the layer '{layer}'.

Required topic: {topic}
Required question shape: {form}
Batch variant number: {index + 1}

The generated QUESTION must explicitly mention or clearly name the required topic
'{topic}'. Do not return the generic question shape unchanged. Vary the wording,
focus, and practical context from other examples. The question must be a real,
standalone user question, not an instruction to the generator.

Use the following approved examples only as style references; do not copy them:
{style}

Available source metadata (use only for broad themes; do not invent unsupported facts):
{sources}

The answer must be self-contained, direct, practical, and safe. If a factual claim
cannot be supported by the supplied metadata, make it a clearly labeled suggestion
or omit it. Return the JSON schema exactly."""
    return index, prompt


def call_model(model: str, prompt: str) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("Install the dependency first: python -m pip install openai") from exc

    # Explicitly pass the endpoint. OpenAI() alone defaults to api.openai.com,
    # which would ignore a Groq-compatible base URL in the environment.
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("GROQ_API_BASE") or os.getenv("OPENAI_API_BASE")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY or OPENAI_API_KEY before generating candidates")

    client_kwargs: dict[str, str] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    request: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "response_format": SCHEMA,
    }
    # Groq's OpenAI-compatible endpoint uses max_tokens. Keep the OpenAI
    # parameter for non-Groq endpoints that expect max_completion_tokens.
    if base_url and "groq.com" in base_url:
        # GPT-OSS may spend part of the completion budget on reasoning before
        # emitting structured JSON. Leave enough room for a valid JSON object.
        request["max_tokens"] = 2400
    else:
        request["max_completion_tokens"] = 1200

    response = client.chat.completions.create(**request)
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Model returned empty content")
    return json.loads(content)


def main() -> None:
    args = parse_args()
    if args.count < 1 or args.count > 500:
        raise SystemExit("--count must be between 1 and 500")
    output = args.output or Path("data/kalam/datasets/pilot_candidates.generated.jsonl")
    examples = load_jsonl(args.examples)
    sources = load_sources(args.source_catalog)
    style = style_context(examples)
    source_text = source_context(sources)
    tasks = [make_task(args.layer, i, style, source_text) for i in range(args.count)]

    if args.dry_run:
        print(json.dumps({
            "model": args.model, "layer": args.layer, "count": args.count,
            "output": str(output), "workers": args.workers,
            "requires_api_key": True,
            "sample_prompt": tasks[0][1],
        }, indent=2))
        return

    existing = load_jsonl(output)
    existing_questions = {normalized(r.get("messages", [{}])[0].get("content", "")) for r in existing}
    output.parent.mkdir(parents=True, exist_ok=True)
    results: list[tuple[int, dict[str, Any] | None, str | None]] = []

    def run(task: tuple[int, str]) -> tuple[int, dict[str, Any] | None, str | None]:
        index, prompt = task
        try:
            return index, call_model(args.model, prompt), None
        except Exception as exc:  # keep other batch items running
            return index, None, f"{type(exc).__name__}: {exc}"

    with futures.ThreadPoolExecutor(max_workers=max(1, min(args.workers, 10))) as executor:
        for result in executor.map(run, tasks):
            results.append(result)

    added = 0
    failures = []
    with output.open("a", encoding="utf-8") as handle:
        for index, candidate, error in sorted(results, key=lambda item: item[0]):
            if error:
                failures.append({"index": index, "error": error})
                continue
            assert candidate is not None
            question = candidate.get("question", "").strip()
            answer = candidate.get("answer", "").strip()
            question_key = normalized(question)
            flags = quality_flags(question, answer, candidate.get("source_refs", []), candidate.get("is_direct_kalam_quote", False))
            if not question_key or question_key in existing_questions:
                flags.append("duplicate_question")
            existing_questions.add(question_key)
            candidate_id = f"generated_{args.layer}_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{index + 1:04d}"
            record = {
                "id": candidate_id,
                "layer": args.layer,
                "task_type": args.layer,
                "messages": [
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": answer},
                ],
                "source_refs": candidate.get("source_refs", []),
                "is_direct_kalam_quote": bool(candidate.get("is_direct_kalam_quote", False)),
                "is_synthetic_demonstration": True,
                "review_status": "pending",
                "auto_flags": sorted(set(flags)),
                "generation": {
                    "model": args.model,
                    "seed": args.seed,
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                },
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            added += 1

    report = {
        "requested": args.count,
        "written": added,
        "failed": len(failures),
        "output": str(output),
        "review_policy": "All generated candidates remain pending until human approval.",
        "failures": failures,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
