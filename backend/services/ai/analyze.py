"""easli — /api/analyze orchestration.

Second half of the 2-stage pipeline: given already-OCR'd per-page text
(produced by services/ocr_service.py) we:
  1. Stitch pages into one text block with explicit page markers.
  2. Guardrail-check that at least one page had readable text.
  3. Build the analyser system prompt (with country/doc-type/scam anchors).
  4. Call Mistral with retry-on-429.
  5. Parse the JSON response.
  6. Normalise it via `services.ai.normalizers.normalize_analysis_payload`.
  7. Validate against the `AnalysisResult` Pydantic model.

Every Mistral error is translated to the exact HTTPException shape the
pre-refactor route handler expected, so the byte-identical contract holds.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import HTTPException

from core import config as _core_config
from core.config import MISTRAL_ANALYSIS_MODEL
from core.exceptions import MistralRateLimited
from core.prompts import build_system_prompt
from models import AnalysisResult
from services.ai.client import mistral_complete_with_retry
from services.ai.normalizers import (
    DEFAULT_DISCLAIMER,
    normalize_analysis_payload,
)
from utils.json_utils import extract_json_from_text

logger = logging.getLogger("server")


def _combine_pages(page_texts: List[str]) -> str:
    """Stitch per-page markdown into a single text block. Page separators
    help the analysis model handle multi-page context correctly.
    """
    if len(page_texts) > 1:
        return "\n\n".join(
            f"--- Seite {i + 1} ---\n\n{txt}" for i, txt in enumerate(page_texts)
        )
    return page_texts[0] if page_texts else ""


def _all_pages_readable(page_texts: List[str]) -> bool:
    """True iff at least one page produced text that isn't the OCR fallback
    placeholder ('[Seite ...]'). Used to bail out with 422 before we burn a
    Mistral analysis call on a page of garbage.
    """
    return any(txt and not txt.startswith("[Seite ") for txt in page_texts)


async def analyze_from_ocr_text(
    page_texts: List[str],
    target_language_label: str,
    target_language_code: str = "",
) -> AnalysisResult:
    """Run the full document-analysis pipeline on already-OCR'd page text."""
    if not getattr(_core_config, "mistral_client", None):
        raise HTTPException(
            status_code=500,
            detail=(
                "Mistral API key not configured. Please set MISTRAL_API_KEY in "
                "backend/.env"
            ),
        )

    combined_text = _combine_pages(page_texts)

    # Guardrail: if OCR extracted literally nothing readable, bail out 422.
    if not _all_pages_readable(page_texts) or not combined_text.strip():
        logger.warning(
            "analysis_unreadable pages=%d total_chars=%d",
            len(page_texts), len(combined_text),
        )
        raise HTTPException(
            status_code=422,
            detail="No readable text was found. Please retry with a clearer photo.",
        )

    page_note = (
        f"The document has {len(page_texts)} page(s). "
        "Treat them as ONE document and produce a single combined analysis."
        if len(page_texts) > 1
        else ""
    )

    user_text = (
        f"Analyze this document and respond ONLY with the JSON object as specified. "
        f"Detect the source language of the document yourself from the text. "
        f"The user's selected target language for the explanation is {target_language_label}. "
        f"Write `reply_draft` and `german_reply_draft` in the SAME language as the source document. "
        f"{page_note}\n\n"
        f"--- EXTRACTED DOCUMENT TEXT (from OCR) ---\n{combined_text}"
    ).strip()

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(target_language_label, target_language_code),
        },
        {"role": "user", "content": user_text},
    ]

    try:
        response = await mistral_complete_with_retry(
            label="analysis",
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        logger.exception(
            "Mistral analysis call failed (model=%s, error_type=%s)",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI analysis failed.")

    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception(
            "Unexpected Mistral response shape (model=%s, choices=%d)",
            MISTRAL_ANALYSIS_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        raise HTTPException(status_code=502, detail="AI returned an empty response")

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error(
            "Could not parse JSON from Mistral analyze response (model=%s, length=%d)",
            MISTRAL_ANALYSIS_MODEL, len(response_text or ""),
        )
        raise HTTPException(
            status_code=502,
            detail="AI returned an invalid response. Please try again.",
        )

    normalize_analysis_payload(parsed, target_language_label, target_language_code)

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception(
            "Validation failed for AI response (model=%s, error_type=%s, top_keys=%d)",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
            len(parsed.keys()) if isinstance(parsed, dict) else 0,
        )
        raise HTTPException(
            status_code=502,
            detail="AI response did not match expected format.",
        )

    if not result.disclaimer:
        result.disclaimer = DEFAULT_DISCLAIMER
    return result
