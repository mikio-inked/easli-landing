"""easli — chat & per-document message log endpoints.

Migrated verbatim from server.py in Phase 3b. Endpoints exposed:
  POST   /api/analyses/{analysis_id}/chat      — ask a question about a letter
  GET    /api/analyses/{analysis_id}/messages  — fetch the chat thread
  DELETE /api/analyses/{analysis_id}/messages  — wipe the chat thread
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.config import (
    MAX_CHAT_QUESTIONS_PER_DOCUMENT,
    MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
    PAYWALL_MODE,
    db,
)
from core.languages import EXPLANATION_LANGUAGES, LANGUAGES
from models import ChatMessage, ChatRequest
from services.ai_service import chat_about_document
from services.entitlement_service import (
    consume_chat_question,
    load_or_create_usage,
    plus_currently_active,
    to_usage_response,
)

logger = logging.getLogger("server")

router = APIRouter(prefix="/api", tags=["chat"])




# ===========================================================================
# POST /analyses/{id}/chat
# ===========================================================================
@router.post("/analyses/{analysis_id}/chat", response_model=ChatMessage)
async def chat_endpoint(analysis_id: str, req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if len(req.message) > 2000:
        raise HTTPException(status_code=400, detail="Message too long")

    doc = await db.analyses.find_one(
        {"id": analysis_id, "device_id": req.device_id},
        {"_id": 0, "created_at_dt": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # ----- Chat-quota enforcement -----
    # Per-document and total-per-tester caps. Plus subscribers bypass the
    # total cap (they paid for it) but still respect the per-document one.
    usage_rec = await load_or_create_usage(req.device_id)
    per_doc_count = (usage_rec.per_document_chat_questions or {}).get(analysis_id, 0)
    if per_doc_count >= MAX_CHAT_QUESTIONS_PER_DOCUMENT:
        logger.info(
            "chat_blocked_per_document_limit device=%s analysis=%s mode=%s",
            req.device_id, analysis_id, PAYWALL_MODE,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "test_limit_reached" if PAYWALL_MODE == "soft" else "limit_reached",
                "message": "Du hast das Limit für Fragen zu diesem Dokument erreicht.",
                "scope": "per_document",
                "usage": to_usage_response(usage_rec).dict(),
            },
        )
    if (
        not plus_currently_active(usage_rec)
        and usage_rec.total_chat_questions_used >= MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER
    ):
        logger.info(
            "chat_blocked_total_limit device=%s mode=%s",
            req.device_id, PAYWALL_MODE,
        )
        return JSONResponse(
            status_code=429 if PAYWALL_MODE == "soft" else 402,
            content={
                "error": "test_limit_reached" if PAYWALL_MODE == "soft" else "payment_required",
                "message": "Dein Frage-Kontingent ist erreicht. Mit easli Plus stellst du mehr Fragen.",
                "scope": "total",
                "usage": to_usage_response(usage_rec).dict(),
            },
        )

    history = doc.get("messages", []) or []
    # Resolve which language version to use for both the document context
    # AND the reply. Priority:
    #   1) explicit req.target_language (user's current Explanation-Language
    #      pref, or the Result-screen language switch). Accepts ANY of the
    #      25 EU-1 Explanation-Languages since Phase 5.
    #   2) the analysis record's primary target_language (original).
    # If the user asked for a language we haven't translated yet, we silently
    # fall back to the primary — we'd rather reply in the wrong language than
    # block a chat turn on a missing translation. The frontend calls
    # /translate BEFORE switching the UI so this fallback is rare in practice.
    override_code = (
        req.target_language if req.target_language in EXPLANATION_LANGUAGES else None
    )
    primary_code = doc.get("target_language") or ""
    translations = doc.get("translations") or {}
    if override_code and override_code != primary_code and override_code in translations:
        target_code = override_code
        target_label = EXPLANATION_LANGUAGES[override_code]
        chat_doc = {**doc, "result": translations[override_code]}
    elif override_code and override_code == primary_code:
        target_code = primary_code
        target_label = (
            doc.get("target_language_label")
            or EXPLANATION_LANGUAGES.get(primary_code)
            or LANGUAGES.get(primary_code, "English")
        )
        chat_doc = doc
    elif override_code and override_code in EXPLANATION_LANGUAGES:
        # Override requested but no cached translation — reply in the override
        # language anyway using the primary-language document context.
        target_code = override_code
        target_label = EXPLANATION_LANGUAGES[override_code]
        chat_doc = doc
    else:
        target_code = primary_code
        target_label = doc.get("target_language_label") or "English"
        chat_doc = doc

    # Soft per-analysis cap to discourage abuse — 80 user turns.
    user_turns = sum(1 for m in history if m.get("role") == "user")
    if user_turns >= 80:
        raise HTTPException(status_code=429, detail="Chat limit for this document reached")

    response = await chat_about_document(
        chat_doc, history, req.message.strip(), target_label, target_code,
    )

    user_msg = ChatMessage(role="user", content=req.message.strip()).dict()
    assistant_msg = ChatMessage(
        role="assistant", content=response.reply, off_topic=response.off_topic,
    ).dict()

    await db.analyses.update_one(
        {"id": analysis_id, "device_id": req.device_id},
        {"$push": {"messages": {"$each": [user_msg, assistant_msg]}}},
    )

    # Consume the chat-question quota only after a successful reply.
    await consume_chat_question(req.device_id, analysis_id)

    return ChatMessage(**assistant_msg)


# ===========================================================================
# GET /analyses/{id}/messages
# ===========================================================================
@router.get(
    "/analyses/{analysis_id}/messages",
    response_model=List[ChatMessage],
)
async def list_messages(analysis_id: str, device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    doc = await db.analyses.find_one(
        {"id": analysis_id, "device_id": device_id},
        {"_id": 0, "id": 1, "messages": 1},
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    raw = doc.get("messages", []) or []
    return [ChatMessage(**m) for m in raw]


# ===========================================================================
# DELETE /analyses/{id}/messages
# ===========================================================================
@router.delete("/analyses/{analysis_id}/messages")
async def clear_messages(analysis_id: str, device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    res = await db.analyses.update_one(
        {"id": analysis_id, "device_id": device_id},
        {"$set": {"messages": []}},
    )
    return {"cleared": res.modified_count}
