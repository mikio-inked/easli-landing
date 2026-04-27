#!/usr/bin/env python3
"""KlarPost backend regression — 2-stage OCR+Analysis pipeline validation.

Covers:
  1. POST /api/analyze with 1/2/4 page synthetic JPEGs (AnalysisResult schema + usage)
  2. /app/backend/_test_retry.py still passes
  3. Existing endpoints (/, /languages, /paywall/config, /usage/{device_id})
  4. POST /api/analyses/{id}/chat ChatMessage shape
  5. DELETE /api/history/{device_id} cleanup
  6. Privacy log audit (ocr_page_ok present; no PII leakage)
  7. Graceful failure on unreadable input (1x1 white PNG)
  8. Idempotency — duplicate idempotency_key consumed once

NEVER logs raw base64 payloads (truncated to 20 chars + length).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont


def _load_frontend_env() -> str:
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found in /app/frontend/.env")


BASE_URL = _load_frontend_env().rstrip("/") + "/api"
TIMEOUT_ANALYZE = 90
TIMEOUT_SHORT = 30

PII_TOKENS = [
    "Sehr geehrte",
    "Frau Muster",
    "123,45",
    "28.02.2026",
    "Telekom AG",
    "ueberweisen",
    "überweisen",
    "DE89",
    "NG12",
]


class Results:
    def __init__(self):
        self.passed: List[str] = []
        self.failed: List[Tuple[str, str]] = []

    def ok(self, name: str):
        self.passed.append(name)
        print(f"  PASS: {name}")

    def fail(self, name: str, detail: str):
        self.failed.append((name, detail))
        print(f"  FAIL: {name} -- {detail}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{'=' * 70}")
        print(f"Total: {total}   Passed: {len(self.passed)}   Failed: {len(self.failed)}")
        if self.failed:
            print("\nFAILURES:")
            for name, detail in self.failed:
                print(f"  - {name}")
                print(f"      {detail}")
        print("=" * 70)


results = Results()


def _trunc_b64(s: str) -> str:
    if len(s) <= 45:
        return s
    return f"{s[:20]}...{s[-20:]} (len={len(s)})"


def _safe_body(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except Exception:
        return resp.text[:400]

    def _scrub(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: (_trunc_b64(v) if isinstance(v, str) and len(v) > 200 else _scrub(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [_scrub(x) for x in o]
        if isinstance(o, str) and len(o) > 200:
            return _trunc_b64(o)
        return o

    return json.dumps(_scrub(body))[:1500]


GERMAN_LETTER_TEXT = [
    "Telekom AG",
    "Landgrabenweg 151",
    "53227 Bonn",
    "",
    "Sehr geehrte Frau Muster,",
    "",
    "vielen Dank fuer Ihre Bestellung. Wir moechten Sie",
    "darauf hinweisen, dass der Rechnungsbetrag in Hoehe",
    "von 123,45 EUR bis zum 28.02.2026 auf unser Konto",
    "zu ueberweisen ist.",
    "",
    "Bitte verwenden Sie als Verwendungszweck Ihre",
    "Kundennummer 9876543210.",
    "",
    "Bei Fragen erreichen Sie unseren Kundenservice",
    "unter der Nummer 0800 33 01000.",
    "",
    "Mit freundlichen Gruessen",
    "Ihre Telekom AG",
]


def build_page_jpeg(page_idx: int = 0, total_pages: int = 1) -> str:
    img = Image.new("RGB", (1280, 1800), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
        small = font

    y = 80
    if total_pages > 1:
        draw.text((80, 40), f"Seite {page_idx + 1} von {total_pages}", fill="black", font=small)
        y = 110

    for line in GERMAN_LETTER_TEXT:
        draw.text((80, y), line, fill="black", font=font)
        y += 54

    if total_pages > 1:
        draw.text((80, y + 60), f"Referenz Seite {page_idx + 1}: AK-{1000 + page_idx}", fill="black", font=small)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def build_tiny_white_png() -> str:
    img = Image.new("RGB", (1, 1), "white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


LOG_FILES = [
    "/var/log/supervisor/backend.err.log",
    "/var/log/supervisor/backend.out.log",
]


def _snapshot_log_sizes() -> Dict[str, int]:
    sizes = {}
    for p in LOG_FILES:
        try:
            sizes[p] = os.path.getsize(p)
        except FileNotFoundError:
            sizes[p] = 0
    return sizes


def _read_logs_since(start_sizes: Dict[str, int]) -> str:
    out = []
    for p in LOG_FILES:
        try:
            start = start_sizes.get(p, 0)
            size_now = os.path.getsize(p)
            with open(p, "rb") as f:
                f.seek(start)
                out.append(f.read(max(0, size_now - start)).decode("utf-8", errors="replace"))
        except FileNotFoundError:
            continue
    return "\n".join(out)


created_analysis_id_for_chat: str = ""
device_for_cleanup: str = ""


def test_existing_smoke():
    print("\n[1] Smoke -- GET /api/")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=TIMEOUT_SHORT)
        assert r.status_code == 200, f"status={r.status_code} body={_safe_body(r)}"
        body = r.json()
        assert body.get("app") == "KlarPost" and body.get("status") == "ok", f"body={body}"
        results.ok("GET /api/ returns {app:'KlarPost', status:'ok'}")
    except Exception as e:
        results.fail("GET /api/", str(e))

    print("\n[2] Smoke -- GET /api/languages")
    try:
        r = requests.get(f"{BASE_URL}/languages", timeout=TIMEOUT_SHORT)
        assert r.status_code == 200, f"status={r.status_code}"
        langs = r.json()
        assert isinstance(langs, list), f"not a list: {type(langs)}"
        assert len(langs) == 7, f"expected 7 languages, got {len(langs)}"
        results.ok(f"GET /api/languages returns list of 7 items ({[l['code'] for l in langs]})")
    except Exception as e:
        results.fail("GET /api/languages", str(e))

    print("\n[3] Smoke -- GET /api/paywall/config")
    try:
        r = requests.get(f"{BASE_URL}/paywall/config", timeout=TIMEOUT_SHORT)
        assert r.status_code == 200, f"status={r.status_code} body={_safe_body(r)}"
        body = r.json()
        assert "paywall_mode" in body, f"paywall_mode missing from {list(body.keys())}"
        results.ok(f"GET /api/paywall/config dict with paywall_mode={body.get('paywall_mode')!r}")
    except Exception as e:
        results.fail("GET /api/paywall/config", str(e))


def test_usage_endpoint(device_id: str):
    print(f"\n[4] Smoke -- GET /api/usage/{device_id[:16]}...")
    try:
        r = requests.get(f"{BASE_URL}/usage/{device_id}", timeout=TIMEOUT_SHORT)
        assert r.status_code == 200, f"status={r.status_code} body={_safe_body(r)}"
        body = r.json()
        assert "free_analyses_used" in body, f"free_analyses_used missing: {list(body.keys())}"
        assert "free_analyses_total" in body, f"free_analyses_total missing: {list(body.keys())}"
        results.ok(f"GET /api/usage/... has free_analyses_used={body['free_analyses_used']}, total={body['free_analyses_total']}")
        return body
    except Exception as e:
        results.fail("GET /api/usage/{device_id}", str(e))
        return None


def _assert_analysis_result_schema(body: Dict[str, Any], label: str) -> bool:
    if "usage" not in body:
        results.fail(f"{label} -- top-level 'usage' field", f"missing. keys={list(body.keys())}")
        return False
    result = body.get("result")
    if not isinstance(result, dict):
        results.fail(f"{label} -- result field", f"not a dict. body_keys={list(body.keys())}")
        return False

    required = [
        "document_type", "sender", "summary_translated",
        "deadlines", "category", "risk_level",
        "scam_warning", "disclaimer",
    ]
    missing = [k for k in required if k not in result]
    if missing:
        results.fail(f"{label} -- result schema", f"missing keys: {missing}. present={list(result.keys())}")
        return False

    if not isinstance(result["deadlines"], list):
        results.fail(f"{label} -- deadlines is list", f"type={type(result['deadlines']).__name__}")
        return False
    if not isinstance(result["scam_warning"], bool):
        results.fail(f"{label} -- scam_warning is bool", f"type={type(result['scam_warning']).__name__}")
        return False
    valid_risk = ("green", "yellow", "red")
    if result["risk_level"] not in valid_risk:
        results.fail(f"{label} -- risk_level literal", f"value={result['risk_level']!r}")
        return False

    results.ok(f"{label} -- AnalysisResult schema complete (risk={result['risk_level']}, category={result['category']}, scam={result['scam_warning']}, deadlines={len(result['deadlines'])})")
    return True


def test_analyze_multipage():
    global created_analysis_id_for_chat, device_for_cleanup

    device_id = f"qa-ocr-pipeline-{uuid.uuid4()}"
    device_for_cleanup = device_id

    for n_pages in (1, 2, 4):
        print(f"\n[5.{n_pages}] POST /api/analyze with {n_pages} page(s) -- device={device_id[:24]}...")
        pages = [
            {"file_base64": build_page_jpeg(i, n_pages), "mime_type": "image/jpeg"}
            for i in range(n_pages)
        ]
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "idempotency_key": f"qa-ocr-{n_pages}p-{uuid.uuid4()}",
            "pages": pages,
        }
        print(f"      payload: device_id={device_id[:24]}..., target_language=en, pages=[{n_pages} x ~{len(pages[0]['file_base64']) // 1024}KB JPEG]")

        t0 = time.time()
        try:
            r = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=TIMEOUT_ANALYZE)
        except requests.Timeout:
            results.fail(f"POST /api/analyze {n_pages}-page -- HTTP call", f"timeout after {TIMEOUT_ANALYZE}s")
            continue
        except Exception as e:
            results.fail(f"POST /api/analyze {n_pages}-page -- HTTP call", f"{type(e).__name__}: {e}")
            continue
        elapsed = time.time() - t0

        if r.status_code != 200:
            results.fail(
                f"POST /api/analyze {n_pages}-page -- status",
                f"got {r.status_code} in {elapsed:.1f}s. body={_safe_body(r)}",
            )
            continue
        if elapsed > 60:
            results.fail(f"POST /api/analyze {n_pages}-page -- <60s latency", f"took {elapsed:.1f}s")
        else:
            results.ok(f"POST /api/analyze {n_pages}-page -> 200 in {elapsed:.1f}s (under 60s budget)")

        body = r.json()
        _assert_analysis_result_schema(body, f"/api/analyze {n_pages}-page")

        if n_pages == 1:
            created_analysis_id_for_chat = body.get("id", "")
            if not created_analysis_id_for_chat:
                results.fail("analyze -- envelope.id for chat follow-up", f"no id in body: {list(body.keys())}")

        usage = body.get("usage", {})
        print(f"      usage after {n_pages}-page: free_used={usage.get('free_analyses_used')}, soft_used={usage.get('soft_extra_used')}")


def test_chat_endpoint():
    print(f"\n[6] POST /api/analyses/{{id}}/chat -- Was ist die Frist?")
    if not created_analysis_id_for_chat:
        results.fail("chat -- prerequisite", "no analysis id from step 5.1; skipping chat test")
        return
    payload = {"device_id": device_for_cleanup, "message": "Was ist die Frist?"}
    try:
        t0 = time.time()
        r = requests.post(
            f"{BASE_URL}/analyses/{created_analysis_id_for_chat}/chat",
            json=payload, timeout=TIMEOUT_ANALYZE,
        )
        elapsed = time.time() - t0
        if r.status_code != 200:
            results.fail("chat -- status", f"got {r.status_code} in {elapsed:.1f}s. body={_safe_body(r)}")
            return
        body = r.json()
        required = ["role", "content", "off_topic", "created_at"]
        missing = [k for k in required if k not in body]
        if missing:
            results.fail("chat -- ChatMessage shape", f"missing={missing}. present={list(body.keys())}")
            return
        if body["role"] != "assistant":
            results.fail("chat -- role", f"expected 'assistant', got {body['role']!r}")
            return
        if not isinstance(body["content"], str) or not body["content"].strip():
            results.fail("chat -- content populated", f"content={body.get('content')!r}")
            return
        results.ok(f"POST /api/analyses/{{id}}/chat -> 200 in {elapsed:.1f}s, role=assistant, content={len(body['content'])} chars, off_topic={body['off_topic']}")
    except Exception as e:
        results.fail("chat", f"{type(e).__name__}: {e}")


def test_graceful_unreadable():
    print("\n[7] Graceful failure -- 1x1 white PNG")
    device = f"qa-unreadable-{uuid.uuid4()}"
    payload = {
        "device_id": device,
        "target_language": "en",
        "idempotency_key": f"qa-unread-{uuid.uuid4()}",
        "pages": [{"file_base64": build_tiny_white_png(), "mime_type": "image/png"}],
    }
    try:
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=TIMEOUT_ANALYZE)
        elapsed = time.time() - t0
        if r.status_code == 502:
            results.fail("unreadable input -- NOT 502", f"got 502 in {elapsed:.1f}s. body={_safe_body(r)}")
            return
        if r.status_code == 422:
            body = _safe_body(r)
            results.ok(f"unreadable input -> 422 (clean) in {elapsed:.1f}s -- {body[:160]}")
            return
        if r.status_code == 200:
            body = r.json()
            result = body.get("result", {}) or {}
            uncertainties = result.get("uncertainties", [])
            results.ok(f"unreadable input -> 200 in {elapsed:.1f}s with {len(uncertainties)} uncertainties (acceptable per spec)")
            try:
                requests.delete(f"{BASE_URL}/history/{device}", timeout=TIMEOUT_SHORT)
            except Exception:
                pass
            return
        body = _safe_body(r)
        if 400 <= r.status_code < 500:
            results.ok(f"unreadable input -> {r.status_code} in {elapsed:.1f}s (non-502, acceptable) -- {body[:160]}")
        else:
            results.fail(f"unreadable input -- status {r.status_code}", body[:200])
    except Exception as e:
        results.fail("unreadable input", f"{type(e).__name__}: {e}")


def test_idempotency():
    print("\n[8] Idempotency -- same analyze request twice")
    device = f"qa-idemp-{uuid.uuid4()}"
    idemp_key = f"qa-idemp-key-{uuid.uuid4()}"
    page = build_page_jpeg(0, 1)
    payload = {
        "device_id": device,
        "target_language": "en",
        "idempotency_key": idemp_key,
        "pages": [{"file_base64": page, "mime_type": "image/jpeg"}],
    }
    print(f"      device={device[:24]}..., idempotency_key={idemp_key[:18]}...")
    try:
        t0 = time.time()
        r1 = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=TIMEOUT_ANALYZE)
        t1 = time.time()
        if r1.status_code != 200:
            results.fail("idempotency -- first call status", f"got {r1.status_code}. body={_safe_body(r1)}")
            return
        body1 = r1.json()
        usage1 = body1.get("usage", {})
        used1 = usage1.get("free_analyses_used", -1)

        r2 = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=TIMEOUT_ANALYZE)
        t2 = time.time()
        if r2.status_code != 200:
            results.fail("idempotency -- second call status", f"got {r2.status_code}. body={_safe_body(r2)}")
            return
        body2 = r2.json()
        usage2 = body2.get("usage", {})
        used2 = usage2.get("free_analyses_used", -1)

        results.ok(f"idempotency -- both calls 200 (t1={t1-t0:.1f}s, t2={t2-t1:.1f}s)")
        if used1 == 1 and used2 == 1:
            results.ok(f"idempotency -- free_analyses_used incremented by exactly 1 (1st={used1}, 2nd={used2})")
        else:
            results.fail(
                "idempotency -- usage increment",
                f"expected 1 and 1, got 1st={used1} 2nd={used2}. Full usage2={usage2}",
            )

        try:
            requests.delete(f"{BASE_URL}/history/{device}", timeout=TIMEOUT_SHORT)
        except Exception:
            pass

    except Exception as e:
        results.fail("idempotency", f"{type(e).__name__}: {e}")


def test_cleanup_delete_history():
    print(f"\n[9] Cleanup -- DELETE /api/history/{device_for_cleanup[:24]}...")
    if not device_for_cleanup:
        results.fail("cleanup -- no device", "device_for_cleanup is empty")
        return
    try:
        r = requests.delete(f"{BASE_URL}/history/{device_for_cleanup}", timeout=TIMEOUT_SHORT)
        if r.status_code != 200:
            results.fail("DELETE /api/history/{device} -- status", f"got {r.status_code}. body={_safe_body(r)}")
            return
        body = r.json()
        if "deleted_analyses" not in body or "deleted_messages" not in body:
            results.fail("DELETE /api/history -- shape", f"missing keys: {list(body.keys())}")
            return
        results.ok(f"DELETE /api/history/... -> 200 with {{deleted_analyses:{body['deleted_analyses']}, deleted_messages:{body['deleted_messages']}}}")
    except Exception as e:
        results.fail("DELETE /api/history/{device}", f"{type(e).__name__}: {e}")


def test_retry_helper_unit():
    print("\n[10] Retry helper unit tests -- python3 /app/backend/_test_retry.py")
    try:
        proc = subprocess.run(
            ["python3", "_test_retry.py"],
            cwd="/app/backend",
            capture_output=True, text=True, timeout=180,
        )
        stdout = proc.stdout or ""
        if proc.returncode != 0:
            results.fail(
                "retry helper unit test -- exit code",
                f"rc={proc.returncode}. stdout={stdout[-500:]!r} stderr={(proc.stderr or '')[-500:]!r}",
            )
            return
        if "ALL 6 TESTS PASSED" not in stdout:
            results.fail(
                "retry helper unit test -- banner",
                f"'ALL 6 TESTS PASSED' missing. stdout tail:\n{stdout[-500:]}",
            )
            return
        results.ok("retry helper unit test: exit=0, 'ALL 6 TESTS PASSED' present")
    except subprocess.TimeoutExpired:
        results.fail("retry helper unit test", "timeout 60s")
    except Exception as e:
        results.fail("retry helper unit test", f"{type(e).__name__}: {e}")


def test_privacy_log_audit(log_snapshot_start: Dict[str, int]):
    print("\n[11] Privacy log audit -- scan backend logs for the test window")
    try:
        window_text = _read_logs_since(log_snapshot_start)
    except Exception as e:
        results.fail("privacy log audit -- log read", f"{type(e).__name__}: {e}")
        return

    ocr_matches = re.findall(r"ocr_page_ok idx=\d+ chars=\d+", window_text)
    if ocr_matches:
        results.ok(f"privacy log -- {len(ocr_matches)} `ocr_page_ok idx=N chars=N` line(s) found (expected)")
    else:
        results.fail(
            "privacy log -- ocr_page_ok expected",
            f"no `ocr_page_ok idx=N chars=N` lines in test window (log chars captured={len(window_text)})",
        )

    leaked = []
    for tok in PII_TOKENS:
        if tok in window_text:
            count = window_text.count(tok)
            idx = window_text.find(tok)
            start = max(0, idx - 40)
            end = min(len(window_text), idx + len(tok) + 40)
            leaked.append((tok, count, window_text[start:end].replace("\n", " ")))
    if leaked:
        detail_parts = []
        for tok, count, preview in leaked:
            detail_parts.append(f"{tok!r}x{count}: ...{preview}...")
        results.fail("privacy log -- PII tokens", "; ".join(detail_parts))
    else:
        results.ok(f"privacy log -- zero PII leakage across {len(PII_TOKENS)} sentinel tokens")

    tb_patterns = [
        r'File ".+server\.py", line \d+, in ocr_pages_with_mistral',
        r'File ".+server\.py", line \d+, in analyze_with_mistral',
        r'File ".+server\.py", line \d+, in ocr_one',
    ]
    hits = []
    for pat in tb_patterns:
        hits.extend(re.findall(pat, window_text))
    if hits:
        results.fail("privacy log -- tracebacks in new OCR/analysis paths", f"{len(hits)} hit(s). sample: {hits[0]!r}")
    else:
        results.ok("privacy log -- zero tracebacks from ocr_pages_with_mistral / analyze_with_mistral / ocr_one")


def main() -> int:
    print(f"KlarPost backend regression -- targeting {BASE_URL}")
    print(f"Started at {datetime.now(timezone.utc).isoformat()}\n")

    log_start = _snapshot_log_sizes()

    test_existing_smoke()
    test_usage_endpoint(f"qa-usage-{uuid.uuid4()}")

    test_analyze_multipage()
    test_chat_endpoint()
    test_graceful_unreadable()
    test_idempotency()
    test_cleanup_delete_history()
    test_retry_helper_unit()
    test_privacy_log_audit(log_start)

    results.summary()
    return 0 if not results.failed else 1


if __name__ == "__main__":
    sys.exit(main())
