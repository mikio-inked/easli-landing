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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import server  # noqa: E402


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
    # we always patch into server.* directly.
    class Stub:
        class chat:
            complete_async = staticmethod(fake)
    server.mistral_client = Stub()  # type: ignore[assignment]
    return calls


async def run_case(name, side_effects, expected_outcome, expected_min_wait_s, expected_max_wait_s, expected_client_hint=None):
    """Run one test scenario and pretty-print the result."""
    calls = patch_complete_async(side_effects)
    t0 = time.monotonic()
    outcome = "ok"
    client_hint = None
    try:
        await server.mistral_complete_with_retry(label="vision", model="test", messages=[])
    except server.MistralRateLimited as rl:
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

    # 4) Persistent 429 with no Retry-After → 4 retries with default backoff
    #    [2, 4, 8, 16] but max-total cap of 45s allows all 4. Total = 30s.
    #    But max_attempts = 5, so we try 5 times. Final hint = 16 (last default).
    results.append(await run_case(
        "persistent 429 without server hint → exhaust default backoff",
        side_effects=[FakeMistralError() for _ in range(5)],
        expected_outcome="rate_limited",
        expected_min_wait_s=29.5, expected_max_wait_s=31.5,
        expected_client_hint=16,
    ))

    # 5) Persistent 429 with server hint 7 → cap at total 45s, so we get
    #    multiple retries each waiting 7s, until budget is exceeded.
    #    7+7+7+7 = 28s ≤ 45s, but 7+7+7+7+7 = 35s ≤ 45s — still fits 5 attempts? 
    #    Actually max_attempts is 5, so we try 5 times total.
    #    Wait sequence: 7+7+7+7 = 28s (4 waits between 5 attempts).
    results.append(await run_case(
        "persistent 429 with server hint=7s, exhausts attempts",
        side_effects=[FakeMistralError(7) for _ in range(6)],
        expected_outcome="rate_limited",
        expected_min_wait_s=27.5, expected_max_wait_s=29.5,
        expected_client_hint=7,
    ))

    # 6) Server hint that's too large (e.g., 120s) → capped to 30s for sleep,
    #    but client_hint forwards the real 120s.
    results.append(await run_case(
        "server hint=120s — capped to max wait, client gets truthful 120s",
        side_effects=[FakeMistralError(120), FakeMistralError(120)],  # 30+30 > 45 budget
        expected_outcome="rate_limited",
        expected_min_wait_s=29.5, expected_max_wait_s=31.5,
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
