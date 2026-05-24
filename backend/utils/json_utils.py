"""easli — robust JSON extraction & Pydantic-Literal sanitiser.

Kept separate from `services/ai_service.py` because both the analyse path
and the chat path need the same JSON-parsing logic AND `core.exceptions`
should not depend on Mistral.

No runtime dependencies beyond the standard library.
"""

import json
import re
from typing import Any, List, Optional

__all__ = [
    "extract_json_from_text",
    "coerce_literal",
    "sanitize_literal_fields",
]


def extract_json_from_text(text: str) -> Optional[dict]:
    """Try to find a JSON object in the LLM response.

    Strategy (fall-through):
      1. If the response is wrapped in a ```json ... ``` fence, extract the
         fenced content.
      2. Try direct json.loads on the (possibly trimmed) text.
      3. As a last resort, take the first `{` and last `}` and try parsing
         the slice between them.
    Returns None if every strategy fails. Never raises.
    """
    if not text:
        return None
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


def coerce_literal(value: Any, allowed: List[str], default: str) -> str:
    """Defensively coerce a possibly-chatty Literal field into one of `allowed`.

    Mistral Large 3 occasionally emits values like
        "high (but the deadline itself is fraudulent)"
    which Pydantic Literal[...] rejects with a ValidationError. We extract the
    first matching token (case-insensitive, word-boundary) so the analysis
    doesn't fail just because the model added editorial commentary.
    """
    if not isinstance(value, str):
        return default
    lowered = value.lower()
    for token in allowed:
        if re.search(r"\b" + re.escape(token) + r"\b", lowered):
            return token
    return default


def sanitize_literal_fields(parsed: dict) -> None:
    """Normalise every Literal[...] field in-place before Pydantic validation.

    Keeps the sanitiser in one place so adding a new Literal in
    AnalysisResult only needs one corresponding entry here.
    """
    if not isinstance(parsed, dict):
        return

    parsed["risk_level"] = coerce_literal(
        parsed.get("risk_level"), ["green", "yellow", "red"], "green",
    )

    category_allowed = [
        "tax", "insurance", "rent", "bank", "health", "government", "court",
        "utilities", "telecom", "work", "education", "other",
    ]
    parsed["category"] = coerce_literal(
        parsed.get("category"), category_allowed, "other",
    )

    deadlines = parsed.get("deadlines")
    if isinstance(deadlines, list):
        for d in deadlines:
            if isinstance(d, dict) and "confidence" in d:
                d["confidence"] = coerce_literal(
                    d.get("confidence"), ["low", "medium", "high"], "medium",
                )

    actions = parsed.get("required_actions")
    if isinstance(actions, list):
        for a in actions:
            if isinstance(a, dict) and "urgency" in a:
                a["urgency"] = coerce_literal(
                    a.get("urgency"), ["low", "medium", "high"], "medium",
                )
