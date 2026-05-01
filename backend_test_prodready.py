"""Production-readiness regression for KlarPost backend.

Covers the 5 current_focus tasks from /app/test_result.md:
  1. Env-driven Mistral model IDs (mistral-large-2512)
  2. /api/analyze on Mistral Large 3 (vision OCR + JSON)
  3. /api/analyses/{id}/chat — same env model
  4. NEW DELETE /api/history/{device_id} — DSGVO Art. 17
  5. Legacy DELETE /api/analyses?device_id=... still works (back-compat)
  6. GET /api/export still works post-refactor
  7. CRITICAL — Privacy log audit (no document content in logs)
  8. Originals not persisted (no base64/image fields in MongoDB doc)
  9. Cleanup
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import time
import uuid
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont
from pymongo import MongoClient

# ----------------------------------------------------------------------------
# Config — REACT_APP_BACKEND_URL is the public preview URL. The frontend's
# .env exposes it as EXPO_PUBLIC_BACKEND_URL for the Expo app.
# ----------------------------------------------------------------------------
BACKEND_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or "https://doc-scanner-de.preview.emergentagent.com"
)
API = f"{BACKEND_URL.rstrip('/')}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "klarpost_database")

LOG_FILES = [
    "/var/log/supervisor/backend.out.log",
    "/var/log/supervisor/backend.err.log",
]

results: list[tuple[str, bool, str]] = []


def record(label: str, ok: bool, detail: str = "") -> None:
    sym = "PASS" if ok else "FAIL"
    print(f"[{sym}] {label}  {detail}")
    results.append((label, ok, detail))


# ----------------------------------------------------------------------------
# Test fixtures — synthetic German letters as PNG bytes
# ----------------------------------------------------------------------------
# Words we'll later grep for in supervisor logs to make sure they NEVER appear.
SECRET_TOKENS = [
    "Sehr geehrte",
    "Versichertennummer",
    "AOK Nordwest",
    "Mitgliedsbeitrag",
    "Bundespolizei Sondereinheit",
    "DE89 3704 0044 0532 0130 00",  # German IBAN we put in benign letter
    "NG12 1234 5678 9012 3456",     # Foreign IBAN we put in scam letter
    "Sofortzahlung 4 850 EUR",
    "iTunes-Gutscheinkarten",
    "1FzWLkAahfbjz9R5N4cFJBRy3sJVR9MZpw",  # fake BTC wallet
    "polizei.bundes.eu@gmail.com",
    "Erika Mustermann",
    "12345678",  # 4+ digit numeric amount used in scam
]


def _make_letter_png(lines: list[str]) -> bytes:
    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28
        )
        font_bold = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
        )
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


# ----------------------------------------------------------------------------
# Capture log baseline so we only audit lines written DURING this run.
# ----------------------------------------------------------------------------
def log_offsets() -> dict[str, int]:
    out: dict[str, int] = {}
    for path in LOG_FILES:
        try:
            out[path] = os.path.getsize(path)
        except OSError:
            out[path] = 0
    return out


def log_diff_since(baseline: dict[str, int]) -> dict[str, str]:
    diffs: dict[str, str] = {}
    for path, start in baseline.items():
        try:
            with open(path, "rb") as f:
                f.seek(start)
                diffs[path] = f.read().decode("utf-8", errors="replace")
        except OSError:
            diffs[path] = ""
    return diffs


# ----------------------------------------------------------------------------
# 1. Env / model-id checks
# ----------------------------------------------------------------------------
def test_env_model_ids() -> None:
    print("\n=== TASK 1: env-driven Mistral model IDs ===")
    r = requests.get(f"{API}/", timeout=30)
    record("GET /api/", r.status_code == 200, f"status={r.status_code} body={r.text}")

    env_path = "/app/backend/.env"
    with open(env_path) as f:
        env = f.read()
    for var in ("MISTRAL_VISION_MODEL", "MISTRAL_ANALYSIS_MODEL", "MISTRAL_CHAT_MODEL"):
        ok = re.search(rf"^{var}=mistral-large-2512\s*$", env, re.MULTILINE) is not None
        record(f"env {var}=mistral-large-2512", ok)

    with open("/app/backend/server.py") as f:
        src = f.read()
    has_pixtral = re.search(r"['\"]pixtral-large-latest['\"]", src) is not None
    has_legacy_large = re.search(r"['\"]mistral-large-latest['\"]", src) is not None
    record("server.py has no hard-coded 'pixtral-large-latest'", not has_pixtral)
    record("server.py has no hard-coded 'mistral-large-latest'", not has_legacy_large)

    # Confirm both functions reference the env-resolved variables
    analyze_uses_env = "model=MISTRAL_VISION_MODEL" in src
    chat_uses_env = "model=MISTRAL_CHAT_MODEL" in src
    record("analyze_with_mistral uses MISTRAL_VISION_MODEL", analyze_uses_env)
    record("chat_about_document uses MISTRAL_CHAT_MODEL", chat_uses_env)


# ----------------------------------------------------------------------------
# 2. /api/analyze — benign + scam
# ----------------------------------------------------------------------------
def test_analyze() -> tuple[str, str, str]:
    print("\n=== TASK 2: /api/analyze on mistral-large-2512 ===")
    device_id = f"qa-prodready-{uuid.uuid4().hex[:8]}"

    # Benign
    benign_b64 = b64(benign_letter_png())
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "file_base64": benign_b64,
        "mime_type": "image/png",
    }
    t0 = time.time()
    r = requests.post(f"{API}/analyze", json=payload, timeout=120)
    dur = time.time() - t0
    ok = r.status_code == 200
    record("POST /api/analyze (benign Krankenkasse)",
           ok, f"status={r.status_code} dur={dur:.1f}s")
    if not ok:
        print("  body:", r.text[:500])
        return device_id, "", ""
    benign = r.json()
    res = benign.get("result", {})
    record(
        "benign: scam_warning=False",
        res.get("scam_warning") is False,
        f"value={res.get('scam_warning')!r}",
    )
    record(
        "benign: target_language='English'",
        res.get("target_language") == "English",
        f"value={res.get('target_language')!r}",
    )
    valid_cats = {
        "tax", "insurance", "rent", "bank", "health", "government",
        "court", "utilities", "telecom", "work", "education", "other",
    }
    record(
        "benign: category in enum",
        res.get("category") in valid_cats,
        f"category={res.get('category')!r}",
    )
    record(
        "benign: AnalysisRecord shape",
        all(k in benign for k in ("id", "device_id", "target_language",
                                  "target_language_label", "mime_type",
                                  "created_at", "result")),
        f"keys={sorted(benign.keys())}",
    )
    benign_id = benign.get("id", "")

    # Scam
    scam_b64 = b64(scam_letter_png())
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "file_base64": scam_b64,
        "mime_type": "image/png",
    }
    t0 = time.time()
    r = requests.post(f"{API}/analyze", json=payload, timeout=120)
    dur = time.time() - t0
    ok = r.status_code == 200
    record("POST /api/analyze (obvious scam)", ok, f"status={r.status_code} dur={dur:.1f}s")
    if not ok:
        print("  body:", r.text[:500])
        return device_id, benign_id, ""
    scam = r.json()
    res = scam.get("result", {})
    record(
        "scam: risk_level='red'",
        res.get("risk_level") == "red",
        f"value={res.get('risk_level')!r}",
    )
    record(
        "scam: scam_warning=True",
        res.get("scam_warning") is True,
        f"value={res.get('scam_warning')!r}",
    )
    sr = res.get("scam_reason") or ""
    record("scam: scam_reason non-empty", bool(sr.strip()), f"len={len(sr)}")
    record(
        "scam: category in {government, other}",
        res.get("category") in {"government", "other"},
        f"category={res.get('category')!r}",
    )
    scam_id = scam.get("id", "")
    return device_id, benign_id, scam_id


# ----------------------------------------------------------------------------
# 3. Chat
# ----------------------------------------------------------------------------
def test_chat(device_id: str, analysis_id: str) -> None:
    print("\n=== TASK 3: /api/analyses/{id}/chat ===")
    if not analysis_id:
        record("chat: prerequisites missing", False)
        return
    # On-topic
    payload = {
        "device_id": device_id,
        "message": "Was bedeutet der Beitrag in diesem Brief?",
    }
    t0 = time.time()
    r = requests.post(f"{API}/analyses/{analysis_id}/chat", json=payload, timeout=120)
    dur = time.time() - t0
    ok = r.status_code == 200
    record("POST chat (on-topic DE question)", ok, f"status={r.status_code} dur={dur:.1f}s")
    if ok:
        data = r.json()
        record("on-topic: off_topic=False",
               data.get("off_topic") is False, f"value={data.get('off_topic')!r}")
        content = data.get("content") or ""
        record("on-topic: content non-empty", bool(content.strip()), f"len={len(content)}")

    # Off-topic
    payload = {"device_id": device_id, "message": "Tell me a joke about cats"}
    t0 = time.time()
    r = requests.post(f"{API}/analyses/{analysis_id}/chat", json=payload, timeout=120)
    dur = time.time() - t0
    ok = r.status_code == 200
    record("POST chat (off-topic cat joke)", ok, f"status={r.status_code} dur={dur:.1f}s")
    if ok:
        data = r.json()
        record(
            "off-topic: off_topic=True",
            data.get("off_topic") is True,
            f"value={data.get('off_topic')!r}",
        )


# ----------------------------------------------------------------------------
# 4. NEW DELETE /api/history/{device_id}
# ----------------------------------------------------------------------------
def test_delete_history() -> None:
    print("\n=== TASK 4: DELETE /api/history/{device_id} ===")
    device_id = f"qa-history-{uuid.uuid4().hex[:8]}"
    # 1 analyze
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "file_base64": b64(benign_letter_png()),
        "mime_type": "image/png",
    }
    r = requests.post(f"{API}/analyze", json=payload, timeout=120)
    if r.status_code != 200:
        record("history-flow analyze prerequisite", False, f"status={r.status_code}")
        return
    analysis_id = r.json()["id"]
    # 1 chat msg
    r2 = requests.post(
        f"{API}/analyses/{analysis_id}/chat",
        json={"device_id": device_id, "message": "Was steht hier drin?"},
        timeout=120,
    )
    record(
        "history-flow seed chat msg",
        r2.status_code == 200,
        f"status={r2.status_code}",
    )

    # GET analyses → 1
    r = requests.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
    items = r.json() if r.status_code == 200 else []
    record(
        "GET /api/analyses → 1 item",
        r.status_code == 200 and len(items) == 1,
        f"status={r.status_code} count={len(items)}",
    )

    # GET messages → ≥ 1 row
    r = requests.get(
        f"{API}/analyses/{analysis_id}/messages",
        params={"device_id": device_id},
        timeout=30,
    )
    msgs = r.json() if r.status_code == 200 else []
    record(
        "GET /messages → ≥1 message row",
        r.status_code == 200 and len(msgs) >= 1,
        f"status={r.status_code} count={len(msgs) if isinstance(msgs, list) else 'n/a'}",
    )

    # DELETE /api/history/{device_id} → 200, shape
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
    has_keys = isinstance(body, dict) and "deleted_analyses" in body and "deleted_messages" in body
    record(
        "response shape {deleted_analyses, deleted_messages}",
        has_keys,
        f"body={body}",
    )
    if has_keys:
        record(
            "deleted_analyses >= 1",
            body["deleted_analyses"] >= 1,
            f"value={body['deleted_analyses']}",
        )
        # NOTE: chat messages are stored INSIDE the analyses doc as a
        # `messages` array (see server.py chat_endpoint), not in a
        # separate `chat_messages` collection. So `deleted_messages` will
        # likely be 0. Record this as a deviation from the request spec.
        record(
            "deleted_messages >= 1 (per task spec)",
            body["deleted_messages"] >= 1,
            f"value={body['deleted_messages']} — note: server uses an embedded "
            "messages array in the analyses doc, so chat_messages collection is "
            "always empty; counter ends up 0",
        )

    # Idempotency: subsequent state checks
    r = requests.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
    record(
        "post-delete: GET /api/analyses empty",
        r.status_code == 200 and r.json() == [],
        f"status={r.status_code} body={r.text[:120]}",
    )
    r = requests.get(
        f"{API}/analyses/{analysis_id}/messages",
        params={"device_id": device_id},
        timeout=30,
    )
    record(
        "post-delete: GET /messages → 404 or empty list",
        (r.status_code == 404)
        or (r.status_code == 200 and r.json() == []),
        f"status={r.status_code} body={r.text[:120]}",
    )

    # DELETE /api/history/ (no device_id)
    r = requests.delete(f"{API}/history/", timeout=30, allow_redirects=False)
    # FastAPI returns 404 (route not matched) or 405. Either is acceptable.
    record(
        "DELETE /api/history/ (empty trailing) → 404",
        r.status_code in (404, 405, 307),
        f"status={r.status_code}",
    )

    # DELETE /api/history/<unknown> → 200 with both counters 0
    r = requests.delete(
        f"{API}/history/qa-does-not-exist-{uuid.uuid4().hex[:6]}", timeout=30
    )
    body = r.json() if r.status_code == 200 else {}
    record(
        "DELETE /api/history/<unknown> idempotent (200, both counters=0)",
        r.status_code == 200
        and body.get("deleted_analyses") == 0
        and body.get("deleted_messages") == 0,
        f"status={r.status_code} body={body}",
    )


# ----------------------------------------------------------------------------
# 5. Legacy DELETE /api/analyses?device_id=... still works
# ----------------------------------------------------------------------------
def test_legacy_delete() -> None:
    print("\n=== TASK 5: legacy DELETE /api/analyses?device_id=... ===")
    device_id = f"qa-legacy-{uuid.uuid4().hex[:8]}"
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "file_base64": b64(benign_letter_png()),
        "mime_type": "image/png",
    }
    r = requests.post(f"{API}/analyze", json=payload, timeout=120)
    if r.status_code != 200:
        record("legacy-flow analyze prerequisite", False, f"status={r.status_code}")
        return
    aid = r.json()["id"]
    requests.post(
        f"{API}/analyses/{aid}/chat",
        json={"device_id": device_id, "message": "Test."},
        timeout=120,
    )
    r = requests.delete(
        f"{API}/analyses", params={"device_id": device_id}, timeout=30
    )
    body = r.json() if r.status_code == 200 else {}
    record(
        "legacy DELETE /api/analyses?device_id=... → 200 {deleted: N}",
        r.status_code == 200
        and isinstance(body, dict)
        and isinstance(body.get("deleted"), int)
        and body["deleted"] >= 1,
        f"status={r.status_code} body={body}",
    )
    r = requests.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
    record(
        "post-legacy-delete list empty",
        r.status_code == 200 and r.json() == [],
        f"status={r.status_code} body={r.text[:120]}",
    )


# ----------------------------------------------------------------------------
# 6. /api/export shape
# ----------------------------------------------------------------------------
def test_export() -> None:
    print("\n=== TASK 6: GET /api/export ===")
    device_id = f"qa-export-{uuid.uuid4().hex[:8]}"
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "file_base64": b64(benign_letter_png()),
        "mime_type": "image/png",
    }
    r = requests.post(f"{API}/analyze", json=payload, timeout=120)
    if r.status_code != 200:
        record("export-flow analyze prerequisite", False, f"status={r.status_code}")
        return

    r = requests.get(f"{API}/export", params={"device_id": device_id}, timeout=30)
    record(
        "GET /api/export status=200",
        r.status_code == 200,
        f"status={r.status_code}",
    )
    if r.status_code != 200:
        return
    body = r.json()
    expected = {"app", "device_id", "exported_at", "data_residency", "count", "analyses"}
    record(
        "/api/export keys EXACT",
        set(body.keys()) == expected,
        f"keys={sorted(body.keys())}",
    )
    record(
        "data_residency=='EU (Mistral AI, Paris)'",
        body.get("data_residency") == "EU (Mistral AI, Paris)",
        f"value={body.get('data_residency')!r}",
    )
    record(
        "device_id echoed",
        body.get("device_id") == device_id,
        f"value={body.get('device_id')!r}",
    )
    record(
        "count == len(analyses) == 1",
        body.get("count") == 1 and len(body.get("analyses", [])) == 1,
        f"count={body.get('count')} len={len(body.get('analyses', []))}",
    )
    record("app=='KlarPost'", body.get("app") == "KlarPost", f"value={body.get('app')!r}")

    # Cleanup
    requests.delete(f"{API}/history/{device_id}", timeout=30)


# ----------------------------------------------------------------------------
# 8. Confirm originals are NOT persisted in MongoDB
# ----------------------------------------------------------------------------
def test_no_originals_in_db(device_id: str, analysis_id: str) -> None:
    print("\n=== TASK 8: originals NOT persisted in MongoDB ===")
    if not analysis_id:
        record("no-originals: prerequisites missing", False)
        return
    try:
        client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        coll = client[DB_NAME].analyses
        doc = coll.find_one({"id": analysis_id, "device_id": device_id})
    except Exception as e:
        record("no-originals: mongo connect", False, f"err={e}")
        return
    if not doc:
        record("no-originals: doc found", False, "doc not found in db.analyses")
        return

    forbidden = {"original_images", "image_base64", "file_base64"}
    found = forbidden.intersection(doc.keys())
    record(
        "no top-level original_images/image_base64/file_base64",
        len(found) == 0,
        f"found_forbidden={list(found)}",
    )

    def _scan(o: Any, path: str = "") -> list[tuple[str, int]]:
        big: list[tuple[str, int]] = []
        if isinstance(o, dict):
            for k, v in o.items():
                if k in forbidden and isinstance(v, str) and len(v) > 0:
                    big.append((f"{path}.{k}", len(v)))
                big.extend(_scan(v, f"{path}.{k}"))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                big.extend(_scan(v, f"{path}[{i}]"))
        elif isinstance(o, str) and len(o) > 1000:
            # base64 has alphabet of A-Za-z0-9+/=
            stripped = o.strip()
            if re.fullmatch(r"[A-Za-z0-9+/=\s]+", stripped) and len(stripped) > 1000:
                big.append((path or "<root>", len(o)))
        return big

    big_blobs = _scan(doc)
    record(
        "no base64-shaped string > 1000 chars anywhere in stored doc",
        len(big_blobs) == 0,
        f"big_blobs={big_blobs[:3]}",
    )

    allowed = {
        "_id", "id", "device_id", "target_language", "target_language_label",
        "mime_type", "created_at", "result", "messages",
    }
    extra = set(doc.keys()) - allowed
    record(
        "stored doc only has allowed top-level keys",
        len(extra) == 0,
        f"extra={list(extra)} all_keys={sorted(doc.keys())}",
    )


# ----------------------------------------------------------------------------
# 7. Privacy log audit
# ----------------------------------------------------------------------------
def test_log_audit(baseline: dict[str, int]) -> None:
    print("\n=== TASK 7: privacy log audit ===")
    diffs = log_diff_since(baseline)
    leaks: list[tuple[str, str, str]] = []
    for path, content in diffs.items():
        for token in SECRET_TOKENS:
            if token and token in content:
                # find the line
                for line in content.splitlines():
                    if token in line:
                        leaks.append((path, token, line.strip()[:200]))
                        break
        # 4+ digit currency amount (e.g. 4850 EUR, 248,50 EUR)
        # Allow common harmless 4-digit numbers like ports/PIDs/years.
        # We grep for "<digits> EUR" or "EUR <digits>" specifically.
        for m in re.finditer(r"\b\d{3,}[.,]?\d*\s*EUR\b|\bEUR\s*\d{3,}", content):
            for line in content.splitlines():
                if m.group(0) in line:
                    leaks.append((path, f"currency:{m.group(0)}", line.strip()[:200]))
                    break

    record(
        "no secret tokens / IBANs / amounts / sender names in logs",
        len(leaks) == 0,
        f"leaks={leaks[:5]} (total {len(leaks)})",
    )
    if leaks:
        for path, tok, line in leaks[:10]:
            print(f"  LEAK in {path} — token={tok!r}")
            print(f"    {line}")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> int:
    print(f"BACKEND_URL = {BACKEND_URL}")
    print(f"API         = {API}")
    print(f"MONGO_URL   = {MONGO_URL}\n")

    baseline = log_offsets()

    # 1. env / model id checks
    test_env_model_ids()

    # 2. analyze (benign + scam)
    device_id, benign_id, scam_id = test_analyze()

    # 3. chat (uses the benign id)
    test_chat(device_id, benign_id)

    # 8. confirm originals not persisted (use the benign analysis we just created)
    test_no_originals_in_db(device_id, benign_id)

    # 4. NEW DELETE /api/history/{device_id}
    test_delete_history()

    # 5. legacy DELETE /api/analyses?device_id=...
    test_legacy_delete()

    # 6. GET /api/export
    test_export()

    # 7. privacy log audit (after every test that hit Mistral)
    test_log_audit(baseline)

    # 9. cleanup test devices
    print("\n=== TASK 9: cleanup ===")
    if device_id:
        try:
            requests.delete(f"{API}/history/{device_id}", timeout=30)
        except Exception:
            pass
    print("cleanup done")

    # Summary
    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"{passed}/{total} assertions passed")
    failures = [(l, d) for l, ok, d in results if not ok]
    if failures:
        print("\nFAILURES:")
        for l, d in failures:
            print(f"  - {l}  ({d})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
