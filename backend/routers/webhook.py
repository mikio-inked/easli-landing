"""easli — RevenueCat webhook handler.

Migrated verbatim from server.py in Phase 3b. Authorization is opt-in via
`REVENUECAT_WEBHOOK_AUTH_HEADER`; if the env var is empty, events are still
accepted (RevenueCat retries forever otherwise) but a WARNING is logged on
every hit so operators see the gap immediately.

Privacy: NEVER logs document content, only event_type / product_id /
period_type / metadata. The RC payload itself is parsed once, fields are
pulled out by name, and the rest is dropped on the floor.

Idempotency: NON_RENEWING_PURCHASE events (single-letter top-ups) are
idempotency-keyed on `event.id` via a bounded ring buffer in the user's
`UsageRecord.consumed_idempotency_keys`. A duplicate webhook delivery is
safely a no-op.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request

from core.config import REVENUECAT_WEBHOOK_AUTH_HEADER, db

logger = logging.getLogger("server")

router = APIRouter(prefix="/api", tags=["webhook"])

# Bounded ring buffer for idempotency keys per user, kept in sync with the
# value defined in server.py. Phase 4 will lift this to core.config as part
# of the entitlement service extraction.
_IDEMP_KEY_RING: int = 32


@router.post("/revenuecat/webhook")
async def revenuecat_webhook(
    request: Request,
    authorization: Optional[str] = Header(None),
):
    """RevenueCat → server webhook.

    Authorization is opt-in via REVENUECAT_WEBHOOK_AUTH_HEADER. If the env
    var is empty, we still accept events but log a clear warning each time.
    Privacy: we NEVER log document content here. We log only event_type and
    counts.
    """
    if REVENUECAT_WEBHOOK_AUTH_HEADER:
        if (authorization or "") != REVENUECAT_WEBHOOK_AUTH_HEADER:
            logger.warning("revenuecat_webhook_unauthorized")
            raise HTTPException(
                status_code=401, detail="Invalid webhook authorization",
            )
    else:
        logger.warning(
            "revenuecat_webhook_unverified — REVENUECAT_WEBHOOK_AUTH_HEADER is not set; "
            "events accepted without verification"
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event") or {}
    event_type = (event.get("type") or "").upper()
    app_user_id = event.get("app_user_id") or event.get("original_app_user_id") or ""
    product_id = event.get("product_id") or ""
    period_type = (event.get("period_type") or "").upper()

    logger.info(
        "rc_webhook event=%s product=%s period=%s",
        event_type, product_id, period_type,
    )

    if not app_user_id:
        # Nothing we can attribute to a device. Still 200 so RC stops retrying.
        return {"ok": True, "ignored": "missing_app_user_id"}

    now_iso = datetime.now(timezone.utc).isoformat()

    # --- Subscription lifecycle ---
    if event_type in ("INITIAL_PURCHASE", "RENEWAL", "PRODUCT_CHANGE", "UNCANCELLATION"):
        period_end = event.get("expiration_at_ms")
        period_end_iso = (
            datetime.fromtimestamp(period_end / 1000, tz=timezone.utc).isoformat()
            if isinstance(period_end, (int, float)) else None
        )
        await db.usage_records.update_one(
            {"device_id": app_user_id},
            {
                "$set": {
                    "plus_active": True,
                    "plus_current_period_start": now_iso,
                    "plus_current_period_end": period_end_iso,
                    "plus_monthly_analyses_used": 0,  # reset on each new period
                    "updated_at": now_iso,
                },
                "$setOnInsert": {
                    "device_id": app_user_id,
                    "created_at": now_iso,
                },
            },
            upsert=True,
        )
        return {"ok": True, "applied": event_type.lower()}

    if event_type in ("CANCELLATION", "EXPIRATION"):
        # CANCELLATION = user cancelled but still has access until period_end.
        # EXPIRATION = period actually ended → flip plus_active off.
        if event_type == "EXPIRATION":
            await db.usage_records.update_one(
                {"device_id": app_user_id},
                {"$set": {"plus_active": False, "updated_at": now_iso}},
                upsert=True,
            )
        return {"ok": True, "applied": event_type.lower()}

    # --- Consumable: 1 letter top-up ---
    if event_type == "NON_RENEWING_PURCHASE":
        # Idempotency: RC always sends a stable `event.id` per purchase.
        rc_event_id = event.get("id")
        if rc_event_id:
            already = await db.usage_records.find_one(
                {
                    "device_id": app_user_id,
                    "consumed_idempotency_keys": f"rc:{rc_event_id}",
                },
                {"_id": 1},
            )
            if already:
                return {"ok": True, "ignored": "duplicate_event"}
        await db.usage_records.update_one(
            {"device_id": app_user_id},
            {
                "$inc": {"single_letter_credits": 1},
                "$set": {"updated_at": now_iso},
                "$setOnInsert": {"device_id": app_user_id, "created_at": now_iso},
                **(
                    {"$push": {
                        "consumed_idempotency_keys": {
                            "$each": [f"rc:{rc_event_id}"],
                            "$slice": -_IDEMP_KEY_RING,
                        }
                    }} if rc_event_id else {}
                ),
            },
            upsert=True,
        )
        logger.info("rc_credit_added device=%s product=%s", app_user_id, product_id)
        return {"ok": True, "applied": "single_letter_credit"}

    # Other events (BILLING_ISSUE, SUBSCRIPTION_PAUSED, REFUND, …) — log only.
    return {"ok": True, "ignored": event_type.lower() or "unknown"}
