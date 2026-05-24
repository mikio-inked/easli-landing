"""easli — /api/analyses/{id}/chat orchestration.

Text-only chat-about-document flow. Builds a system prompt from the
stored AnalysisResult, appends the last 12 turns of the embedded message
history, sends the user's question and returns a `ChatResponse`.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import HTTPException

from core import config as _core_config
from core.config import MISTRAL_CHAT_MODEL
from core.exceptions import MistralRateLimited
from core.prompts import build_chat_system_prompt
from models import ChatResponse
from services.ai.client import mistral_complete_with_retry
from utils.json_utils import extract_json_from_text

logger = logging.getLogger("server")


async def chat_about_document(
    record_dict: dict,
    history: List[dict],
    user_message: str,
    target_language_label: str,
    target_language_code: str = "",
) -> ChatResponse:
    if not getattr(_core_config, "mistral_client", None):
        raise HTTPException(
            status_code=500,
            detail=(
                "Mistral API key not configured. Please set MISTRAL_API_KEY in "
                "backend/.env"
            ),
        )

    system_prompt = build_chat_system_prompt(
        record_dict, target_language_label, target_language_code,
    )

    # Build a proper Mistral message list — system + last 12 turns + current user.
    messages: List[dict] = [{"role": "system", "content": system_prompt}]
    for m in (history or [])[-12:]:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content") or ""
        if not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                f"{user_message}\n\n"
                f"Reply now as the assistant in {target_language_label}, following ALL rules. "
                "Output ONLY the JSON object."
            ),
        }
    )

    try:
        response = await mistral_complete_with_retry(
            label="chat",
            model=MISTRAL_CHAT_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        # Privacy: only log the model + exception type, never the messages.
        logger.exception(
            "Mistral chat call failed (model=%s, error_type=%s)",
            MISTRAL_CHAT_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI chat failed.")

    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        # Privacy: never log the raw chat response.
        logger.exception(
            "Unexpected Mistral chat response shape (model=%s, choices=%d)",
            MISTRAL_CHAT_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        return ChatResponse(reply="", off_topic=False)

    parsed = extract_json_from_text(response_text)
    if not parsed or "reply" not in parsed:
        # Fall back to treating the raw text as the reply if parsing fails.
        return ChatResponse(reply=(response_text or "").strip()[:1500], off_topic=False)

    return ChatResponse(
        reply=str(parsed.get("reply", "")).strip(),
        off_topic=bool(parsed.get("off_topic", False)),
    )
