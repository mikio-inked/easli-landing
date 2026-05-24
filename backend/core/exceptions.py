"""easli — shared application exceptions.

Kept tiny and dependency-free so any module (routers, services, server.py)
can raise them without pulling in heavy infrastructure.

All exceptions inherit from the standard `Exception` and are translated to
clean HTTP responses by the FastAPI route handlers (NOT by global handlers,
so the per-route Retry-After / detail messaging stays under tight control).
"""

from __future__ import annotations


class EasliError(Exception):
    """Base class for every application-specific exception.

    Plain `Exception` subclasses would also work, but having a common ancestor
    lets us write `except EasliError` in middleware/diagnostics without
    catching arbitrary infrastructure errors.
    """


class MistralRateLimited(EasliError):
    """Final-attempt Mistral 429.

    Raised by the retry helper after all backoff attempts have been exhausted
    OR the cumulative-wait budget would be exceeded. The route handler maps
    this to HTTP 429 with the truthful Retry-After hint forwarded so the iOS
    client can show a \"try again in N seconds\" toast that matches reality.
    """

    def __init__(self, retry_after: int):
        super().__init__("rate_limited")
        # Always a positive integer — see `_parse_retry_after_seconds`.
        self.retry_after: int = max(1, int(retry_after))


class ConfigurationError(EasliError):
    """Raised when a required env var is missing or malformed AT BOOT.

    Used by `core.config` to fail fast with a clear message instead of letting
    a `KeyError: 'MONGO_URL'` traceback surface on every request.
    """


class EntitlementDenied(EasliError):
    """Raised by the entitlement service when a request is not allowed.

    Carries the structured reason + message the frontend wants to show; the
    route handler translates this to an HTTP 402/429 with the same payload.
    Will be used by `services.entitlement_service` once routes are extracted.
    """

    def __init__(self, reason: str, message: str, status_code: int = 402):
        super().__init__(reason)
        self.reason: str = reason
        self.message: str = message
        self.status_code: int = status_code
