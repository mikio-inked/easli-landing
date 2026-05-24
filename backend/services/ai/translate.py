"""easli — /api/analyses/{id}/translate orchestration.

Text-only Mistral call that re-localises a previously-analysed
AnalysisResult into a new explanation language. No OCR, no vision, no
original-image access. Cheap (~2-3s) and safe to cache.

Factual invariants (sender, dates, risk_level, IDs, reply_options ids,
extracted_entities, reply_draft) are enforced AFTER the model responds —
see `apply_translation_invariants` in normalizers.py.
"""

from __future__ import annotations

import json
import logging

from fastapi import HTTPException

from core import config as _core_config
from core.config import MISTRAL_ANALYSIS_MODEL
from core.exceptions import MistralRateLimited
from core.prompts import build_translation_system_prompt
from models import AnalysisResult
from services.ai.client import mistral_complete_with_retry
from services.ai.normalizers import (
    DEFAULT_DISCLAIMER,
    apply_translation_invariants,
    slim_for_translation,
)
from utils.json_utils import extract_json_from_text

logger = logging.getLogger("server")


async def translate_analysis_with_mistral(
    source_result: dict,
    current_target_label: str,
    new_target_label: str,
    new_target_code: str,
) -> AnalysisResult:
    """Re-localise a previously-analysed AnalysisResult into `new_target_label`."""
    if not getattr(_core_config, "mistral_client", None):
        raise HTTPException(
            status_code=500,
            detail=(
                "Mistral API key not configured. Please set MISTRAL_API_KEY in "
                "backend/.env"
            ),
        )

    slim = slim_for_translation(source_result)

    messages = [
        {
            "role": "system",
            "content": build_translation_system_prompt(
                current_target_label, new_target_label, new_target_code,
            ),
        },
        {
            "role": "user",
            "content": (
                f"Re-localise this analysis into {new_target_label}. "
                "Return ONLY the JSON object.\n\n"
                f"INPUT_JSON:\n{json.dumps(slim, ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = await mistral_complete_with_retry(
            label="translate",
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
            "translation_failed model=%s error_type=%s",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="Translation failed.")

    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception(
            "translation_failed_shape model=%s choices=%d",
            MISTRAL_ANALYSIS_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        raise HTTPException(
            status_code=502,
            detail="Translation returned empty response",
        )

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error(
            "translation_failed_parse model=%s length=%d",
            MISTRAL_ANALYSIS_MODEL, len(response_text or ""),
        )
        raise HTTPException(
            status_code=502,
            detail="Translation returned invalid JSON.",
        )

    apply_translation_invariants(parsed, slim, new_target_label)

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception(
            "translation_failed_validation model=%s error_type=%s",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Translation did not match expected format.",
        )

    if not result.disclaimer:
        result.disclaimer = DEFAULT_DISCLAIMER
    return result
