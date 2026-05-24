"""Quick in-memory check for the new mistral_complete_with_retry helper.

NOT a real pytest — just a script we run once after editing the retry logic
to verify it honours Retry-After, falls back when missing, and surfaces the
correct hint to the client. Privacy: no real Mistral calls.
"""

import asyncio
import os
import sys
import time
from typing import List, Tuple

# Ensure backend dir is importable + .env loaded.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# After Phase 5 the retry helper lives in services/ai_service. We still
# patch the Mistral client stub via core.config + services.ai_service.
from core import config as ai_config  # noqa: E402
from core.exceptions import MistralRateLimited  # noqa: E402
from services import ai_service  # noqa: E402


# ---- Fake httpx Headers / Response / SDKError lookalikes -------------------


class FakeHeaders(dict):
    """Minimal httpx.Headers replacement — case-insensitive get."""
    def get(self, key, default=None):
        for k, v in self.items():
            if k.lower() == key.lower():
                return v
        return default


class FakeMistralError(Exception):
    """Minimal stand-in for mistralai.SDKError that satisfies our detectors."""
    def __init__(self, retry_after=None):
        self.status_code = 429
        self.headers = FakeHeaders()
        if retry_after is not None:
            self.headers["retry-after"] = str(retry_after)
        super().__init__("API error occurred: Status 429. Body: rate_limited")


def patch_complete_async(side_effects: List):
    """Replace mistral_client.chat.complete_async with a callable that yields
    the next item from side_effects each call. Items can be exception classes
    (instances will be raised) or any value (returned).
    """
    calls: List[Tuple[float, ...]] = []
    iterator = iter(side_effects)

    async def fake(**kwargs):
        calls.append((time.monotonic(),))
        nxt = next(iterator)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    # mistral_client may be None on machines without an API key — for the test
    # we always patch into core.config / services.ai_service directly.
    class Stub:
        class chat:
            complete_async = staticmethod(fake)
    ai_config.mistral_client = Stub()  # type: ignore[assignment]
    ai_service.mistral_client = Stub()  # type: ignore[assignment]
    return calls


async def run_case(name, side_effects, expected_outcome, expected_min_wait_s, expected_max_wait_s, expected_client_hint=None):
    """Run one test scenario and pretty-print the result."""
    calls = patch_complete_async(side_effects)
    t0 = time.monotonic()
    outcome = "ok"
    client_hint = None
    try:
        await ai_service.mistral_complete_with_retry(label="vision", model="test", messages=[])
    except MistralRateLimited as rl:
        outcome = "rate_limited"
        client_hint = rl.retry_after
    except Exception as e:
        outcome = f"error:{type(e).__name__}"
    elapsed = time.monotonic() - t0

    waited_ok = expected_min_wait_s <= elapsed <= expected_max_wait_s
    outcome_ok = outcome == expected_outcome
    hint_ok = expected_client_hint is None or client_hint == expected_client_hint
    overall = "PASS" if (waited_ok and outcome_ok and hint_ok) else "FAIL"
    print(
        f"[{overall}] {name}\n"
        f"        outcome={outcome} (expected {expected_outcome})\n"
        f"        elapsed={elapsed:.2f}s (expected {expected_min_wait_s}–{expected_max_wait_s}s)\n"
        f"        attempts={len(calls)} client_hint={client_hint} (expected {expected_client_hint})"
    )
    return overall == "PASS"


async def main():
    results = []

    # 1) Success on first try — no retries.
    results.append(await run_case(
        "first attempt succeeds",
        side_effects=["FAKE_RESPONSE"],
        expected_outcome="ok",
        expected_min_wait_s=0, expected_max_wait_s=0.5,
    ))

    # 2) Server says Retry-After: 1 → should wait ~1s and try again.
    results.append(await run_case(
        "server hint Retry-After=1, then success",
        side_effects=[FakeMistralError(retry_after=1), "FAKE_RESPONSE"],
        expected_outcome="ok",
        expected_min_wait_s=0.9, expected_max_wait_s=2.0,
    ))

    # 3) Server hint of 5, then 5, then success — total ~10s wait.
    results.append(await run_case(
        "two server hints of 5s each, then success",
        side_effects=[FakeMistralError(5), FakeMistralError(5), "FAKE_RESPONSE"],
        expected_outcome="ok",
        expected_min_wait_s=9.5, expected_max_wait_s=11.5,
    ))

    # 4) Persistent 429 with no Retry-After → exhaust default backoff
    #    [2, 4, 8] with 4 total attempts (3 retries). Budget cap 25s means
    #    we stop waiting once cumulative ≥ 25s; for [2, 4, 8] total waits
    #    are 2+4+8 = 14s — fits budget → all 3 retries taken.
    #    Final hint = 8 (last default backoff value used).
    results.append(await run_case(
        "persistent 429 without server hint → exhaust default backoff",
        side_effects=[FakeMistralError() for _ in range(5)],
        expected_outcome="rate_limited",
        expected_min_wait_s=13.5, expected_max_wait_s=15.5,
        expected_client_hint=8,
    ))

    # 5) Persistent 429 with server hint 7 → total budget 25s allows 3
    #    retries (7+7+7 = 21s). 4th attempt fires, 5th would blow budget.
    results.append(await run_case(
        "persistent 429 with server hint=7s, exhausts attempts",
        side_effects=[FakeMistralError(7) for _ in range(6)],
        expected_outcome="rate_limited",
        expected_min_wait_s=20.5, expected_max_wait_s=22.5,
        expected_client_hint=7,
    ))

    # 6) Server hint that's too large (120s) → capped to 20s for sleep,
    #    but client_hint forwards the real 120s. After 1 retry of 20s we're
    #    at total_waited=20s; another 20s would exceed the 25s budget →
    #    surrender after just 1 retry (2 attempts total).
    results.append(await run_case(
        "server hint=120s — capped to max wait, client gets truthful 120s",
        side_effects=[FakeMistralError(120), FakeMistralError(120)],
        expected_outcome="rate_limited",
        expected_min_wait_s=19.5, expected_max_wait_s=21.5,
        expected_client_hint=120,
    ))

    print()
    if all(results):
        print(f"ALL {len(results)} TESTS PASSED ✓")
        sys.exit(0)
    else:
        print(f"FAILED: {results.count(False)}/{len(results)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
