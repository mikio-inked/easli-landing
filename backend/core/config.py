"""easli — central configuration & infrastructure clients.

Loads `.env`, configures Sentry (privacy-first, opt-in), opens the
Mongo + Mistral clients, and exposes all paywall / quota knobs as
module-level constants. Importing this module is the canonical bootstrap
moment of the backend — every other module reads from it.

Design rules:
  • No FastAPI imports here. This file must be importable from a unit test,
    a CLI script, or a worker without dragging Starlette / Uvicorn in.
  • Every env-var lookup is fail-safe: missing / malformed values fall back
    to a documented default. Boot must never crash on a missing optional.
  • Mandatory env vars (MONGO_URL, DB_NAME) DO fail fast — a misconfigured
    container should refuse to start, not silently corrupt data.
  • Privacy: NO log line in this module ever prints a value of any secret
    (API key, Sentry DSN, webhook secret). Only env-var presence is logged.

DSGVO posture for Sentry:
  • `send_default_pii=False`  — never auto-collect IP / cookies / headers.
  • `include_local_variables=False` — never attach `image_base64` or OCR
    text to a stack frame.
  • `max_breadcrumbs=30`        — small enough to never leak request bodies.

The sentry init runs at IMPORT TIME so it precedes any later module that
might raise during construction (e.g. Mistral client). Keep this module
at the very top of `main.py` and `server.py`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.exceptions import ConfigurationError

# ---------------------------------------------------------------------------
# 1. dotenv — load BEFORE we read any environment variable below.
# ---------------------------------------------------------------------------
# The .env file lives next to /app/backend/server.py historically. We resolve
# the project root from this file's location so the path is stable whether
# the backend is launched from `/app`, `/app/backend`, or via a CI runner.
_BACKEND_DIR: Path = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")


# ---------------------------------------------------------------------------
# 2. Sentry — import-time side-effect, opt-in via SENTRY_DSN.
# ---------------------------------------------------------------------------
# Activated automatically when SENTRY_DSN env var is set. Uses the Logging
# + FastAPI integrations so that all Python exceptions and any logger.error
# call bubble up to Sentry. Designed to be a zero-cost no-op when DSN is
# blank — perfect for local dev / CI.
_sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
if _sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=_sentry_dsn,
            traces_sample_rate=float(
                os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")
            ),
            environment=os.environ.get("SENTRY_ENV", "production"),
            release=os.environ.get("SENTRY_RELEASE") or None,
            send_default_pii=False,  # privacy-first, never send IPs/headers
            # CRITICAL — never attach local-variable values to stack frames.
            # Without this, sentry_sdk would helpfully include `req.image_base64`
            # (the user's letter as Base64!), OCR text, draft replies and so on
            # whenever an exception bubbles up from /api/analyze. That would
            # break our DSGVO posture entirely.
            include_local_variables=False,
            # Reduce breadcrumb noise + memory footprint.
            max_breadcrumbs=30,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
        )
    except Exception as _e:  # noqa: BLE001 — never let Sentry crash the boot.
        logging.getLogger(__name__).warning("sentry_init_failed err=%s", _e)


# ---------------------------------------------------------------------------
# 3. Logging — single, consistent format across the whole backend.
# ---------------------------------------------------------------------------
# Done here so every later `logging.getLogger(__name__)` inherits the same
# format without each module needing to call basicConfig itself.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("easli.config")


# ---------------------------------------------------------------------------
# 4. Helpers.
# ---------------------------------------------------------------------------
def _int_env(name: str, default: int) -> int:
    """Read an int env var, defaulting safely on missing/garbage values.

    Negative values are clamped to 0 — every quota in easli is non-negative.
    """
    try:
        return max(0, int(os.environ.get(name, str(default)).strip()))
    except (ValueError, TypeError):
        return default


def _str_env(name: str, default: str = "") -> str:
    """Read a string env var, stripping whitespace."""
    return (os.environ.get(name, default) or "").strip()


# ---------------------------------------------------------------------------
# 5. MongoDB.
# ---------------------------------------------------------------------------
# Both vars are MANDATORY — if they're missing we fail fast rather than
# returning 500s for every request. The container will be auto-restarted
# by supervisor / Railway and the operator gets a clean error in logs.
_mongo_url = _str_env("MONGO_URL")
_db_name = _str_env("DB_NAME")
if not _mongo_url:
    raise ConfigurationError("MONGO_URL is required (set in backend/.env)")
if not _db_name:
    raise ConfigurationError("DB_NAME is required (set in backend/.env)")

MONGO_URL: str = _mongo_url
DB_NAME: str = _db_name

mongo_client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URL)
db: AsyncIOMotorDatabase = mongo_client[DB_NAME]


# ---------------------------------------------------------------------------
# 6. Mistral AI — EU-hosted (Paris), DSGVO-friendly OpenAI alternative.
# ---------------------------------------------------------------------------
# Model IDs are pinned via env vars to dated releases so we don't silently
# adopt new models. Mistral Large 3 (`mistral-large-2512`) is the current
# multimodal frontier model and replaces both pixtral-large-2411 and
# mistral-large-2411 (both deprecated, retiring Feb 27, 2026).
MISTRAL_API_KEY: str = _str_env("MISTRAL_API_KEY")
MISTRAL_VISION_MODEL: str = _str_env("MISTRAL_VISION_MODEL", "mistral-large-2512")
MISTRAL_ANALYSIS_MODEL: str = _str_env("MISTRAL_ANALYSIS_MODEL", "mistral-large-2512")
MISTRAL_CHAT_MODEL: str = _str_env("MISTRAL_CHAT_MODEL", "mistral-large-2512")
# Dedicated OCR model — extremely fast (0.5-1s/page) and orders of magnitude
# cheaper than running a full multimodal model over every page.
MISTRAL_OCR_MODEL: str = _str_env("MISTRAL_OCR_MODEL", "mistral-ocr-latest")

# 60s per individual API call. Vision was 30s but OCR+text split is
# much faster (typ. 4-10s) — we still keep 60s as a safety ceiling for
# edge cases like Mistral warming up a cold model. Combined with our
# retry helper's 25s cumulative-wait budget this gives a hard ~85s
# upper bound per Mistral phase — well inside the iOS client's 120s
# upload-timeout.
_MISTRAL_TIMEOUT_MS: int = _int_env("MISTRAL_TIMEOUT_MS", 60_000)

# Lazy import — so unit tests that don't touch the model can run without
# the SDK being installed (it always is in production, but this keeps the
# config layer import-safe).
try:
    from mistralai import Mistral as _MistralClient  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    _MistralClient = None  # type: ignore[assignment]

mistral_client: Optional["_MistralClient"] = (  # noqa: F821
    _MistralClient(api_key=MISTRAL_API_KEY, timeout_ms=_MISTRAL_TIMEOUT_MS)
    if (MISTRAL_API_KEY and _MistralClient is not None)
    else None
)


# ---------------------------------------------------------------------------
# 7. Paywall / Usage quotas.
# ---------------------------------------------------------------------------
# Read once at startup so behaviour is predictable. All values are also
# documented in /app/backend/.env. NEVER log these values together with
# document content.
_paywall_mode = _str_env("PAYWALL_MODE", "soft").lower() or "soft"
if _paywall_mode not in ("disabled", "soft", "hard"):
    _paywall_mode = "soft"
PAYWALL_MODE: str = _paywall_mode

FREE_ANALYSES: int = _int_env("FREE_ANALYSES", 3)
SOFT_TEST_EXTRA_ANALYSES: int = _int_env("SOFT_TEST_EXTRA_ANALYSES", 10)
MAX_PAGES_PER_DOCUMENT: int = _int_env("MAX_PAGES_PER_DOCUMENT", 5)
MAX_CHAT_QUESTIONS_PER_DOCUMENT: int = _int_env("MAX_CHAT_QUESTIONS_PER_DOCUMENT", 5)
MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER: int = _int_env("MAX_TOTAL_CHAT_QUESTIONS_PER_TESTER", 20)
PLUS_MONTHLY_ANALYSES: int = _int_env("PLUS_MONTHLY_ANALYSES", 20)
MAX_TRANSLATIONS_PER_ANALYSIS: int = _int_env("MAX_TRANSLATIONS_PER_ANALYSIS", 6)

# DSGVO storage minimisation: stored analyses auto-delete after this many
# days. Enforced via a MongoDB TTL index on `analyses.created_at_dt`. Set
# to 0 to disable auto-deletion (not recommended for production).
ANALYSIS_TTL_DAYS: int = _int_env("ANALYSIS_TTL_DAYS", 90)


# ---------------------------------------------------------------------------
# 8. RevenueCat & dev tooling.
# ---------------------------------------------------------------------------
# When set, RC webhook requires this exact value in the Authorization header.
# Leaving it empty in production is logged as a WARNING on every webhook hit.
REVENUECAT_WEBHOOK_AUTH_HEADER: str = _str_env("REVENUECAT_WEBHOOK_AUTH_HEADER")

# `DEV_TOOLS_ENABLED` defaults to True in soft/disabled to make TestFlight QA
# easy. In hard production set DEV_TOOLS_ENABLED=0 (the default when
# PAYWALL_MODE == 'hard' unless explicitly overridden) and the dev simulation
# endpoints return 404.
DEV_TOOLS_ENABLED: bool = (
    _str_env("DEV_TOOLS_ENABLED", "0") == "1" or PAYWALL_MODE != "hard"
)


# ---------------------------------------------------------------------------
# 9. CORS.
# ---------------------------------------------------------------------------
_DEFAULT_ORIGINS = [
    "https://easli.app",
    "https://www.easli.app",
    "https://api.easli.app",
    "http://localhost:3000",
    "http://localhost:8081",
]
_origins_env = _str_env("ALLOWED_ORIGINS")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _origins_env.split(",") if o.strip()]
    if _origins_env
    else list(_DEFAULT_ORIGINS)
)


# ---------------------------------------------------------------------------
# 10. Rate-limit defaults (read by core.security at import time).
# ---------------------------------------------------------------------------
RATE_LIMIT_ANALYZE: str = _str_env("RATE_LIMIT_ANALYZE", "30/minute")


# ---------------------------------------------------------------------------
# 11. Boot summary — metadata-only, NEVER logs any secret value.
# ---------------------------------------------------------------------------
logger.info(
    "config_loaded paywall_mode=%s mistral=%s db=%s sentry=%s dev_tools=%s",
    PAYWALL_MODE,
    "yes" if mistral_client else "no",
    DB_NAME,
    "on" if _sentry_dsn else "off",
    "on" if DEV_TOOLS_ENABLED else "off",
)
