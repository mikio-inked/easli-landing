"""easli — Mistral 429 detection & Retry-After parsing.

Kept tiny and SDK-defensive so we can keep the mistralai version bumpable
without digging through retry code. Both helpers handle every shape the
SDK has shipped (.status_code attribute, .response.status_code, error-body
strings).
"""

from typing import Optional

__all__ = [
    "is_rate_limit_error",
    "parse_retry_after_seconds",
    "RATE_LIMIT_DEFAULT_BACKOFF_SECONDS",
    "RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS",
    "RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS",
    "RATE_LIMIT_FALLBACK_CLIENT_HINT",
]

# Default backoff schedule (seconds) used ONLY when Mistral's 429 response
# does not include a Retry-After header. Modern Mistral endpoints almost
# always send one; this fallback is for robustness.
# Total fallback wait: 2 + 4 + 8 = 14s across 4 attempts (5 total attempts).
RATE_LIMIT_DEFAULT_BACKOFF_SECONDS = [2, 4, 8]

# Hard cap on a single sleep — even if Mistral asks us to wait 5 minutes, we
# don't keep an iOS upload connection open that long. The client gets a clean
# 429 with the original Retry-After hint forwarded.
RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS = 20

# Hard cap on total accumulated retry-wait. Tightened from 45s → 25s because
# combined with our 30s per-call Mistral timeout (timeout_ms on the client),
# 25s of retry-wait + 4×30s of API-call time keeps us inside the iOS 120s
# upload-timeout window with margin to spare.
RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS = 25

# Default we surface to the client if Mistral didn't tell us anything.
RATE_LIMIT_FALLBACK_CLIENT_HINT = 8


def is_rate_limit_error(exc: Exception) -> bool:
    """Best-effort detection across mistralai SDK versions.

    Only signals that *unambiguously* mean HTTP 429 trigger a retry. We do
    NOT match the bare phrase "rate limit" anywhere — that would be too
    loose and could pick up unrelated text.
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
    #    emits ("Status 429" comes straight from the SDK formatter; "1300"
    #    is Mistral's documented rate-limit error code).
    msg = str(exc)
    if "Status 429" in msg or '"code":"1300"' in msg or 'raw_status_code":429' in msg:
        return True
    return False


def parse_retry_after_seconds(exc: Exception) -> Optional[int]:
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
        raw = headers.get("retry-after") or headers.get("Retry-After")
    except Exception:
        return None
    if not raw:
        return None
    try:
        v = int(str(raw).strip())
        return max(1, v)
    except (ValueError, TypeError):
        return None
