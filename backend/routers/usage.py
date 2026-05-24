"""easli — usage, paywall, export & developer-tool endpoints.

Migrated verbatim from server.py in Phase 3a of the refactor. The dev
simulation endpoint at the bottom is intentionally gated by
`DEV_TOOLS_ENABLED` and silently 404s in hard-production mode.

Endpoints exposed:
  GET  /api/usage/{device_id}     — usage meter snapshot
  GET  /api/paywall/config        — client-side paywall configuration
  GET  /api/export                — DSGVO Art. 15 "download my data"
  POST /api/dev/usage/reset       — dev / TestFlight QA only
  POST /api/dev/usage/simulate    — dev / TestFlight QA only
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from core.config import (
    DEV_TOOLS_ENABLED,
    FREE_ANALYSES,
    MAX_CHAT_QUESTIONS_PER_DOCUMENT,
    MAX_PAGES_PER_DOCUMENT,
    MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
    PAYWALL_MODE,
    PLUS_MONTHLY_ANALYSES,
    SOFT_TEST_EXTRA_ANALYSES,
    db,
)
from models import UsageRecord, UsageResponse
from services.entitlement_service import (
    load_or_create_usage,
    to_usage_response,
)

logger = logging.getLogger("server")  # keep legacy logger name for filters

router = APIRouter(prefix="/api", tags=["usage"])




def _require_dev_tools() -> None:
    if not DEV_TOOLS_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")


# ===========================================================================
# Usage meter
# ===========================================================================
@router.get("/usage/{device_id}", response_model=UsageResponse)
async def get_usage(device_id: str):
    """Return the public-safe usage view so the client can render meters."""
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    rec = await load_or_create_usage(device_id)
    return to_usage_response(rec)


# ===========================================================================
# Paywall config (read-only)
# ===========================================================================
@router.get("/paywall/config")
async def get_paywall_config():
    """Lightweight endpoint the client polls on startup.

    Returns ONLY mode + limits + product IDs — never any keys.
    """
    return {
        "paywall_mode": PAYWALL_MODE,
        "free_analyses": FREE_ANALYSES,
        "soft_test_extra_analyses": SOFT_TEST_EXTRA_ANALYSES,
        "max_pages_per_document": MAX_PAGES_PER_DOCUMENT,
        "max_chat_questions_per_document": MAX_CHAT_QUESTIONS_PER_DOCUMENT,
        "max_total_chat_questions_per_tester": MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
        "plus_monthly_analyses": PLUS_MONTHLY_ANALYSES,
        "products": {
            "single_letter": "easli_single_letter",
            "plus_monthly": "easli_plus_monthly",
            "plus_yearly": "easli_plus_yearly",
        },
        "entitlements": {"plus": "plus"},
    }


# ===========================================================================
# DSGVO Art. 15 export
# ===========================================================================
@router.get("/export")
async def export_my_data(device_id: str):
    """DSGVO Art. 15 — let the user download all data we hold for them.

    Returns a single JSON document with every analysis (no MongoDB internal
    fields). The frontend hands this to the share sheet so the user can save
    it to Files / iCloud Drive / send by email.
    """
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    cursor = db.analyses.find(
        {"device_id": device_id},
        {"_id": 0, "created_at_dt": 0},  # strip TTL helper field
    ).sort("created_at", -1)
    records: List[dict] = []
    async for doc in cursor:
        records.append(doc)
    usage_doc = await db.usage_records.find_one({"device_id": device_id}, {"_id": 0}) or {}
    return {
        "app": "easli",
        "device_id": device_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "data_residency": "EU (Mistral AI, Paris)",
        "count": len(records),
        "analyses": records,
        "usage": usage_doc,
    }


# ===========================================================================
# Developer / QA simulation endpoints
# ===========================================================================
# Disabled when DEV_TOOLS_ENABLED is False (i.e. PAYWALL_MODE=hard without
# the explicit DEV_TOOLS_ENABLED=1 flag). When disabled, these routes 404.

@router.post("/dev/usage/reset")
async def dev_reset_usage(device_id: str):
    _require_dev_tools()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    fresh = UsageRecord(
        device_id=device_id,
        last_usage_reset_at=datetime.now(timezone.utc).isoformat(),
    )
    await db.usage_records.replace_one(
        {"device_id": device_id}, fresh.dict(), upsert=True
    )
    return to_usage_response(fresh).dict()


@router.post("/dev/usage/simulate")
async def dev_simulate(device_id: str, scenario: str):
    """Quick scenarios for QA & TestFlight.

    Supported scenarios:
        free_limit             → free_analyses_used = FREE_ANALYSES
        soft_limit             → soft_extra_analyses_used = SOFT_TEST_EXTRA_ANALYSES (and free_limit)
        plus_active            → plus_active=true, period_end = +30 days, monthly_used=0
        plus_expired           → plus_active=false, period_end in the past
        plus_monthly_limit     → plus_active=true, monthly_used=PLUS_MONTHLY_ANALYSES
        add_single_letter      → single_letter_credits += 1
        reset_chat             → total_chat_questions_used=0, per_document_chat_questions={}
    """
    _require_dev_tools()
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")

    await load_or_create_usage(device_id)
    now = datetime.now(timezone.utc)
    update: dict = {"updated_at": now.isoformat()}

    if scenario == "free_limit":
        update["free_analyses_used"] = FREE_ANALYSES
    elif scenario == "soft_limit":
        update["free_analyses_used"] = FREE_ANALYSES
        update["soft_extra_analyses_used"] = SOFT_TEST_EXTRA_ANALYSES
    elif scenario == "plus_active":
        update["plus_active"] = True
        update["plus_current_period_start"] = now.isoformat()
        update["plus_current_period_end"] = (now + timedelta(days=30)).isoformat()
        update["plus_monthly_analyses_used"] = 0
    elif scenario == "plus_expired":
        update["plus_active"] = False
        update["plus_current_period_end"] = (now - timedelta(days=1)).isoformat()
    elif scenario == "plus_monthly_limit":
        update["plus_active"] = True
        update["plus_current_period_start"] = now.isoformat()
        update["plus_current_period_end"] = (now + timedelta(days=30)).isoformat()
        update["plus_monthly_analyses_used"] = PLUS_MONTHLY_ANALYSES
    elif scenario == "add_single_letter":
        await db.usage_records.update_one(
            {"device_id": device_id},
            {"$inc": {"single_letter_credits": 1}, "$set": {"updated_at": now.isoformat()}},
            upsert=True,
        )
        refreshed = await load_or_create_usage(device_id)
        return to_usage_response(refreshed).dict()
    elif scenario == "reset_chat":
        update["total_chat_questions_used"] = 0
        update["per_document_chat_questions"] = {}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario}'")

    await db.usage_records.update_one(
        {"device_id": device_id}, {"$set": update}, upsert=True
    )
    refreshed = await load_or_create_usage(device_id)
    logger.info("dev_simulate device=%s scenario=%s", device_id, scenario)
    return to_usage_response(refreshed).dict()
