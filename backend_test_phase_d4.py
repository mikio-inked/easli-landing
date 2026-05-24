#!/usr/bin/env python3
"""Phase D4 — Final Release-Readiness Backend Smoke Test for easli 2.0.

Sections:
  (A) Standard 13-step regression (delegated to /app/backend_test.py)
  (B) FR-country spot check on synthesized DGFiP letter
  (C) Report-flow smoke (POST /api/report + direct pymongo verification)
  (D) Cleanup + privacy log audit
"""
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont

# ---- Resolve BASE URL from /app/frontend/.env -------------------------------
def _read_env(path, key):
    with open(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln.startswith(f"{key}="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"{key} not found in {path}")

BASE = _read_env("/app/frontend/.env", "EXPO_PUBLIC_BACKEND_URL").rstrip("/")
API = f"{BASE}/api"
MONGO_URL = _read_env("/app/backend/.env", "MONGO_URL").strip('"')
DB_NAME = _read_env("/app/backend/.env", "DB_NAME").strip('"')

DEVICE_PHASE_B = "qa-phaseB-001"
DEVICE_FR_SPOT = "qa-d4-fr-spot-001"

print(f"BASE={BASE}")
print(f"MONGO_URL={MONGO_URL}")
print(f"DB_NAME={DB_NAME}")
print(f"DEVICE_PHASE_B={DEVICE_PHASE_B}")
print(f"DEVICE_FR_SPOT={DEVICE_FR_SPOT}")

# capture window for log audit
TEST_WINDOW_START = time.time()
results: list = []


def record(section, name, status, latency_ms=None, note=""):
    line = f"[{status}] {section}.{name}"
    if latency_ms is not None:
        line += f" ({latency_ms:.0f}ms)"
    if note:
        line += f" — {note}"
    print(line)
    results.append((section, name, status, latency_ms, note))


def post(path, **kw):
    t0 = time.time()
    r = requests.post(f"{API}{path}", timeout=180, **kw)
    return r, (time.time() - t0) * 1000.0


def get(path, **kw):
    t0 = time.time()
    r = requests.get(f"{API}{path}", timeout=60, **kw)
    return r, (time.time() - t0) * 1000.0


def delete_(path, **kw):
    t0 = time.time()
    r = requests.delete(f"{API}{path}", timeout=60, **kw)
    return r, (time.time() - t0) * 1000.0


# ============================================================================
# (B) FR DGFiP letter — synth
# ============================================================================
FR_LETTER_LINES = [
    "Direction Générale des Finances Publiques",
    "Service des Impôts des Particuliers",
    "12, rue de Bercy",
    "75012 Paris",
    "",
    "Madame Martin,",
    "",
    "Objet : Avis d'imposition 2026 — Référence FR-2026-0042",
    "",
    "Conformément à votre avis d'imposition, vous êtes redevable",
    "de la somme de 482,50 EUR au titre de l'impôt sur le revenu.",
    "",
    "Le règlement doit être effectué avant le 30/07/2026 à l'ordre",
    "du Trésor Public, par virement à l'IBAN suivant :",
    "FR76 3000 4002 7100 0001 2345 678",
    "",
    "Pour toute question, veuillez contacter Madame Martin au",
    "01 23 45 67 89 — service.impots@dgfip.finances.gouv.fr",
    "",
    "Veuillez agréer, Madame, l'expression de nos salutations distinguées.",
    "",
    "Direction Générale des Finances Publiques",
]


def _render_fr_png() -> str:
    img = Image.new("RGB", (800, 1100), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22
        )
    except Exception:
        font = ImageFont.load_default()
    y = 40
    for line in FR_LETTER_LINES:
        draw.text((40, y), line, fill="black", font=font)
        y += 36
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ============================================================================
# (A) Standard 13-step regression
# ============================================================================
def section_a_regression():
    print("\n=== SECTION A — Standard 13-step regression ===\n")
    # 1) reset usage for qa-phaseB-001
    r, ms = post(f"/dev/usage/reset?device_id={DEVICE_PHASE_B}")
    if r.status_code != 200:
        record("A", "usage_reset_phaseB", "FAIL", ms,
               f"status={r.status_code} body={r.text[:200]}")
    else:
        record("A", "usage_reset_phaseB", "PASS", ms, "ok")

    # 2) Run /app/backend_test.py
    t0 = time.time()
    proc = subprocess.run(
        ["python3", "/app/backend_test.py"],
        capture_output=True, text=True, timeout=900,
    )
    elapsed = (time.time() - t0) * 1000.0
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    print(stdout)
    if stderr.strip():
        print("STDERR:", stderr[-2000:])

    # Parse step-by-step PASS/FAIL counts from stdout summary
    pass_count = stdout.count(" PASS ")
    fail_count = stdout.count(" FAIL ")
    # also accept summary "PASS: N | FAIL: M"
    m = re.search(r"PASS:\s*(\d+)\s*\|\s*FAIL:\s*(\d+)", stdout)
    if m:
        pass_count = int(m.group(1))
        fail_count = int(m.group(2))

    record("A", "backend_test_py", "PASS" if (proc.returncode == 0 and fail_count == 0) else "FAIL",
           elapsed,
           f"rc={proc.returncode} pass={pass_count} fail={fail_count}")

    # Extract individual step results
    step_re = re.compile(r"step\s*(\d+):\s+(PASS|FAIL)\s+([\d.]+ms|—)\s+(.{0,140})")
    for sm in step_re.finditer(stdout):
        step_no = sm.group(1)
        status = sm.group(2)
        latms = sm.group(3)
        note = sm.group(4).strip()
        record("A", f"step{step_no}", status, None, f"{latms} | {note[:100]}")

    return proc.returncode == 0 and fail_count == 0


# ============================================================================
# (B) FR-country spot check
# ============================================================================
FR_ANALYSIS_ID = None
FR_REPLY_TEXT = None


def section_b_fr_spot():
    global FR_ANALYSIS_ID, FR_REPLY_TEXT
    print("\n=== SECTION B — FR-country spot check ===\n")

    # B1 - usage reset
    r, ms = post(f"/dev/usage/reset?device_id={DEVICE_FR_SPOT}")
    if r.status_code != 200:
        record("B", "usage_reset_fr", "FAIL", ms,
               f"status={r.status_code} body={r.text[:200]}")
        return False
    record("B", "usage_reset_fr", "PASS", ms, "ok")

    # B2 - synth + analyze
    b64 = _render_fr_png()
    print(f"FR letter PNG base64 len={len(b64)}")
    payload = {
        "device_id": DEVICE_FR_SPOT,
        "target_language": "en",
        "file_base64": b64,
        "mime_type": "image/png",
        "idempotency_key": str(uuid.uuid4()),
    }
    r, ms = post("/analyze", json=payload)
    if r.status_code != 200:
        record("B", "analyze_fr", "FAIL", ms,
               f"status={r.status_code} body={r.text[:400]}")
        return False
    env = r.json()
    FR_ANALYSIS_ID = env.get("id")
    res = env.get("result") or {}
    country = res.get("detected_country_code")
    confidence = res.get("jurisdiction_confidence")
    category = res.get("category")
    src = res.get("source_language_code")
    fails = []
    if country != "FR":
        fails.append(f"detected_country_code={country!r} (expected 'FR')")
    if confidence not in ("high", "medium"):
        fails.append(f"jurisdiction_confidence={confidence!r} (expected 'high' or 'medium')")
    if category != "tax":
        fails.append(f"category={category!r} (expected 'tax')")
    if fails:
        record("B", "analyze_fr", "FAIL", ms,
               f"id={FR_ANALYSIS_ID} src={src!r} issues={fails}")
        return False
    record("B", "analyze_fr", "PASS", ms,
           f"id={FR_ANALYSIS_ID} country={country!r} confidence={confidence!r} "
           f"category={category!r} src={src!r}")

    # B3 - generate-reply FR
    payload = {
        "device_id": DEVICE_FR_SPOT,
        "intent": "inquiry",
        "reply_language_code": "fr",
    }
    r, ms = post(f"/analyses/{FR_ANALYSIS_ID}/generate-reply", json=payload)
    if r.status_code != 200:
        record("B", "generate_reply_fr", "FAIL", ms,
               f"status={r.status_code} body={r.text[:400]}")
        return False
    body = r.json()
    reply_text = body.get("reply_text") or ""
    reply_lang = body.get("reply_language_code")
    FR_REPLY_TEXT = reply_text

    # Validate salutation start (Madame / Monsieur / Madame, Monsieur,)
    starts_ok = (
        reply_text.startswith("Madame")
        or reply_text.startswith("Monsieur")
    )
    # Validate canonical sign-off "Je vous prie d'agréer" (allow curly U+2019)
    signoff_re = re.compile(r"Je vous prie d[\u2019']agr[ée]er", re.IGNORECASE)
    has_signoff = bool(signoff_re.search(reply_text))

    fails = []
    if not starts_ok:
        fails.append(f"opener not Madame/Monsieur: first40={reply_text[:40]!r}")
    if not has_signoff:
        fails.append(f"missing 'Je vous prie d'agréer'; last80={reply_text[-80:]!r}")
    if reply_lang != "fr":
        fails.append(f"reply_language_code={reply_lang!r} (expected 'fr')")

    if fails:
        record("B", "generate_reply_fr", "FAIL", ms,
               f"issues={fails}")
        return False
    record("B", "generate_reply_fr", "PASS", ms,
           f"reply_lang={reply_lang!r} len={len(reply_text)} "
           f"first40={reply_text[:40]!r} signoff_OK")
    return True


# ============================================================================
# (C) Report-flow smoke
# ============================================================================
def section_c_report():
    print("\n=== SECTION C — Report-flow smoke ===\n")
    if not FR_ANALYSIS_ID:
        record("C", "skip", "FAIL", None, "no FR_ANALYSIS_ID")
        return False

    # C1 - canonical reason spec: review-request used 'spam' & 'incorrect'
    # which are NOT in the backend Literal. Test both as-requested (expect 422)
    # AND with the actual canonical reasons to verify end-to-end report flow.

    # C1a - As-requested: reason='spam' (expected to FAIL with 422 per code)
    body_spam = {
        "analysis_id": FR_ANALYSIS_ID,
        "device_id": DEVICE_FR_SPOT,
        "reason": "spam",
        "comment": "QA D4 release smoke",
    }
    r, ms = post("/report", json=body_spam)
    if r.status_code == 200:
        record("C", "report_spam_as_requested", "PASS", ms,
               f"200 OK body={r.text[:200]}")
    else:
        # Reason 'spam' is NOT in backend Literal:
        # ['inaccurate','translation_error','offensive','scam_missed','other']
        record("C", "report_spam_as_requested", "FAIL", ms,
               f"status={r.status_code} — 'spam' NOT in backend Literal "
               f"(allowed: inaccurate/translation_error/offensive/scam_missed/other) "
               f"body={r.text[:200]}")

    # C1b - With canonical reason: 'other' + the same comment
    body_canon = {
        "analysis_id": FR_ANALYSIS_ID,
        "device_id": DEVICE_FR_SPOT,
        "reason": "other",
        "comment": "QA D4 release smoke",
    }
    r, ms = post("/report", json=body_canon)
    if r.status_code != 200:
        record("C", "report_other_canonical", "FAIL", ms,
               f"status={r.status_code} body={r.text[:300]}")
        canonical_ok = False
    else:
        body = r.json()
        ok = body.get("ok")
        report_id = body.get("report_id")
        if ok is True and report_id:
            record("C", "report_other_canonical", "PASS", ms,
                   f"ok=True report_id={report_id}")
            canonical_ok = True
        else:
            record("C", "report_other_canonical", "FAIL", ms,
                   f"bad envelope: {body}")
            canonical_ok = False

    # C2 - Direct pymongo verification
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URL)
        coll = client[DB_NAME].reports
        # Find any report doc for this device
        doc = coll.find_one({"device_id": DEVICE_FR_SPOT})
        if not doc:
            record("C", "pymongo_lookup", "FAIL", None,
                   f"no doc for device_id={DEVICE_FR_SPOT}")
        else:
            missing = []
            for f in ("status", "created_at", "reason", "comment",
                      "analysis_id", "device_id"):
                if f not in doc:
                    missing.append(f)
            # Review expected reason='spam' & comment='QA D4 release smoke',
            # but we wrote 'other' + 'QA D4 release smoke' due to Literal constraint.
            checks = {
                "status_present": doc.get("status") in ("new", "triaged", "resolved"),
                "created_at_is_datetime": isinstance(doc.get("created_at"), datetime),
                "comment_match": doc.get("comment") == "QA D4 release smoke",
                "analysis_id_match": doc.get("analysis_id") == FR_ANALYSIS_ID,
                "device_id_match": doc.get("device_id") == DEVICE_FR_SPOT,
                "reason_in_literal": doc.get("reason") in (
                    "inaccurate", "translation_error", "offensive",
                    "scam_missed", "other"
                ),
            }
            all_ok = (not missing) and all(checks.values())
            if all_ok:
                record("C", "pymongo_lookup", "PASS", None,
                       f"all required fields present; doc.reason={doc.get('reason')!r} "
                       f"status={doc.get('status')!r} created_at={doc.get('created_at')}")
            else:
                record("C", "pymongo_lookup", "FAIL", None,
                       f"missing={missing} checks={checks} doc_keys={list(doc.keys())}")
    except Exception as e:
        record("C", "pymongo_lookup", "FAIL", None, f"exception={e!r}")

    # C3 - Missing-comment optional path
    # Review used reason='incorrect' (not in Literal). Test as-requested,
    # then test with the closest canonical 'inaccurate' (which matches the
    # i18n string 'report_reason_inaccurate' = 'Wrong or incomplete analysis').
    body_incorrect = {
        "analysis_id": FR_ANALYSIS_ID,
        "device_id": DEVICE_FR_SPOT,
        "reason": "incorrect",
    }
    r, ms = post("/report", json=body_incorrect)
    if r.status_code == 200:
        record("C", "report_incorrect_as_requested", "PASS", ms,
               f"200 OK body={r.text[:200]}")
    else:
        record("C", "report_incorrect_as_requested", "FAIL", ms,
               f"status={r.status_code} — 'incorrect' NOT in backend Literal "
               f"(closest canonical: 'inaccurate') body={r.text[:200]}")

    # C3b - canonical missing-comment path
    body_canon_nc = {
        "analysis_id": FR_ANALYSIS_ID,
        "device_id": DEVICE_FR_SPOT,
        "reason": "inaccurate",
    }
    r, ms = post("/report", json=body_canon_nc)
    if r.status_code != 200:
        record("C", "report_inaccurate_no_comment", "FAIL", ms,
               f"status={r.status_code} body={r.text[:300]}")
    else:
        body = r.json()
        if body.get("ok") and body.get("report_id"):
            record("C", "report_inaccurate_no_comment", "PASS", ms,
                   f"ok=True report_id={body.get('report_id')}")
        else:
            record("C", "report_inaccurate_no_comment", "FAIL", ms,
                   f"bad envelope: {body}")

    return True


# ============================================================================
# (D) Cleanup + privacy log audit
# ============================================================================
def section_d_cleanup_audit():
    print("\n=== SECTION D — Cleanup + privacy log audit ===\n")

    # D1 - DELETE history phaseB
    r, ms = delete_(f"/history/{DEVICE_PHASE_B}")
    if r.status_code != 200:
        record("D", "delete_history_phaseB", "FAIL", ms,
               f"status={r.status_code} body={r.text[:200]}")
    else:
        body = r.json()
        record("D", "delete_history_phaseB", "PASS", ms,
               f"deleted_analyses={body.get('deleted_analyses')} "
               f"deleted_messages={body.get('deleted_messages')}")

    # D2 - DELETE history FR
    r, ms = delete_(f"/history/{DEVICE_FR_SPOT}")
    if r.status_code != 200:
        record("D", "delete_history_fr", "FAIL", ms,
               f"status={r.status_code} body={r.text[:200]}")
    else:
        body = r.json()
        record("D", "delete_history_fr", "PASS", ms,
               f"deleted_analyses={body.get('deleted_analyses')} "
               f"deleted_messages={body.get('deleted_messages')}")

    # D3 - Privacy log audit
    log_paths = [
        "/var/log/supervisor/backend.out.log",
        "/var/log/supervisor/backend.err.log",
    ]
    pii_tokens = [
        "Sehr geehrte", "AOK", "Mustermann", "iTunes",
        "NG12", "DE89", "Bundespolizei", "482,50",
        "Berlin-Mitte", "Direction Générale", "Madame Martin",
    ]
    pii_hits = {tok: 0 for tok in pii_tokens}
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

    any_hits = sum(pii_hits.values())
    nonzero = {k: v for k, v in pii_hits.items() if v > 0}
    if any_hits == 0:
        record("D", "privacy_log_audit", "PASS", None,
               f"ZERO hits across all 11 PII tokens")
    else:
        record("D", "privacy_log_audit", "FAIL", None,
               f"PII leaks detected: {nonzero}")

    return any_hits == 0


# ============================================================================
# Main
# ============================================================================
def main():
    print("\n=== Phase D4 Final Release-Readiness Backend Smoke ===\n")
    a_ok = section_a_regression()
    b_ok = section_b_fr_spot()
    c_ok = section_c_report()
    d_ok = section_d_cleanup_audit()

    print("\n=== SUMMARY ===")
    n_pass = sum(1 for *_, s, _, _ in results if s == "PASS")
    n_fail = sum(1 for *_, s, _, _ in results if s == "FAIL")
    print(f"Total: {len(results)} | PASS: {n_pass} | FAIL: {n_fail}")
    print(f"Section A: {'PASS' if a_ok else 'FAIL'}")
    print(f"Section B: {'PASS' if b_ok else 'FAIL'}")
    print(f"Section C: PARTIAL (see above)")
    print(f"Section D: {'PASS' if d_ok else 'FAIL'}")
    for sect, name, status, ms, note in results:
        ms_s = f"{ms:.0f}ms" if ms is not None else "—"
        print(f"  [{status:<4}] {sect}.{name:<32}  {ms_s:>8}  {note[:120]}")

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
