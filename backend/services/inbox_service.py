"""easli — inbound-email pipeline glue.

Wires the inbox webhook (defined in `inbox.py`) to the analyse pipeline
(currently in `routers/scan.py`). Kept out of `routers/inbox.py` because
this is internal plumbing, not an HTTP endpoint.

Phase 5 of the backend refactor moved this code out of `server.py` so
the legacy module entry point could be deleted. The function is called
exactly once from `main.py` at startup via `install_inbox_dependencies()`.
"""

import logging

from core.config import db
from core.languages import EXPLANATION_LANGUAGES
from inbox import install_dependencies as _install_inbox
from models import AnalyzeRequest, PageInput

logger = logging.getLogger("easli.inbox_service")

__all__ = ["install_inbox_dependencies"]


async def _inbox_analyze_callback(
    *,
    device_id: str,
    pages: list,
    target_language: str,
    source: str,
) -> str:
    """Run the existing /analyze flow for an inbound email.

    Email-forwarded analyses currently bypass the per-device free quota —
    they're billed at the user's existing tier on a future revision. For
    now they always succeed (provided Mistral does).

    Privacy: only counts and metadata are logged. The page bodies passed in
    are NEVER written to any log here.
    """
    fake_req = AnalyzeRequest(
        device_id=device_id,
        target_language=(
            target_language if target_language in EXPLANATION_LANGUAGES else "en"
        ),
        pages=[PageInput(**p) for p in pages],
    )

    # The starlette Request object is faked just enough for slowapi to not
    # blow up. The handler lives in routers.scan; we import it LAZILY so
    # this module doesn't trigger the FastAPI/router-graph import chain at
    # boot time (which would break the `main.py` cold-start ordering).
    class _FakeReq:
        client = type("c", (), {"host": "inbox-webhook"})()
        headers: dict = {}
        method = "POST"
        url = type("u", (), {"path": "/api/analyze"})()

    from routers.scan import analyze_document as _analyze_document  # noqa: E402

    result = await _analyze_document(_FakeReq(), fake_req)  # type: ignore[arg-type]
    if hasattr(result, "id"):
        logger.info(
            "inbox_analyze_ok device=%s pages=%d source=%s",
            device_id, len(pages or []), source,
        )
        return result.id  # type: ignore[union-attr]
    # Paywalled path — analyse was blocked by entitlement. Return empty so
    # the inbox webhook still 200s; the email-forwarding flow will surface
    # the limit via a separate notification path later.
    logger.info(
        "inbox_analyze_blocked device=%s pages=%d source=%s",
        device_id, len(pages or []), source,
    )
    return ""


def install_inbox_dependencies() -> None:
    """Wire the inbox webhook to the local analyse pipeline.

    Called by `main.py` exactly once after the FastAPI app is built. Kept as
    a function (rather than executing on module import) so unit tests can
    import this module without triggering Mongo writes.
    """
    _install_inbox(db=db, analyze_callback=_inbox_analyze_callback)
    logger.info("inbox_dependencies_installed")
