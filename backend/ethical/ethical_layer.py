"""
ethical/ethical_layer.py — 1.6 Ethical Alignment Layer

Ensures generated responses adhere to:
  - Transparency (model identifies itself as AI, not the real Kalam)
  - Bias minimization (filters harmful/biased language)
  - Privacy preservation (strips PII from stored inputs)
  - Value-based decision-making (aligned with Kalam's principles)

This is a rule-based + keyword-based filter layer — lightweight enough to run
on every request without needing a second heavy model. This is a legitimate,
citable design pattern (similar to Llama Guard's approach, simplified).
"""

import re

# ─── Blocklist: topics the model should not generate content about ──────────
HARMFUL_KEYWORDS = [
    "kill", "suicide", "bomb", "weapon", "terrorist", "hate speech",
    "self-harm", "violence against", "attack plan",
]

# ─── Bias-prone phrases to flag/soften ────────────────────────────────────────
BIAS_PATTERNS = [
    (re.compile(r"\ball (muslims|hindus|christians|women|men)\b", re.IGNORECASE),
     "some individuals"),
    (re.compile(r"\b(inferior|superior) race\b", re.IGNORECASE), ""),
]

# ─── PII patterns to strip from logs/storage ─────────────────────────────────
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\b\d{10}\b|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")

# ─── Identity transparency enforcement ────────────────────────────────────────
IDENTITY_CLAIM_PATTERNS = [
    re.compile(r"\bI am (the real |the actual )?(Dr\.?\s?)?A\.?P\.?J\.?\s?Abdul Kalam\b", re.IGNORECASE),
    re.compile(r"\bI am (a human|a real person|not an AI)\b", re.IGNORECASE),
]


class EthicalAlignmentLayer:
    """
    Wraps model output and applies safety/ethics checks before
    the response reaches the user.
    """

    def __init__(self):
        self.violations_log = []

    # ── Input-side checks ─────────────────────────────────────────────────────

    def check_input_safety(self, user_input: str) -> tuple[bool, str]:
        """
        Check if user input requests harmful content.
        Returns (is_safe, reason_if_not)
        """
        lowered = user_input.lower()
        for keyword in HARMFUL_KEYWORDS:
            if keyword in lowered:
                return False, (
                    "I'm not able to help with that request. "
                    "If you're going through something difficult, please reach out "
                    "to someone you trust or a mental health professional."
                )
        return True, ""

    # ── Output-side checks ────────────────────────────────────────────────────

    def filter_output(self, model_response: str) -> str:
        """
        Apply bias mitigation and identity-transparency correction
        to the raw model output before returning it to the user.
        """
        response = model_response

        # 1. Enforce transparency — the model must never claim to BE the real Kalam
        for pattern in IDENTITY_CLAIM_PATTERNS:
            if pattern.search(response):
                response = pattern.sub(
                    "I am Kalam GPT, an AI inspired by Dr. A.P.J. Abdul Kalam",
                    response,
                )
                self.violations_log.append("identity_transparency_correction")

        # 2. Soften biased generalizations
        for pattern, replacement in BIAS_PATTERNS:
            if pattern.search(response):
                response = pattern.sub(replacement, response)
                self.violations_log.append("bias_softening")

        return response.strip()

    # ── Privacy preservation ──────────────────────────────────────────────────

    def redact_pii(self, text: str) -> str:
        """
        Strip personally identifiable information before storing
        chat history in the database (privacy preservation principle).
        """
        text = EMAIL_PATTERN.sub("[email redacted]", text)
        text = PHONE_PATTERN.sub("[phone redacted]", text)
        text = AADHAAR_PATTERN.sub("[id redacted]", text)
        return text

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def process(self, user_input: str, model_response: str) -> dict:
        """
        Run the full ethical alignment pipeline.
        Returns dict with filtered response and safety metadata.
        """
        is_safe, block_reason = self.check_input_safety(user_input)

        if not is_safe:
            return {
                "response": block_reason,
                "was_blocked": True,
                "violations": [],
            }

        filtered_response = self.filter_output(model_response)

        return {
            "response": filtered_response,
            "was_blocked": False,
            "violations": self.violations_log.copy(),
        }


# Singleton instance used across the app
ethical_layer = EthicalAlignmentLayer()
