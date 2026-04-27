"""KlarPost backend privacy hardening + TTL regression.

Validates two new behaviours in /app/backend/server.py:

  1. RequestValidationError redaction handler (DSGVO):
     - 422 body has only loc/type/msg per error
     - NO `body` field anywhere in the response
     - Backend logs only `request_validation_error path=… n_errors=…`

  2. MongoDB TTL index for storage minimisation (DSGVO Art. 5(1)(e)):
     - `ttl_created_at_dt` index exists on analyses.created_at_dt
       with expireAfterSeconds = ANALYSIS_TTL_DAYS * 86400
     - /api/analyze writes BOTH created_at (ISO str) AND created_at_dt (BSON Date)
     - All public read paths strip created_at_dt
     - Idempotent on backend restart

Plus no-regressions check for previously-passing flows.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import time
import uuid
from datetime import datetime
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont
from pymongo import MongoClient

BACKEND_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("REACT_APP_BACKEND_URL")
    or "https://doc-assistant-app.preview.emergentagent.com"
)
API = f"{BACKEND_URL.rstrip('/')}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "klarpost_database")

LOG_FILES = [
    "/var/log/supervisor/backend.out.log",
    "/var/log/supervisor/backend.err.log",
]

# Tokens that MUST NOT appear in supervisor logs.
SECRET_TOKENS = [
    "Sehr geehrte",
    "AOK",
    "Bundespolizei",
    "Mustermann",
    "Versichert",
    "iTunes",
    "DE89",
    "NG12",
    "Sofortzahlung",
    "248,50",
    "4 850",
    "polizei.bundes.eu",
]

results: list[tuple[str, bool, str]] = []


def record(label: str, ok: bool, detail: str = "") -> None:
    sym = "PASS" if ok else "FAIL"
    print(f"[{sym}] {label}  {detail}")
    results.append((label, ok, detail))


# ---------- helpers ----------

def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def benign_letter_png() -> bytes:
    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
        font_bold = font
    lines = [
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
        "Mit freundlichen Grüßen,",
        "AOK Nordwest Kundenservice",
    ]
    y = 80
    for i, line in enumerate(lines):
        f = font_bold if i == 0 or line.startswith("**") else font
        text = line.lstrip("*").strip() if line.startswith("**") else line
        draw.text((80, y), text, fill="black", font=f)
        y += 48
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def find_keys_recursive(obj: Any, target: str) -> list[str]:
    """Return list of dotted paths where the key `target` appears."""
    hits: list[str] = []

    def walk(o: Any, path: str) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{path}.{k}" if path else k
                if k == target:
                    hits.append(p)
                walk(v, p)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(obj, "")
    return hits


def read_log_tail(approx_bytes: int = 200_000) -> str:
    out = ""
    for path in LOG_FILES:
        if not os.path.exists(path):
            continue
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                if size > approx_bytes:
                    f.seek(-approx_bytes, 2)
                out += f.read().decode("utf-8", errors="replace")
        except OSError:
            continue
    return out


def log_snapshot_marker() -> int:
    """Return current size of out.log to use as a marker for "logs after this point"."""
    p = "/var/log/supervisor/backend.err.log"
    return os.path.getsize(p) if os.path.exists(p) else 0


def log_after(marker: int) -> str:
    """Return logs (out + err) after the given marker."""
    out = ""
    for path in LOG_FILES:
        if not os.path.exists(path):
            continue
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                # Use marker only as a heuristic; safer to just read the last
                # 200KB of each log.
                start = max(0, size - 200_000)
                f.seek(start)
                out += f.read().decode("utf-8", errors="replace") + "\n"
        except OSError:
            continue
    return out


# ---------- TEST 1: GET /api/ ----------

def test_root() -> None:
    print("\n=== TEST 1: GET /api/ ===")
    try:
        r = requests.get(f"{API}/", timeout=15)
    except Exception as e:
        record("GET /api/ network", False, str(e))
        return
    ok = r.status_code == 200
    record("GET /api/ status=200", ok, f"got {r.status_code}")
    if ok:
        try:
            j = r.json()
            record(
                "GET /api/ body has app=KlarPost status=ok",
                j.get("app") == "KlarPost" and j.get("status") == "ok",
                f"body={j}",
            )
        except Exception as e:
            record("GET /api/ body parse", False, str(e))


# ---------- TEST 2: RequestValidationError redaction ----------

def test_validation_redaction() -> None:
    print("\n=== TEST 2: /api/analyze validation redaction ===")
    device_id = f"qa-validation-{uuid.uuid4().hex[:8]}"

    # Two malformed payloads:
    # 1) device_id wrong type (int) — fails Pydantic
    # 2) pages where mime_type is non-string (number)
    payloads = [
        {
            "label": "device_id_as_int",
            "body": {"device_id": 123, "target_language": "en"},
        },
        {
            "label": "pages_mime_type_as_int",
            "body": {
                "device_id": device_id,
                "target_language": "en",
                "pages": [{"file_base64": "AAAA", "mime_type": 999}],
            },
        },
    ]

    err_log_size_before = (
        os.path.getsize("/var/log/supervisor/backend.err.log")
        if os.path.exists("/var/log/supervisor/backend.err.log")
        else 0
    )
    out_log_size_before = (
        os.path.getsize("/var/log/supervisor/backend.out.log")
        if os.path.exists("/var/log/supervisor/backend.out.log")
        else 0
    )

    for pl in payloads:
        try:
            r = requests.post(f"{API}/analyze", json=pl["body"], timeout=15)
        except Exception as e:
            record(f"POST malformed ({pl['label']}) network", False, str(e))
            continue

        ok_status = r.status_code == 422
        record(
            f"POST malformed ({pl['label']}) status=422",
            ok_status,
            f"got {r.status_code}",
        )
        if not ok_status:
            print(f"   body: {r.text[:300]}")
            continue
        try:
            body = r.json()
        except Exception as e:
            record(f"POST malformed ({pl['label']}) JSON parse", False, str(e))
            continue

        # Top-level must be exactly {"detail": [...]}
        record(
            f"POST malformed ({pl['label']}) top-level key 'detail' is list",
            isinstance(body, dict) and isinstance(body.get("detail"), list),
            f"keys={list(body.keys()) if isinstance(body, dict) else type(body)}",
        )

        # CRITICAL: NO `body` key anywhere in the response.
        body_hits = find_keys_recursive(body, "body")
        record(
            f"POST malformed ({pl['label']}) NO `body` key anywhere in response",
            len(body_hits) == 0,
            f"found at: {body_hits}" if body_hits else "clean",
        )

        # Each error item only has loc/type/msg (allow ctx/url subset to be ignored)
        REQ_KEYS = {"loc", "type", "msg"}
        ALLOWED_EXTRA = {"ctx", "url", "input"}
        # NOTE: the spec allows ctx/url. `input` echoes the user value and
        # we want to flag it if ANY error item carries it.
        all_items_ok = True
        any_input_field = False
        details_seen: list[str] = []
        for item in body["detail"]:
            details_seen.append(str(list(item.keys()) if isinstance(item, dict) else type(item).__name__))
            if not isinstance(item, dict):
                all_items_ok = False
                continue
            keys = set(item.keys())
            if not REQ_KEYS.issubset(keys):
                all_items_ok = False
            if "input" in keys:
                any_input_field = True
        record(
            f"POST malformed ({pl['label']}) each detail has loc/type/msg",
            all_items_ok,
            f"items keys={details_seen}",
        )
        record(
            f"POST malformed ({pl['label']}) NO `input` echo in details",
            not any_input_field,
            "clean" if not any_input_field else "input field present (echoes user value)",
        )

    # Inspect logs AFTER both requests.
    time.sleep(0.5)  # give logger flush a beat
    new_logs = ""
    for path, before in [
        ("/var/log/supervisor/backend.err.log", err_log_size_before),
        ("/var/log/supervisor/backend.out.log", out_log_size_before),
    ]:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            f.seek(before)
            new_logs += f.read().decode("utf-8", errors="replace") + "\n"

    # Count `request_validation_error` lines
    rve_lines = [
        ln for ln in new_logs.splitlines()
        if "request_validation_error" in ln and "path=/api/analyze" in ln
    ]
    record(
        "Backend log: request_validation_error lines for /api/analyze count==2",
        len(rve_lines) == 2,
        f"found {len(rve_lines)} lines: {rve_lines}",
    )

    # Confirm no payload echo: scan new logs for sensitive markers + base64
    leak_hits: list[str] = []
    for line in new_logs.splitlines():
        # No mention of `body=` (FastAPI default echoes body=<dict>)
        if re.search(r"\bbody\s*=", line):
            leak_hits.append(f"body=: {line.strip()[:160]}")
        # No mistral-key tokens (key starts with 'gA' or similar — we just
        # ensure no 30+ char alphanumeric sequence appears alongside the
        # log line for 'analyze' validation; conservatively flag any base64
        # blob >= 100 chars).
        if re.search(r"[A-Za-z0-9+/]{100,}", line):
            leak_hits.append(f"base64_blob: {line.strip()[:160]}")
    record(
        "Backend log: no `body=` echo or base64 blob in new lines",
        len(leak_hits) == 0,
        f"hits={leak_hits[:3]}" if leak_hits else "clean",
    )


# ---------- TEST 3: TTL index introspection ----------

def test_ttl_index() -> dict:
    print("\n=== TEST 3: MongoDB TTL index introspection ===")
    info: dict = {"found": False}
    try:
        c = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        db = c[DB_NAME]
        idx_list = list(db.analyses.list_indexes())
        print(f"   indexes on analyses: {[ix.get('name') for ix in idx_list]}")

        ttl_ix = next((ix for ix in idx_list if ix.get("name") == "ttl_created_at_dt"), None)
        record("TTL index ttl_created_at_dt exists", ttl_ix is not None, str([ix.get("name") for ix in idx_list]))
        if ttl_ix is None:
            return info
        info["ttl_index"] = ttl_ix
        info["found"] = True
        # key={'created_at_dt': 1}
        key = dict(ttl_ix.get("key", {}))
        record(
            "TTL index key == {'created_at_dt': 1}",
            key == {"created_at_dt": 1},
            f"key={key}",
        )
        # expireAfterSeconds = 90 * 86400 = 7776000
        eas = ttl_ix.get("expireAfterSeconds")
        record(
            "TTL index expireAfterSeconds == 7776000 (90 days)",
            eas == 7776000,
            f"got {eas}",
        )

        # Compound + unique indexes
        names = {ix.get("name") for ix in idx_list}
        record(
            "Compound index device_created_idx exists",
            "device_created_idx" in names,
            f"names={names}",
        )

        usage_idx = list(c[DB_NAME].usage_records.list_indexes())
        usage_names = {ix.get("name") for ix in usage_idx}
        record(
            "Unique index device_unique_idx on usage_records",
            "device_unique_idx" in usage_names,
            f"names={usage_names}",
        )
    except Exception as e:
        record("TTL index introspection", False, str(e))
    return info


# ---------- TEST 4: created_at_dt set on insert + stripped from responses ----------

def test_created_at_dt_lifecycle() -> tuple[str, str]:
    print("\n=== TEST 4: created_at_dt insert + strip ===")
    device_id = f"qa-ttl-{uuid.uuid4().hex[:8]}"
    payload = {
        "device_id": device_id,
        "target_language": "en",
        "idempotency_key": "ttl-test-1",
        "file_base64": b64(benign_letter_png()),
        "mime_type": "image/png",
    }
    t0 = time.time()
    try:
        r = requests.post(f"{API}/analyze", json=payload, timeout=120)
    except Exception as e:
        record("POST /api/analyze (TTL test) network", False, str(e))
        return device_id, ""
    elapsed = time.time() - t0
    ok = r.status_code == 200
    record(f"POST /api/analyze status=200 ({elapsed:.1f}s)", ok, f"got {r.status_code}: {r.text[:240]}")
    if not ok:
        return device_id, ""
    body = r.json()
    analysis_id = body.get("id") or ""
    record(
        "Analyze response has expected AnalysisResult shape",
        all(k in body for k in ("risk_level", "category", "scam_warning", "summary_translated", "target_language")),
        f"keys={list(body.keys())}",
    )

    # Direct pymongo: confirm created_at AND created_at_dt
    try:
        c = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        db = c[DB_NAME]
        # The /api/analyze response is the AnalysisResult itself, not the
        # AnalysisRecord. Look up the most recent doc for this device.
        doc = db.analyses.find_one({"device_id": device_id}, sort=[("created_at", -1)])
        if doc is None:
            record("MongoDB doc exists for device", False, "no doc found")
        else:
            print(f"   doc keys: {list(doc.keys())}")
            record(
                "Doc has created_at (str)",
                isinstance(doc.get("created_at"), str),
                f"created_at type={type(doc.get('created_at')).__name__}",
            )
            record(
                "Doc has created_at_dt (datetime/BSON Date)",
                isinstance(doc.get("created_at_dt"), datetime),
                f"created_at_dt type={type(doc.get('created_at_dt')).__name__}, value={doc.get('created_at_dt')}",
            )
            # Use the doc's `id` (UUID) for downstream lookups
            if not analysis_id:
                analysis_id = doc.get("id", "")
    except Exception as e:
        record("Direct pymongo doc lookup", False, str(e))

    if not analysis_id:
        # Fall back: list endpoint to grab id
        try:
            r2 = requests.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
            if r2.status_code == 200:
                rows = r2.json()
                if rows:
                    analysis_id = rows[0].get("id", "")
        except Exception:
            pass

    if not analysis_id:
        record("Acquire analysis_id for downstream tests", False, "no id")
        return device_id, ""

    # GET /api/analyses/{id}?device_id=...
    try:
        r3 = requests.get(f"{API}/analyses/{analysis_id}", params={"device_id": device_id}, timeout=30)
    except Exception as e:
        record("GET /api/analyses/{id} network", False, str(e))
        r3 = None
    if r3 is not None:
        record("GET /api/analyses/{id} status=200", r3.status_code == 200, f"got {r3.status_code}: {r3.text[:200]}")
        if r3.status_code == 200:
            j = r3.json()
            hits = find_keys_recursive(j, "created_at_dt")
            record(
                "GET /api/analyses/{id} response has NO created_at_dt anywhere",
                len(hits) == 0,
                f"found at: {hits}" if hits else "clean",
            )
            # also verify _id is stripped
            id_hits = find_keys_recursive(j, "_id")
            record(
                "GET /api/analyses/{id} response has NO _id (Mongo internal)",
                len(id_hits) == 0,
                f"found at: {id_hits}" if id_hits else "clean",
            )

    # GET /api/export?device_id=...
    try:
        r4 = requests.get(f"{API}/export", params={"device_id": device_id}, timeout=30)
    except Exception as e:
        record("GET /api/export network", False, str(e))
        r4 = None
    if r4 is not None:
        record("GET /api/export status=200", r4.status_code == 200, f"got {r4.status_code}")
        if r4.status_code == 200:
            j = r4.json()
            # Recursive scan for created_at_dt
            hits = find_keys_recursive(j, "created_at_dt")
            record(
                "GET /api/export response has NO created_at_dt anywhere",
                len(hits) == 0,
                f"found at: {hits}" if hits else "clean",
            )
            # Required key set
            expected = {"app", "device_id", "exported_at", "data_residency", "count", "analyses", "usage"}
            actual = set(j.keys())
            record(
                "GET /api/export key set == expected",
                actual == expected,
                f"actual={actual}, missing={expected - actual}, extra={actual - expected}",
            )
            record(
                "GET /api/export data_residency='EU (Mistral AI, Paris)'",
                j.get("data_residency") == "EU (Mistral AI, Paris)",
                f"got {j.get('data_residency')!r}",
            )
            record(
                "GET /api/export count >= 1 with our analysis",
                j.get("count", 0) >= 1 and len(j.get("analyses", [])) >= 1,
                f"count={j.get('count')}, analyses len={len(j.get('analyses', []))}",
            )

    # GET /api/analyses?device_id=...
    try:
        r5 = requests.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
    except Exception as e:
        record("GET /api/analyses network", False, str(e))
        r5 = None
    if r5 is not None:
        record("GET /api/analyses status=200", r5.status_code == 200, f"got {r5.status_code}")
        if r5.status_code == 200:
            j = r5.json()
            hits = find_keys_recursive(j, "created_at_dt")
            record(
                "GET /api/analyses response has NO created_at_dt anywhere",
                len(hits) == 0,
                f"found at: {hits}" if hits else "clean",
            )

    return device_id, analysis_id


# ---------- TEST 5: idempotency of startup handler ----------

def test_startup_idempotency() -> None:
    print("\n=== TEST 5: startup handler idempotency ===")
    err_size_before = os.path.getsize("/var/log/supervisor/backend.err.log") if os.path.exists("/var/log/supervisor/backend.err.log") else 0
    out_size_before = os.path.getsize("/var/log/supervisor/backend.out.log") if os.path.exists("/var/log/supervisor/backend.out.log") else 0

    print("   restarting backend...")
    try:
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True, capture_output=True, timeout=30)
    except Exception as e:
        record("supervisorctl restart backend", False, str(e))
        return
    record("supervisorctl restart backend", True, "")

    # Wait for ready
    deadline = time.time() + 60
    ready = False
    while time.time() < deadline:
        try:
            r = requests.get(f"{API}/", timeout=4)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
        time.sleep(1.0)
    record("Backend reachable after restart", ready, "")
    if not ready:
        return

    # Give startup handlers a moment to log
    time.sleep(1.5)

    # Read new log lines
    new_logs = ""
    for path, before in [
        ("/var/log/supervisor/backend.err.log", err_size_before),
        ("/var/log/supervisor/backend.out.log", out_size_before),
    ]:
        if not os.path.exists(path):
            continue
        with open(path, "rb") as f:
            f.seek(before)
            new_logs += f.read().decode("utf-8", errors="replace") + "\n"

    # Look for ttl_index_ready line
    ttl_lines = [ln for ln in new_logs.splitlines() if "ttl_index_ready" in ln]
    record(
        "Startup logs contain 'ttl_index_ready' after restart",
        len(ttl_lines) >= 1,
        f"lines: {ttl_lines}",
    )
    if ttl_lines:
        # Parse backfilled=N — should be 0 (we already backfilled previously)
        m = re.search(r"backfilled=(\d+)", ttl_lines[-1])
        if m:
            backfilled = int(m.group(1))
            record(
                "Restart 'backfilled' count is small (idempotent, ideally 0)",
                backfilled <= 1,
                f"backfilled={backfilled}",
            )

    # Confirm no traceback / no setup_failed in startup
    bad = [ln for ln in new_logs.splitlines() if "Traceback" in ln or "ttl_index_setup_failed" in ln]
    record(
        "Startup has no Traceback / no ttl_index_setup_failed",
        len(bad) == 0,
        f"bad={bad[:3]}" if bad else "clean",
    )


# ---------- TEST 6: no regressions ----------

def test_no_regressions(reuse_device: str, reuse_id: str) -> None:
    print("\n=== TEST 6: no regressions ===")

    # GET /api/
    try:
        r = requests.get(f"{API}/", timeout=15)
        record("GET /api/ → 200 with KlarPost/ok", r.status_code == 200 and r.json().get("app") == "KlarPost", f"{r.status_code}: {r.text[:100]}")
    except Exception as e:
        record("GET /api/ regression", False, str(e))

    # GET /api/languages
    try:
        r = requests.get(f"{API}/languages", timeout=15)
        ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) == 7
        record("GET /api/languages → 200 with 7 entries", ok, f"{r.status_code}: count={len(r.json()) if r.status_code==200 else '-'}")
    except Exception as e:
        record("GET /api/languages regression", False, str(e))

    # POST /api/analyses/{id}/chat — on-topic German question
    if reuse_id and reuse_device:
        try:
            r = requests.post(
                f"{API}/analyses/{reuse_id}/chat",
                json={"device_id": reuse_device, "message": "Was bedeutet dieser Brief in einfachen Worten?"},
                timeout=120,
            )
            ok = r.status_code == 200
            record("POST /chat (on-topic DE) → 200", ok, f"{r.status_code}: {r.text[:200]}")
            if ok:
                j = r.json()
                record(
                    "Chat: off_topic=False and content non-empty",
                    j.get("off_topic") is False and bool((j.get("content") or "").strip()),
                    f"off_topic={j.get('off_topic')}, content_len={len(j.get('content') or '')}",
                )
        except Exception as e:
            record("POST /chat regression", False, str(e))

    # GET /api/export?device_id=
    try:
        r = requests.get(f"{API}/export", params={"device_id": reuse_device}, timeout=30)
        ok = r.status_code == 200
        record("GET /api/export regression → 200", ok, f"{r.status_code}")
        if ok:
            j = r.json()
            expected = {"app", "device_id", "exported_at", "data_residency", "count", "analyses", "usage"}
            record(
                "GET /api/export key set EXACTLY matches expected",
                set(j.keys()) == expected,
                f"got={set(j.keys())}",
            )
    except Exception as e:
        record("GET /api/export regression", False, str(e))

    # DELETE /api/history/{device_id}
    try:
        r = requests.delete(f"{API}/history/{reuse_device}", timeout=30)
        ok = r.status_code == 200
        record(f"DELETE /api/history/{reuse_device} → 200", ok, f"{r.status_code}")
        if ok:
            j = r.json()
            record(
                "DELETE /api/history body has deleted_analyses + deleted_messages",
                "deleted_analyses" in j and "deleted_messages" in j,
                f"body={j}",
            )
            record(
                "DELETE /api/history deleted_analyses >= 1",
                j.get("deleted_analyses", 0) >= 1,
                f"deleted_analyses={j.get('deleted_analyses')}",
            )
    except Exception as e:
        record("DELETE /api/history regression", False, str(e))


# ---------- TEST 7: full privacy log audit ----------

def test_privacy_audit() -> None:
    print("\n=== TEST 7: full privacy log audit ===")
    logs = read_log_tail(approx_bytes=400_000)

    # Sensitive tokens
    bad: list[str] = []
    for tok in SECRET_TOKENS:
        if tok in logs:
            bad.append(tok)
    record(f"Privacy: ZERO sensitive tokens in last logs", len(bad) == 0, f"hits={bad}")

    # 4+ digit EUR amounts? Match like "4 850 EUR" / "248,50 EUR" / "1234 EUR"
    eur_hits = re.findall(r"\b\d{3,}[\d ,.]*\s*EUR\b", logs)
    eur_hits = [h for h in eur_hits if h.strip()]
    record("Privacy: NO 3+ digit EUR amounts in logs", len(eur_hits) == 0, f"hits={eur_hits[:5]}")

    # base64 blobs > 100 chars
    b64_hits = re.findall(r"[A-Za-z0-9+/]{100,}", logs)
    record("Privacy: NO base64 blobs >100 chars in logs", len(b64_hits) == 0, f"sample={b64_hits[0][:60] + '...' if b64_hits else ''}")

    # Mistral key fragment — read it from .env, then look for any 8-char prefix
    key = os.environ.get("MISTRAL_API_KEY", "")
    if not key:
        # try parsing /app/backend/.env
        try:
            with open("/app/backend/.env", "r") as f:
                for line in f:
                    if line.startswith("MISTRAL_API_KEY"):
                        key = line.split("=", 1)[1].strip().strip("'\"")
                        break
        except Exception:
            pass
    if key and len(key) >= 12:
        frag = key[:8]
        record(
            "Privacy: Mistral API key fragment NOT in logs",
            frag not in logs,
            f"checked fragment len=8 (redacted)",
        )

    # `body=` echo
    body_hits = re.findall(r"\bbody\s*=", logs)
    record("Privacy: NO 'body=' echoes in logs", len(body_hits) == 0, f"count={len(body_hits)}")


# ---------- cleanup ----------

def cleanup_device(device_id: str) -> None:
    if not device_id:
        return
    try:
        r = requests.delete(f"{API}/history/{device_id}", timeout=30)
        print(f"   cleanup DELETE /api/history/{device_id} → {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"   cleanup error: {e}")


def main() -> int:
    print(f"BACKEND: {API}")
    print(f"MONGO: {MONGO_URL} db={DB_NAME}")

    test_root()
    test_validation_redaction()
    info = test_ttl_index()
    device, analysis_id = test_created_at_dt_lifecycle()
    test_startup_idempotency()
    # After restart, re-confirm TTL index still good
    print("\n=== TEST 3b: TTL index after restart ===")
    test_ttl_index()
    test_no_regressions(device, analysis_id)
    test_privacy_audit()

    # cleanup
    print("\n=== CLEANUP ===")
    cleanup_device(device)

    # summary
    print("\n=== SUMMARY ===")
    passes = sum(1 for _, ok, _ in results if ok)
    fails = sum(1 for _, ok, _ in results if not ok)
    print(f"PASS: {passes}   FAIL: {fails}   TOTAL: {len(results)}")
    if fails:
        print("\nFailed assertions:")
        for label, ok, detail in results:
            if not ok:
                print(f"  ❌ {label}  — {detail}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
