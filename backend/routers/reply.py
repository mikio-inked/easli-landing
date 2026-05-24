"""easli — reply assistant & translate endpoints.

Migrated verbatim from server.py in Phase 3b of the refactor. Route
bodies are unchanged — they still call helpers/services that currently
live in server.py. Phase 4 will move those helpers out into `services/*`.

Endpoints exposed:
  POST /api/analyses/{analysis_id}/translate       — cached translation
  POST /api/analyses/{analysis_id}/generate-reply  — intent-based reply draft

No `from __future__ import annotations` here — Pydantic v2 cannot resolve
ForwardRefs through FastAPI's body-parameter classifier (we hit this in
Phase 3a on `routers/scan.py:analyze_document`). Sticking to plain runtime
type hints avoids the issue across the entire `routers/` package.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.config import (
    MAX_TRANSLATIONS_PER_ANALYSIS,
    MISTRAL_ANALYSIS_MODEL,
    db,
)
from core.languages import EXPLANATION_LANGUAGES, LANGUAGES
from core.prompts import (
    INTENT_DESCRIPTIONS,
    build_reply_generation_prompt,
    resolve_reply_language,
)
from services.ai_service import (
    mistral_complete_with_retry,
    translate_analysis_with_mistral,
)
from services.entitlement_service import (
    load_or_create_usage,
    to_usage_response,
)
from models import (
    AnalysisRecord,
    GenerateReplyRequest,
    GenerateReplyResponse,
    TranslateRequest,
)

logger = logging.getLogger("server")

router = APIRouter(prefix="/api", tags=["reply"])




# ===========================================================================
# POST /analyses/{id}/translate
# ===========================================================================
@router.post("/analyses/{analysis_id}/translate")
async def translate_analysis_endpoint(analysis_id: str, req: TranslateRequest):
    """Return the analysis for `analysis_id` localised into `target_language`.

    Cache semantics:
      - If target == primary → returns the primary result. Free.
      - If target already translated → returns the cached translation. Free
        (no Mistral call). Logs `translation_cache_hit`.
      - Else: runs a text-only Mistral call, stores the translation, bumps
        the tracking counters (translation_count, translated_languages).
        Never counts as a new document analysis — no free/plus analyses
        quota is consumed.

    Privacy: the log lines below contain only metadata (device + analysis
    id + target code + cache hit/miss). Never the source text, translations,
    sender, or amounts.
    """
    if req.target_language not in EXPLANATION_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported target language")
    if not req.device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    target_code = req.target_language
    target_label = EXPLANATION_LANGUAGES[target_code]

    doc = await db.analyses.find_one(
        {"id": analysis_id, "device_id": req.device_id},
        {"_id": 0, "created_at_dt": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")

    logger.info(
        "translation_requested device=%s analysis=%s target=%s",
        req.device_id, analysis_id, target_code,
    )

    primary_code = doc.get("target_language") or ""
    translations = doc.get("translations") or {}

    # ---- Cache hit: primary language ----------------------------------
    if target_code == primary_code:
        logger.info(
            "translation_cache_hit device=%s analysis=%s target=%s source=primary",
            req.device_id, analysis_id, target_code,
        )
        rec = AnalysisRecord(**doc)
        usage_rec = await load_or_create_usage(req.device_id)
        return {
            **rec.dict(),
            "usage": to_usage_response(usage_rec).dict(),
        }

    # ---- Cache hit: previously translated -----------------------------
    if target_code in translations:
        logger.info(
            "translation_cache_hit device=%s analysis=%s target=%s source=translations",
            req.device_id, analysis_id, target_code,
        )
        cached_result = translations[target_code]
        rec_dict = {
            **doc,
            "target_language": target_code,
            "target_language_label": target_label,
            "result": cached_result,
        }
        rec = AnalysisRecord(**rec_dict)
        usage_rec = await load_or_create_usage(req.device_id)
        return {
            **rec.dict(),
            "usage": to_usage_response(usage_rec).dict(),
        }

    # ---- Miss: call Mistral (text-only) -------------------------------
    distinct_translations = set(translations.keys())
    if len(distinct_translations) >= MAX_TRANSLATIONS_PER_ANALYSIS:
        logger.info(
            "translation_blocked_per_doc_limit device=%s analysis=%s target=%s distinct=%d",
            req.device_id, analysis_id, target_code, len(distinct_translations),
        )
        usage_rec = await load_or_create_usage(req.device_id)
        return JSONResponse(
            status_code=429,
            content={
                "error": "translation_limit_reached",
                "message": (
                    "Du hast das Limit für Sprachwechsel bei diesem Dokument erreicht. "
                    "Mit easli Plus kannst du mehr Sprachen freischalten."
                ),
                "scope": "per_document",
                "usage": to_usage_response(usage_rec).dict(),
            },
        )

    primary_label = doc.get("target_language_label") or LANGUAGES.get(primary_code, "English")
    source_result = doc.get("result") or {}

    try:
        new_result = await translate_analysis_with_mistral(
            source_result=source_result,
            current_target_label=primary_label,
            new_target_label=target_label,
            new_target_code=target_code,
        )
    except HTTPException as http_exc:
        logger.info(
            "translation_failed device=%s analysis=%s target=%s status=%d",
            req.device_id, analysis_id, target_code, http_exc.status_code,
        )
        raise

    # Persist into the analysis doc under `translations[<code>]`.
    await db.analyses.update_one(
        {"id": analysis_id, "device_id": req.device_id},
        {
            "$set": {
                f"translations.{target_code}": new_result.dict(),
            }
        },
    )

    # Bump tracking counters (NOT analysis-quota counters).
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.usage_records.update_one(
        {"device_id": req.device_id},
        {
            "$inc": {"translation_count": 1},
            "$addToSet": {"translated_languages": target_code},
            "$set": {"updated_at": now_iso},
            "$setOnInsert": {
                "device_id": req.device_id,
                "created_at": now_iso,
            },
        },
        upsert=True,
    )

    logger.info(
        "translation_success device=%s analysis=%s target=%s",
        req.device_id, analysis_id, target_code,
    )

    # Build response envelope like /api/analyze so the frontend can drop it
    # straight into setLastResult().
    rec_dict = {
        **doc,
        "target_language": target_code,
        "target_language_label": target_label,
        "result": new_result.dict(),
        "translations": {
            **(doc.get("translations") or {}),
            target_code: new_result.dict(),
        },
    }
    rec = AnalysisRecord(**rec_dict)
    refreshed = await load_or_create_usage(req.device_id)
    return {
        **rec.dict(),
        "usage": to_usage_response(refreshed).dict(),
    }


# ===========================================================================
# POST /analyses/{id}/generate-reply
# ===========================================================================
@router.post(
    "/analyses/{analysis_id}/generate-reply",
    response_model=GenerateReplyResponse,
)
async def generate_reply_endpoint(analysis_id: str, req: GenerateReplyRequest):
    """Generate a tailored reply draft for a specific intent.

    The intent must be one of the canonical ids (inquiry / extension /
    confirm / objection / submit_documents / cancel). Returns the reply
    text in the SOURCE document's language so the user can paste it
    straight into a mailto: composer.
    """
    intent = (req.intent or "").strip().lower()
    if intent not in INTENT_DESCRIPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported intent: {intent}")

    doc = await db.analyses.find_one(
        {"id": analysis_id, "device_id": req.device_id},
        {"_id": 0, "created_at_dt": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")

    target_lang = (doc.get("target_language") or "en").strip()
    target_label = (
        EXPLANATION_LANGUAGES.get(target_lang)
        or LANGUAGES.get(target_lang, "English")
    )

    sys_prompt = build_reply_generation_prompt(
        doc, intent, target_label, req.custom_instruction or "",
        reply_language_code=req.reply_language_code,
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Generate the reply now. Intent: {intent}."},
    ]

    try:
        resp = await mistral_complete_with_retry(
            label="generate_reply",
            model=MISTRAL_ANALYSIS_MODEL,
            messages=msgs,
            temperature=0.4,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "generate_reply_call_failed analysis=%s intent=%s",
            analysis_id, intent,
        )
        raise HTTPException(status_code=502, detail="Reply generation failed") from exc

    raw = (resp.choices[0].message.content or "").strip()
    # Phase R6: expect strict JSON with reply_text + reply_explanation.
    # Fall back to plain-text if parsing fails so a Mistral hiccup doesn't
    # break the reply flow entirely — the explainer just won't show that turn.
    reply_text = ""
    reply_explanation = ""
    try:
        if raw.startswith("```"):
            raw = raw.strip("`").strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            reply_text = (parsed.get("reply_text") or "").strip()
            reply_explanation = (parsed.get("reply_explanation") or "").strip()
    except Exception:
        reply_text = raw
        reply_explanation = ""

    # Strip accidental markdown fences or "Subject:" prefixes that some
    # models still leak through despite JSON-mode.
    if reply_text.startswith("```"):
        reply_text = reply_text.strip("`").strip()
        if reply_text.startswith("plaintext\n"):
            reply_text = reply_text[len("plaintext\n"):]
    for prefix in ("Subject:", "Betreff:", "Asunto:", "Konu:"):
        if reply_text.lower().startswith(prefix.lower()):
            nl = reply_text.find("\n")
            reply_text = reply_text[nl + 1:].strip() if nl != -1 else reply_text

    resolved_code, _ = resolve_reply_language(doc, req.reply_language_code)
    return GenerateReplyResponse(
        reply_text=reply_text,
        intent=intent,
        reply_language_code=resolved_code,
        reply_explanation=reply_explanation,
    )
