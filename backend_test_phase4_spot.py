#!/usr/bin/env python3
"""Phase 4 services-extraction spot checks (review request additional checks).

A) POST /api/analyze synthetic letter target=en
   - extracted_entities has all 5 keys: email, subject, reference_number, contact_person, organization
   - detected_country_code is a string
   - reply_options has >= 4 entries
   - risk_level in {green,yellow,red}

B) POST /api/analyses/{id}/translate target=it
   - sender / risk_level / category byte-identical to source
   - reply_options ids preserved

C) POST /api/revenuecat/webhook NON_RENEWING_PURCHASE same event.id twice
   - second call: response includes "duplicate_event" OR credits unchanged

Privacy log audit: 9 PII tokens — must be ZERO matches.
"""
import os
import io
import sys
import json
import time
import uuid
import base64
import subprocess

import requests
from PIL import Image, ImageDraw, ImageFont


def _read_base_url() -> str:
    with open("/app/frontend/.env") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found")


BASE = _read_base_url()
API = f"{BASE}/api"
DEVICE_ID = f"qa-phase4-spot-{uuid.uuid4().hex[:8]}"
print(f"BASE={BASE}  DEVICE_ID={DEVICE_ID}")


LETTER_LINES = [
    "Finanzamt Berlin-Mitte",
    "Hauptstrasse 12",
    "10115 Berlin",
    "",
    "Sehr geehrter Herr Mustermann,",
    "",
    "Steuernummer 27/466/78910",
    "Aktenzeichen: FA-2026-DE-0001",
    "Betreff: Einkommensteuerbescheid 2025",
    "",
    "Bitte zahlen Sie 482,50 EUR bis spaetestens 30.07.2026",
    "auf das folgende Konto:",
    "IBAN: DE89 3704 0044 0532 0130 00",
    "Verwendungszweck: Einkommensteuer 2025",
    "",
    "Bei Rueckfragen wenden Sie sich bitte an Frau Schulz",
    "E-Mail: schulz@finanzamt-berlin.de",
    "Telefon: 030 1234567",
    "",
    "Mit freundlichen Gruessen",
    "Finanzamt Berlin-Mitte",
]


def _render_letter_png() -> str:
    img = Image.new("RGB", (800, 1100), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    y = 40
    for line in LETTER_LINES:
        draw.text((40, y), line, fill="black", font=font)
        y += 36
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


results = []


def _check(name, ok, detail):
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} — {detail}")
    results.append((name, ok, detail))


# --- A) analyze ---
print("\n--- A) POST /api/analyze target=en ---")
png_b64 = _render_letter_png()
t0 = time.time()
r = requests.post(
    f"{API}/analyze",
    json={
        "device_id": DEVICE_ID,
        "target_language": "en",
        "pages": [{"file_base64": png_b64, "mime_type": "image/png"}],
    },
    timeout=120,
)
dt = int((time.time() - t0) * 1000)
_check("A_http_200", r.status_code == 200, f"status={r.status_code} dt={dt}ms")
if r.status_code != 200:
    print("BODY:", r.text[:400])
    sys.exit(1)

env = r.json()
result = env.get("result") or {}
ANALYSIS_ID = env.get("id")
print(f"  ANALYSIS_ID={ANALYSIS_ID}")

ent = result.get("extracted_entities") or {}
expected_keys = {"email", "subject", "reference_number", "contact_person", "organization"}
_check(
    "A_extracted_entities_keys",
    set(ent.keys()) == expected_keys,
    f"keys={sorted(ent.keys())}",
)

dcc = result.get("detected_country_code")
_check("A_detected_country_code_is_str", isinstance(dcc, str), f"detected_country_code={dcc!r}")

ropts = result.get("reply_options") or []
_check("A_reply_options_ge_4", isinstance(ropts, list) and len(ropts) >= 4, f"n_reply_options={len(ropts)}")

rl = result.get("risk_level")
_check("A_risk_level_enum", rl in {"green", "yellow", "red"}, f"risk_level={rl!r}")

# capture invariants
SRC_SENDER = result.get("sender")
SRC_RISK = rl
SRC_CATEGORY = result.get("category")
SRC_REPLY_OPT_IDS = [o.get("id") for o in ropts]
print(f"  src sender={SRC_SENDER!r} risk={SRC_RISK!r} category={SRC_CATEGORY!r}")
print(f"  reply_option ids={SRC_REPLY_OPT_IDS}")


# --- B) translate target=it ---
print("\n--- B) POST /api/analyses/{id}/translate target=it ---")
t0 = time.time()
r = requests.post(
    f"{API}/analyses/{ANALYSIS_ID}/translate",
    json={"device_id": DEVICE_ID, "target_language": "it"},
    timeout=120,
)
dt = int((time.time() - t0) * 1000)
_check("B_http_200", r.status_code == 200, f"status={r.status_code} dt={dt}ms")
if r.status_code != 200:
    print("BODY:", r.text[:500])
else:
    tenv = r.json()
    tres = tenv.get("result") or {}
    _check("B_sender_byte_identical", tres.get("sender") == SRC_SENDER, f"src={SRC_SENDER!r} dst={tres.get('sender')!r}")
    _check("B_risk_level_byte_identical", tres.get("risk_level") == SRC_RISK, f"src={SRC_RISK!r} dst={tres.get('risk_level')!r}")
    _check("B_category_byte_identical", tres.get("category") == SRC_CATEGORY, f"src={SRC_CATEGORY!r} dst={tres.get('category')!r}")
    dst_ropts = tres.get("reply_options") or []
    dst_ids = [o.get("id") for o in dst_ropts]
    _check(
        "B_reply_option_ids_preserved",
        dst_ids == SRC_REPLY_OPT_IDS,
        f"src_ids={SRC_REPLY_OPT_IDS} dst_ids={dst_ids}",
    )


# --- C) revenuecat webhook idempotency ---
print("\n--- C) POST /api/revenuecat/webhook NON_RENEWING_PURCHASE x2 (same event.id) ---")
RC_DEVICE = f"qa-phase4-rc-{uuid.uuid4().hex[:8]}"
EVT_ID = f"evt-{uuid.uuid4().hex}"
now_ms = int(time.time() * 1000)

# Need RC webhook auth — check env
import subprocess as _sp
auth_proc = _sp.run(
    ["bash", "-lc", "grep -E '^RC_WEBHOOK_AUTH|^REVENUECAT_WEBHOOK_AUTH' /app/backend/.env || true"],
    capture_output=True, text=True
)
print(f"  RC auth env hint: {auth_proc.stdout.strip()!r}")

headers = {}
# try common header names
rc_auth_val = None
for ln in auth_proc.stdout.splitlines():
    if "=" in ln:
        k, v = ln.split("=", 1)
        rc_auth_val = v.strip().strip('"').strip("'")
        break
if rc_auth_val:
    headers["Authorization"] = rc_auth_val

payload = {
    "event": {
        "id": EVT_ID,
        "type": "NON_RENEWING_PURCHASE",
        "app_user_id": RC_DEVICE,
        "product_id": "easli_single_letter",
        "purchased_at_ms": now_ms,
        "expiration_at_ms": None,
    }
}

r1 = requests.post(f"{API}/revenuecat/webhook", json=payload, headers=headers, timeout=30)
print(f"  call1 status={r1.status_code} body={r1.text[:200]}")
r2 = requests.post(f"{API}/revenuecat/webhook", json=payload, headers=headers, timeout=30)
print(f"  call2 status={r2.status_code} body={r2.text[:200]}")

# Examine: call2 should be "duplicate_event" OR credits unchanged
call1_body = {}
call2_body = {}
try:
    call1_body = r1.json()
except Exception:
    pass
try:
    call2_body = r2.json()
except Exception:
    pass

# fetch usage to inspect credits
usage_r = requests.get(f"{API}/usage/{RC_DEVICE}", timeout=15)
print(f"  usage status={usage_r.status_code} body={usage_r.text[:300]}")
credits_after = None
if usage_r.status_code == 200:
    u = usage_r.json()
    credits_after = u.get("single_letter_credits", u.get("paid_letter_credits"))

call2_str = json.dumps(call2_body).lower()
is_duplicate = "duplicate" in call2_str or "ignored" in call2_str
# alternative: credits unchanged at 1 means second call didn't add
credits_unchanged = credits_after == 1
_check(
    "C_idempotency_dedup",
    r1.status_code == 200 and r2.status_code == 200 and (is_duplicate or credits_unchanged),
    f"call1={r1.status_code} call2={r2.status_code} call2_body={call2_body} credits_after={credits_after}",
)


# --- Privacy log audit ---
print("\n--- Privacy log audit ---")
PII_TOKENS = [
    "Bundespolizei",
    "Sehr geehrte",
    "AOK",
    "Mustermann",
    "iTunes",
    "Nigeria",
    "NG12",
    "DE89 3704",
    "schulz@finanzamt-berlin.de",
]
log_files = ["/var/log/supervisor/backend.out.log", "/var/log/supervisor/backend.err.log"]
hits = {}
for tok in PII_TOKENS:
    cnt = 0
    for lf in log_files:
        if os.path.exists(lf):
            try:
                with open(lf, "rb") as f:
                    raw = f.read()
                cnt += raw.count(tok.encode("utf-8"))
            except Exception:
                pass
    hits[tok] = cnt
print(f"  PII hits: {hits}")
all_clean = all(v == 0 for v in hits.values())
_check("Z_privacy_log_audit_clean", all_clean, f"hits={hits}")


# Cleanup
try:
    requests.delete(f"{API}/history/{DEVICE_ID}", timeout=10)
except Exception:
    pass
try:
    requests.delete(f"{API}/history/{RC_DEVICE}", timeout=10)
except Exception:
    pass


# Summary
print("\n=== SUMMARY ===")
total = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed
print(f"Total: {total} | PASS: {passed} | FAIL: {failed}")
for name, ok, detail in results:
    flag = "PASS" if ok else "FAIL"
    print(f"  {flag} {name}: {detail}")

sys.exit(0 if failed == 0 else 1)
