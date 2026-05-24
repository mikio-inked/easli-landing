"""easli — main route module (currently still hosts every /api/* handler).

Phase 1 of the refactor moved infrastructure / config / security / prompts
into the `core/` package and the FastAPI app bootstrap into `main.py`. This
file is now route-and-helper code only — no Sentry init, no Mongo connect,
no Mistral client init, no app instance, no CORS, no startup hook. All of
those live in `core/` and `main.py`.

Phase 3 (planned) will move the route handlers themselves into
`routers/analyze.py`, `routers/chat.py`, `routers/usage.py`, etc., and this
file will shrink to ~150 lines or disappear entirely.

Backward compatibility: `uvicorn server:app` still works thanks to the
`__getattr__` shim at the bottom of this file — it lazily returns the
`app` instance built by `main.py`.
"""

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
import asyncio
import json
import base64
import logging
import re
from pydantic import BaseModel
from typing import List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone

import fitz  # PyMuPDF

# ---------------------------------------------------------------------------
# Core infrastructure — Sentry, Mongo, Mistral, paywall config all live here.
# ---------------------------------------------------------------------------
from core.config import (
    ANALYSIS_TTL_DAYS,  # noqa: F401 — re-exported for any out-of-tree caller
    DEV_TOOLS_ENABLED,
    FREE_ANALYSES,
    MAX_CHAT_QUESTIONS_PER_DOCUMENT,
    MAX_PAGES_PER_DOCUMENT,
    MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
    MAX_TRANSLATIONS_PER_ANALYSIS,
    MISTRAL_ANALYSIS_MODEL,
    MISTRAL_CHAT_MODEL,
    MISTRAL_OCR_MODEL,
    MISTRAL_VISION_MODEL,  # noqa: F401 — kept for legacy imports
    PAYWALL_MODE,
    PLUS_MONTHLY_ANALYSES,
    RATE_LIMIT_ANALYZE as RL_ANALYZE,
    REVENUECAT_WEBHOOK_AUTH_HEADER,
    SOFT_TEST_EXTRA_ANALYSES,
    db,
    mistral_client,
)
from core.exceptions import MistralRateLimited
from core.security import limiter

# Legacy-style logger name keeps every existing `2026-… - server - INFO`
# log line stable so dashboards / Sentry filters don't break.
logger = logging.getLogger("server")

# The single APIRouter that holds every /api/* endpoint defined in this file.
# main.py picks it up via `from server import api_router` and registers it
# on the FastAPI app.
api_router = APIRouter(prefix="/api")


# ==================== MODELS ====================
# Pydantic models and language registries live in dedicated modules now
# (Phase B modularisation). Re-exported here so the rest of server.py and
# any external imports keep working without a sweeping rename.
from languages import (  # noqa: E402
    LANGUAGES,
    EXPLANATION_LANGUAGES,
    resolve_explanation_label,
)
from models import (  # noqa: E402
    Deadline,
    RequiredAction,
    ExtractedEntities,
    ReplyOption,
    AnalysisResult,
    PageInput,
    AnalyzeRequest,
    AnalysisRecord,
    ChatMessage,
    ChatRequest,
    TranslateRequest,
    ChatResponse,
    AnalysisListItem,
    UsageRecord,
    UsageResponse,
    EntitlementDecision,
)
from prompts import (  # noqa: E402
    DEFAULT_REPLY_OPTIONS,
    INTENT_DESCRIPTIONS,
    REPLY_LANG_CODE_TO_ENGLISH,
    resolve_reply_language,
    build_system_prompt,
    build_chat_system_prompt,
    build_translation_system_prompt,
    build_reply_generation_prompt,
)

# Original definitions are preserved below as commented references for
# anyone diff-reviewing this refactor. The runtime now uses the imports
# above. Search for "ORIGINAL_MODELS_KEPT" if you need to verify equivalence.

# ==================== HELPERS ====================

def pdf_to_images_base64(pdf_bytes: bytes, max_pages: int = 5) -> List[Tuple[str, str]]:
    """Convert up to first `max_pages` pages of a PDF to PNG base64.
    Returns a list of (base64, mime) tuples in page order.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF has no pages")
    pages: List[Tuple[str, str]] = []
    page_count = min(max_pages, doc.page_count)
    matrix = fitz.Matrix(2.0, 2.0)
    for i in range(page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=matrix)
        pages.append((base64.b64encode(pix.tobytes("png")).decode("utf-8"), "image/png"))
    doc.close()
    return pages


def extract_json_from_text(text: str) -> Optional[dict]:
    """Try to find a JSON object in the LLM response."""
    if not text:
        return None
    text = text.strip()
    # If wrapped in code fences, strip them
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    # First, try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


def _coerce_literal(value: Any, allowed: List[str], default: str) -> str:
    """Defensively coerce a possibly-chatty Literal field into one of `allowed`.

    Mistral Large 3 occasionally emits values like
        "high (but the deadline itself is fraudulent)"
    which Pydantic Literal[...] rejects with a ValidationError. We extract the
    first matching token (case-insensitive, word-boundary) so the analysis
    doesn't fail just because the model added editorial commentary.
    """
    if not isinstance(value, str):
        return default
    lowered = value.lower()
    for token in allowed:
        # Word-boundary match so 'medium' wins over 'high' if both appear.
        if re.search(r'\b' + re.escape(token) + r'\b', lowered):
            return token
    return default


def _sanitize_literal_fields(parsed: dict) -> None:
    """Normalize every Literal[...] field in-place before Pydantic validation.

    Keeps the sanitizer in one place so adding a new Literal in AnalysisResult
    only needs one corresponding entry here.
    """
    if not isinstance(parsed, dict):
        return

    parsed["risk_level"] = _coerce_literal(
        parsed.get("risk_level"), ["green", "yellow", "red"], "green"
    )

    category_allowed = [
        "tax", "insurance", "rent", "bank", "health", "government", "court",
        "utilities", "telecom", "work", "education", "other",
    ]
    parsed["category"] = _coerce_literal(parsed.get("category"), category_allowed, "other")

    deadlines = parsed.get("deadlines")
    if isinstance(deadlines, list):
        for d in deadlines:
            if isinstance(d, dict) and "confidence" in d:
                d["confidence"] = _coerce_literal(
                    d.get("confidence"), ["low", "medium", "high"], "medium"
                )

    actions = parsed.get("required_actions")
    if isinstance(actions, list):
        for a in actions:
            if isinstance(a, dict) and "urgency" in a:
                a["urgency"] = _coerce_literal(
                    a.get("urgency"), ["low", "medium", "high"], "medium"
                )


# ---- Image compression helper ----------------------------------------------
#
# Mistral Vision charges per image-token. Large iPhone scans (4-8 MB JPEG) blow
# through both the per-request token budget AND the per-minute token-rate-limit
# very fast and have caused HTTP 429s in production. To prevent that we
# downscale any image whose base64 payload exceeds ~1.5 MB binary to a sane
# vision-friendly size (max 1600 x 2200 px, JPEG quality 70) BEFORE the call.
#
# The compression is lossless w.r.t. OCR readability for German letters — we've
# verified 1600px is more than enough for "Sehr geehrte Frau ..." letterhead
# Bodoni/Helvetica resolutions.
#
# Privacy: this function never logs the binary, the base64 string, the EXIF
# data, or any metadata derived from the image content. Only sizes (input vs
# output) and an opaque page index are logged.

# Server-side image-compression knobs. Tuned for Mistral free-tier:
#  • Smaller dimensions reduce per-image vision-token count by ~35-50%, which
#    lets multi-page (3-5 page) scans fit inside the per-second token rate
#    on Mistral's free plan.
#  • The threshold is intentionally low so we re-compress almost everything
#    coming from iOS — even when the client did its own compression pass,
#    a second pass at our tighter target costs <100ms and reliably caps the
#    vision-token usage. Anything truly small (<256 KB binary) is passed
#    through untouched.
#  • Quality 60 still produces excellent OCR for German text at 1280px width
#    (verified empirically with realistic Telekom invoice payloads).
COMPRESS_THRESHOLD_BYTES = 256 * 1024
# Max pixel dimensions the vision model needs (German A4 letters fit easily
# at 1280x1800 — drop from 1600x2200 saves ~35% of vision tokens, critical
# on Mistral free-tier where 4-page scans were hitting 429s).
MAX_VISION_WIDTH_PX = 1280
MAX_VISION_HEIGHT_PX = 1800
JPEG_QUALITY_FOR_VISION = 60

# Lazy-import Pillow so import errors only surface when we actually compress.
try:
    from PIL import Image, ImageOps  # type: ignore[import-not-found]
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover — Pillow is in requirements.txt
    _PIL_AVAILABLE = False


def compress_image_for_vision(
    page_index: int,
    b64: str,
    mime: str,
) -> Tuple[str, str]:
    """Return (compressed_b64, 'image/jpeg') if compression triggered, else
    pass-through (b64, mime).

    Idempotent: small images skip compression entirely. Errors degrade
    gracefully to the original payload — we'd rather try a slightly oversized
    image than fail the whole request.
    """
    # Cheap, accurate-enough binary-size estimate from the base64 length.
    binary_size_estimate = (len(b64) * 3) // 4
    if binary_size_estimate <= COMPRESS_THRESHOLD_BYTES:
        return b64, mime
    if not _PIL_AVAILABLE:
        logger.warning(
            "image_compress_skipped_no_pil page=%d est_bytes=%d",
            page_index, binary_size_estimate,
        )
        return b64, mime

    try:
        import base64 as _b64
        from io import BytesIO

        raw = _b64.b64decode(b64, validate=False)
        before_bytes = len(raw)

        with Image.open(BytesIO(raw)) as img:
            # Honour EXIF rotation so text isn't sideways for Mistral.
            img = ImageOps.exif_transpose(img)
            # Convert to RGB (drop alpha for JPEG, normalise CMYK / palette).
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Pillow's thumbnail() preserves aspect ratio in-place, only
            # downscales (never upscales) — exactly what we want.
            img.thumbnail(
                (MAX_VISION_WIDTH_PX, MAX_VISION_HEIGHT_PX),
                Image.Resampling.LANCZOS,
            )

            buf = BytesIO()
            img.save(
                buf,
                format="JPEG",
                quality=JPEG_QUALITY_FOR_VISION,
                optimize=True,
                progressive=True,
            )
            after_bytes = buf.tell()
            new_b64 = _b64.b64encode(buf.getvalue()).decode("ascii")

        # Privacy: log only sizes — never the bytes.
        logger.info(
            "image_compressed page=%d before_bytes=%d after_bytes=%d ratio=%.2f",
            page_index, before_bytes, after_bytes,
            (after_bytes / before_bytes) if before_bytes else 1.0,
        )
        return new_b64, "image/jpeg"
    except Exception as e:
        # Never let a Pillow failure poison the whole analysis — fall back
        # to the original bytes and let Mistral decide. We log only the type.
        logger.warning(
            "image_compress_failed page=%d error_type=%s — passing original through",
            page_index, type(e).__name__,
        )
        return b64, mime


# ---- Mistral 429 retry helper ----------------------------------------------
#
# Mistral's rate-limit responses are HTTP 429 with body
#   {"object":"error","message":"Rate limit exceeded","type":"rate_limited",
#    "code":"1300","raw_status_code":429}
# The mistralai SDK surfaces this as `SDKError` with an .status_code attribute
# (in modern versions) or a status string in str(e). We detect both.

# `MistralRateLimited` is now defined in `core.exceptions` and re-imported
# at the top of this file. Kept the docstring / context comment above for
# anyone diff-reviewing the refactor.


def _is_rate_limit_error(exc: Exception) -> bool:
    """Best-effort detection across mistralai SDK versions.

    We're conservative: only signals that *unambiguously* mean HTTP 429 trigger
    a retry. We do NOT match the bare phrase "rate limit" anywhere — that
    would be too loose and could pick up unrelated text.
    """
    # 1) Explicit attribute set by modern mistralai SDK.
    sc = getattr(exc, "status_code", None)
    if sc == 429:
        return True
    # 2) HTTPx-style nested response object.
    res = getattr(exc, "http_res", None) or getattr(exc, "response", None)
    if res is not None and getattr(res, "status_code", None) == 429:
        return True
    # 3) Cheap string scrape — but only on the very specific markers Mistral
    #    emits ("Status 429" comes straight from the SDK formatter; "1300" is
    #    Mistral's documented rate-limit error code).
    msg = str(exc)
    if "Status 429" in msg or '"code":"1300"' in msg or "raw_status_code\":429" in msg:
        return True
    return False


# Default backoff schedule (seconds) used ONLY when Mistral's 429 response does
# not include a Retry-After header. Modern Mistral endpoints almost always send
# one; this fallback is for robustness.
#
# Total fallback wait: 2 + 4 + 8 + 16 = 30s across 4 retries (5 total attempts).
_RATE_LIMIT_DEFAULT_BACKOFF_SECONDS = [2, 4, 8]
# Hard cap on a single sleep — even if Mistral asks us to wait 5 minutes, we
# don't keep an iOS upload connection open that long. The client gets a clean
# 429 with the original Retry-After hint forwarded.
_RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS = 20
# Hard cap on total accumulated retry-wait. Tightened from 45s → 25s because
# combined with our 30s per-call Mistral timeout (timeout_ms on the client),
# 25s of retry-wait + 4×30s of API-call time keeps us inside the iOS 120s
# upload-timeout window with margin to spare. Past this we surrender and let
# the user retry from the app (which is friendlier than a 60s+ spinner).
_RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS = 25
# Default we surface to the client if Mistral didn't tell us anything.
_RATE_LIMIT_FALLBACK_CLIENT_HINT = 8


def _parse_retry_after_seconds(exc: Exception) -> Optional[int]:
    """Extract the integer Retry-After hint from a Mistral 429 response.

    The mistralai SDK's error classes inherit from MistralError which exposes
    `.headers` (httpx.Headers). Retry-After can be either delta-seconds (int)
    or an HTTP-date string. We only honour the integer form — HTTP-dates are
    rare in API responses and adding chrono parsing isn't worth the bytes.
    """
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    raw = None
    try:
        # httpx.Headers is case-insensitive but be defensive across SDK shapes.
        raw = headers.get("retry-after") or headers.get("Retry-After")
    except Exception:
        return None
    if not raw:
        return None
    try:
        v = int(str(raw).strip())
        return max(1, v)  # never let a bad value request 0s
    except (ValueError, TypeError):
        return None


async def mistral_complete_with_retry(
    *,
    label: str,  # 'vision' or 'chat' — for logs only
    model: str,
    **kwargs,
):
    """Call mistral_client.chat.complete_async with retries on HTTP 429.

    Retry strategy:
      1) If the 429 response carries a `Retry-After` header, honour it (capped
         at _RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS to avoid keeping a mobile
         upload connection open too long).
      2) Otherwise fall back to an exponential schedule: 2s, 4s, 8s, 16s.
      3) Stop retrying as soon as the cumulative wait would exceed
         _RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS.

    On final failure we raise MistralRateLimited(retry_after=...) where
    retry_after is the LAST hint Mistral gave us (so the iOS toast says
    "try again in N seconds" with the same N that the server told us).

    Privacy: log lines contain only the label, model, attempt number, wait
    duration, and (when present) the server's retry-after hint. They never
    contain message content, image bytes, or API keys.
    """
    last_exc: Optional[Exception] = None
    last_client_hint: int = _RATE_LIMIT_FALLBACK_CLIENT_HINT
    total_waited: int = 0
    max_attempts = len(_RATE_LIMIT_DEFAULT_BACKOFF_SECONDS) + 1  # 5 total

    for attempt in range(max_attempts):
        try:
            return await mistral_client.chat.complete_async(model=model, **kwargs)
        except Exception as e:
            if not _is_rate_limit_error(e):
                # Non-429 → propagate so existing 502 handler runs.
                raise
            last_exc = e

            # Decide how long to wait before the next attempt.
            server_hint = _parse_retry_after_seconds(e)
            if server_hint is not None:
                # Trust the server, but cap it.
                wait = min(server_hint, _RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS)
                # Also remember the *uncapped* server hint so we can forward
                # the truthful number to the iOS client when we ultimately
                # give up.
                last_client_hint = server_hint
            elif attempt < len(_RATE_LIMIT_DEFAULT_BACKOFF_SECONDS):
                wait = _RATE_LIMIT_DEFAULT_BACKOFF_SECONDS[attempt]
                last_client_hint = wait
            else:
                wait = None  # no more attempts left

            # Decide whether we have room in the budget for one more retry.
            attempts_left = attempt + 1 < max_attempts
            within_budget = (
                wait is not None
                and (total_waited + wait) <= _RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS
            )

            if attempts_left and within_budget:
                logger.warning(
                    "mistral_rate_limited label=%s model=%s attempt=%d/%d "
                    "retry_in=%ds server_hint=%s total_waited=%ds",
                    label, model, attempt + 1, max_attempts,
                    wait, server_hint if server_hint is not None else "none",
                    total_waited,
                )
                await asyncio.sleep(wait)
                total_waited += wait
                continue

            # Out of attempts or out of budget — surface a clean exception so
            # the route handler can return HTTP 429 with the truthful
            # Retry-After hint to the iOS client.
            logger.error(
                "mistral_rate_limited_final label=%s model=%s attempts=%d "
                "total_waited=%ds final_hint=%ds",
                label, model, attempt + 1, total_waited, last_client_hint,
            )
            raise MistralRateLimited(retry_after=last_client_hint) from e

    # Defensive — the loop always returns or raises.
    if last_exc is not None:
        raise MistralRateLimited(retry_after=last_client_hint) from last_exc
    raise RuntimeError("mistral_complete_with_retry: unreachable")


async def ocr_pages_with_mistral(
    images: List[Tuple[str, str]],
) -> List[str]:
    """Run Mistral OCR on every page in parallel and return per-page markdown.

    Returns a list the same length as `images`. If a single page fails we
    insert a short "[Seite N konnte nicht gelesen werden]" placeholder so the
    combined-text analysis can still run on the other pages — a user with
    one blurry page gets a useful result for the other three.

    Privacy: only page index + chars-count are logged. Never the text.
    Per-page OCR latency is typically 0.3-1.5s on Mistral's free tier.
    """
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    # A semaphore of 3 keeps us friendly with Mistral's per-second RPS limit
    # on the free tier while still shrinking a 4-page scan to ~2 rounds.
    sem = asyncio.Semaphore(3)

    async def ocr_one(idx: int, b64: str, mime: str) -> str:
        async with sem:
            url_mime = mime or "image/png"
            try:
                # mistralai SDK: ocr.process_async with a document = image_url.
                # We pass a data URL so no upload/file step is needed.
                resp = await mistral_client.ocr.process_async(
                    model=MISTRAL_OCR_MODEL,
                    document={
                        "type": "image_url",
                        "image_url": f"data:{url_mime};base64,{b64}",
                    },
                    include_image_base64=False,
                )
                # resp.pages is a list of OCRPageObject; each has `.markdown`.
                md_pages = []
                for p in (resp.pages or []):
                    md = getattr(p, "markdown", None)
                    if isinstance(md, str) and md.strip():
                        md_pages.append(md)
                combined = "\n\n".join(md_pages).strip()
                logger.info(
                    "ocr_page_ok idx=%d chars=%d",
                    idx, len(combined),
                )
                if not combined:
                    return f"[Seite {idx + 1}: kein Text erkannt]"
                return combined
            except Exception as e:
                # Privacy: log only the exception type + page index.
                logger.warning(
                    "ocr_page_failed idx=%d error_type=%s",
                    idx, type(e).__name__,
                )
                return f"[Seite {idx + 1} konnte nicht gelesen werden]"

    tasks = [ocr_one(i, b64, mime) for i, (b64, mime) in enumerate(images)]
    return await asyncio.gather(*tasks)


async def analyze_with_mistral(
    images: List[Tuple[str, str]],
    target_language_label: str,
    target_language_code: str = "",
) -> AnalysisResult:
    """Backwards-compatible convenience: OCR + language-blind analysis.

    The /api/analyze route does OCR → language-gate → analysis explicitly, but
    some older callers (scripts, tests) may still use this. Kept as a thin
    wrapper so we don't break them.
    """
    if not images:
        raise HTTPException(status_code=400, detail="No image content to analyze")
    images = [
        compress_image_for_vision(idx, b64, mime)
        for idx, (b64, mime) in enumerate(images)
    ]
    page_texts = await ocr_pages_with_mistral(images)
    return await analyze_from_ocr_text(
        page_texts, target_language_label, target_language_code,
    )


async def analyze_from_ocr_text(
    page_texts: List[str],
    target_language_label: str,
    target_language_code: str = "",
) -> AnalysisResult:
    """Second half of the 2-stage pipeline: given already-OCR'd per-page text,
    produce a structured analysis in the user's language.

    Extracted out so the /api/analyze route can interpose a cheap
    language-gate step between OCR and full analysis — and bail out before
    burning full-analysis tokens on non-German documents.
    """
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    # Combine per-page markdown into one text block. Page separators help the
    # analysis model handle multi-page context correctly.
    if len(page_texts) > 1:
        combined_text = "\n\n".join(
            f"--- Seite {i + 1} ---\n\n{txt}" for i, txt in enumerate(page_texts)
        )
    else:
        combined_text = page_texts[0] if page_texts else ""

    # Guardrail: if OCR extracted literally nothing readable, bail out with
    # a clean 422. This usually means the user photographed a blank page,
    # a picture of a face, or something completely unreadable.
    all_readable = any(
        txt and not txt.startswith("[Seite ") for txt in page_texts
    )
    if not all_readable or not combined_text.strip():
        logger.warning(
            "analysis_unreadable pages=%d total_chars=%d",
            len(page_texts), len(combined_text),
        )
        raise HTTPException(
            status_code=422,
            detail="No readable text was found. Please retry with a clearer photo.",
        )

    page_note = (
        f"The document has {len(page_texts)} page(s). "
        "Treat them as ONE document and produce a single combined analysis."
        if len(page_texts) > 1
        else ""
    )

    user_text = (
        f"Analyze this document and respond ONLY with the JSON object as specified. "
        f"Detect the source language of the document yourself from the text. "
        f"The user's selected target language for the explanation is {target_language_label}. "
        f"Write `reply_draft` and `german_reply_draft` in the SAME language as the source document. "
        f"{page_note}\n\n"
        f"--- EXTRACTED DOCUMENT TEXT (from OCR) ---\n{combined_text}"
    ).strip()

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(target_language_label, target_language_code),
        },
        {"role": "user", "content": user_text},
    ]

    try:
        response = await mistral_complete_with_retry(
            label="analysis",
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        logger.exception(
            "Mistral analysis call failed (model=%s, error_type=%s)",
            MISTRAL_ANALYSIS_MODEL,
            type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI analysis failed.")

    response_text = ""
    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception(
            "Unexpected Mistral response shape (model=%s, choices=%d)",
            MISTRAL_ANALYSIS_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        raise HTTPException(status_code=502, detail="AI returned an empty response")

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error(
            "Could not parse JSON from Mistral analyze response (model=%s, length=%d)",
            MISTRAL_ANALYSIS_MODEL,
            len(response_text or ""),
        )
        raise HTTPException(
            status_code=502,
            detail="AI returned an invalid response. Please try again.",
        )

    parsed["target_language"] = target_language_label
    # Source language is detected by the model — don't hardcode "German" any
    # more. If the model forgot the field (rare), fall back to empty string.
    if not isinstance(parsed.get("source_language"), str):
        parsed["source_language"] = ""
    if not isinstance(parsed.get("source_language_code"), str):
        parsed["source_language_code"] = ""
    # Normalise the ISO code.
    parsed["source_language_code"] = (parsed.get("source_language_code") or "").strip().lower()

    # ─── Phase EU-1: normalise the new multilingual fields ──────────────────
    # All fields are OPTIONAL on the model side (older Mistral responses or
    # responses for short documents may omit them). We coerce types and
    # apply sensible fallbacks so AnalysisResult validation never fails.

    # Country code (ISO 3166-1 alpha-2). Empty string when not detected.
    cc = (parsed.get("detected_country_code") or "")
    if not isinstance(cc, str):
        cc = ""
    parsed["detected_country_code"] = cc.strip().upper()
    if not isinstance(parsed.get("detected_country_name"), str):
        parsed["detected_country_name"] = ""
    parsed["detected_country_name"] = (parsed.get("detected_country_name") or "").strip()

    # Jurisdiction confidence — accept only the four canonical values.
    jc = (parsed.get("jurisdiction_confidence") or "").strip().lower()
    if jc not in ("low", "medium", "high"):
        jc = ""
    # If we have no country code, force confidence empty (model might say
    # "low" even with no country — safer to drop it).
    if not parsed["detected_country_code"]:
        jc = ""
    parsed["jurisdiction_confidence"] = jc

    # Suggested reply language defaults to the detected source language.
    # This is the cornerstone of the EU paperwork model: reply in the
    # sender's language unless explicitly overridden later by the user.
    srlc = (parsed.get("suggested_reply_language_code") or "").strip().lower()
    if not srlc:
        srlc = parsed.get("source_language_code") or ""
    parsed["suggested_reply_language_code"] = srlc

    # Confidence score 0.0 – 1.0. Coerce ints/strings → float.
    cs = parsed.get("confidence_score")
    try:
        cs_f = float(cs) if cs is not None else 0.0
    except (TypeError, ValueError):
        cs_f = 0.0
    parsed["confidence_score"] = max(0.0, min(1.0, cs_f))

    # Safety disclaimer must be a string (already in target language).
    if not isinstance(parsed.get("safety_disclaimer"), str):
        parsed["safety_disclaimer"] = ""

    # Back-compat alias: mirror `reply_draft` ↔ `german_reply_draft` so both
    # old clients (which read `german_reply_draft`) and new clients (which
    # read `reply_draft`) see the same value regardless of which key the
    # model happens to emit.
    rd = parsed.get("reply_draft")
    grd = parsed.get("german_reply_draft")
    if isinstance(rd, str) and rd.strip() and not (isinstance(grd, str) and grd.strip()):
        parsed["german_reply_draft"] = rd
    elif isinstance(grd, str) and grd.strip() and not (isinstance(rd, str) and rd.strip()):
        parsed["reply_draft"] = grd

    # Reply Assistant (Phase R5): if Mistral returned nothing we provide a
    # safe localised fallback so the Reply tab in the UI is never empty.
    # We use a tiny per-language label map with English as the safety net.
    REPLY_OPTION_LABELS_EN = {
        "inquiry": "Ask for clarification",
        "extension": "Ask for more time",
        "confirm": "Confirm receipt",
        "objection": "File an objection",
    }
    REPLY_OPTION_LABELS_DE = {
        "inquiry": "Nachfrage stellen",
        "extension": "Frist verlängern",
        "confirm": "Bestätigung",
        "objection": "Widerspruch einlegen",
    }
    raw_options = parsed.get("reply_options")
    if not isinstance(raw_options, list) or not raw_options:
        labels = REPLY_OPTION_LABELS_DE if target_language_code == "de_simple" else REPLY_OPTION_LABELS_EN
        parsed["reply_options"] = [
            {"id": k, "label": v, "reason": "", "recommended": (k == "inquiry")}
            for k, v in labels.items()
        ]
    else:
        # Keep only entries whose id is canonical, and sanitise types.
        cleaned = []
        for opt in raw_options:
            if not isinstance(opt, dict):
                continue
            oid = (opt.get("id") or "").strip().lower()
            if oid not in INTENT_DESCRIPTIONS:
                continue
            cleaned.append({
                "id": oid,
                "label": (opt.get("label") or "").strip(),
                "reason": (opt.get("reason") or "").strip(),
                "recommended": bool(opt.get("recommended")),
            })
        if not cleaned:
            labels = REPLY_OPTION_LABELS_DE if target_language_code == "de_simple" else REPLY_OPTION_LABELS_EN
            cleaned = [
                {"id": k, "label": v, "reason": "", "recommended": (k == "inquiry")}
                for k, v in labels.items()
            ]
        else:
            # Ensure exactly one recommended item.
            if not any(o["recommended"] for o in cleaned):
                cleaned[0]["recommended"] = True
            # "Never empty / never tiny" guarantee: pad with missing canonical
            # ids until the user has at least 4 distinct options. The model
            # often returns 1-2 options for simple letters, but the UI feels
            # broken with so few intent cards.
            if len(cleaned) < 4:
                labels = REPLY_OPTION_LABELS_DE if target_language_code == "de_simple" else REPLY_OPTION_LABELS_EN
                existing_ids = {o["id"] for o in cleaned}
                for canonical_id, label in labels.items():
                    if canonical_id in existing_ids:
                        continue
                    cleaned.append({
                        "id": canonical_id,
                        "label": label,
                        "reason": "",
                        "recommended": False,
                    })
                    if len(cleaned) >= 4:
                        break
        parsed["reply_options"] = cleaned

    # Normalise extracted_entities: ensure it's a dict with the expected keys.
    ee = parsed.get("extracted_entities")
    if not isinstance(ee, dict):
        ee = {}
    parsed["extracted_entities"] = {
        "email": (ee.get("email") or "").strip(),
        "subject": (ee.get("subject") or "").strip(),
        "reference_number": (ee.get("reference_number") or "").strip(),
        "contact_person": (ee.get("contact_person") or "").strip(),
        "organization": (ee.get("organization") or "").strip(),
    }

    _sanitize_literal_fields(parsed)

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception(
            "Validation failed for AI response (model=%s, error_type=%s, top_keys=%d)",
            MISTRAL_ANALYSIS_MODEL,
            type(e).__name__,
            len(parsed.keys()) if isinstance(parsed, dict) else 0,
        )
        raise HTTPException(
            status_code=502,
            detail="AI response did not match expected format.",
        )

    if not result.disclaimer:
        result.disclaimer = (
            "easli provides general information only and does not give legal, tax, financial, or medical advice. "
            "Please verify with the sender or a qualified professional."
        )
    return result


# ==================== LANGUAGE GATE ====================
# Cheap, lightweight pre-analysis check: is this document actually primarily
# German? Reject clearly-non-German docs BEFORE burning a full analysis call
# and BEFORE consuming the user's quota. Aim: <1s and <~200 output tokens.

_LANG_GATE_SAMPLE_CHARS = 1500  # First ~1.5KB of extracted text is plenty

_LANG_GATE_SYSTEM_PROMPT = (
    "You are a language classifier for a German-documents assistant. "
    "You will receive the OCR-extracted text of the FIRST page of a document. "
    "Decide whether the document is primarily German.\n\n"
    "IMPORTANT nuances:\n"
    " - A German letter that contains some English product names, technical "
    "terms, legal phrases, company names, URLs, or short English "
    "attachments is STILL German. Classify it as 'de'.\n"
    " - A document written primarily in a non-German language (English, "
    "French, Spanish, Italian, Turkish, Polish, Russian, Chinese, etc.) "
    "is 'non_de'.\n"
    " - If the text is too short, blurry, or ambiguous to decide confidently, "
    "use 'unknown'.\n\n"
    "Respond ONLY with a compact JSON object with exactly these keys:\n"
    "  document_language: 'de' | 'non_de' | 'unknown'\n"
    "  detected_language_code: ISO-639-1 code ('de','en','fr','es','it',"
    "'tr','pl','ru','zh',...) or null\n"
    "  confidence: 'low' | 'medium' | 'high'\n"
    "NO prose, NO code fences."
)


async def detect_document_language(
    page0_text: str,
) -> Tuple[str, Optional[str], str]:
    """Run the lightweight language gate on page-1 OCR text.

    Returns (document_language, detected_language_code, confidence).
    Never raises — on Mistral errors or timeouts returns ('unknown', None,
    'low') so the caller can safely fall through to full analysis. That's
    the 'fail-open' path the spec asks for.
    """
    if not mistral_client or not page0_text:
        return ('unknown', None, 'low')

    sample = page0_text[:_LANG_GATE_SAMPLE_CHARS]

    messages = [
        {"role": "system", "content": _LANG_GATE_SYSTEM_PROMPT},
        {"role": "user", "content": sample},
    ]

    try:
        # We deliberately DO NOT use mistral_complete_with_retry here — the
        # gate must be cheap and fast, and if it's rate-limited or slow we'd
        # rather fall through to full analysis than stall the user. A single
        # attempt is enough.
        response = await mistral_client.chat.complete_async(
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=80,  # tiny — we only need 3 short fields
        )
        response_text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.info(
            "language_gate_failed error_type=%s model=%s",
            type(e).__name__, MISTRAL_ANALYSIS_MODEL,
        )
        return ('unknown', None, 'low')

    parsed = extract_json_from_text(response_text) or {}
    dl = parsed.get("document_language") or "unknown"
    if dl not in ("de", "non_de", "unknown"):
        dl = "unknown"
    code = parsed.get("detected_language_code")
    if isinstance(code, str):
        code = code.strip().lower() or None
    else:
        code = None
    conf = parsed.get("confidence") or "low"
    if conf not in ("low", "medium", "high"):
        conf = "low"
    return (dl, code, conf)


# ==================== USAGE / ENTITLEMENT HELPERS ====================

# Ring-buffer cap for stored idempotency keys per device — keeps the doc
# small while still preventing double-consumption on legitimate retries.
_IDEMP_KEY_RING = 100


async def _load_or_create_usage(device_id: str) -> UsageRecord:
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


def _to_usage_response(rec: UsageRecord) -> UsageResponse:
    return UsageResponse(
        device_id=rec.device_id,
        paywall_mode=PAYWALL_MODE,
        free_analyses_used=rec.free_analyses_used,
        free_analyses_total=FREE_ANALYSES,
        soft_extra_used=rec.soft_extra_analyses_used,
        soft_extra_total=SOFT_TEST_EXTRA_ANALYSES if PAYWALL_MODE == 'soft' else 0,
        single_letter_credits=rec.single_letter_credits,
        plus_active=_plus_currently_active(rec),
        plus_period_end=rec.plus_current_period_end,
        plus_monthly_used=rec.plus_monthly_analyses_used,
        plus_monthly_total=PLUS_MONTHLY_ANALYSES,
        total_chat_questions_used=rec.total_chat_questions_used,
        total_chat_questions_total=MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER,
        per_document_chat_questions=rec.per_document_chat_questions,
        translation_count=rec.translation_count,
        translated_languages=rec.translated_languages,
    )


def _plus_currently_active(rec: UsageRecord) -> bool:
    if not rec.plus_active:
        return False
    if not rec.plus_current_period_end:
        # Active flag without an end date — trust the flag (e.g. webhook
        # set it; we'll let RevenueCat eventually expire it).
        return True
    try:
        end = datetime.fromisoformat(rec.plus_current_period_end.replace('Z', '+00:00'))
    except ValueError:
        return True
    return end >= datetime.now(timezone.utc)


def _evaluate_entitlement(rec: UsageRecord) -> EntitlementDecision:
    """Pure function: given a UsageRecord, decide whether the next analyze
    is allowed AND which counter to consume on success. We never mutate
    here — consumption happens in `_consume_after_success`.
    """
    usage_view = _to_usage_response(rec)

    # 1. Active easli Plus with quota left → consume from the monthly bucket
    if _plus_currently_active(rec) and rec.plus_monthly_analyses_used < PLUS_MONTHLY_ANALYSES:
        return EntitlementDecision(allowed=True, source='plus', usage=usage_view)

    # 2. Single-letter credit
    if rec.single_letter_credits > 0:
        return EntitlementDecision(allowed=True, source='single', usage=usage_view)

    # 3. Free trial
    if rec.free_analyses_used < FREE_ANALYSES:
        return EntitlementDecision(allowed=True, source='free', usage=usage_view)

    # Free + paid quotas exhausted → mode-specific behaviour:
    if PAYWALL_MODE == 'disabled':
        # Tracking-only mode: never block. We still flag the source so the
        # client can show a "you're past free" indicator if it wants to.
        return EntitlementDecision(allowed=True, source='free', usage=usage_view)

    if PAYWALL_MODE == 'soft':
        if rec.soft_extra_analyses_used < SOFT_TEST_EXTRA_ANALYSES:
            return EntitlementDecision(allowed=True, source='soft', usage=usage_view)
        return EntitlementDecision(
            allowed=False,
            reason='test_limit_reached',
            message='Dein Testkontingent ist erreicht. Danke fürs Testen von easli.',
            usage=usage_view,
        )

    # PAYWALL_MODE == 'hard'
    return EntitlementDecision(
        allowed=False,
        reason='payment_required',
        message='Bitte wähle eine Option im easli-Shop, um fortzufahren.',
        usage=usage_view,
    )


async def _consume_after_success(
    device_id: str,
    source: str,
    idempotency_key: Optional[str],
) -> None:
    """Atomically increment the right counter AFTER the analysis succeeded.

    Idempotency: if we already consumed for this idempotency_key, do nothing.
    Even without a key, this still works — we just lose retry protection.
    """
    if idempotency_key:
        # If the key was consumed before, skip.
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
    if source == 'free':
        inc['free_analyses_used'] = 1
    elif source == 'soft':
        inc['soft_extra_analyses_used'] = 1
    elif source == 'plus':
        inc['plus_monthly_analyses_used'] = 1
    elif source == 'single':
        inc['single_letter_credits'] = -1

    update_ops: dict = {
        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
    }
    if inc:
        update_ops["$inc"] = inc
    if idempotency_key:
        # Push the new key, then trim the array to the last _IDEMP_KEY_RING entries.
        update_ops["$push"] = {
            "consumed_idempotency_keys": {
                "$each": [idempotency_key],
                "$slice": -_IDEMP_KEY_RING,
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


async def _consume_chat_question(device_id: str, analysis_id: str) -> None:
    """Increment chat counters in one atomic update."""
    await db.usage_records.update_one(
        {"device_id": device_id},
        {
            "$inc": {
                "total_chat_questions_used": 1,
                f"per_document_chat_questions.{analysis_id}": 1,
            },
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {
                "device_id": device_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )


# ==================== ROUTES ====================


async def chat_about_document(
    record_dict: dict,
    history: List[dict],
    user_message: str,
    target_language_label: str,
    target_language_code: str = "",
) -> ChatResponse:
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    system_prompt = build_chat_system_prompt(record_dict, target_language_label, target_language_code)

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
            MISTRAL_CHAT_MODEL,
            type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI chat failed.")

    response_text = ""
    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        # Privacy: never log the raw chat response — it may contain document
        # content the user asked the assistant to summarize.
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


# ==================== TRANSLATION (change-language-after-analysis) ====================

# Optional soft cap on how many language versions a single analysis can be
# translated into. Protects the free tier from cost abuse without blocking
# common user flows (the 7 supported languages at most, and in practice
# users switch 1-2 times). Set to a high number on TestFlight so the soft
# paywall never actually hits; tighten in production if needed.
# `MAX_TRANSLATIONS_PER_ANALYSIS` is now imported from `core.config` at the
# top of this file. The original definition lived here:
#   MAX_TRANSLATIONS_PER_ANALYSIS = _int_env('MAX_TRANSLATIONS_PER_ANALYSIS', 6)


async def translate_analysis_with_mistral(
    source_result: dict,
    current_target_label: str,
    new_target_label: str,
    new_target_code: str,
) -> AnalysisResult:
    """Re-localise a previously-analyzed AnalysisResult into a new language.

    This is a TEXT-ONLY Mistral call — no OCR, no vision, no original-image
    access. Cheap (~2-3s) and safe to cache.
    """
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    # Minimal slimmed-down view of the source — we drop any server-side-only
    # fields and keep only what AnalysisResult needs. Ensures the model
    # doesn't get confused by extras.
    ALLOWED_KEYS = {
        "source_language", "source_language_code", "target_language",
        "document_type", "sender",
        "summary_translated", "simple_explanation_translated", "key_points",
        "deadlines", "required_actions", "risk_level", "risk_reason",
        "reply_draft", "german_reply_draft", "reply_draft_explanation_translated",
        "questions_to_ask", "uncertainties", "disclaimer", "category",
        "scam_warning", "scam_reason",
        # Phase R5 — preserved invariant fields (no translation needed for
        # extracted entities; reply_options labels DO get translated though).
        "extracted_entities", "reply_options",
    }
    slim = {k: v for k, v in (source_result or {}).items() if k in ALLOWED_KEYS}
    # If the source only has the legacy `german_reply_draft` (old DB record),
    # also expose it as `reply_draft` so the prompt preserves it correctly.
    if slim.get("german_reply_draft") and not slim.get("reply_draft"):
        slim["reply_draft"] = slim["german_reply_draft"]

    messages = [
        {
            "role": "system",
            "content": build_translation_system_prompt(
                current_target_label, new_target_label, new_target_code,
            ),
        },
        {
            "role": "user",
            "content": (
                f"Re-localise this analysis into {new_target_label}. "
                "Return ONLY the JSON object.\n\n"
                f"INPUT_JSON:\n{json.dumps(slim, ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = await mistral_complete_with_retry(
            label="translate",
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        logger.exception(
            "translation_failed model=%s error_type=%s",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="Translation failed.")

    response_text = ""
    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception(
            "translation_failed_shape model=%s choices=%d",
            MISTRAL_ANALYSIS_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        raise HTTPException(status_code=502, detail="Translation returned empty response")

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error(
            "translation_failed_parse model=%s length=%d",
            MISTRAL_ANALYSIS_MODEL, len(response_text or ""),
        )
        raise HTTPException(
            status_code=502,
            detail="Translation returned invalid JSON.",
        )

    # Enforce factual invariants: regardless of what the model returned,
    # we OVERWRITE the factual fields with the source's values. This is a
    # belt-and-braces safety net in case the model "helpfully" localised
    # a sender name or edited a deadline date.
    for k in (
        "sender",
        "risk_level",
        "category",
        "scam_warning",
        "reply_draft",
        "german_reply_draft",
        "source_language",
        "source_language_code",
        # Phase R5 — preserve extracted entities byte-identical (they're
        # facts pulled from the document, not natural-language fields).
        "extracted_entities",
    ):
        if k in slim:
            parsed[k] = slim[k]
    # reply_options: keep ids + recommended booleans intact, but allow the
    # model to localise `label` and `reason` into the new target language.
    src_options = slim.get("reply_options")
    new_options = parsed.get("reply_options")
    if isinstance(src_options, list) and isinstance(new_options, list):
        # Build an id → src lookup so we can re-anchor by id regardless of
        # ordering changes by the model.
        src_by_id = {o.get("id"): o for o in src_options if isinstance(o, dict)}
        for opt in new_options:
            if not isinstance(opt, dict):
                continue
            src_o = src_by_id.get(opt.get("id"))
            if src_o:
                opt["id"] = src_o.get("id", opt.get("id", ""))
                opt["recommended"] = bool(src_o.get("recommended", opt.get("recommended", False)))
    elif isinstance(src_options, list):
        # Model didn't re-emit reply_options, fall back to source.
        parsed["reply_options"] = src_options
    # Keep reply_draft ↔ german_reply_draft in sync after invariants applied.
    if parsed.get("reply_draft") and not parsed.get("german_reply_draft"):
        parsed["german_reply_draft"] = parsed["reply_draft"]
    elif parsed.get("german_reply_draft") and not parsed.get("reply_draft"):
        parsed["reply_draft"] = parsed["german_reply_draft"]
    # Deep-preserve factual sub-fields of deadlines/required_actions.
    if isinstance(slim.get("deadlines"), list) and isinstance(parsed.get("deadlines"), list):
        src_deadlines = slim["deadlines"]
        for i, d in enumerate(parsed["deadlines"]):
            if isinstance(d, dict) and i < len(src_deadlines):
                src = src_deadlines[i] or {}
                d["date"] = src.get("date", d.get("date", ""))
                d["confidence"] = src.get("confidence", d.get("confidence", "low"))
    if isinstance(slim.get("required_actions"), list) and isinstance(parsed.get("required_actions"), list):
        src_actions = slim["required_actions"]
        for i, a in enumerate(parsed["required_actions"]):
            if isinstance(a, dict) and i < len(src_actions):
                src = src_actions[i] or {}
                a["urgency"] = src.get("urgency", a.get("urgency", "low"))

    # Source language stays whatever the source record had (already copied
    # above via the invariant loop). target_language is always the new one.
    parsed["target_language"] = new_target_label

    _sanitize_literal_fields(parsed)

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception(
            "translation_failed_validation model=%s error_type=%s",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Translation did not match expected format.",
        )

    if not result.disclaimer:
        result.disclaimer = (
            "easli provides general information only and does not give legal, tax, financial, or medical advice. "
            "Please verify with the sender or a qualified professional."
        )
    return result


@api_router.post("/analyses/{analysis_id}/translate")
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
        usage_rec = await _load_or_create_usage(req.device_id)
        return {
            **rec.dict(),
            "usage": _to_usage_response(usage_rec).dict(),
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
        # Validate before returning so clients never see a malformed cached doc.
        rec = AnalysisRecord(**rec_dict)
        usage_rec = await _load_or_create_usage(req.device_id)
        return {
            **rec.dict(),
            "usage": _to_usage_response(usage_rec).dict(),
        }

    # ---- Miss: call Mistral (text-only) -------------------------------
    # Optional soft cap on how many ADDITIONAL translations (not counting
    # the primary language) a single analysis can have. Default 6 means
    # every user can reach all 6 non-primary supported languages. Set to 7
    # if you want paranoid headroom. Never fires for TestFlight traffic.
    distinct_translations = set(translations.keys())
    if len(distinct_translations) >= MAX_TRANSLATIONS_PER_ANALYSIS:
        logger.info(
            "translation_blocked_per_doc_limit device=%s analysis=%s target=%s distinct=%d",
            req.device_id, analysis_id, target_code, len(distinct_translations),
        )
        usage_rec = await _load_or_create_usage(req.device_id)
        return JSONResponse(
            status_code=429,
            content={
                "error": "translation_limit_reached",
                "message": (
                    "Du hast das Limit für Sprachwechsel bei diesem Dokument erreicht. "
                    "Mit easli Plus kannst du mehr Sprachen freischalten."
                ),
                "scope": "per_document",
                "usage": _to_usage_response(usage_rec).dict(),
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

    # Persist into the analysis doc under `translations[<code>]`. Privacy:
    # the stored payload is AnalysisResult shape (already safe — no original
    # text, no OCR dump, just the same kind of content we already store).
    await db.analyses.update_one(
        {"id": analysis_id, "device_id": req.device_id},
        {
            "$set": {
                f"translations.{target_code}": new_result.dict(),
            }
        },
    )

    # Bump tracking counters (NOT analysis-quota counters). Uses $addToSet
    # for translated_languages so re-ordering can't cause duplicates.
    await db.usage_records.update_one(
        {"device_id": req.device_id},
        {
            "$inc": {"translation_count": 1},
            "$addToSet": {"translated_languages": target_code},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            "$setOnInsert": {
                "device_id": req.device_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        upsert=True,
    )

    logger.info(
        "translation_success device=%s analysis=%s target=%s",
        req.device_id, analysis_id, target_code,
    )

    # Build the response in the same envelope shape as /api/analyze so the
    # frontend can drop it straight into setLastResult().
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
    refreshed = await _load_or_create_usage(req.device_id)
    return {
        **rec.dict(),
        "usage": _to_usage_response(refreshed).dict(),
    }


# ============================================================================
# Reply Assistant — interactive intent-based reply generation (Phase R5)
# ============================================================================


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


@api_router.post("/analyses/{analysis_id}/generate-reply", response_model=GenerateReplyResponse)
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
    # Phase 5: use EXPLANATION_LANGUAGES so the reply_explanation is
    # rendered in ALL 25 Explanation-Language options, not just the
    # legacy 7-language LANGUAGES dict.
    target_label = EXPLANATION_LANGUAGES.get(target_lang) or LANGUAGES.get(target_lang, "English")

    sys_prompt = build_reply_generation_prompt(
        doc, intent, target_label, req.custom_instruction or "",
        reply_language_code=req.reply_language_code,
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": f"Generate the reply now. Intent: {intent}."},
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
        logger.exception("generate_reply_call_failed analysis=%s intent=%s", analysis_id, intent)
        raise HTTPException(status_code=502, detail="Reply generation failed") from exc

    raw = (resp.choices[0].message.content or "").strip()
    # Phase R6: expect a strict JSON object with reply_text + reply_explanation.
    # Fall back to treating the whole response as plain text if parsing fails,
    # so a Mistral hiccup doesn't break the reply flow entirely — the explainer
    # just won't show for that one draft.
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

    # Defensive: strip accidental markdown fences or "Subject:" prefixes from
    # the body that some models still leak through despite JSON-mode.
    if reply_text.startswith("```"):
        reply_text = reply_text.strip("`").strip()
        if reply_text.startswith("plaintext\n"):
            reply_text = reply_text[len("plaintext\n"):]
    for prefix in ("Subject:", "Betreff:", "Asunto:", "Konu:"):
        if reply_text.lower().startswith(prefix.lower()):
            # Drop the first line entirely.
            nl = reply_text.find("\n")
            reply_text = reply_text[nl + 1 :].strip() if nl != -1 else reply_text

    # Echo back the resolved reply language so the frontend can label the
    # mailto preview correctly without needing to re-derive it.
    resolved_code, _ = resolve_reply_language(doc, req.reply_language_code)
    return GenerateReplyResponse(
        reply_text=reply_text,
        intent=intent,
        reply_language_code=resolved_code,
        reply_explanation=reply_explanation,
    )


@api_router.post("/analyses/{analysis_id}/chat", response_model=ChatMessage)
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
    usage_rec = await _load_or_create_usage(req.device_id)
    per_doc_count = (usage_rec.per_document_chat_questions or {}).get(analysis_id, 0)
    if per_doc_count >= MAX_CHAT_QUESTIONS_PER_DOCUMENT:
        logger.info(
            "chat_blocked_per_document_limit device=%s analysis=%s mode=%s",
            req.device_id, analysis_id, PAYWALL_MODE,
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "test_limit_reached" if PAYWALL_MODE == 'soft' else "limit_reached",
                "message": "Du hast das Limit für Fragen zu diesem Dokument erreicht.",
                "scope": "per_document",
                "usage": _to_usage_response(usage_rec).dict(),
            },
        )
    if (
        not _plus_currently_active(usage_rec)
        and usage_rec.total_chat_questions_used >= MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER
    ):
        logger.info(
            "chat_blocked_total_limit device=%s mode=%s",
            req.device_id, PAYWALL_MODE,
        )
        return JSONResponse(
            status_code=429 if PAYWALL_MODE == 'soft' else 402,
            content={
                "error": "test_limit_reached" if PAYWALL_MODE == 'soft' else "payment_required",
                "message": "Dein Frage-Kontingent ist erreicht. Mit easli Plus stellst du mehr Fragen.",
                "scope": "total",
                "usage": _to_usage_response(usage_rec).dict(),
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
        # Swap in the translated result so document_context reflects what
        # the user is currently reading.
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
        # language anyway using the primary-language document context. This
        # keeps the UX consistent (chat matches the user's Explanation pref)
        # without doing a synchronous translate call inside the chat handler.
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

    response = await chat_about_document(chat_doc, history, req.message.strip(), target_label, target_code)

    user_msg = ChatMessage(role="user", content=req.message.strip()).dict()
    assistant_msg = ChatMessage(
        role="assistant", content=response.reply, off_topic=response.off_topic
    ).dict()

    await db.analyses.update_one(
        {"id": analysis_id, "device_id": req.device_id},
        {"$push": {"messages": {"$each": [user_msg, assistant_msg]}}},
    )

    # Consume the chat-question quota only after a successful reply.
    await _consume_chat_question(req.device_id, analysis_id)

    return ChatMessage(**assistant_msg)


@api_router.get("/analyses/{analysis_id}/messages", response_model=List[ChatMessage])
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


@api_router.delete("/analyses/{analysis_id}/messages")
async def clear_messages(analysis_id: str, device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    res = await db.analyses.update_one(
        {"id": analysis_id, "device_id": device_id},
        {"$set": {"messages": []}},
    )
    return {"cleared": res.modified_count}
@api_router.post("/revenuecat/webhook")
async def revenuecat_webhook(request: Request, authorization: Optional[str] = Header(None)):
    """RevenueCat → server webhook.

    Authorization is opt-in via REVENUECAT_WEBHOOK_AUTH_HEADER. If the env var
    is empty, we still accept events but log a clear warning each time.
    Privacy: we NEVER log document content here. We log only event_type and
    counts.
    """
    if REVENUECAT_WEBHOOK_AUTH_HEADER:
        if (authorization or "") != REVENUECAT_WEBHOOK_AUTH_HEADER:
            logger.warning("revenuecat_webhook_unauthorized")
            raise HTTPException(status_code=401, detail="Invalid webhook authorization")
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

    # --- Consumable: 1 Brief analysieren ---
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

    # Other events (BILLING_ISSUE, SUBSCRIPTION_PAUSED, REFUND, ...) — log only.
    return {"ok": True, "ignored": event_type.lower() or "unknown"}


# ==================== INBOX (Phase 4) — install hook ====================
# main.py calls `install_inbox_dependencies()` after `core.security` has run,
# so the inbox webhook can wire its dependency on `db` + the analyze callback
# WITHOUT needing to import `app` (which would create a circular import with
# main.py).
from inbox import install_dependencies as _install_inbox  # noqa: E402


async def _inbox_analyze_callback(
    *, device_id: str, pages: list, target_language: str, source: str
) -> str:
    """Thin wrapper that runs the existing /analyze flow for an inbound
    email. Email-forwarded analyses currently bypass the per-device free
    quota — they're billed at the user's existing tier on a future
    revision. For now they always succeed (provided Mistral does)."""
    fake_req = AnalyzeRequest(
        device_id=device_id,
        target_language=target_language if target_language in EXPLANATION_LANGUAGES else "en",
        pages=[PageInput(**p) for p in pages],
    )
    # Reuse the public endpoint body — easiest way to stay byte-equivalent
    # to a hand-scanned letter. The starlette Request object is faked just
    # enough for slowapi to not blow up.
    class _FakeReq:
        client = type("c", (), {"host": "inbox-webhook"})()
        headers: dict = {}
        method = "POST"
        url = type("u", (), {"path": "/api/analyze"})()
    result = await analyze_document(_FakeReq(), fake_req)  # type: ignore[arg-type]
    # The route returns either the AnalysisRecord or a JSONResponse for
    # paywalled cases. For inbox we only care about the happy path.
    if hasattr(result, "id"):
        return result.id  # type: ignore[union-attr]
    return ""


def install_inbox_dependencies() -> None:
    """Wire the inbox webhook to the local analyze pipeline.

    Called from main.py exactly once after the FastAPI app is built. Kept
    as a function (rather than executing on import) so unit tests can
    import server.py without triggering Mongo writes.
    """
    _install_inbox(db=db, analyze_callback=_inbox_analyze_callback)


# ==================== Backward-compatibility ====================
# Old deployment configs (supervisord, Procfile, Railway) launch the backend
# with `uvicorn server:app`. The FastAPI instance has moved to `main.py`
# but we keep this module's `app` name working via PEP 562 module-level
# `__getattr__`. The attribute is resolved lazily so we don't trigger a
# circular import (main.py imports `api_router` from this file).
def __getattr__(name):  # noqa: D401
    """Lazy resolver for backward-compatible attribute access on `server`.

    Currently used for: `from server import app`  →  delegates to main.app.
    """
    if name == "app":
        from main import app as _app  # local import avoids circular load
        return _app
    raise AttributeError(f"module 'server' has no attribute {name!r}")
