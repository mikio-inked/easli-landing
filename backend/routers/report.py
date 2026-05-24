"""easli — user-reporting endpoint (Guideline 1.2 / 1.1.6 compliance).

Every analysis result in the app exposes a "Report this analysis" button
that lets a user flag a problematic output (wrong analysis, translation
error, offensive content, missed scam, other). The reports land in this
endpoint, which stores them in the `reports` collection for manual
triage by the operator.

Privacy contract:
  - We NEVER receive the document content; only the analysis_id is
    captured so the operator can look it up via the existing admin tools.
  - The optional free-text comment is capped to 500 chars and stripped
    of NULL bytes; we log only its CHAR COUNT, never its content.
  - Reports are anonymous: device_id is a UUIDv4 generated client-side
    in expo-secure-store, never linked to any account.

Rate-limiting: 5 reports per device per day enforced via a simple
MongoDB count query (slowapi keys per-IP, which is wrong for our flow).
Reports past the daily quota return HTTP 429 with a calm message.

Retention: reports inherit the same 90-day TTL as analyses via the
`reports_ttl_idx` index created in `main.py`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.config import db

logger = logging.getLogger("server")

router = APIRouter(prefix="/api", tags=["report"])

REPORT_COMMENT_MAX = 500
REPORTS_PER_DEVICE_PER_DAY = 5

ReportReason = Literal[
    "inaccurate",
    "translation_error",
    "offensive",
    "scam_missed",
    "other",
]


class ReportSubmission(BaseModel):
    """Inbound POST body for /api/report."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    device_id: str = Field(min_length=8, max_length=128)
    analysis_id: Optional[str] = Field(default=None, max_length=128)
    reason: ReportReason
    comment: Optional[str] = Field(default=None, max_length=REPORT_COMMENT_MAX)
    app_version: Optional[str] = Field(default=None, max_length=32)
    ui_language: Optional[str] = Field(default=None, max_length=12)
    detected_country_code: Optional[str] = Field(default=None, max_length=2)

    @field_validator("comment")
    @classmethod
    def _strip_null_bytes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.replace("\x00", "").strip()
        return cleaned[:REPORT_COMMENT_MAX] or None


class ReportSubmissionResponse(BaseModel):
    ok: bool = True
    report_id: str


@router.post("/report", response_model=ReportSubmissionResponse)
async def submit_report(body: ReportSubmission) -> ReportSubmissionResponse:
    """Persist an anonymous user-report.

    Returns 429 when the device has already submitted
    REPORTS_PER_DEVICE_PER_DAY reports in the last 24h — the user-facing
    error message stays calm.
    """
    # Daily-quota check. We don't lock; the race is harmless (worst-case
    # we accept one extra report per device per day).
    one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
    recent_count = await db.reports.count_documents({
        "device_id": body.device_id,
        "created_at": {"$gte": one_day_ago},
    })
    if recent_count >= REPORTS_PER_DEVICE_PER_DAY:
        # Privacy: don't leak the exact count to the client.
        logger.info(
            "report_rate_limited device=%s recent=%d",
            body.device_id[:8] + "…", recent_count,
        )
        raise HTTPException(
            status_code=429,
            detail="You have reached today's report limit. Try again tomorrow.",
        )

    record = {
        "_id": str(uuid.uuid4()),
        "device_id": body.device_id,
        "analysis_id": body.analysis_id or "",
        "reason": body.reason,
        "comment": body.comment or "",
        "app_version": body.app_version or "",
        "ui_language": body.ui_language or "",
        "detected_country_code": (body.detected_country_code or "").upper()[:2],
        "created_at": datetime.now(timezone.utc),
        "status": "new",  # new → triaged → resolved (Admin Panel)
    }
    await db.reports.insert_one(record)

    # Metadata-only log line. Comment CONTENT never appears in logs.
    logger.info(
        "report_submitted reason=%s has_analysis=%s has_comment=%s comment_chars=%d "
        "ui_lang=%s country=%s",
        body.reason,
        "yes" if record["analysis_id"] else "no",
        "yes" if record["comment"] else "no",
        len(record["comment"]),
        record["ui_language"] or "-",
        record["detected_country_code"] or "-",
    )

    return ReportSubmissionResponse(ok=True, report_id=record["_id"])
