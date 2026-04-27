"""Followup regression test for KlarPost backend.

Verifies the two production-readiness FIXES applied in /app/backend/server.py:
  FIX 1: Defensive Literal-field coercion (no more 502s due to chatty enum values)
  FIX 2: DELETE /api/history/{device_id} now returns correct deleted_messages count
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
import uuid
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

BACKEND_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or "https://doc-assistant-app.preview.emergentagent.com"
)
API = f"{BACKEND_URL.rstrip('/')}/api"

LOG_FILES = [
    "/var/log/supervisor/backend.out.log",
    "/var/log/supervisor/backend.err.log",
]

# Tokens that MUST NOT appear in supervisor logs after the test run.
SECRET_TOKENS = [
    "Bundespolizei",
    "Mustermann",
    "Sehr geehrte",
    "AOK Nordwest",
    "Mitgliedsbeitrag",
    "Versichertennummer",
    "iTunes-Gutscheinkarten",
    "DE89 3704 0044 0532 0130 00",
    "NG12 1234 5678 9012 3456",
    "polizei.bundes.eu@gmail.com",
    "1FzWLkAahfbjz9R5N4cFJBRy3sJVR9MZpw",
    "Sofortzahlung",
    "01.01.2026",
    "248,50 EUR",
    "4 850 EUR",
]

results: list[tuple[str, bool, str]] = []


def record(label: str, ok: bool, detail: str = "") -> None:
    sym = "PASS" if ok else "FAIL"
    print(f"[{sym}] {label}  {detail}")
    results.append((label, ok, detail))


def _make_letter_png(lines: list[str]) -> bytes:
    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font
    y = 80
    for i, line in enumerate(lines):
        f = font_bold if i == 0 or line.startswith("**") else font
        text = line.lstrip("*").strip() if line.startswith("**") else line
        draw.text((80, y), text, fill="black", font=f)
        y += 48
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def benign_letter_png() -> bytes:
    return _make_letter_png(
        [
            "**AOK Nordwest",
            "Bismarckstraße 12",
            "44135 Dortmund",
            "",
            "An: Erika Mustermann",
            "Versichertennummer: A123456789",
            "",
            "Sehr geehrte Frau Mustermann,",
            "",
            "wir möchten Sie informieren, dass sich Ihr",
            "Mitgliedsbeitrag zum 01.01.2026 ändert.",
            "Der neue Beitrag beträgt 248,50 EUR pro Monat.",
            "",
            "Bei Fragen wenden Sie sich bitte an unsere",
            "Servicehotline. Das Beitragskonto lautet",
            "DE89 3704 0044 0532 0130 00.",
            "",
            "Mit freundlichen Grüßen,",
            "AOK Nordwest Kundenservice",
        ]
    )


def scam_letter_png() -> bytes:
    return _make_letter_png(
        [
            "**Bundespolizei Sondereinheit Cybercrime",
            "Absender: polizei.bundes.eu@gmail.com",
            "",
            "DRINGEND – Az. 12345678",
            "",
            "Gegen Sie wird ein Strafverfahren",
            "wegen illegaler Aktivitäten geführt.",
            "Sofortzahlung 4 850 EUR notwendig binnen 24h,",
            "sonst erfolgt sofortige Verhaftung.",
            "",
            "Zahlung NUR via iTunes-Gutscheinkarten oder",
            "Bitcoin an Wallet:",
            "1FzWLkAahfbjz9R5N4cFJBRy3sJVR9MZpw",
            "",
            "Alternativ Überweisung auf Konto:",
            "NG12 1234 5678 9012 3456 (Nigeria)",
            "",
            "Antwort an: polizei.bundes.eu@gmail.com",
        ]
    )


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def log_offsets() -> dict[str, int]:
    out: dict[str, int] = {}
    for p in LOG_FILES:
        try:
            out[p] = os.path.getsize(p)
        except OSError:
            out[p] = 0
    return out


def log_diff_since(baseline: dict[str, int]) -> dict[str, str]:
    diffs: dict[str, str] = {}
    for p, start in baseline.items():
        try:
            with open(p, "rb") as f:
                f.seek(start)
                diffs[p] = f.read().decode("utf-8", errors="replace")
        except OSError:
            diffs[p] = ""
    return diffs


# ---------------------------------------------------------------------------
# 1. STRESS TEST FIX-1: scam fixture 5x in a row → must all return 200
# ---------------------------------------------------------------------------
def test_scam_stress() -> None:
    print("\n=== STRESS-1: scam fixture 5x (literal coercion) ===")
    device_id = f"qa-followup-scam-{uuid.uuid4().hex[:8]}"
    scam_b64 = b64(scam_letter_png())
    successes = 0
    fail_details: list[str] = []
    for i in range(1, 6):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": scam_b64,
            "mime_type": "image/png",
        }
        t0 = time.time()
        try:
            r = requests.post(f"{API}/analyze", json=payload, timeout=180)
        except Exception as e:
            record(f"scam run #{i}", False, f"network exception: {e}")
            fail_details.append(f"run#{i}=NETWORK:{e}")
            continue
        dur = time.time() - t0
        if r.status_code == 200:
            data = r.json()
            res = data.get("result", {}) or {}
            ok = (
                res.get("risk_level") == "red"
                and res.get("scam_warning") is True
            )
            record(
                f"scam run #{i}",
                ok,
                f"status=200 dur={dur:.1f}s risk={res.get('risk_level')!r} scam={res.get('scam_warning')!r} cat={res.get('category')!r}",
            )
            if ok:
                successes += 1
            else:
                fail_details.append(
                    f"run#{i}=200 but risk/scam wrong: risk={res.get('risk_level')!r}, scam={res.get('scam_warning')!r}"
                )
        else:
            body = r.text[:400]
            record(
                f"scam run #{i}",
                False,
                f"status={r.status_code} dur={dur:.1f}s body={body}",
            )
            fail_details.append(f"run#{i}=HTTP{r.status_code}:{body}")
    record(
        "STRESS-1 summary: 5/5 scam analyses returned 200 with risk=red & scam_warning=True",
        successes == 5,
        f"successes={successes}/5; failures={fail_details}",
    )


# ---------------------------------------------------------------------------
# 2. STRESS TEST other Literal fields: benign 3x
# ---------------------------------------------------------------------------
def test_benign_stress() -> tuple[str, str]:
    print("\n=== STRESS-2: benign fixture 3x (Literal fields stay valid) ===")
    device_id = f"qa-followup-benign-{uuid.uuid4().hex[:8]}"
    benign_b64 = b64(benign_letter_png())
    valid_cats = {
        "tax", "insurance", "rent", "bank", "health", "government",
        "court", "utilities", "telecom", "work", "education", "other",
    }
    last_id = ""
    successes = 0
    for i in range(1, 4):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": benign_b64,
            "mime_type": "image/png",
        }
        t0 = time.time()
        try:
            r = requests.post(f"{API}/analyze", json=payload, timeout=180)
        except Exception as e:
            record(f"benign run #{i}", False, f"network exception: {e}")
            continue
        dur = time.time() - t0
        if r.status_code == 200:
            data = r.json()
            res = data.get("result", {}) or {}
            target_lang = res.get("target_language")
            cat = res.get("category")
            risk = res.get("risk_level")
            ok = (
                target_lang == "English"
                and cat in valid_cats
                and risk in {"green", "yellow", "red"}
            )
            record(
                f"benign run #{i}",
                ok,
                f"status=200 dur={dur:.1f}s target={target_lang!r} cat={cat!r} risk={risk!r}",
            )
            if ok:
                successes += 1
                last_id = data.get("id", last_id)
        else:
            record(
                f"benign run #{i}",
                False,
                f"status={r.status_code} dur={dur:.1f}s body={r.text[:300]}",
            )
    record(
        "STRESS-2 summary: 3/3 benign analyses returned valid Literal fields",
        successes == 3,
        f"successes={successes}/3",
    )
    return device_id, last_id


# ---------------------------------------------------------------------------
# 3. DELETE /api/history/{device_id} counter
# ---------------------------------------------------------------------------
def test_history_counter() -> None:
    print("\n=== FIX-2: DELETE /api/history/{device_id} counter ===")
    device_id = f"qa-history-fix-{uuid.uuid4().hex[:8]}"

    # 3a. POST /api/analyze (1 image, target_language='en')
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "file_base64": b64(benign_letter_png()),
        "mime_type": "image/png",
    }
    r = requests.post(f"{API}/analyze", json=payload, timeout=180)
    if r.status_code != 200:
        record("history-fix prerequisite analyze", False, f"status={r.status_code} body={r.text[:300]}")
        return
    record("history-fix prerequisite analyze", True, f"status=200 id={r.json().get('id', '')[:8]}")
    analysis_id = r.json()["id"]

    # 3b. POST 3 chat messages
    chat_msgs = [
        "Was steht im Brief?",
        "Wann ist die Frist?",
        "Was muss ich tun?",
    ]
    chat_ok = 0
    for msg in chat_msgs:
        rc = requests.post(
            f"{API}/analyses/{analysis_id}/chat",
            json={"device_id": device_id, "message": msg},
            timeout=180,
        )
        if rc.status_code == 200:
            chat_ok += 1
        else:
            print(f"  chat fail status={rc.status_code} body={rc.text[:200]}")
    record(
        "history-fix seed 3 chat messages",
        chat_ok == 3,
        f"successful_chats={chat_ok}/3",
    )

    # 3c. GET messages → expect at least 6 (3 user + 3 assistant)
    r = requests.get(
        f"{API}/analyses/{analysis_id}/messages",
        params={"device_id": device_id},
        timeout=30,
    )
    msgs = r.json() if r.status_code == 200 else []
    record(
        "GET /messages → ≥6 embedded msgs",
        r.status_code == 200 and isinstance(msgs, list) and len(msgs) >= 6,
        f"status={r.status_code} count={len(msgs) if isinstance(msgs, list) else 'n/a'}",
    )
    embedded_seen = len(msgs) if isinstance(msgs, list) else 0

    # 3d. DELETE /api/history/{device_id}
    r = requests.delete(f"{API}/history/{device_id}", timeout=30)
    body: Any = {}
    try:
        body = r.json()
    except Exception:
        pass
    record(
        "DELETE /api/history/{id} status=200",
        r.status_code == 200,
        f"status={r.status_code} body={body}",
    )
    if isinstance(body, dict):
        record(
            "deleted_analyses == 1",
            body.get("deleted_analyses") == 1,
            f"value={body.get('deleted_analyses')!r}",
        )
        record(
            f"deleted_messages >= 6 (embedded msgs counted; previously was always 0)",
            isinstance(body.get("deleted_messages"), int) and body["deleted_messages"] >= 6,
            f"value={body.get('deleted_messages')!r} (embedded GET saw {embedded_seen})",
        )

    # 3e. GET /api/analyses → empty list
    r = requests.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
    arr = r.json() if r.status_code == 200 else None
    record(
        "GET /api/analyses → empty after history wipe",
        r.status_code == 200 and arr == [],
        f"status={r.status_code} body={arr}",
    )

    # 3f. DELETE /api/history/<another-fresh-device-id> → idempotent (200, both 0)
    fresh = f"qa-history-fresh-{uuid.uuid4().hex[:8]}"
    r = requests.delete(f"{API}/history/{fresh}", timeout=30)
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    record(
        "DELETE /api/history/<fresh-unknown> idempotent: 200 + both counters=0",
        r.status_code == 200
        and isinstance(body, dict)
        and body.get("deleted_analyses") == 0
        and body.get("deleted_messages") == 0,
        f"status={r.status_code} body={body}",
    )


# ---------------------------------------------------------------------------
# 4. Privacy log audit
# ---------------------------------------------------------------------------
def test_privacy_logs(baseline: dict[str, int]) -> None:
    print("\n=== AUDIT: privacy log audit (no document content) ===")
    diffs = log_diff_since(baseline)
    leaks: list[str] = []
    for path, blob in diffs.items():
        for tok in SECRET_TOKENS:
            if tok in blob:
                leaks.append(f"{os.path.basename(path)}: '{tok}'")
    record(
        "privacy log audit: zero document-content tokens leaked",
        not leaks,
        f"leaks={leaks if leaks else 'none'}",
    )
    if leaks:
        # Print short context for each leak to help main agent debug
        for path, blob in diffs.items():
            for tok in SECRET_TOKENS:
                if tok in blob:
                    idx = blob.find(tok)
                    snippet = blob[max(0, idx - 80): idx + len(tok) + 80].replace("\n", " | ")
                    print(f"   LEAK [{os.path.basename(path)}] '{tok}': …{snippet}…")


# ---------------------------------------------------------------------------
# 5. Regression sanity: GET /, /languages, /export
# ---------------------------------------------------------------------------
def test_no_regression() -> None:
    print("\n=== NO-REGRESSION: GET /api/, /api/languages, /api/export ===")
    r = requests.get(f"{API}/", timeout=30)
    record("GET /api/ → 200", r.status_code == 200, f"status={r.status_code} body={r.text[:120]}")

    r = requests.get(f"{API}/languages", timeout=30)
    ok_shape = False
    if r.status_code == 200:
        try:
            arr = r.json()
            ok_shape = (
                isinstance(arr, list)
                and len(arr) >= 5
                and all(isinstance(x, dict) and "code" in x and "label" in x for x in arr)
            )
        except Exception:
            pass
    record(
        "GET /api/languages → 200 + list of {code,label}",
        ok_shape,
        f"status={r.status_code} count={len(r.json()) if r.status_code == 200 else 'n/a'}",
    )

    dev = f"qa-export-noregress-{uuid.uuid4().hex[:8]}"
    r = requests.get(f"{API}/export", params={"device_id": dev}, timeout=30)
    body = r.json() if r.status_code == 200 else {}
    expected = {"app", "device_id", "exported_at", "data_residency", "count", "analyses"}
    has_keys = isinstance(body, dict) and set(body.keys()) == expected
    record(
        "GET /api/export → 200 + exact key set",
        r.status_code == 200 and has_keys,
        f"status={r.status_code} keys={sorted(body.keys()) if isinstance(body, dict) else 'n/a'}",
    )
    if has_keys:
        record(
            "export: data_residency='EU (Mistral AI, Paris)'",
            body.get("data_residency") == "EU (Mistral AI, Paris)",
            f"value={body.get('data_residency')!r}",
        )
        record(
            "export: count=0 for fresh device",
            body.get("count") == 0 and body.get("analyses") == [],
            f"count={body.get('count')!r}, analyses={body.get('analyses')!r}",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print(f"Backend: {API}")
    baseline = log_offsets()

    # Stress tests first (they generate the bulk of the LLM traffic)
    test_scam_stress()
    test_benign_stress()
    test_history_counter()
    test_no_regression()
    # Privacy audit LAST so it sees all log activity from above
    test_privacy_logs(baseline)

    # Final summary
    print("\n" + "=" * 72)
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"RESULT: {passed}/{total} assertions PASSED")
    print("=" * 72)
    failures = [(lbl, det) for lbl, ok, det in results if not ok]
    if failures:
        print("\nFAILURES:")
        for lbl, det in failures:
            print(f"  - {lbl}  {det}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
