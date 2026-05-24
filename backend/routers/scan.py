"""easli — scan, analyze & history endpoints.

Migrated verbatim from server.py in Phase 3a of the refactor. Route
bodies are unchanged — they still call helpers/services that currently
live in server.py (analyze_from_ocr_text, ocr_pages_with_mistral, etc.).
Phase 4 will move those helpers out into `services/*` and the route
bodies will shrink to thin service calls.

Endpoints exposed:
  GET    /api/                                — health/root
  GET    /api/languages                       — supported EXPLANATION_LANGUAGES
  POST   /api/analyze                         — main entry: OCR + analyse
  GET    /api/analyses                        — history list (slim)
  GET    /api/analyses/{analysis_id}          — history detail (full record)
  DELETE /api/analyses/{analysis_id}          — single delete
  DELETE /api/analyses                        — wipe-all-for-device (legacy)
  DELETE /api/history/{device_id}             — DSGVO Art. 17 erasure
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import List, Tuple

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.config import (
    MAX_PAGES_PER_DOCUMENT,
    PAYWALL_MODE,
    RATE_LIMIT_ANALYZE,
    db,
)
from core.languages import EXPLANATION_LANGUAGES
from core.security import limiter
from models import (
    AnalysisListItem,
    AnalysisRecord,
    AnalyzeRequest,
    UsageResponse,
)

logger = logging.getLogger("server")  # keep legacy logger name for log filters

router = APIRouter(prefix="/api", tags=["scan"])


# ---------------------------------------------------------------------------
# Lazy server-helper imports.
# ---------------------------------------------------------------------------
# These live in server.py for now (Phase 3a is structural only — no business
# logic moves yet). We import them at call time inside each handler to keep
# the module-level import graph linear (server.py imports nothing from
# routers/, so we can freely import the other direction without a cycle).
def _server():
    """Late-bound proxy to server.py helpers. Cheap on every call (already
    in `sys.modules` once the app booted)."""
    import server  # local import = no circular-import risk
    return server


# ===========================================================================
# Root / health / languages
# ===========================================================================
@router.get("/")
async def root():
    return {"app": "easli", "status": "ok"}


@router.get("/languages")
async def get_languages():
    # Since Phase EU-1 this returns the full 25-language Explanation set,
    # not just the 7 UI-translated legacy ones.
    return [{"code": k, "label": v} for k, v in EXPLANATION_LANGUAGES.items()]


# ===========================================================================
# POST /analyze — the main scan endpoint.
# ===========================================================================
@router.post("/analyze")
@limiter.limit(RATE_LIMIT_ANALYZE)
async def analyze_document(request: Request, req: AnalyzeRequest):
    s = _server()

    # Validate language — accepts the full EU-1 Explanation-Language set
    # (25 codes) since Phase 5. See `EXPLANATION_LANGUAGES` at top.
    if req.target_language not in EXPLANATION_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    target_language_label = EXPLANATION_LANGUAGES[req.target_language]

    # ----- Entitlement gate (server-side source of truth) -----
    usage_rec = await s._load_or_create_usage(req.device_id)
    decision = s._evaluate_entitlement(usage_rec)
    if not decision.allowed:
        if decision.reason == "test_limit_reached":
            logger.info(
                "test_limit_reached device=%s mode=%s",
                req.device_id, PAYWALL_MODE,
            )
            status_code = 429
        else:
            logger.info(
                "analysis_blocked_payment_required device=%s mode=%s",
                req.device_id, PAYWALL_MODE,
            )
            status_code = 402
        return JSONResponse(
            status_code=status_code,
            content={
                "error": decision.reason,
                "message": decision.message,
                "usage": decision.usage.dict(),
            },
        )

    # ----- Normalise pages input -----
    raw_pages: List[Tuple[str, str]] = []
    if req.pages:
        for p in req.pages:
            raw_pages.append((p.file_base64, p.mime_type))
    elif req.file_base64 and req.mime_type:
        raw_pages.append((req.file_base64, req.mime_type))
    else:
        raise HTTPException(status_code=400, detail="No file content provided")

    if len(raw_pages) == 0:
        raise HTTPException(status_code=400, detail="No file content provided")

    # MAX_PAGES_PER_DOCUMENT is configured via env; hard-cap at 20 for safety.
    MAX_TOTAL_PAGES = max(1, min(MAX_PAGES_PER_DOCUMENT, 20))
    images: List[Tuple[str, str]] = []
    for raw_b64, raw_mime in raw_pages:
        if len(images) >= MAX_TOTAL_PAGES:
            break
        try:
            raw_bytes = base64.b64decode(raw_b64, validate=False)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 file content")
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Empty file content")
        if len(raw_bytes) > 25 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large. Please use a file under 25MB.")
        mime = (raw_mime or "").lower().strip()
        if mime == "application/pdf" or mime == "pdf":
            try:
                budget = MAX_TOTAL_PAGES - len(images)
                pdf_pages = s.pdf_to_images_base64(raw_bytes, max_pages=min(MAX_TOTAL_PAGES, budget))
            except Exception as e:
                logger.exception("PDF conversion failed (error_type=%s)", type(e).__name__)
                raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(e)}")
            images.extend(pdf_pages)
        elif mime in ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"):
            image_mime = "image/jpeg" if mime == "image/jpg" else mime
            images.append((raw_b64, image_mime))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {raw_mime}. Use JPEG, PNG, WEBP or PDF.")

    if not images:
        raise HTTPException(status_code=400, detail="No readable pages found")

    # ----- Compress + OCR all pages -----
    images = [
        s.compress_image_for_vision(idx, b64, mime)
        for idx, (b64, mime) in enumerate(images)
    ]

    try:
        page_texts = await s.ocr_pages_with_mistral(images)
    except Exception as e:
        logger.exception(
            "Mistral OCR stage failed (model=%s, error_type=%s)",
            s.MISTRAL_OCR_MODEL,
            type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI analysis failed.")

    page0_text = page_texts[0] if page_texts else ""
    logger.info(
        "language_gate_checked device=%s pages=%d p0_chars=%d",
        req.device_id, len(page_texts), len(page0_text or ""),
    )
    doc_lang, det_code, conf = await s.detect_document_language(page0_text)

    uncertainty_notice = None
    if doc_lang == "unknown" or conf == "low":
        logger.info(
            "language_gate_unknown device=%s detected=%s confidence=%s",
            req.device_id, det_code or "?", conf,
        )
        uncertainty_notice = (
            "Die Sprache konnte nicht sicher erkannt werden. "
            "Die Analyse kann ungenau sein."
        )
    else:
        logger.info(
            "language_gate_passed device=%s detected=%s confidence=%s doc_lang=%s",
            req.device_id, det_code or "?", conf, doc_lang,
        )

    # ----- Full analysis on OCR text -----
    result = await s.analyze_from_ocr_text(
        page_texts, target_language_label, req.target_language,
    )

    if uncertainty_notice:
        existing = list(result.uncertainties or [])
        if uncertainty_notice not in existing:
            existing.insert(0, uncertainty_notice)
            result.uncertainties = existing

    record = AnalysisRecord(
        device_id=req.device_id,
        target_language=req.target_language,
        target_language_label=target_language_label,
        mime_type=(req.pages[0].mime_type if req.pages else (req.mime_type or "")),
        result=result,
    )

    # Store analysis result only — never the original document.
    doc = record.dict()
    doc["created_at_dt"] = datetime.now(timezone.utc)
    await db.analyses.insert_one(doc)

    # Consume usage only AFTER the analyse call succeeded.
    await s._consume_after_success(
        req.device_id,
        decision.source or "free",
        req.idempotency_key,
    )
    logger.info(
        "analysis_allowed device=%s source=%s mode=%s",
        req.device_id, decision.source, PAYWALL_MODE,
    )

    refreshed = await s._load_or_create_usage(req.device_id)
    return {
        **record.dict(),
        "usage": s._to_usage_response(refreshed).dict(),
    }


# ===========================================================================
# History list / detail / delete
# ===========================================================================
@router.get("/analyses", response_model=List[AnalysisListItem])
async def list_analyses(device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    cursor = db.analyses.find(
        {"device_id": device_id},
        {
            "_id": 0,
            "id": 1,
            "created_at": 1,
            "target_language": 1,
            "target_language_label": 1,
            "result.document_type": 1,
            "result.sender": 1,
            "result.risk_level": 1,
            "result.summary_translated": 1,
            "result.category": 1,
            "result.scam_warning": 1,
            "result.detected_country_code": 1,
        },
    ).sort("created_at", -1).limit(200)
    items: List[AnalysisListItem] = []
    async for doc in cursor:
        result = doc.get("result", {}) or {}
        items.append(AnalysisListItem(
            id=doc.get("id", ""),
            created_at=doc.get("created_at", ""),
            target_language=doc.get("target_language", ""),
            target_language_label=doc.get("target_language_label", ""),
            document_type=result.get("document_type", ""),
            sender=result.get("sender", ""),
            risk_level=result.get("risk_level", "green"),
            summary_translated=result.get("summary_translated", ""),
            category=result.get("category", "other"),
            scam_warning=bool(result.get("scam_warning", False)),
            detected_country_code=result.get("detected_country_code", ""),
        ))
    return items


@router.get("/analyses/{analysis_id}", response_model=AnalysisRecord)
async def get_analysis(analysis_id: str, device_id: str):
    doc = await db.analyses.find_one(
        {"id": analysis_id, "device_id": device_id},
        {"_id": 0, "created_at_dt": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisRecord(**doc)


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str, device_id: str):
    res = await db.analyses.delete_one({"id": analysis_id, "device_id": device_id})
    return {"deleted": res.deleted_count}


@router.delete("/analyses")
async def delete_all_analyses(device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    res = await db.analyses.delete_many({"device_id": device_id})
    return {"deleted": res.deleted_count}


@router.delete("/history/{device_id}")
async def delete_history_for_device(device_id: str):
    """DSGVO Art. 17 — right to erasure.

    Wipes every analysis and every chat message for the given anonymous
    device_id. This is the explicit "Delete my data" endpoint called from the
    Settings screen.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    # Count embedded messages BEFORE delete so we can return an honest total.
    embedded_count = 0
    cursor = db.analyses.find(
        {"device_id": device_id},
        {"messages": 1, "_id": 0},
    )
    async for doc in cursor:
        msgs = doc.get("messages")
        if isinstance(msgs, list):
            embedded_count += len(msgs)

    analyses_res = await db.analyses.delete_many({"device_id": device_id})
    legacy_res = await db.chat_messages.delete_many({"device_id": device_id})

    return {
        "deleted_analyses": analyses_res.deleted_count,
        "deleted_messages": embedded_count + legacy_res.deleted_count,
    }
