"""easli — legacy module entry point.

After Phase 4 of the backend refactor this file is effectively empty:
every helper has moved out (services/* + utils/*), every route has moved
out (routers/*), and every Pydantic model lives in `models.schemas`. The
FastAPI app itself is built in `main.py`.

What's left in this file and why:

  1. `api_router` — the historic `APIRouter(prefix="/api")` instance.
     No handlers attach to it any more, but `main.py` still calls
     `app.include_router(api_router)` for symmetry with the original
     structure. Keeping the symbol avoids breaking any out-of-tree
     code or test that imports it.

  2. `_inbox_analyze_callback` + `install_inbox_dependencies` — these
     wire the Phase-4 inbound-email webhook to the analyse pipeline.
     They live here (rather than in `routers/`) because they're an
     INTERNAL plumbing concern, not an HTTP endpoint. `main.py` calls
     `install_inbox_dependencies()` once at startup.

  3. `__getattr__` — PEP 562 lazy attribute resolver. Keeps the old
     deployment command `uvicorn server:app` working by transparently
     forwarding `server.app` → `main.app`. Resolves at access time so
     no circular import is triggered at module load.

Anything else that used to live here has been deleted; if you can't
find a function, grep `services/` or `utils/` first, then `routers/`.
"""

import logging
from typing import List, Optional, Tuple, Any  # noqa: F401 — re-exported for tests

from fastapi import APIRouter

from core.config import db
from models import AnalyzeRequest, PageInput
from core.languages import EXPLANATION_LANGUAGES

# Legacy-style logger name keeps every existing `2026-… - server - INFO`
# log line stable so dashboards / Sentry filters don't break.
logger = logging.getLogger("server")

# Empty APIRouter kept for symmetry — every real route moved to routers/*.
# Removing it would force a corresponding edit in main.py; we'll cleanly
# delete both in a follow-up "Phase 5" pass once we're confident there are
# no external callers left.
api_router = APIRouter(prefix="/api")


# ==================== INBOX (Phase 4 feature) — install hook ====================
from inbox import install_dependencies as _install_inbox  # noqa: E402


async def _inbox_analyze_callback(
    *, device_id: str, pages: list, target_language: str, source: str
) -> str:
    """Thin wrapper that runs the existing /analyze flow for an inbound
    email.

    Email-forwarded analyses currently bypass the per-device free quota —
    they're billed at the user's existing tier on a future revision. For
    now they always succeed (provided Mistral does).
    """
    fake_req = AnalyzeRequest(
        device_id=device_id,
        target_language=target_language if target_language in EXPLANATION_LANGUAGES else "en",
        pages=[PageInput(**p) for p in pages],
    )
    # The starlette Request object is faked just enough for slowapi to not
    # blow up. The handler moved to routers.scan in Phase 3a, so we import
    # it lazily to avoid a circular dependency.
    class _FakeReq:
        client = type("c", (), {"host": "inbox-webhook"})()
        headers: dict = {}
        method = "POST"
        url = type("u", (), {"path": "/api/analyze"})()

    from routers.scan import analyze_document as _analyze_document  # noqa: E402
    result = await _analyze_document(_FakeReq(), fake_req)  # type: ignore[arg-type]
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


# ==================== Backward-compatibility (PEP 562 lazy `app`) ====================
def __getattr__(name):  # noqa: D401
    """Lazy resolver for backward-compatible attribute access on `server`.

    Currently used for: `from server import app`  →  delegates to main.app.
    Resolves at first access, so the circular import (main imports
    api_router from server, server imports app from main) is sidestepped.
    """
    if name == "app":
        from main import app as _app
        return _app
    raise AttributeError(f"module 'server' has no attribute {name!r}")
