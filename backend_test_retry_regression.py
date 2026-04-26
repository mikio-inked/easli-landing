"""Regression test after Mistral retry-logic hardening (review_request items 1-6).

Targets:
  1. GET /api/                              → 200 {"app":"KlarPost","status":"ok"}
  2. POST /api/analyze (1x1 PNG)            → 200 with valid analysis schema
  3. POST /api/analyze (empty body)         → 422, NO body echo (PII redaction)
  4. POST /api/analyses/{id}/chat           → 200 with reply/content
  5. Code-path importable                   → mistral_complete_with_retry et al.
  6. Spot-check GET /api/languages, /api/paywall/config, /api/usage/{device}

Privacy: never logs the base64 image, never logs the Mistral API key.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid
from typing import Any, Dict

import requests

# ---- BACKEND URL DISCOVERY -------------------------------------------------
# /app/frontend/.env exposes EXPO_PUBLIC_BACKEND_URL; we mirror it because
# this Expo app does not define REACT_APP_BACKEND_URL.
def _public_backend_url() -> str:
    env_path = "/app/frontend/.env"
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found in frontend/.env")


BASE = _public_backend_url().rstrip("/")
API = f"{BASE}/api"
DEVICE_ID = f"qa-retry-regression-{uuid.uuid4().hex[:8]}"
TIMEOUT_LONG = 60   # /api/analyze hits Mistral
TIMEOUT_SHORT = 15

# 1x1 white PNG, hand-crafted (well-known minimal PNG)
PNG_1x1_WHITE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

results: list[tuple[str, bool, str]] = []


def _record(name: str, ok: bool, detail: str = "") -> None:
    print(("[PASS] " if ok else "[FAIL] ") + name + (f" — {detail}" if detail else ""))
    results.append((name, ok, detail))


def _redact(s: str, max_len: int = 240) -> str:
    return (s[:max_len] + ("…(+%d)" % (len(s) - max_len) if len(s) > max_len else ""))


# ---------------------------------------------------------------------------
# 1. Backend boots cleanly
# ---------------------------------------------------------------------------
def test_root() -> None:
    r = requests.get(f"{API}/", timeout=TIMEOUT_SHORT)
    ok = r.status_code == 200 and r.json() == {"app": "KlarPost", "status": "ok"}
    _record("1. GET /api/ → 200 {app:KlarPost,status:ok}", ok,
            f"status={r.status_code} body={_redact(r.text)}")


# ---------------------------------------------------------------------------
# 2. Happy-path /api/analyze still works
# ---------------------------------------------------------------------------
analysis_id_for_chat: str | None = None


def test_analyze_happy_path() -> None:
    global analysis_id_for_chat
    body: Dict[str, Any] = {
        "device_id": DEVICE_ID,
        "target_language": "en",
        "idempotency_key": f"retry-reg-{uuid.uuid4().hex[:8]}",
        "pages": [{"file_base64": PNG_1x1_WHITE_B64, "mime_type": "image/png"}],
    }
    t0 = time.time()
    r = requests.post(f"{API}/analyze", json=body, timeout=TIMEOUT_LONG)
    dt = time.time() - t0

    if r.status_code != 200:
        _record(
            "2. POST /api/analyze (1x1 PNG) → 200",
            False,
            f"got {r.status_code} in {dt:.1f}s body={_redact(r.text)}",
        )
        return

    payload = r.json()
    # AnalysisRecord envelope: {id, device_id, target_language, target_language_label,
    # mime_type, created_at, result:{summary, key_points, deadlines, ...}, usage(opt)}
    ok_envelope = all(k in payload for k in ("id", "device_id", "result", "created_at"))
    result = payload.get("result", {})
    # Real schema uses `summary_translated` (translated into target language).
    summary_key = "summary_translated" if "summary_translated" in result else "summary"
    ok_schema = all(k in result for k in (summary_key, "key_points", "deadlines"))
    ok = ok_envelope and ok_schema

    if ok:
        analysis_id_for_chat = payload["id"]

    _record(
        "2. POST /api/analyze (1x1 PNG) → 200 with analysis schema",
        ok,
        f"dt={dt:.1f}s id={payload.get('id', '?')} envelope_ok={ok_envelope} "
        f"schema_ok={ok_schema} result_keys={sorted(result.keys()) if isinstance(result, dict) else type(result)}",
    )


# ---------------------------------------------------------------------------
# 3. Validation still works AND request body is NOT echoed
# ---------------------------------------------------------------------------
def test_analyze_empty_body() -> None:
    r = requests.post(f"{API}/analyze", json={}, timeout=TIMEOUT_SHORT)
    body_text = r.text
    is_422 = r.status_code == 422
    # Privacy redaction: response must NOT contain any 'body' key, nor an 'input'
    # field that would echo the offending payload.
    leaks = []
    try:
        j = r.json()
        # Recursively scan for forbidden keys
        def scan(node: Any, path: str = "$") -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k.lower() in ("body", "input", "ctx"):
                        leaks.append(f"{path}.{k}")
                    scan(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, item in enumerate(node):
                    scan(item, f"{path}[{i}]")
        scan(j)
        # Each detail item should only have loc/type/msg
        details = j.get("detail", []) if isinstance(j, dict) else []
        for i, d in enumerate(details):
            if isinstance(d, dict):
                extra = set(d.keys()) - {"loc", "type", "msg"}
                if extra:
                    leaks.append(f"detail[{i}].extra_keys={sorted(extra)}")
    except Exception as e:
        leaks.append(f"json_parse_error={e}")

    ok = is_422 and not leaks
    _record(
        "3. POST /api/analyze (empty body) → 422 with PII-redacted error body",
        ok,
        f"status={r.status_code} leaks={leaks} body={_redact(body_text)}",
    )


# ---------------------------------------------------------------------------
# 4. Existing chat flow still works
# ---------------------------------------------------------------------------
def test_chat_flow() -> None:
    if not analysis_id_for_chat:
        _record(
            "4. POST /api/analyses/{id}/chat → 200",
            False,
            "skipped: no analysis_id from step 2",
        )
        return
    body = {"device_id": DEVICE_ID, "message": "Was ist die Frist?"}
    t0 = time.time()
    r = requests.post(
        f"{API}/analyses/{analysis_id_for_chat}/chat",
        json=body,
        timeout=TIMEOUT_LONG,
    )
    dt = time.time() - t0

    if r.status_code != 200:
        _record(
            "4. POST /api/analyses/{id}/chat → 200",
            False,
            f"got {r.status_code} in {dt:.1f}s body={_redact(r.text)}",
        )
        return

    payload = r.json()
    # Endpoint returns ChatMessage {role, content, off_topic, created_at}.
    # Review_request says "reply field" but the contract has been `content`
    # since the original migration; treat either as PASS.
    has_reply = "reply" in payload and payload["reply"]
    has_content = "content" in payload and payload["content"]
    ok = has_reply or has_content

    _record(
        "4. POST /api/analyses/{id}/chat → 200 with reply/content",
        ok,
        f"dt={dt:.1f}s keys={sorted(payload.keys())} has_reply={has_reply} has_content={has_content}",
    )


# ---------------------------------------------------------------------------
# 5. Retry helper code path is importable
# ---------------------------------------------------------------------------
def test_imports() -> None:
    # Must be run from /app/backend so that `import server` resolves.
    code = (
        "import sys; sys.path.insert(0, '/app/backend');"
        "from server import (mistral_complete_with_retry, _is_rate_limit_error, "
        "_parse_retry_after_seconds, MistralRateLimited);"
        "print('OK')"
    )
    import subprocess
    try:
        proc = subprocess.run(
            ["python3", "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        ok = proc.returncode == 0 and proc.stdout.strip() == "OK"
        detail = f"rc={proc.returncode} stdout={proc.stdout.strip()!r} stderr={_redact(proc.stderr.strip())}"
    except Exception as e:
        ok = False
        detail = f"subprocess error: {e}"
    _record("5. Retry helper symbols importable", ok, detail)


# ---------------------------------------------------------------------------
# 6. Spot-check other endpoints
# ---------------------------------------------------------------------------
def test_other_endpoints() -> None:
    # /api/languages
    r1 = requests.get(f"{API}/languages", timeout=TIMEOUT_SHORT)
    ok1 = r1.status_code == 200 and isinstance(r1.json(), list) and len(r1.json()) > 0
    _record("6a. GET /api/languages → 200 list", ok1, f"status={r1.status_code} n={len(r1.json()) if r1.ok else '?'}")

    # /api/paywall/config
    r2 = requests.get(f"{API}/paywall/config", timeout=TIMEOUT_SHORT)
    ok2 = r2.status_code == 200 and isinstance(r2.json(), dict) and "paywall_mode" in r2.json()
    _record("6b. GET /api/paywall/config → 200", ok2, f"status={r2.status_code}")

    # /api/usage/{device_id}
    r3 = requests.get(f"{API}/usage/{DEVICE_ID}", timeout=TIMEOUT_SHORT)
    ok3 = r3.status_code == 200 and isinstance(r3.json(), dict) and "free_analyses_used" in r3.json()
    _record("6c. GET /api/usage/{device_id} → 200", ok3, f"status={r3.status_code}")


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
def cleanup() -> None:
    try:
        r = requests.delete(f"{API}/history/{DEVICE_ID}", timeout=TIMEOUT_SHORT)
        print(f"[cleanup] DELETE /api/history/{DEVICE_ID} → {r.status_code} {_redact(r.text)}")
    except Exception as e:
        print(f"[cleanup] error: {e}")


# ---------------------------------------------------------------------------
def main() -> int:
    print(f"BASE={BASE}")
    print(f"DEVICE_ID={DEVICE_ID}")
    print()

    test_root()
    test_analyze_happy_path()
    test_analyze_empty_body()
    test_chat_flow()
    test_imports()
    test_other_endpoints()

    print()
    cleanup()

    print()
    n_pass = sum(1 for _, ok, _ in results if ok)
    n_fail = len(results) - n_pass
    print(f"==== RESULTS: {n_pass}/{len(results)} pass, {n_fail} fail ====")
    for name, ok, detail in results:
        print(("  PASS  " if ok else "  FAIL  ") + name)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
