"""PDF-aligned KalamGPT response orchestration.

This module keeps the first version deliberately simple and testable:
- a deterministic router selects personality, reasoning, innovation, or mixed;
- the existing RAG engine supplies evidence;
- a structured plan is requested for complex questions;
- the existing model wrapper writes the final answer;
- lightweight verification prevents identity claims and unsupported quote framing.

The model's hidden chain-of-thought is never returned to the caller.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from .prompts.layers import COMBINED_LAYER_POLICY, IDENTITY_POLICY


@dataclass
class LayerDecision:
    active_layers: list[str]
    task_type: str
    needs_reasoning_plan: bool
    needs_innovation: bool
    risk_profile: str = "normal"


@dataclass
class KalamResponse:
    response: str
    sources: list[dict[str, Any]]
    active_layers: list[str]
    task_type: str
    verification: dict[str, Any]
    model_version: str = "kalam-orchestrator-0.1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_REASONING_TERMS = {
    "why", "root cause", "system", "problem", "policy", "development",
    "education", "society", "nation", "country", "failure", "impact",
    "history", "historical", "strategy", "should we", "how can", "why should",
}
_INNOVATION_TERMS = {
    "idea", "innovate", "innovation", "design", "create", "invent",
    "future", "imagine", "solution", "build", "project", "technology",
    "improve", "connect", "using only", "limited resources",
}
_HIGH_RISK_TERMS = {
    "suicide", "self harm", "kill", "weapon", "medical diagnosis",
    "legal case", "financial advice",
}


def _contains_term(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def route_question(question: str) -> LayerDecision:
    """Choose layers without forcing every question into a long template."""
    reasoning = _contains_term(question, _REASONING_TERMS)
    innovation = _contains_term(question, _INNOVATION_TERMS)
    lowered = question.lower()
    risk = "high" if _contains_term(question, _HIGH_RISK_TERMS) else "normal"

    if reasoning and innovation:
        layers = ["personality", "reasoning", "innovation"]
        task = "mixed"
    elif innovation:
        layers = ["personality", "innovation"]
        task = "innovation"
    elif reasoning:
        layers = ["personality", "reasoning"]
        task = "reasoning"
    else:
        layers = ["personality"]
        task = "personality"

    if any(word in lowered for word in ("hello", "hi", "thank you", "who are you")):
        layers = ["personality"]
        task = "conversation"
        reasoning = innovation = False

    return LayerDecision(
        active_layers=layers,
        task_type=task,
        needs_reasoning_plan=reasoning,
        needs_innovation=innovation,
        risk_profile=risk,
    )


def _plan_instructions(question: str, decision: LayerDecision) -> str:
    if not decision.needs_reasoning_plan:
        return "No long reasoning plan is needed. Answer directly and helpfully."
    return f"""
Create a compact private planning object for this question:
{question}

Use exactly these fields:
- ROOT: the deeper problem
- SYSTEM: the larger systems involved
- HISTORY: only relevant verified evidence from the sources
- HUMAN: who is affected and who can act
- PATH: three practical steps

Do not reveal private chain-of-thought. Use the plan only to improve the answer.
""".strip()


def _innovation_instructions(decision: LayerDecision) -> str:
    if not decision.needs_innovation:
        return "Do not force an innovation framework into this answer."
    return """
For an innovation question, use only the useful lenses from the evidence and label
new proposals as new ideas: cross-domain mechanism, nature analogy, reverse telescope,
youth catalyst, and constraint creativity. Do not attribute generated ideas to Kalam.
""".strip()


def build_generation_prompt(question: str, decision: LayerDecision, retrieved: list[dict]) -> str:
    # Keep the prompt small enough that GPT-2 does not discard the instructions
    # when the retrieved corpus contains long passages.
    evidence = "\n\n".join(
        f"[SOURCE {i + 1} | {item.get('source', 'unknown')} | "
        f"score={item.get('relevance_score', 0)}]\n{item.get('text', '')[:900]}"
        for i, item in enumerate(retrieved[:2])
    )
    if not evidence:
        evidence = "[No verified source passage was retrieved. Do not invent citations or quotes.]"

    return f"""{COMBINED_LAYER_POLICY}

ACTIVE LAYERS: {', '.join(decision.active_layers)}
TASK TYPE: {decision.task_type}

{_plan_instructions(question, decision)}

{_innovation_instructions(decision)}

RETRIEVED EVIDENCE:
{evidence}

USER QUESTION:
{question}

Write only the final user-facing answer. Be warm and clear. Mention uncertainty when
the evidence is insufficient. If quoting, quote only text supported by the evidence and
make it clear whether it is a direct verified quote or a paraphrase. End with a practical
next step when one is appropriate.
""".strip()


def verify_response(question: str, answer: str, retrieved: list[dict]) -> dict[str, Any]:
    """Lightweight guardrail; later replace with stronger claim verification."""
    lowered = answer.lower()
    identity_patterns = [
        r"\bi am dr\.?\s*a\.?\s*p\.?\s*j\.?\s*abdul kalam\b",
        r"\bi am apj abdul kalam\b",
        r"\bwhen i worked at drdo\b",
        r"\bmy personal experience\b",
    ]
    identity_violation = any(re.search(p, lowered) for p in identity_patterns)
    quote_claim = 'kalam said' in lowered or 'dr. kalam said' in lowered or 'abdul kalam said' in lowered
    has_evidence = bool(retrieved)
    unsupported_quote_warning = quote_claim and not has_evidence
    return {
        "identity_safe": not identity_violation,
        "grounded": has_evidence,
        "quote_review_needed": unsupported_quote_warning,
        "needs_review": identity_violation or unsupported_quote_warning,
    }


def _clean_generated_text(text: str) -> str:
    """Remove common corpus/model artifacts before showing text to a user."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\[/?(?:url|body|quote|p)[^\]]*\]", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    for marker in ("USER QUESTION:", "RETRIEVED EVIDENCE:", "</s>", "[/INST]"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    return text.strip(" \"'")


def _conversation_answer(question: str) -> str | None:
    lowered = question.lower().strip().rstrip("?!.,")
    if lowered in {"who are you", "who r you", "what are you"}:
        return (
            "I am KalamGPT, an AI inspired by Dr. A. P. J. Abdul Kalam's public "
            "writings, speeches, scientific outlook, and human-centered values. "
            "I am not Dr. Kalam, and I do not have his personal memories."
        )
    if lowered in {"hi", "hello", "hey", "good morning", "good evening"}:
        return "Hello. I am KalamGPT. What would you like to explore today?"
    return None


def generate_kalam_response(question: str, model, rag_engine, *, top_k: int = 2, **generation_kwargs) -> KalamResponse:
    decision = route_question(question)
    direct_answer = _conversation_answer(question) if decision.task_type == "conversation" else None
    retrieved = [] if direct_answer else rag_engine.retrieve_context(question, top_k=top_k)
    generation_prompt = build_generation_prompt(question, decision, retrieved)
    answer = direct_answer or model.generate(
        user_message=generation_prompt,
        rag_context="",
        max_new_tokens=min(generation_kwargs.pop("max_new_tokens", 120), 120),
        temperature=min(generation_kwargs.pop("temperature", 0.35), 0.5),
        **generation_kwargs,
    )
    answer = _clean_generated_text(answer)
    verification = verify_response(question, answer, retrieved)
    if not verification["identity_safe"]:
        answer = (
            "I am KalamGPT, an AI inspired by Dr. A. P. J. Abdul Kalam's public work; "
            "I am not Dr. Kalam. I will answer using verified sources and clearly mark uncertainty."
        )
    return KalamResponse(
        response=answer,
        sources=retrieved,
        active_layers=decision.active_layers,
        task_type=decision.task_type,
        verification=verification,
    )
