"""easli — Pydantic schemas (single source of truth).

Every data shape that crosses an API boundary, a DB boundary, or an internal
service boundary is defined here. Pure data classes — no business logic.
Safe to import from anywhere (routes, services, tests, CLI scripts).

Pydantic v2 idioms used throughout:
  • `model_config = ConfigDict(...)` — v2 way to declare model options.
  • `Field(default_factory=...)`     — lazy defaults for mutable values.
  • `Literal[...]`                   — closed enums on strings.
  • Strict type hints              — every field annotated; no `Any`.

DSGVO posture:
  • Every field that could carry user content is OPTIONAL (defaults to
    empty string / empty list). The OCR may legitimately miss fields and we
    never want a validation error to leak a partial document context.
  • `UsageRecord.consumed_idempotency_keys` is the only field with a hard
    privacy bias — it's a small bounded ring buffer of opaque uuids, never
    document content.

EU-1 multilingual additions are marked with "EU-1" or "EU-wide" comments.
Adding optional EU fields here NEVER breaks older DB documents because
Pydantic v2 fills defaults transparently on read-back.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Type aliases — keep enums centralised so a future Literal change touches one
# place. Mypy + IDEs benefit; Pydantic v2 also enforces them at runtime.
# ---------------------------------------------------------------------------
RiskLevel = Literal["green", "yellow", "red"]

ConfidenceLevel = Literal["low", "medium", "high"]

JurisdictionConfidence = Literal["", "low", "medium", "high"]

DocumentCategory = Literal[
    "tax",
    "insurance",
    "rent",
    "bank",
    "health",
    "government",
    "court",
    "utilities",
    "telecom",
    "work",
    "education",
    "other",
]

# Sources allowed in EntitlementDecision — one per quota bucket the analyze
# pipeline can consume from.
EntitlementSource = Literal["plus", "single", "free", "soft"]

# Documented refusal reasons surfaced to the iOS client as JSON body fields.
EntitlementReason = Literal["payment_required", "test_limit_reached"]


# ===========================================================================
# Analysis-result building blocks
# ===========================================================================
class Deadline(BaseModel):
    """A single deadline pulled out of the document.

    `date` is kept as a string (not `datetime`) on purpose: the OCR
    surfaces dates in many local formats ("30 July 2026", "30.07.2026",
    "30/7/2026") and we'd rather hand the user the original glyphs than
    silently re-format.
    """

    date: str = ""
    description: str = ""
    confidence: ConfidenceLevel = "low"


class RequiredAction(BaseModel):
    """One thing the recipient may have to do because of this letter."""

    action: str = ""
    urgency: ConfidenceLevel = "low"
    reason: str = ""


class ExtractedEntities(BaseModel):
    """Concrete data points pulled from the document — used by the Reply
    Assistant to pre-fill recipient / subject / contact fields without
    forcing the user to type them again. Every field is OPTIONAL because
    the OCR may not contain the value (privacy-positive default)."""

    email: str = ""
    subject: str = ""
    reference_number: str = ""
    contact_person: str = ""
    organization: str = ""


class ReplyOption(BaseModel):
    """One actionable reply intent the user can pick. The `id` MUST be one
    of the canonical intent ids so the /generate-reply endpoint can
    interpret it consistently across languages.

    Canonical intent ids:
      • inquiry          (Nachfrage stellen)
      • extension        (Fristverlängerung erbitten)
      • confirm          (Bestätigung / Annahme)
      • objection        (Widerspruch einlegen)
      • submit_documents (Unterlagen nachreichen)
      • cancel           (Kündigung / Widerruf)
    """

    id: str = ""
    label: str = ""
    reason: str = ""
    recommended: bool = False


# ===========================================================================
# AnalysisResult — the biggest schema; result of one /analyze call.
# ===========================================================================
class AnalysisResult(BaseModel):
    """Structured output of the Mistral analyser for one document.

    Backwards-compat invariants (DO NOT change without bumping the API):
      • `german_reply_draft` is preserved as a legacy alias of `reply_draft`.
        Both fields always carry the SAME value after analysis.
      • Every field defaults to empty so older DB docs that pre-date EU-1
        load without validation errors.
    """

    # ----- Source-language detection -----
    source_language: str = ""
    # ISO-639-1 code of the detected source language ('de', 'en', 'fr', …).
    # Empty string when unknown.
    source_language_code: str = ""

    # ----- Target language for the explanation -----
    target_language: str = ""

    # ----- Headline metadata -----
    document_type: str = ""
    sender: str = ""

    # ----- Natural-language fields (in TARGET language) -----
    summary_translated: str = ""
    simple_explanation_translated: str = ""
    key_points: list[str] = Field(default_factory=list)

    # ----- Structured action items -----
    deadlines: list[Deadline] = Field(default_factory=list)
    required_actions: list[RequiredAction] = Field(default_factory=list)

    # ----- Risk surface -----
    risk_level: RiskLevel = "green"
    risk_reason: str = ""

    # ----- Reply drafts -----
    # Polite neutral reply draft, written in the SAME language as the source
    # document. Replaces the old `german_reply_draft` (kept below as alias).
    reply_draft: str = ""
    # Legacy alias kept for backward compat with older clients / DB records.
    german_reply_draft: str = ""
    reply_draft_explanation_translated: str = ""

    # ----- Helpful follow-up surface -----
    questions_to_ask: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    disclaimer: str = ""

    # ----- Reply Assistant (interactive intent-based replies) -----
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    reply_options: list[ReplyOption] = Field(default_factory=list)

    # ----- High-level filtering / sorting fields -----
    category: DocumentCategory = "other"
    scam_warning: bool = False
    scam_reason: str = ""

    # ----- Phase EU-1: European multilingual paperwork support -----
    detected_country_code: str = ""  # ISO 3166-1 alpha-2
    detected_country_name: str = ""
    jurisdiction_confidence: JurisdictionConfidence = ""
    suggested_reply_language_code: str = ""
    confidence_score: float = 0.0
    safety_disclaimer: str = ""


# ===========================================================================
# Request / response shapes
# ===========================================================================
class PageInput(BaseModel):
    """One page of a multi-page scan, sent as base64."""

    file_base64: str
    mime_type: str


class AnalyzeRequest(BaseModel):
    """Body of POST /api/analyze.

    Supports BOTH the legacy single-file payload (`file_base64` + `mime_type`)
    and the modern multi-page array (`pages`). The route normalises both into
    a list before processing.
    """

    device_id: str
    target_language: str  # one of EXPLANATION_LANGUAGES keys (validated in route)

    # Idempotency key generated by the client at the moment the user taps
    # "Analyze". Required-but-tolerated: if the same key is seen twice we
    # do NOT consume usage twice, even if the analysis itself runs again.
    idempotency_key: Optional[str] = None

    # Legacy single-page payload (still supported for upload / older clients):
    file_base64: Optional[str] = None
    mime_type: Optional[str] = None

    # New multi-page payload — used by the iOS-style scanner.
    pages: Optional[list[PageInput]] = None


class AnalysisRecord(BaseModel):
    """One stored /analyze result. Persisted as a single MongoDB document."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    target_language: str
    target_language_label: str
    mime_type: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    result: AnalysisResult
    # Additional language versions of `result`, keyed by target_language code.
    # Populated by POST /api/analyses/{id}/translate. Cached so a repeat
    # language switch is free (no Mistral call).
    translations: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """One turn in a per-document chat thread."""

    role: Literal["user", "assistant"]
    content: str
    off_topic: bool = False
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ChatRequest(BaseModel):
    """Body of POST /api/analyses/{id}/chat."""

    device_id: str
    message: str
    target_language: Optional[str] = None


class TranslateRequest(BaseModel):
    """Body of POST /api/analyses/{id}/translate."""

    device_id: str
    target_language: str  # one of EXPLANATION_LANGUAGES keys


class ChatResponse(BaseModel):
    reply: str
    off_topic: bool


class AnalysisListItem(BaseModel):
    """Slim projection used by GET /api/analyses (history list).

    Kept small on purpose so the history screen can load 100+ items in one
    round-trip without dragging the full result tree.
    """

    id: str
    created_at: str
    target_language: str
    target_language_label: str
    document_type: str
    sender: str
    risk_level: str
    summary_translated: str
    category: str = "other"
    scam_warning: bool = False
    # EU-wide: empty string when the analyser couldn't lock onto a country.
    # Optional + safe default so older DB docs (pre-EU-1) keep loading.
    # Future use: history-by-country filter and per-country statistics.
    detected_country_code: str = ""


# ===========================================================================
# Usage / paywall
# ===========================================================================
class UsageRecord(BaseModel):
    """Server-side usage state per anonymous device_id.

    All counters live ONLY here on the backend — never trust local storage,
    because users can reinstall the app and reset AsyncStorage at will.
    """

    device_id: str

    # ----- Analyse quotas -----
    free_analyses_used: int = 0
    soft_extra_analyses_used: int = 0
    single_letter_credits: int = 0

    # ----- Plus subscription state (mirrored from RevenueCat webhook) -----
    plus_active: bool = False
    plus_current_period_start: Optional[str] = None
    plus_current_period_end: Optional[str] = None
    plus_monthly_analyses_used: int = 0

    # ----- Chat quotas -----
    total_chat_questions_used: int = 0
    per_document_chat_questions: dict[str, int] = Field(default_factory=dict)

    # ----- Idempotency ring (bounded) -----
    consumed_idempotency_keys: list[str] = Field(default_factory=list)

    # ----- Translation tracking -----
    translation_count: int = 0
    translated_languages: list[str] = Field(default_factory=list)

    last_usage_reset_at: Optional[str] = None

    # ----- Email-Forwarding (Phase 4) -----
    # 8-char URL-safe token used to address this device's personal easli
    # inbox: `letters-{inbox_token}@inbox.easli.app`. Generated on first
    # GET /api/inbox/me request and never changes afterwards (rotation is
    # a deliberate user action via DELETE /api/inbox/me). Kept on the
    # usage record because it's effectively a per-device identifier and
    # we already store all per-device state here.
    inbox_token: Optional[str] = None
    inbox_letters_received: int = 0

    # ----- Audit timestamps -----
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class UsageResponse(BaseModel):
    """Public-safe view of usage state.

    The iOS client reads this to render meters; it intentionally excludes
    internal fields like `consumed_idempotency_keys` and `inbox_token`.
    """

    device_id: str
    paywall_mode: str
    free_analyses_used: int
    free_analyses_total: int
    soft_extra_used: int
    soft_extra_total: int
    single_letter_credits: int
    plus_active: bool
    plus_period_end: Optional[str]
    plus_monthly_used: int
    plus_monthly_total: int
    total_chat_questions_used: int
    total_chat_questions_total: int
    per_document_chat_questions: dict[str, int]
    translation_count: int = 0
    translated_languages: list[str] = Field(default_factory=list)


class EntitlementDecision(BaseModel):
    """Outcome of the server-side gate run before every /api/analyze call.

    Pure value object — no DB writes happen inside the evaluator. The route
    only `_consume_after_success` once the analysis returned successfully.
    """

    model_config = ConfigDict(frozen=False)  # mutated by tests sometimes

    allowed: bool
    source: Optional[EntitlementSource] = None
    reason: Optional[EntitlementReason] = None
    message: str = ""
    usage: UsageResponse


# ===========================================================================
# Reply Assistant (Phase R5/R6) — currently defined in server.py for backward
# compat with the existing route handler; will move here in Phase 3 when the
# route is extracted to routers/reply.py. Kept as a placeholder import
# location so callers can already say:
#     from models import GenerateReplyRequest, GenerateReplyResponse
# without breaking. Defined locally here to avoid a circular dep when the
# route eventually relocates.
# ===========================================================================
class GenerateReplyRequest(BaseModel):
    device_id: str
    intent: str = ""
    custom_instruction: str = ""
    # Phase EU-1: optional explicit reply language. When omitted, the endpoint
    # falls back to the analysis' `suggested_reply_language_code`, then to the
    # detected `source_language_code`. ISO-639-1 (e.g. "de", "fr", "nl") or
    # BCP-47 (e.g. "zh-Hans"). Empty string means "use default".
    reply_language_code: Optional[str] = None


class GenerateReplyResponse(BaseModel):
    reply_text: str
    intent: str
    # Phase EU-1: which language the draft is actually written in (ISO-639-1
    # or BCP-47). Empty string means "unknown / fell back to source".
    reply_language_code: str = ""
    # Phase R6 (Reply Explainer): a 2-4 sentence summary of what the
    # reply says, written in the user's EXPLANATION-Language (not the
    # sender's language). Lets a user who reads the letter via
    # translation understand what they are about to send. Empty string
    # when Mistral couldn't produce one — callers should gracefully hide
    # the explainer UI in that case rather than show a blank box.
    reply_explanation: str = ""
