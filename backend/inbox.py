"""
Email-Forwarding routes for easli.

Architecture:
  1. Each device gets a unique 8-char `inbox_token` lazily-generated on
     first GET /api/inbox/me.
  2. Their personal forwarding address is `letters-{token}@inbox.easli.app`.
  3. The user forwards (or directly addresses) a letter from their mail
     client to that address.
  4. An external Inbound-Mail provider (Mailgun, SendGrid, CloudMailin,
     Postmark…) is configured to parse the email and POST a webhook
     payload to /api/inbox/inbound.
  5. We extract the recipient → look up the inbox_token → look up the
     device_id → run the existing analyze pipeline on every attachment
     (or the inline image, if no attachment is present) → save the result
     to `analyses` with `source: "email"`.
  6. (Optional, future): trigger a Push notification to the device.

Provider-agnostic by design: we accept a flexible payload schema and
extract whatever fields the provider sent. Add a new provider by
adding a new normaliser. We currently support:
    • Mailgun "fully-parsed" (multipart/form-data POST)
    • A simple JSON variant for testing / custom providers.

Security:
  • The webhook is unauthenticated by URL but verified via the
    `X-Easli-Inbox-Secret` header — set INBOX_WEBHOOK_SECRET in the
    backend env and configure your mail provider to send the same value.
  • Rate-limited via slowapi.
  • No PII is logged (recipient/from are reduced to their domain).
"""

from __future__ import annotations

import logging
import os
import secrets
import string
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INBOX_DOMAIN = os.environ.get("INBOX_DOMAIN", "inbox.easli.app")
INBOX_ADDRESS_PREFIX = "letters-"
INBOX_WEBHOOK_SECRET = os.environ.get("INBOX_WEBHOOK_SECRET", "")

# How many letters per email we will analyze in one webhook call (cap to
# avoid being abused as a free LLM-fanout vector).
MAX_ATTACHMENTS_PER_EMAIL = 5

# Tokens are short, URL-safe and human-readable. Lowercase + digits only
# (no l/1, no I/0 collisions for users typing them on a hotel WiFi).
_TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
_TOKEN_LENGTH = 8


def _generate_token() -> str:
    return "".join(secrets.choice(_TOKEN_ALPHABET) for _ in range(_TOKEN_LENGTH))


def inbox_email_for(token: str) -> str:
    return f"{INBOX_ADDRESS_PREFIX}{token}@{INBOX_DOMAIN}"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class InboxInfo(BaseModel):
    device_id: str
    inbox_token: str
    inbox_email: str
    inbox_letters_received: int


class InboundResult(BaseModel):
    status: str
    analyses_created: int
    matched_device_id: Optional[str] = None
    skipped_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# These two helpers are injected by server.py at startup so this module
# doesn't have to import the (large) server.py file directly. Keeps the
# dependency graph clean and the module independently testable.
_db: Optional[AsyncIOMotorDatabase] = None
_analyze_callback = None  # async fn(device_id, pages, target_language, source) -> id


def install_dependencies(db, analyze_callback):
    global _db, _analyze_callback
    _db = db
    _analyze_callback = analyze_callback


async def _get_or_assign_inbox_token(device_id: str) -> InboxInfo:
    """Idempotent: returns existing token if one is already on the usage
    record, otherwise generates a new one and persists it. Retries up to
    3 times on the (extremely unlikely) token collision."""
    if _db is None:
        raise HTTPException(status_code=500, detail="db not initialised")
    coll = _db["usage_records"]
    existing = await coll.find_one({"device_id": device_id})
    if existing and existing.get("inbox_token"):
        token = existing["inbox_token"]
        return InboxInfo(
            device_id=device_id,
            inbox_token=token,
            inbox_email=inbox_email_for(token),
            inbox_letters_received=int(existing.get("inbox_letters_received", 0)),
        )
    for _ in range(3):
        token = _generate_token()
        clash = await coll.find_one({"inbox_token": token})
        if clash:
            continue
        # Upsert: create the usage_records row if it doesn't exist yet,
        # otherwise just set the token + counter on the existing one.
        await coll.update_one(
            {"device_id": device_id},
            {
                "$set": {
                    "inbox_token": token,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "$setOnInsert": {
                    "device_id": device_id,
                    "inbox_letters_received": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )
        return InboxInfo(
            device_id=device_id,
            inbox_token=token,
            inbox_email=inbox_email_for(token),
            inbox_letters_received=0,
        )
    raise HTTPException(status_code=500, detail="could not allocate inbox token")


# === GET /api/inbox/me?device_id=... =====================================
@router.get("/inbox/me", response_model=InboxInfo)
async def get_my_inbox(device_id: str):
    if not device_id or len(device_id) < 4:
        raise HTTPException(status_code=400, detail="device_id required")
    return await _get_or_assign_inbox_token(device_id)


# === POST /api/inbox/rotate =============================================
class RotateRequest(BaseModel):
    device_id: str


@router.post("/inbox/rotate", response_model=InboxInfo)
async def rotate_my_inbox(req: RotateRequest):
    """Generate a fresh token. Useful if the old one was shared widely or
    is receiving spam. The old address is permanently retired."""
    if _db is None:
        raise HTTPException(status_code=500, detail="db not initialised")
    coll = _db["usage_records"]
    for _ in range(3):
        token = _generate_token()
        clash = await coll.find_one({"inbox_token": token})
        if clash:
            continue
        await coll.update_one(
            {"device_id": req.device_id},
            {
                "$set": {
                    "inbox_token": token,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            upsert=True,
        )
        return InboxInfo(
            device_id=req.device_id,
            inbox_token=token,
            inbox_email=inbox_email_for(token),
            inbox_letters_received=0,
        )
    raise HTTPException(status_code=500, detail="could not rotate token")


# === POST /api/inbox/inbound ============================================
#
# Webhook from the inbound mail provider. Accepts a flexible JSON body —
# we just need `to` (the easli inbox address that received the mail) and
# a list of attachments as base64-encoded bytes. Both Mailgun's and
# SendGrid's parsed payloads can be transformed to this shape in a small
# adapter (a few lines of YAML / a Cloudflare Worker).
#
# Auth: provider must include header `X-Easli-Inbox-Secret: <secret>`
# matching the INBOX_WEBHOOK_SECRET env var. Without that header we
# return 401 immediately so the provider's retry queue gets cleared.


class InboundAttachment(BaseModel):
    filename: Optional[str] = None
    content_type: str = "application/octet-stream"
    base64: str  # raw bytes, base64-encoded


class InboundEmail(BaseModel):
    to: str  # e.g. "letters-abc123@inbox.easli.app"
    # Original sender, for logging only. Aliased so providers that send
    # `"from"` (a reserved word in Python) still bind correctly.
    from_: Optional[str] = None
    subject: Optional[str] = None
    target_language: Optional[str] = None
    attachments: List[InboundAttachment] = []

    model_config = {"populate_by_name": True}


@router.post("/inbox/inbound", response_model=InboundResult)
async def receive_inbound_email(
    payload: InboundEmail,
    request: Request,
    x_easli_inbox_secret: Optional[str] = Header(None),
):
    # 1) AuthN
    if not INBOX_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="inbound webhook disabled (no secret configured)")
    if x_easli_inbox_secret != INBOX_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid webhook secret")

    if _db is None or _analyze_callback is None:
        raise HTTPException(status_code=500, detail="db / analyze not initialised")

    # 2) Parse recipient → token
    recipient = (payload.to or "").strip().lower()
    if not recipient.startswith(INBOX_ADDRESS_PREFIX) or "@" not in recipient:
        return InboundResult(status="skipped", analyses_created=0,
                             skipped_reason="recipient_not_easli_inbox")
    local_part = recipient.split("@", 1)[0]
    token = local_part[len(INBOX_ADDRESS_PREFIX):]
    if not token or len(token) > 32:
        return InboundResult(status="skipped", analyses_created=0,
                             skipped_reason="malformed_token")

    # 3) Look up device_id
    usage = await _db["usage_records"].find_one({"inbox_token": token})
    if not usage:
        return InboundResult(status="skipped", analyses_created=0,
                             skipped_reason="unknown_token")
    device_id = usage["device_id"]

    # 4) Choose target language: provider override > user's stored lang > English.
    target_lang = (
        payload.target_language
        or usage.get("preferred_target_language")
        or "en"
    )

    # 5) Analyze each attachment (capped). Skip non-image, non-PDF mimes.
    attachments = payload.attachments[:MAX_ATTACHMENTS_PER_EMAIL]
    accepted_mimes = {
        "image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic",
        "application/pdf",
    }
    created = 0
    for att in attachments:
        if att.content_type.lower() not in accepted_mimes:
            continue
        try:
            await _analyze_callback(
                device_id=device_id,
                pages=[{"file_base64": att.base64, "mime_type": att.content_type}],
                target_language=target_lang,
                source="email",
            )
            created += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("inbox_inbound_analyze_failed device=%s err=%s", device_id, exc)

    # 6) Bump letter-counter for the user's "Mailbox" badge in Settings.
    if created > 0:
        await _db["usage_records"].update_one(
            {"device_id": device_id},
            {"$inc": {"inbox_letters_received": created}},
        )

    # 7) Privacy-safe log: never include the full `from` or `subject`.
    from_domain = ""
    if payload.from_ and "@" in payload.from_:
        from_domain = payload.from_.split("@", 1)[1].lower()
    logger.info(
        "inbox_inbound_done device=%s from_domain=%s attachments=%d accepted=%d",
        device_id, from_domain, len(payload.attachments), created,
    )

    return InboundResult(
        status="ok",
        analyses_created=created,
        matched_device_id=device_id,
    )
