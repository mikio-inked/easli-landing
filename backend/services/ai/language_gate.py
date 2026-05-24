"""easli — pre-analysis language gate.

Cheap, lightweight check: is this document actually primarily in a
language we support? Rejects clearly-foreign / unreadable docs BEFORE
the expensive full analysis call and BEFORE consuming the user's quota.

Design goals: <1s wall-clock, <~200 output tokens, never raises.
On any error we return ('unknown', None, 'low') so the caller can
safely fall through to a full analysis.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from core import config as _core_config
from core.config import MISTRAL_ANALYSIS_MODEL
from utils.json_utils import extract_json_from_text

logger = logging.getLogger("server")

# First ~1.5KB of extracted text is plenty for a language guess.
_LANG_GATE_SAMPLE_CHARS: int = 1500

_LANG_GATE_SYSTEM_PROMPT: str = (
    "You are a language classifier for a German-documents assistant. "
    "You will receive the OCR-extracted text of the FIRST page of a document. "
    "Decide whether the document is primarily German.\n\n"
    "IMPORTANT nuances:\n"
    " - A German letter that contains some English product names, technical "
    "terms, legal phrases, company names, URLs, or short English "
    "attachments is STILL German. Classify it as 'de'.\n"
    " - A document written primarily in a non-German language (English, "
    "French, Spanish, Italian, Turkish, Polish, Russian, Chinese, etc.) "
    "is 'non_de'.\n"
    " - If the text is too short, blurry, or ambiguous to decide confidently, "
    "use 'unknown'.\n\n"
    "Respond ONLY with a compact JSON object with exactly these keys:\n"
    "  document_language: 'de' | 'non_de' | 'unknown'\n"
    "  detected_language_code: ISO-639-1 code ('de','en','fr','es','it',"
    "'tr','pl','ru','zh',...) or null\n"
    "  confidence: 'low' | 'medium' | 'high'\n"
    "NO prose, NO code fences."
)


async def detect_document_language(
    page0_text: str,
) -> Tuple[str, Optional[str], str]:
    """Run the lightweight language gate on page-1 OCR text.

    Returns (document_language, detected_language_code, confidence).
    Never raises — on Mistral errors or empty input returns
    ('unknown', None, 'low') so the caller falls through to full analysis.
    """
    client = getattr(_core_config, "mistral_client", None)
    if not client or not page0_text:
        return ("unknown", None, "low")

    sample = page0_text[:_LANG_GATE_SAMPLE_CHARS]

    messages = [
        {"role": "system", "content": _LANG_GATE_SYSTEM_PROMPT},
        {"role": "user", "content": sample},
    ]

    try:
        # We deliberately DO NOT use mistral_complete_with_retry here — the
        # gate must be cheap and fast, and if it's rate-limited or slow we'd
        # rather fall through to full analysis than stall the user.
        response = await client.chat.complete_async(
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=80,
        )
        response_text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.info(
            "language_gate_failed error_type=%s model=%s",
            type(e).__name__, MISTRAL_ANALYSIS_MODEL,
        )
        return ("unknown", None, "low")

    parsed = extract_json_from_text(response_text) or {}
    dl = parsed.get("document_language") or "unknown"
    if dl not in ("de", "non_de", "unknown"):
        dl = "unknown"
    code = parsed.get("detected_language_code")
    if isinstance(code, str):
        code = code.strip().lower() or None
    else:
        code = None
    conf = parsed.get("confidence") or "low"
    if conf not in ("low", "medium", "high"):
        conf = "low"
    return (dl, code, conf)
