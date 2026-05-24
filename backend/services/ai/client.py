"""easli — Mistral client access + retry helper.

Holds the ONE function every other ai/* module calls when it talks to
Mistral: `mistral_complete_with_retry()`. Centralising the retry logic
guarantees identical 429-handling across analyse / chat / translate.

Mistral client lookup is *late-bound*: we import the `core.config` module
(not just the `mistral_client` symbol) and read `config.mistral_client`
at call time. This single design choice makes the helper trivially
mockable from tests — patching `core.config.mistral_client = Stub()`
is enough; we don't need to also patch every consumer module.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from core import config as _core_config
from core.exceptions import MistralRateLimited
from utils.retry_utils import (
    RATE_LIMIT_DEFAULT_BACKOFF_SECONDS,
    RATE_LIMIT_FALLBACK_CLIENT_HINT,
    RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS,
    RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS,
    is_rate_limit_error,
    parse_retry_after_seconds,
)

logger = logging.getLogger("server")


# Re-export for legacy callers that import `mistral_client` from this module
# AND for code paths that only need to do a None-check before building a
# request. The variable is captured at import time AND on every fresh
# attribute access via `_core_config.mistral_client` — this gives tests
# the freedom to replace the client object at any time.
mistral_client = _core_config.mistral_client  # type: ignore[assignment]


def _get_mistral_client():
    """Return the current Mistral client, picking up runtime patches on
    `core.config.mistral_client` automatically. Returns None if no API
    key is configured (the caller is expected to raise an HTTP 500)."""
    return getattr(_core_config, "mistral_client", None)


async def mistral_complete_with_retry(
    *,
    label: str,  # 'analysis' | 'chat' | 'translate' — for logs only
    model: str,
    **kwargs,
):
    """Call mistral_client.chat.complete_async with retries on HTTP 429.

    Retry strategy:
      1) If the 429 response carries a `Retry-After` header, honour it
         (capped at RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS so a mobile upload
         connection doesn't hang too long).
      2) Otherwise fall back to exponential backoff: 2s, 4s, 8s.
      3) Stop retrying as soon as the cumulative wait would exceed
         RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS.

    On final failure we raise MistralRateLimited(retry_after=...) where
    retry_after is the LAST hint Mistral gave us, so the iOS toast says
    "try again in N seconds" with the same N the server told us.
    """
    client = _get_mistral_client()
    if client is None:
        # Mirrors the previous behaviour: callers checked `mistral_client`
        # truthiness before calling us, but we guard here too so a missing
        # key produces a clear error instead of an AttributeError.
        raise RuntimeError("mistral_client not configured")

    last_exc: Optional[Exception] = None
    last_client_hint: int = RATE_LIMIT_FALLBACK_CLIENT_HINT
    total_waited: int = 0
    max_attempts = len(RATE_LIMIT_DEFAULT_BACKOFF_SECONDS) + 1  # 4 total

    for attempt in range(max_attempts):
        try:
            return await client.chat.complete_async(model=model, **kwargs)
        except Exception as e:
            if not is_rate_limit_error(e):
                # Non-429 → propagate so the existing 502 handler runs.
                raise
            last_exc = e

            # Decide how long to wait before the next attempt.
            server_hint = parse_retry_after_seconds(e)
            if server_hint is not None:
                wait = min(server_hint, RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS)
                # Remember the *uncapped* server hint so we can forward
                # the truthful number to the iOS client when we give up.
                last_client_hint = server_hint
            elif attempt < len(RATE_LIMIT_DEFAULT_BACKOFF_SECONDS):
                wait = RATE_LIMIT_DEFAULT_BACKOFF_SECONDS[attempt]
                last_client_hint = wait
            else:
                wait = None  # no more attempts left

            attempts_left = attempt + 1 < max_attempts
            within_budget = (
                wait is not None
                and (total_waited + wait) <= RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS
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
                # Re-resolve the client in case a test swapped it mid-flight.
                client = _get_mistral_client() or client
                continue

            # Out of attempts or out of budget — surface a clean exception
            # so the route handler can return HTTP 429 with the truthful
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
