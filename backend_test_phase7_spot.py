#!/usr/bin/env python3
"""Phase 7 spot-checks — services/ai_service.py → services/ai/ sub-package.

Verifies the 5 Phase 7 invariants on top of the standard 13-step suite:
  (a) Phase 6b — Finanzamt fixture: detected_country_code='DE',
      jurisdiction_confidence in {medium, high}
  (b) Phase 6d — DE source doc, intent='inquiry', no reply_language_code:
      reply_text begins 'Sehr geehrte' AND ends 'Mit freundlichen Grüßen'
  (c) Phase 6d — same DE source doc, reply_language_code='fr':
      reply_text begins 'Madame' AND contains French sign-off
      (Cordialement OR 'Je vous prie d'agréer')
  (d) Phase 7 — translate to Italian: reply_draft byte-identical AND
      reply_options[].id byte-identical to original.
  (e) Phase 7 — chat returns valid ChatResponse JSON.

Final: privacy log audit + DELETE /api/history cleanup.
"""
import base64
import io
import json
import os
import re
import sys
import time
import uuid

import requests
from PIL import Image, ImageDraw, ImageFont


def _read_base() -> str:
    with open("/app/frontend/.env") as fh:
        for ln in fh:
            ln = ln.strip()
            if ln.startswith("EXPO_PUBLIC_BACKEND_URL="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
    raise RuntimeError("no BASE")


BASE = _read_base()
API = f"{BASE}/api"
DEVICE = "qa-phase7-spot-001"
print(f"BASE={BASE}")
print(f"DEVICE={DEVICE}")


LETTER = [
    "Finanzamt Berlin-Mitte",
    "Hauptstrasse 12",
    "10115 Berlin",
    "",
    "Sehr geehrte Frau Schulz,",
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


def _render_png() -> str:
    img = Image.new("RGB", (800, 1000), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    y = 40
    for ln in LETTER:
        d.text((40, y), ln, fill="black", font=font)
        y += 36
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def post(p, **kw):
    t = time.time()
    r = requests.post(f"{API}{p}", timeout=120, **kw)
    return r, (time.time() - t) * 1000


def delete_(p, **kw):
    t = time.time()
    r = requests.delete(f"{API}{p}", timeout=60, **kw)
    return r, (time.time() - t) * 1000


def main():
    # cleanup leftovers
    try:
        delete_(f"/history/{DEVICE}")
    except Exception:
        pass
    # reset usage
    requests.post(f"{API}/dev/usage/reset?device_id={DEVICE}", timeout=30)

    b64 = _render_png()
    print(f"Rendered PNG b64_len={len(b64)}")

    summary = {}

    # (a) Analyze the DE Finanzamt fixture
    payload = {
        "device_id": DEVICE,
        "target_language": "en",
        "file_base64": b64,
        "mime_type": "image/png",
        "idempotency_key": str(uuid.uuid4()),
    }
    r, ms = post("/analyze", json=payload)
    if r.status_code != 200:
        print(f"[A] FAIL — analyze status={r.status_code} body={r.text[:400]}")
        sys.exit(1)
    env = r.json()
    ANID = env.get("id")
    res = env.get("result") or {}
    country = res.get("detected_country_code")
    jc = res.get("jurisdiction_confidence")
    cat = res.get("category")
    orig_reply_draft = res.get("reply_draft") or ""
    orig_options = res.get("reply_options") or []
    orig_option_ids = [opt.get("id") for opt in orig_options]
    a_ok = (country == "DE" and jc in ("medium", "high"))
    print(f"[A] {'PASS' if a_ok else 'FAIL'} analyze {ms:.0f}ms — "
          f"country={country!r} jc={jc!r} category={cat!r} "
          f"reply_draft_len={len(orig_reply_draft)} "
          f"option_ids={orig_option_ids}")
    summary["A_analyze"] = {
        "ok": a_ok, "ms": ms, "country": country, "jc": jc,
        "anid": ANID, "reply_draft_len": len(orig_reply_draft),
        "option_ids": orig_option_ids,
    }

    # (b) Generate-reply intent=inquiry — DE default
    r, ms = post(f"/analyses/{ANID}/generate-reply",
                 json={"device_id": DEVICE, "intent": "inquiry"})
    b_ok = False
    de_reply = ""
    if r.status_code == 200:
        body = r.json()
        de_reply = body.get("reply_text") or ""
        de_lang = body.get("reply_language_code")
        b_ok = (
            de_reply.startswith("Sehr geehrte")
            and de_reply.rstrip().endswith("Mit freundlichen Grüßen")
            and de_lang == "de"
        )
        print(f"[B] {'PASS' if b_ok else 'FAIL'} de-reply {ms:.0f}ms — "
              f"lang={de_lang!r} first60={de_reply[:60]!r} "
              f"last40={de_reply[-40:]!r}")
    else:
        print(f"[B] FAIL — status={r.status_code} body={r.text[:400]}")
    summary["B_de_reply"] = {
        "ok": b_ok, "ms": ms,
        "first60": de_reply[:60],
        "last40": de_reply[-40:],
    }

    # (c) Generate-reply intent=inquiry — FR target lang
    r, ms = post(f"/analyses/{ANID}/generate-reply",
                 json={"device_id": DEVICE, "intent": "inquiry",
                       "reply_language_code": "fr"})
    c_ok = False
    fr_reply = ""
    if r.status_code == 200:
        body = r.json()
        fr_reply = body.get("reply_text") or ""
        fr_lang = body.get("reply_language_code")
        starts = fr_reply.lstrip().startswith("Madame")
        contains_fr_signoff = (
            "Cordialement" in fr_reply
            or "Je vous prie d\u2019agréer" in fr_reply
            or "Je vous prie d'agréer" in fr_reply
            or "Je vous prie d\u2019agreer" in fr_reply
        )
        c_ok = starts and contains_fr_signoff and fr_lang == "fr"
        print(f"[C] {'PASS' if c_ok else 'FAIL'} fr-reply {ms:.0f}ms — "
              f"lang={fr_lang!r} starts_Madame={starts} "
              f"contains_fr_signoff={contains_fr_signoff}")
        print(f"    first60={fr_reply[:60]!r}")
        print(f"    last40={fr_reply[-40:]!r}")
    else:
        print(f"[C] FAIL — status={r.status_code} body={r.text[:400]}")
    summary["C_fr_reply"] = {
        "ok": c_ok, "ms": ms,
        "first60": fr_reply[:60],
        "last40": fr_reply[-40:],
    }

    # (d) Translate to Italian; reply_draft + option ids byte-identical
    r, ms = post(f"/analyses/{ANID}/translate",
                 json={"device_id": DEVICE, "target_language": "it"})
    d_ok = False
    if r.status_code == 200:
        env2 = r.json()
        res2 = env2.get("result") or {}
        it_reply_draft = res2.get("reply_draft") or ""
        it_options = res2.get("reply_options") or []
        it_option_ids = [opt.get("id") for opt in it_options]
        tlang = res2.get("target_language")
        draft_identical = (it_reply_draft == orig_reply_draft)
        ids_identical = (it_option_ids == orig_option_ids)
        d_ok = draft_identical and ids_identical
        print(f"[D] {'PASS' if d_ok else 'FAIL'} translate-it {ms:.0f}ms — "
              f"target={tlang!r} draft_byte_identical={draft_identical} "
              f"option_ids_byte_identical={ids_identical}")
        if not draft_identical:
            print(f"    orig_draft_len={len(orig_reply_draft)} "
                  f"it_draft_len={len(it_reply_draft)}")
        if not ids_identical:
            print(f"    orig_ids={orig_option_ids} it_ids={it_option_ids}")
    else:
        print(f"[D] FAIL — status={r.status_code} body={r.text[:400]}")
    summary["D_translate_it"] = {"ok": d_ok, "ms": ms}

    # (e) Chat
    r, ms = post(f"/analyses/{ANID}/chat",
                 json={"device_id": DEVICE,
                       "message": "What is the deadline mentioned in the letter?"})
    e_ok = False
    if r.status_code == 200:
        body = r.json()
        content = body.get("content") or ""
        role = body.get("role")
        e_ok = (role == "assistant" and len(content) > 30)
        print(f"[E] {'PASS' if e_ok else 'FAIL'} chat {ms:.0f}ms — "
              f"role={role!r} content_len={len(content)} "
              f"sample={content[:80]!r}")
    else:
        print(f"[E] FAIL — status={r.status_code} body={r.text[:400]}")
    summary["E_chat"] = {"ok": e_ok, "ms": ms}

    # Privacy log audit
    print("\n--- LOG AUDIT ---")
    pii_tokens = [
        "Sehr geehrte", "AOK", "Bundespolizei", "Mustermann",
        "iTunes", "DE89", "NG12", "248,50", "4 850",
    ]
    pii_hits = {t: 0 for t in pii_tokens}
    for p in ("/var/log/supervisor/backend.out.log",
              "/var/log/supervisor/backend.err.log"):
        if not os.path.exists(p):
            continue
        try:
            with open(p, errors="ignore") as fh:
                txt = fh.read()
        except Exception:
            continue
        for tok in pii_tokens:
            pii_hits[tok] += txt.count(tok)
    print(f"PII hits across both logs: {pii_hits}")
    total_pii = sum(pii_hits.values())
    audit_clean = (total_pii == 0)
    print(f"audit_clean={audit_clean}")

    # Cleanup
    r, ms = delete_(f"/history/{DEVICE}")
    cleanup_ok = (r.status_code == 200)
    print(f"\n[CLEANUP] {'PASS' if cleanup_ok else 'FAIL'} "
          f"DELETE /api/history/{DEVICE} {ms:.0f}ms — body={r.text[:200]}")

    # Final tally
    print("\n=== PHASE 7 SPOT-CHECK SUMMARY ===")
    all_ok = True
    for tag, d in summary.items():
        flag = "PASS" if d.get("ok") else "FAIL"
        if not d.get("ok"):
            all_ok = False
        print(f"  {tag}: {flag}")
    print(f"  AUDIT: {'CLEAN' if audit_clean else 'DIRTY'}")
    print(f"  CLEANUP: {'OK' if cleanup_ok else 'FAIL'}")
    if not audit_clean:
        all_ok = False
    if not cleanup_ok:
        all_ok = False
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
