"""easli — usage / quota / paywall decision service.

Owns every piece of logic that decides:
  • Can this device run another /api/analyze call?
  • Which quota bucket should consume on success (free / soft / single / plus)?
  • Is this device's easli Plus subscription currently valid?

Never raises HTTPException — routes translate the EntitlementDecision into
the appropriate HTTP response. Single source of truth for the data layout
of `usage_records` collection.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from core.config import (
    FREE_ANALYSES,
    MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
    PAYWALL_MODE,
    PLUS_MONTHLY_ANALYSES,
    SOFT_TEST_EXTRA_ANALYSES,
    db,
)
from models import EntitlementDecision, UsageRecord, UsageResponse

logger = logging.getLogger("server")

__all__ = [
    "IDEMP_KEY_RING",
    "load_or_create_usage",
    "to_usage_response",
    "plus_currently_active",
    "evaluate_entitlement",
    "consume_after_success",
    "consume_chat_question",
]

# Ring-buffer cap for stored idempotency keys per device — keeps the doc
# small while still preventing double-consumption on legitimate retries.
IDEMP_KEY_RING: int = 100


async def load_or_create_usage(device_id: str) -> UsageRecord:
    """Fetch the usage doc for a device, creating a fresh one if absent.

    Never raises; if the DB is unreachable the caller will surface that as
    a 500 from the analyze endpoint.
    """
    doc = await db.usage_records.find_one({"device_id": device_id}, {"_id": 0})
    if doc:
        # Be defensive: old documents may be missing newer fields.
        doc.setdefault("per_document_chat_questions", {})
        doc.setdefault("consumed_idempotency_keys", [])
        return UsageRecord(**doc)
    rec = UsageRecord(device_id=device_id)
    await db.usage_records.insert_one(rec.dict())
    return rec


def plus_currently_active(rec: UsageRecord) -> bool:
    if not rec.plus_active:
        return False
    if not rec.plus_current_period_end:
        # Active flag without an end date — trust the flag (e.g. webhook
        # set it; we'll let RevenueCat eventually expire it).
        return True
    try:
        end = datetime.fromisoformat(
            rec.plus_current_period_end.replace("Z", "+00:00")
        )
    except ValueError:
        return True
    return end >= datetime.now(timezone.utc)


def to_usage_response(rec: UsageRecord) -> UsageResponse:
    return UsageResponse(
        device_id=rec.device_id,
        paywall_mode=PAYWALL_MODE,
        free_analyses_used=rec.free_analyses_used,
        free_analyses_total=FREE_ANALYSES,
        soft_extra_used=rec.soft_extra_analyses_used,
        soft_extra_total=SOFT_TEST_EXTRA_ANALYSES if PAYWALL_MODE == "soft" else 0,
        single_letter_credits=rec.single_letter_credits,
        plus_active=plus_currently_active(rec),
        plus_period_end=rec.plus_current_period_end,
        plus_monthly_used=rec.plus_monthly_analyses_used,
        plus_monthly_total=PLUS_MONTHLY_ANALYSES,
        total_chat_questions_used=rec.total_chat_questions_used,
        total_chat_questions_total=MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
        per_document_chat_questions=rec.per_document_chat_questions,
        translation_count=rec.translation_count,
        translated_languages=rec.translated_languages,
    )


def evaluate_entitlement(rec: UsageRecord) -> EntitlementDecision:
    """Pure function: given a UsageRecord, decide whether the next analyze
    is allowed AND which counter to consume on success.

    Never mutates — consumption happens in `consume_after_success`.
    """
    usage_view = to_usage_response(rec)

    # 1. Active easli Plus with quota left → consume from the monthly bucket
    if plus_currently_active(rec) and rec.plus_monthly_analyses_used < PLUS_MONTHLY_ANALYSES:
        return EntitlementDecision(allowed=True, source="plus", usage=usage_view)

    # 2. Single-letter credit
    if rec.single_letter_credits > 0:
        return EntitlementDecision(allowed=True, source="single", usage=usage_view)

    # 3. Free trial
    if rec.free_analyses_used < FREE_ANALYSES:
        return EntitlementDecision(allowed=True, source="free", usage=usage_view)

    # Free + paid quotas exhausted → mode-specific behaviour:
    if PAYWALL_MODE == "disabled":
        # Tracking-only mode: never block.
        return EntitlementDecision(allowed=True, source="free", usage=usage_view)

    if PAYWALL_MODE == "soft":
        if rec.soft_extra_analyses_used < SOFT_TEST_EXTRA_ANALYSES:
            return EntitlementDecision(allowed=True, source="soft", usage=usage_view)
        return EntitlementDecision(
            allowed=False,
            reason="test_limit_reached",
            message="Dein Testkontingent ist erreicht. Danke fürs Testen von easli.",
            usage=usage_view,
        )

    # PAYWALL_MODE == 'hard'
    return EntitlementDecision(
        allowed=False,
        reason="payment_required",
        message="Bitte wähle eine Option im easli-Shop, um fortzufahren.",
        usage=usage_view,
    )


async def consume_after_success(
    device_id: str,
    source: str,
    idempotency_key: Optional[str],
) -> None:
    """Atomically increment the right counter AFTER the analysis succeeded.

    Idempotency: if we already consumed for this idempotency_key, do nothing.
    Even without a key, this still works — we just lose retry protection.
    """
    if idempotency_key:
        existing = await db.usage_records.find_one(
            {"device_id": device_id, "consumed_idempotency_keys": idempotency_key},
            {"_id": 1},
        )
        if existing:
            logger.info(
                "usage_consumed=skip_idempotent device=%s source=%s",
                device_id, source,
            )
            return

    inc: dict = {}
    if source == "free":
        inc["free_analyses_used"] = 1
    elif source == "soft":
        inc["soft_extra_analyses_used"] = 1
    elif source == "plus":
        inc["plus_monthly_analyses_used"] = 1
    elif source == "single":
        inc["single_letter_credits"] = -1

    update_ops: dict = {
        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
    }
    if inc:
        update_ops["$inc"] = inc
    if idempotency_key:
        update_ops["$push"] = {
            "consumed_idempotency_keys": {
                "$each": [idempotency_key],
                "$slice": -IDEMP_KEY_RING,
            }
        }

    await db.usage_records.update_one(
        {"device_id": device_id},
        update_ops,
        upsert=True,
    )

    # Privacy-safe event log: ONLY metadata. No document content.
    logger.info(
        "usage_consumed device=%s source=%s mode=%s",
        device_id, source, PAYWALL_MODE,
    )


async def consume_chat_question(device_id: str, analysis_id: str) -> None:
    """Increment chat counters in one atomic update."""
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.usage_records.update_one(
        {"device_id": device_id},
        {
            "$inc": {
                "total_chat_questions_used": 1,
                f"per_document_chat_questions.{analysis_id}": 1,
            },
            "$set": {"updated_at": now_iso},
            "$setOnInsert": {
                "device_id": device_id,
                "created_at": now_iso,
            },
        },
        upsert=True,
    )
