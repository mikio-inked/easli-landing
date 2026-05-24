"""easli — FastAPI application bootstrap.

This file is the new, slim entry point for the easli backend. It does NOTHING
except:
  1. Force `core.config` to load first (so dotenv + Sentry are wired BEFORE
     any other module touches an env var or raises an exception).
  2. Instantiate the FastAPI `app`.
  3. Configure cross-cutting concerns (rate limiter, CORS, diag middleware,
     safe validation handler) via `core.security.configure_security(app)`.
  4. Register every router (api routes, inbox, admin).
  5. Wire startup / shutdown hooks for MongoDB indexes & client cleanup.

Business logic, data models, and prompt templates intentionally do NOT live
here. They live in `core/`, `models/`, `services/`, and `routers/` (the
latter two arrive in Phase 3 / Phase 4 of the refactor).

Deployment compatibility:
  • `uvicorn main:app` — the new canonical command.
  • `uvicorn server:app` — STILL WORKS via a PEP 562 lazy-load shim at the
    bottom of `server.py`. Supervisor / Procfile / Railway can be migrated
    to `main:app` at any time without code changes.

DSGVO posture: all logging here is metadata-only (counts, ids, types).
NEVER log document content, API keys, IPs, or any field that could carry
personal information from a scanned letter.
"""

from __future__ import annotations

# 1. Configuration FIRST — side-effect: dotenv load + Sentry init.
#    Every subsequent import expects these to be ready.
from core import config as _config  # noqa: F401 — side-effect import

import logging
from datetime import datetime, timezone

from fastapi import FastAPI

from core.config import (
    ANALYSIS_TTL_DAYS,
    db,
    mongo_client,
)
from core.security import configure_security

logger = logging.getLogger("easli.main")


# ---------------------------------------------------------------------------
# 2. FastAPI app.
# ---------------------------------------------------------------------------
app: FastAPI = FastAPI(title="easli API")


# ---------------------------------------------------------------------------
# 3. Cross-cutting middleware / handlers.
# ---------------------------------------------------------------------------
# Must run BEFORE any router is registered; middlewares attached later only
# apply to routes added afterwards.
configure_security(app)


# ---------------------------------------------------------------------------
# 4. Routers.
# ---------------------------------------------------------------------------
# Imported here (not at top of file) so the import order is deterministic:
#   core.config  →  core.security  →  configure_security(app)  →  routers
# This way no router module can accidentally bypass the security setup by
# registering middlewares earlier.

# 4a. Main API routes that are still in `server.py` (translate, generate-reply,
#     chat, messages, revenuecat-webhook). The `api_router` symbol is the
#     APIRouter that holds the remaining /api/* endpoints — they'll move into
#     routers/{reply,chat,webhook}.py in Phase 3b. The `install_inbox_dependencies`
#     helper wires the inbox webhook to the local analyze pipeline.
from server import api_router, install_inbox_dependencies  # noqa: E402

app.include_router(api_router)

# 4b. Scan, analyze, history endpoints (Phase 3a — extracted from server.py).
from routers.scan import router as scan_router  # noqa: E402

app.include_router(scan_router)

# 4c. Usage, paywall, export, dev tools (Phase 3a — extracted from server.py).
from routers.usage import router as usage_router  # noqa: E402

app.include_router(usage_router)

# 4d. Email forwarding (Phase 4 feature). Lives in its own module.
from inbox import router as inbox_router  # noqa: E402

install_inbox_dependencies()
app.include_router(inbox_router, prefix="/api")

# 4e. Admin web UI + redemption codes. Lives in its own module since
#     before the refactor; only the include site has moved here.
from admin import make_admin_router  # noqa: E402
from core.security import limiter as _limiter  # noqa: E402

app.include_router(make_admin_router(db, limiter=_limiter))


# ---------------------------------------------------------------------------
# 5. Lifecycle hooks.
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup_create_indexes() -> None:
    """Bootstrap MongoDB indexes on every backend start. Idempotent."""
    # 5a. TTL on analyses for storage minimisation (DSGVO Art. 5(1)(e)).
    if ANALYSIS_TTL_DAYS > 0:
        try:
            await db.analyses.create_index(
                "created_at_dt",
                expireAfterSeconds=ANALYSIS_TTL_DAYS * 86400,
                name="ttl_created_at_dt",
                background=True,
            )
            # Backfill `created_at_dt` (BSON Date) for legacy docs that only
            # carry the ISO-string `created_at`. Chunked so a large collection
            # doesn't block startup.
            backfilled = 0
            cursor = db.analyses.find(
                {"created_at_dt": {"$exists": False}},
                {"_id": 1, "created_at": 1},
            ).limit(500)
            async for legacy in cursor:
                ts = legacy.get("created_at")
                if not ts:
                    continue
                try:
                    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    parsed = datetime.now(timezone.utc)
                await db.analyses.update_one(
                    {"_id": legacy["_id"]},
                    {"$set": {"created_at_dt": parsed}},
                )
                backfilled += 1
            logger.info(
                "ttl_index_ready collection=analyses ttl_days=%s backfilled=%s",
                ANALYSIS_TTL_DAYS, backfilled,
            )
        except Exception as e:  # noqa: BLE001 — never crash boot on Mongo hiccup
            logger.warning(
                "ttl_index_setup_failed error_type=%s",
                type(e).__name__,
            )

    # 5b. Hot-path indexes (idempotent).
    try:
        await db.analyses.create_index(
            [("device_id", 1), ("created_at", -1)],
            name="device_created_idx",
        )
        await db.usage_records.create_index(
            "device_id", unique=True, name="device_unique_idx",
        )
        # Phase D — analytics indices for the admin dashboard.
        # Sparse + background: zero impact on existing writes; only docs that
        # have the field get indexed.
        await db.analyses.create_index(
            "target_language",
            name="target_language_idx",
            sparse=True,
            background=True,
        )
        await db.analyses.create_index(
            "detected_country_code",
            name="detected_country_idx",
            sparse=True,
            background=True,
        )
        await db.redemption_codes.create_index(
            "code", unique=True, name="code_unique_idx",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("index_setup_failed error_type=%s", type(e).__name__)


@app.on_event("shutdown")
async def _shutdown_close_mongo() -> None:
    mongo_client.close()


# ---------------------------------------------------------------------------
# 6. Boot summary (metadata-only).
# ---------------------------------------------------------------------------
logger.info(
    "easli_app_ready routes=%d",
    len([r for r in app.routes]),
)
