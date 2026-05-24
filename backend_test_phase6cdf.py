#!/usr/bin/env python3
"""Phase 6c+d+f country-pack injection spot checks.

Spot checks on top of the standard 13-step regression suite:
 (a) German Finanzamt fixture: detected_country_code='DE' and
     jurisdiction_confidence in {medium,high} (no regression from 6c+f).
 (b) generate-reply intent='inquiry' on DE doc (default reply_lang_code=de):
     reply_text BEGINS with "Sehr geehrte Damen und Herren," (no contact_person)
     OR "Sehr geehrte/r Frau/Herr {Lastname},"
     ENDS with "Mit freundlichen Grüßen"
     reply_explanation is in English (target_language=English).
 (c) generate-reply intent='inquiry' reply_language_code='fr' on same DE doc:
     reply_text BEGINS with "Madame, Monsieur," and ENDS with
     "Je vous prie d'agréer" or "Cordialement,".
 (d) generate-reply reply_language_code='en' on same DE doc:
     reply_text BEGINS with "Dear Sir or Madam," and ENDS with
     "Yours faithfully," or "Kind regards,".

Cleanup at end via DELETE /api/history/qa-phase6cdf-001.
"""
import base64
import io
import re
import sys
import time
import uuid

import requests
from PIL import Image, ImageDraw, ImageFont


BASE = "https://paperwork-eu.preview.emergentagent.com"
API = f"{BASE}/api"
DEVICE_ID = "qa-phase6cdf-001"
print(f"BASE={BASE}\nDEVICE_ID={DEVICE_ID}\n")


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
    "Steuerbescheid Einkommensteuer 2025",
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


def render_letter_png() -> str:
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


def post(path, **kw):
    t0 = time.time()
    r = requests.post(f"{API}{path}", timeout=120, **kw)
    return r, (time.time() - t0) * 1000.0


def delete_(path, **kw):
    t0 = time.time()
    r = requests.delete(f"{API}{path}", timeout=60, **kw)
    return r, (time.time() - t0) * 1000.0


results = []

def record(name, status, ms=None, note=""):
    line = f"[{status}] {name}"
    if ms is not None:
        line += f" ({ms:.0f}ms)"
    if note:
        line += f" — {note}"
    print(line)
    results.append((name, status, ms, note))


# 0) Reset usage so we don't hit 429
post(f"/dev/usage/reset?device_id={DEVICE_ID}")
delete_(f"/history/{DEVICE_ID}")


# Step A — analyze German Finanzamt fixture
b64 = render_letter_png()
print(f"Rendered letter PNG, base64 len={len(b64)}\n")

payload = {
    "device_id": DEVICE_ID,
    "target_language": "en",
    "file_base64": b64,
    "mime_type": "image/png",
    "idempotency_key": str(uuid.uuid4()),
}
r, ms = post("/analyze", json=payload)
if r.status_code != 200:
    record("A_analyze", "FAIL", ms, f"status={r.status_code} body={r.text[:300]}")
    sys.exit(1)
env = r.json()
de_id = env.get("id")
res = env.get("result") or {}
detected_country = res.get("detected_country_code", "")
jur_conf = res.get("jurisdiction_confidence", "")
category = res.get("category")
contact_person = (res.get("extracted_entities") or {}).get("contact_person", "") or ""
sender = res.get("sender", "")

print(f"  de_id={de_id}")
print(f"  detected_country_code={detected_country!r} jurisdiction_confidence={jur_conf!r}")
print(f"  category={category!r} sender={sender!r}")
print(f"  contact_person={contact_person!r}\n")

# Spot check (a)
fails = []
if detected_country != "DE":
    fails.append(f"detected_country_code={detected_country!r} (expected 'DE')")
if jur_conf not in ("medium", "high"):
    fails.append(f"jurisdiction_confidence={jur_conf!r} (expected medium|high)")
if fails:
    record("A_country_anchor", "FAIL", ms, "; ".join(fails))
else:
    record("A_country_anchor", "PASS", ms,
           f"detected_country=DE jur_conf={jur_conf!r} category={category!r}")


def first80(s: str) -> str:
    return s[:80]


def last60(s: str) -> str:
    return s[-60:]


# Spot check (b) — generate-reply default (de)
print("\n--- Spot check (b): generate-reply intent=inquiry default lang -> de ---")
payload = {"device_id": DEVICE_ID, "intent": "inquiry"}
r, ms = post(f"/analyses/{de_id}/generate-reply", json=payload)
if r.status_code != 200:
    record("B_reply_de", "FAIL", ms, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    reply_text = body.get("reply_text") or ""
    reply_lang = body.get("reply_language_code")
    reply_expl = body.get("reply_explanation") or ""
    print(f"  reply_language_code={reply_lang!r}")
    print(f"  reply_text len={len(reply_text)}")
    print(f"  reply_text FIRST 80: {first80(reply_text)!r}")
    print(f"  reply_text LAST  60: {last60(reply_text)!r}")
    print(f"  reply_explanation len={len(reply_expl)}")
    print(f"  reply_explanation FIRST 120: {reply_expl[:120]!r}")

    fails = []
    # opener: with contact_person='Frau Schulz' OR 'Mustermann' (could be either depending on extraction),
    # the prompt should produce the named form OR the unknown form.
    de_named = re.match(r"Sehr geehrte/r Frau/Herr \w", reply_text)
    de_unknown = reply_text.startswith("Sehr geehrte Damen und Herren,")
    # The model could also use the named form with proper substitution.
    de_named_proper = re.match(r"Sehr geehrte[r]?\s+(Frau|Herr)\s+\w+", reply_text)
    if not (de_named or de_unknown or de_named_proper):
        fails.append(f"opener missing canonical 'Sehr geehrte...'; got: {first80(reply_text)!r}")
    # closing
    if "Mit freundlichen Grüßen" not in reply_text and "Mit freundlichen Gruessen" not in reply_text:
        fails.append(f"missing 'Mit freundlichen Grüßen'; last60={last60(reply_text)!r}")
    # Forbidden artifacts
    if "[Your Name]" in reply_text or "[Ihr Name]" in reply_text:
        fails.append("contains '[Your Name]' placeholder")
    if re.search(r"\bKind regards\b", reply_text, re.IGNORECASE):
        fails.append("contains 'Kind regards' (English closer in DE reply)")
    if re.search(r"\bHallo\b", reply_text):
        fails.append("contains 'Hallo' (informal opener)")
    if reply_lang != "de":
        fails.append(f"reply_language_code={reply_lang!r} (expected 'de')")

    # Explanation should be in English (target_language='en' was 'English')
    # Quick heuristic: ASCII-only stopwords
    expl_english_markers = re.search(
        r"\b(You are|This|This is|asking|confirming|the letter|reply|deadline|paid|payment)\b",
        reply_expl, re.IGNORECASE)
    if not expl_english_markers:
        fails.append(f"reply_explanation not obviously English; sample={reply_expl[:120]!r}")

    if fails:
        record("B_reply_de", "FAIL", ms, "; ".join(fails))
    else:
        record("B_reply_de", "PASS", ms,
               f"reply_lang=de canonical opener+closer present; expl English")


# Spot check (c) — generate-reply reply_language_code=fr
print("\n--- Spot check (c): generate-reply intent=inquiry reply_lang=fr ---")
payload = {"device_id": DEVICE_ID, "intent": "inquiry", "reply_language_code": "fr"}
r, ms = post(f"/analyses/{de_id}/generate-reply", json=payload)
if r.status_code != 200:
    record("C_reply_fr", "FAIL", ms, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    reply_text = body.get("reply_text") or ""
    reply_lang = body.get("reply_language_code")
    reply_expl = body.get("reply_explanation") or ""
    print(f"  reply_language_code={reply_lang!r}")
    print(f"  reply_text len={len(reply_text)}")
    print(f"  reply_text FIRST 80: {first80(reply_text)!r}")
    print(f"  reply_text LAST  60: {last60(reply_text)!r}")

    fails = []
    if not reply_text.startswith("Madame, Monsieur,"):
        fails.append(f"opener not 'Madame, Monsieur,'; first80={first80(reply_text)!r}")
    has_formal_closer = ("Je vous prie d'agréer" in reply_text or "Cordialement," in reply_text)
    if not has_formal_closer:
        fails.append(f"missing French sign-off; last60={last60(reply_text)!r}")
    if reply_lang != "fr":
        fails.append(f"reply_language_code={reply_lang!r} (expected 'fr')")
    if "[Your Name]" in reply_text or "[Votre Nom]" in reply_text:
        fails.append("contains '[Your Name]' placeholder")
    if re.search(r"\bSehr geehrte\b", reply_text):
        fails.append("contains German opener (should be French)")

    if fails:
        record("C_reply_fr", "FAIL", ms, "; ".join(fails))
    else:
        record("C_reply_fr", "PASS", ms, "FR opener+closer canonical")


# Spot check (d) — generate-reply reply_language_code=en
print("\n--- Spot check (d): generate-reply intent=inquiry reply_lang=en ---")
payload = {"device_id": DEVICE_ID, "intent": "inquiry", "reply_language_code": "en"}
r, ms = post(f"/analyses/{de_id}/generate-reply", json=payload)
if r.status_code != 200:
    record("D_reply_en", "FAIL", ms, f"status={r.status_code} body={r.text[:300]}")
else:
    body = r.json()
    reply_text = body.get("reply_text") or ""
    reply_lang = body.get("reply_language_code")
    print(f"  reply_language_code={reply_lang!r}")
    print(f"  reply_text len={len(reply_text)}")
    print(f"  reply_text FIRST 80: {first80(reply_text)!r}")
    print(f"  reply_text LAST  60: {last60(reply_text)!r}")

    fails = []
    if not reply_text.startswith("Dear Sir or Madam,"):
        fails.append(f"opener not 'Dear Sir or Madam,'; first80={first80(reply_text)!r}")
    has_en_closer = ("Yours faithfully," in reply_text or "Kind regards," in reply_text)
    if not has_en_closer:
        fails.append(f"missing English sign-off; last60={last60(reply_text)!r}")
    if reply_lang != "en":
        fails.append(f"reply_language_code={reply_lang!r} (expected 'en')")
    if "[Your Name]" in reply_text:
        fails.append("contains '[Your Name]' placeholder")
    if re.search(r"\bSehr geehrte\b", reply_text):
        fails.append("contains German opener (should be English)")

    if fails:
        record("D_reply_en", "FAIL", ms, "; ".join(fails))
    else:
        record("D_reply_en", "PASS", ms, "EN opener+closer canonical")


# Cleanup
print("\n--- Cleanup ---")
r, ms = delete_(f"/history/{DEVICE_ID}")
if r.status_code == 200:
    record("Z_cleanup", "PASS", ms, f"body={r.text[:140]}")
else:
    record("Z_cleanup", "FAIL", ms, f"status={r.status_code}")


# Summary
print("\n=== Phase 6c+d+f SPOT SUMMARY ===")
n_pass = sum(1 for _, s, *_ in results if s == "PASS")
n_fail = sum(1 for _, s, *_ in results if s == "FAIL")
print(f"Total: {len(results)} | PASS: {n_pass} | FAIL: {n_fail}")
for name, status, ms, note in results:
    ms_str = f"{ms:.0f}ms" if ms is not None else "—"
    print(f"  {name:>20}: {status:<4} {ms_str:>8}  {note[:160]}")

sys.exit(0 if n_fail == 0 else 1)
