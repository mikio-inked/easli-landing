"""easli — cross-cutting security & request-shaping primitives.

What lives here:
  • The slowapi rate limiter (single instance, shared by every route module).
  • The client-IP resolver that respects X-Forwarded-For from
    Railway / Cloudflare.
  • The diagnostic request-logger middleware (privacy-safe; never reads body).
  • The CORS middleware installer.
  • A safe RequestValidationError handler that NEVER echoes the request body
    back to the client — critical because /api/analyze bodies contain Base64
    image content of personal letters.

What does NOT live here:
  • Admin / JWT / bcrypt logic — those stay in `admin.py` (separate module,
    bounded scope, already battle-tested).
  • Entitlement checks — those belong in `services.entitlement_service` when
    routes are extracted.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Awaitable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.cors import CORSMiddleware

from core.config import ALLOWED_ORIGINS

logger = logging.getLogger("easli.security")


# ---------------------------------------------------------------------------
# 1. Client IP resolver.
# ---------------------------------------------------------------------------
def client_ip(request: Request) -> str:
    """Best-effort client IP for rate limiting.

    Prefers the left-most public IP from X-Forwarded-For (Railway sets this,
    Cloudflare prepends to it), falls back to the direct peer address.
    Same semantics as the original implementation in server.py — a verbatim
    port — we only renamed the function from `_client_ip` to `client_ip`
    because it's now a public utility.
    """
    fwd = request.headers.get("x-forwarded-for") or ""
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return get_remote_address(request)


# ---------------------------------------------------------------------------
# 2. Rate limiter — single shared instance.
# ---------------------------------------------------------------------------
# In-process (memory://) storage. Per-worker counters are fine for our
# 1-3 worker fleet — anything bigger needs a Redis backend, but that's
# a tomorrow problem.
limiter: Limiter = Limiter(
    key_func=client_ip,
    default_limits=[],
    storage_uri="memory://",
)


# ---------------------------------------------------------------------------
# 3. Diagnostic request logger — privacy-safe.
# ---------------------------------------------------------------------------
# Added because we observed a class of failures where iOS clients reported
# 429 errors with no corresponding entries in the standard access log. Logs
# ONE line per request with enough metadata to triage where in the stack a
# request is being dropped:
#   - method, path, query
#   - source IP (X-Forwarded-For / direct)
#   - User-Agent (truncated to 80 chars)
#   - Content-Length (if present)
#   - response status, response time, exception class (if any)
# Privacy: NEVER reads or logs the request body. Only headers + URL.
async def _diag_request_logger(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = time.monotonic()
    fwd = (
        request.headers.get("x-forwarded-for")
        or (request.client.host if request.client else "?")
    )
    ua = (request.headers.get("user-agent") or "")[:80]
    cl = request.headers.get("content-length") or "?"
    method = request.method
    path = request.url.path
    qs = request.url.query or ""
    try:
        response = await call_next(request)
        dur_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "diag_req method=%s path=%s qs=%s status=%s dur_ms=%s "
            "fwd=%s cl=%s ua=%s",
            method, path, qs[:100], response.status_code, dur_ms,
            fwd, cl, ua,
        )
        return response
    except Exception as e:
        dur_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "diag_req method=%s path=%s qs=%s status=EXC dur_ms=%s "
            "fwd=%s cl=%s ua=%s exc_type=%s",
            method, path, qs[:100], dur_ms, fwd, cl, ua, type(e).__name__,
        )
        raise


# ---------------------------------------------------------------------------
# 4. Safe validation-error handler.
# ---------------------------------------------------------------------------
# DSGVO + privacy: never let a malformed request body end up in a stack
# trace (the default FastAPI 422 echoes the offending body, which for
# /api/analyze can include a base64-encoded image). Returns a stripped-down
# 422 with only field paths and the error type — no body, no values, no
# document content.
async def safe_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    safe_errors: list[dict] = []
    for err in exc.errors():
        safe_errors.append({
            "loc": list(err.get("loc", [])),
            "type": err.get("type", "value_error"),
            "msg": err.get("msg", "Invalid input"),
        })
    logger.info(
        "request_validation_error path=%s n_errors=%s",
        request.url.path, len(safe_errors),
    )
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# ---------------------------------------------------------------------------
# 5. Master setup function.
# ---------------------------------------------------------------------------
def configure_security(app: FastAPI) -> None:
    """Wire up the limiter, diag middleware, CORS, and validation handler
    on the given FastAPI app.

    Call this exactly once from `main.py` AFTER `app = FastAPI()` and
    BEFORE any router is included. Order matters: middlewares attached
    after `include_router` are not applied to those routes.
    """
    # 1. Limiter — must be attached to app.state so slowapi's @limiter.limit
    #    decorators on individual routes can find it.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 2. Diag request logger — first middleware so it captures everything.
    app.middleware("http")(_diag_request_logger)

    # 3. CORS — origins are read at import time from core.config.
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_origins=ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Validation-error handler — privacy-safe replacement for FastAPI's
    #    default that echoes the offending body.
    app.add_exception_handler(RequestValidationError, safe_validation_exception_handler)

    logger.info(
        "security_configured cors_origins=%d limiter=memory",
        len(ALLOWED_ORIGINS),
    )
