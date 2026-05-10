#!/usr/bin/env python3
"""Phase B refactor regression test for easli backend.

Targets the public preview backend URL read from /app/frontend/.env
(EXPO_PUBLIC_BACKEND_URL). All API calls hit ${BASE}/api/...

Runs the 13-step plan from the review request.
"""
import os
import re
import sys
import time
import json
import uuid
import base64
import io
import subprocess
from typing import Tuple

import requests
from PIL import Image, ImageDraw, ImageFont


# ---- Resolve BASE URL from /app/frontend/.env -------------------------------
def _read_base_url() -> str:
    env_path = "/app/frontend/.env"
    with open(env_path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln.startswith("EXPO_PUBLIC_BACKEND_URL="):
                v = ln.split("=", 1)[1].strip().strip('"').strip("'")
                return v.rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found in /app/frontend/.env")


BASE = _read_base_url()
API = f"{BASE}/api"
DEVICE_ID = "qa-phaseB-001"
print(f"BASE={BASE}")
print(f"DEVICE_ID={DEVICE_ID}")


# ---- Synthetic German letter rendered to PNG --------------------------------
LETTER_LINES = [
    "Finanzamt Berlin-Mitte",
    "Hauptstrasse 12",
    "10115 Berlin",
    "",
    "Sehr geehrter Herr Mustermann,",
    "",
    "Steuernummer 27/466/78910",
    "Aktenzeichen: FA-2026-DE-0001",
    "",
    "Bitte zahlen Sie 482,50 EUR bis spaetestens 30.07.2026",
    "auf das folgende Konto:",
    "IBAN: DE89 3704 0044 0532 0130 00",
    "Verwendungszweck: Einkommensteuer 2025",
    "",
    "Bei Rueckfragen wenden Sie sich bitte an Frau Schulz",
    "Telefon: 030 1234567",
    "",
    "Mit freundlichen Gruessen",
    "Finanzamt Berlin-Mitte",
]


def _render_letter_png() -> str:
    img = Image.new("RGB", (800, 1000), "white")
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


# ---- Helpers ----------------------------------------------------------------
results = []
DE_ID = None
ORIG_REPLY_DRAFT_EN = None


def record(step, status, latency_ms=None, note=""):
    line = f"[{status}] step{step}"
    if latency_ms is not None:
        line += f" ({latency_ms:.0f}ms)"
    if note:
        line += f" — {note}"
    print(line)
    results.append((step, status, latency_ms, note))


def post(path, **kw):
    t0 = time.time()
    r = requests.post(f"{API}{path}", timeout=120, **kw)
    return r, (time.time() - t0) * 1000.0


def get(path, **kw):
    t0 = time.time()
    r = requests.get(f"{API}{path}", timeout=60, **kw)
    return r, (time.time() - t0) * 1000.0


def delete_(path, **kw):
    t0 = time.time()
    r = requests.delete(f"{API}{path}", timeout=60, **kw)
    return r, (time.time() - t0) * 1000.0


# ---- Step 1: Import smoke ---------------------------------------------------
def step1_import():
    proc = subprocess.run(
        ["python3", "-c",
         "import server, prompts, models, languages, admin; "
         "print('OK', len(languages.EXPLANATION_LANGUAGES), 'langs')"],
        cwd="/app/backend",
        capture_output=True, text=True, timeout=30,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode == 0 and "OK 27 langs" in out:
        record(1, "PASS", note=f"stdout='{out}'")
        return True
    record(1, "FAIL", note=f"rc={proc.returncode} stdout='{out}' stderr='{err}'")
    return False


# ---- Step 2: GET /api/ ------------------------------------------------------
def step2_root():
    r, ms = get("/")
    if r.status_code != 200:
        record(2, "FAIL", ms, f"status={r.status_code} body={r.text[:200]}")
        return False
    body = r.json()
    if body.get("app") == "easli" and body.get("status") == "ok":
        record(2, "PASS", ms, f"body={body}")
        return True
    record(2, "FAIL", ms, f"body={body}")
    return False


# ---- Step 3: GET /api/languages ---------------------------------------------
def step3_languages():
    r, ms = get("/languages")
    if r.status_code != 200:
        record(3, "FAIL", ms, f"status={r.status_code}")
        return False
    body = r.json()
    if not isinstance(body, list) or len(body) < 27:
        record(3, "FAIL", ms, f"len={len(body) if isinstance(body, list) else 'N/A'}")
        return False
    codes = {item.get("code"): item.get("label") for item in body if isinstance(item, dict)}
    required = ["de_simple", "en", "fr", "it", "pl", "ar", "hi", "zh-Hans", "vi", "tr", "ru"]
    missing = [c for c in required if c not in codes]
    bad_shape = [item for item in body if not (isinstance(item, dict) and "code" in item and "label" in item)]
    if missing or bad_shape:
        record(3, "FAIL", ms, f"missing={missing} bad_shape_count={len(bad_shape)}")
        return False
    record(3, "PASS", ms,
           f"len={len(body)} all 11 required codes present")
    return True


# ---- Step 4: POST /api/analyze (target_language=en) -------------------------
def step4_analyze_en(b64):
    global DE_ID, ORIG_REPLY_DRAFT_EN
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "en",
        "file_base64": b64,
        "mime_type": "image/png",
        "idempotency_key": str(uuid.uuid4()),
    }
    r, ms = post("/analyze", json=payload)
    if r.status_code != 200:
        record(4, "FAIL", ms, f"status={r.status_code} body={r.text[:400]}")
        return False
    if ms > 60000:
        record(4, "FAIL", ms, f"latency >60s")
        return False
    env = r.json()
    DE_ID = env.get("id")
    res = env.get("result") or {}
    src = res.get("source_language_code")
    country = res.get("detected_country_code", "")
    summary = res.get("summary_translated") or ""
    reply = res.get("reply_draft") or ""
    cat = res.get("category")
    scam = res.get("scam_warning")
    tlang = res.get("target_language")

    fails = []
    if src != "de":
        fails.append(f"source_language_code={src!r} (expected 'de')")
    if country not in ("DE", ""):
        fails.append(f"detected_country_code={country!r}")
    if len(summary) < 40:
        fails.append(f"summary_translated len={len(summary)} <40")
    if not reply:
        fails.append("reply_draft empty")
    if not cat:
        fails.append("category missing")
    if scam is not False:
        fails.append(f"scam_warning={scam!r} (expected False)")
    if tlang != "English":
        fails.append(f"target_language={tlang!r} (expected 'English')")

    if fails:
        record(4, "FAIL", ms, f"DE_ID={DE_ID} issues={fails}")
        return False
    ORIG_REPLY_DRAFT_EN = reply
    record(4, "PASS", ms,
           f"DE_ID={DE_ID} src=de country={country!r} summary_len={len(summary)} "
           f"reply_len={len(reply)} category={cat!r} scam={scam} tlang={tlang!r}")
    return True


# ---- Step 5: POST /api/analyze (target_language=pl) -------------------------
def step5_analyze_pl(b64):
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "pl",
        "file_base64": b64,
        "mime_type": "image/png",
        "idempotency_key": str(uuid.uuid4()),
    }
    r, ms = post("/analyze", json=payload)
    if r.status_code != 200:
        record(5, "FAIL", ms, f"status={r.status_code} body={r.text[:400]}")
        return False
    env = r.json()
    res = env.get("result") or {}
    tlang = res.get("target_language")
    summary = res.get("summary_translated") or ""
    reply = res.get("reply_draft") or ""
    src = res.get("source_language_code")

    fails = []
    if tlang != "Polish (Polski)":
        fails.append(f"target_language={tlang!r}")
    polish_diacritics = re.compile(r"[ąćęłńóśźż]", re.IGNORECASE)
    if not polish_diacritics.search(summary):
        fails.append(f"no Polish diacritics in summary; sample='{summary[:80]}'")
    has_umlaut = bool(re.search(r"[äöüÄÖÜß]", reply))
    has_german_polite = (
        ("sehr geehrte" in reply.lower())
        or ("freundliche" in reply.lower())
        or ("freundlichen" in reply.lower())
        or ("mit freundlichen" in reply.lower())
    )
    if not (has_umlaut or has_german_polite):
        fails.append(f"reply_draft not in German; sample='{reply[:120]}'")
    if src != "de":
        fails.append(f"source_language_code={src!r}")

    if fails:
        record(5, "FAIL", ms, f"issues={fails}")
        return False
    record(5, "PASS", ms,
           f"tlang={tlang!r} summary_len={len(summary)} polish_diacritic=YES "
           f"reply_german=YES src={src!r}")
    return True


# ---- Step 6: POST /api/analyses/{DE_ID}/translate (it) ----------------------
def step6_translate_it():
    if not DE_ID:
        record(6, "FAIL", note="no DE_ID from step 4")
        return False
    payload = {"device_id": DEVICE_ID, "target_language": "it"}
    r, ms = post(f"/analyses/{DE_ID}/translate", json=payload)
    if r.status_code != 200:
        record(6, "FAIL", ms, f"status={r.status_code} body={r.text[:400]}")
        return False
    env = r.json()
    res = env.get("result") or {}
    tlang = res.get("target_language")
    summary = res.get("summary_translated") or ""
    reply = res.get("reply_draft") or ""

    fails = []
    if tlang != "Italian (Italiano)":
        fails.append(f"target_language={tlang!r}")
    italian_markers = ["deve", "del", "questa", "lettera", "della", "pagamento", "entro"]
    summary_lower = summary.lower()
    if not any(marker in summary_lower for marker in italian_markers):
        fails.append(f"no Italian markers in summary; sample='{summary[:100]}'")
    # Phase-3 invariant: reply_draft byte-identical to step 4
    if reply != ORIG_REPLY_DRAFT_EN:
        fails.append(
            f"reply_draft NOT byte-identical: step4_len={len(ORIG_REPLY_DRAFT_EN or '')} "
            f"step6_len={len(reply)}"
        )

    if fails:
        record(6, "FAIL", ms, f"issues={fails}")
        return False
    record(6, "PASS", ms,
           f"tlang={tlang!r} summary_len={len(summary)} italian_marker=YES "
           f"reply_byte_identical=YES (len={len(reply)})")
    return True


# ---- Step 7: POST /api/analyses/{DE_ID}/chat --------------------------------
def step7_chat():
    payload = {
        "device_id": DEVICE_ID,
        "message": "What is the deadline mentioned in this letter?",
    }
    r, ms = post(f"/analyses/{DE_ID}/chat", json=payload)
    if r.status_code != 200:
        record(7, "FAIL", ms, f"status={r.status_code} body={r.text[:400]}")
        return False
    if ms > 30000:
        record(7, "FAIL", ms, "latency >30s")
        return False
    body = r.json()
    content = body.get("content") or ""
    role = body.get("role")
    fails = []
    if len(content) < 30:
        fails.append(f"content len={len(content)}")
    if role != "assistant":
        fails.append(f"role={role!r}")
    if fails:
        record(7, "FAIL", ms, f"issues={fails} content[:80]='{content[:80]}'")
        return False
    record(7, "PASS", ms, f"role={role!r} content_len={len(content)} sample='{content[:80]}'")
    return True


# ---- Step 8: POST /api/analyses/{DE_ID}/generate-reply (no lang) -----------
def step8_generate_reply_default():
    payload = {"device_id": DEVICE_ID, "intent": "inquiry"}
    r, ms = post(f"/analyses/{DE_ID}/generate-reply", json=payload)
    if r.status_code != 200:
        record(8, "FAIL", ms, f"status={r.status_code} body={r.text[:400]}")
        return False
    body = r.json()
    reply_text = body.get("reply_text") or ""
    reply_lang = body.get("reply_language_code")
    reply_expl = body.get("reply_explanation") or ""
    fails = []
    if not reply_text:
        fails.append("reply_text empty")
    if reply_lang != "de":
        fails.append(f"reply_language_code={reply_lang!r} (expected 'de')")
    if not reply_expl:
        fails.append("reply_explanation empty")
    if fails:
        record(8, "FAIL", ms, f"issues={fails}")
        return False
    record(8, "PASS", ms,
           f"reply_len={len(reply_text)} reply_lang={reply_lang!r} expl_len={len(reply_expl)}")
    return True


# ---- Step 9: POST /api/analyses/{DE_ID}/generate-reply (en) -----------------
def step9_generate_reply_en():
    payload = {"device_id": DEVICE_ID, "intent": "extension", "reply_language_code": "en"}
    r, ms = post(f"/analyses/{DE_ID}/generate-reply", json=payload)
    if r.status_code != 200:
        record(9, "FAIL", ms, f"status={r.status_code} body={r.text[:400]}")
        return False
    body = r.json()
    reply_text = body.get("reply_text") or ""
    reply_lang = body.get("reply_language_code")
    fails = []
    has_english_marker = (
        re.search(r"\bDear\b", reply_text)
        or re.search(r"\bSincerely\b", reply_text, re.IGNORECASE)
        or re.search(r"\bThank you\b", reply_text, re.IGNORECASE)
        or re.search(r"\bYours\b", reply_text)
        or re.search(r"\bRegards\b", reply_text, re.IGNORECASE)
        or re.search(r"\bBest\b", reply_text)
    )
    if not has_english_marker:
        fails.append(f"no English greeting/closer; sample='{reply_text[:120]}'")
    if reply_lang != "en":
        fails.append(f"reply_language_code={reply_lang!r} (expected 'en')")
    if fails:
        record(9, "FAIL", ms, f"issues={fails}")
        return False
    record(9, "PASS", ms, f"reply_len={len(reply_text)} reply_lang={reply_lang!r}")
    return True


# ---- Step 10: GET /api/analyses ---------------------------------------------
def step10_list():
    r, ms = get("/analyses", params={"device_id": DEVICE_ID})
    if r.status_code != 200:
        record(10, "FAIL", ms, f"status={r.status_code} body={r.text[:200]}")
        return False
    body = r.json()
    if not isinstance(body, list) or len(body) < 1:
        record(10, "FAIL", ms, f"len={len(body) if isinstance(body, list) else 'N/A'}")
        return False
    ids = [it.get("id") for it in body]
    if DE_ID not in ids:
        record(10, "FAIL", ms, f"DE_ID={DE_ID} NOT in list ids={ids}")
        return False
    record(10, "PASS", ms, f"count={len(body)} DE_ID present")
    return True


# ---- Step 11: NEGATIVE — invalid target_language ----------------------------
def step11_invalid_lang(b64):
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "xx-bogus",
        "file_base64": b64,
        "mime_type": "image/png",
        "idempotency_key": str(uuid.uuid4()),
    }
    r, ms = post("/analyze", json=payload)
    if r.status_code not in (400, 422):
        record(11, "FAIL", ms, f"status={r.status_code} (expected 4xx)")
        return False
    body_text = r.text.lower()
    if "unsupported" in body_text and "target" in body_text:
        record(11, "PASS", ms, f"status={r.status_code} body={r.text[:120]}")
        return True
    record(11, "FAIL", ms, f"status={r.status_code} body={r.text[:200]} (expected 'Unsupported target language')")
    return False


# ---- Step 12: NEGATIVE — no pages and no file_base64 ------------------------
def step12_no_content():
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "en",
        "idempotency_key": str(uuid.uuid4()),
    }
    r, ms = post("/analyze", json=payload)
    if r.status_code not in (400, 422):
        record(12, "FAIL", ms, f"status={r.status_code}")
        return False
    body_text = r.text.lower()
    if "no file content" in body_text or "file content" in body_text:
        record(12, "PASS", ms, f"status={r.status_code} body={r.text[:160]}")
        return True
    record(12, "FAIL", ms, f"status={r.status_code} body={r.text[:200]} (expected detail mentioning missing file content)")
    return False


# ---- Step 13: CLEANUP -------------------------------------------------------
def step13_cleanup():
    r, ms = delete_(f"/history/{DEVICE_ID}")
    if r.status_code != 200:
        record(13, "FAIL", ms, f"status={r.status_code} body={r.text[:200]}")
        return False
    body = r.json()
    da = body.get("deleted_analyses", 0)
    dm = body.get("deleted_messages", 0)
    if da < 1:
        record(13, "FAIL", ms, f"deleted_analyses={da} (<1) body={body}")
        return False
    record(13, "PASS", ms, f"deleted_analyses={da} deleted_messages={dm}")
    return True


# ---- Privacy-log audit ------------------------------------------------------
def audit_logs(start_ts):
    print("\n--- LOG AUDIT ---")
    log_paths = [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ]
    pii_tokens = ["482,50", "27/466", "Berlin-Mitte"]
    pii_hits = {tok: 0 for tok in pii_tokens}
    import_errors = 0
    mistral_calls = 0
    for path in log_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            continue
        for tok in pii_tokens:
            pii_hits[tok] += content.count(tok)
        import_errors += content.count("ImportError")
        # count mistral chat completions calls (loose)
        mistral_calls += len(re.findall(r"https://api\.mistral\.ai/v1", content))
    print(f"PII token hits: {pii_hits}")
    print(f"ImportError occurrences: {import_errors}")
    print(f"Total api.mistral.ai/v1 lines in logs (cumulative): {mistral_calls}")
    return pii_hits, import_errors, mistral_calls


# ---- Main -------------------------------------------------------------------
def main():
    print("\n=== Phase B refactor regression — starting ===\n")
    start_ts = time.time()

    # Render the synthetic letter once
    b64 = _render_letter_png()
    print(f"Rendered letter PNG, base64 len={len(b64)}")

    # Cleanup any stale data from previous runs first
    try:
        delete_(f"/history/{DEVICE_ID}")
    except Exception:
        pass

    step1_import()
    step2_root()
    step3_languages()
    step4_analyze_en(b64)
    step5_analyze_pl(b64)
    step6_translate_it()
    step7_chat()
    step8_generate_reply_default()
    step9_generate_reply_en()
    step10_list()
    step11_invalid_lang(b64)
    step12_no_content()
    step13_cleanup()

    pii_hits, import_errors, mistral_calls = audit_logs(start_ts)

    print("\n=== SUMMARY ===")
    n_pass = sum(1 for _, s, *_ in results if s == "PASS")
    n_fail = sum(1 for _, s, *_ in results if s == "FAIL")
    print(f"Total: {len(results)} | PASS: {n_pass} | FAIL: {n_fail}")
    for step, status, ms, note in results:
        ms_str = f"{ms:.0f}ms" if ms is not None else "—"
        print(f"  step{step:>2}: {status:<4} {ms_str:>8}  {note[:140]}")

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
