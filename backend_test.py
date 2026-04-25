"""
KlarPost backend tests for new AnalysisResult schema fields:
- category (enum)
- scam_warning (bool)
- scam_reason (string, populated only when scam_warning is true)

Plus: GET /api/analyses?device_id=... returns category and scam_warning per item.
"""
import base64
import io
import os
import random
import string
import sys
import time
from typing import Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

# Public URL pulled from EXPO_PUBLIC_BACKEND_URL (frontend/.env)
BACKEND_URL = "https://klarpost-mvp.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

VALID_CATEGORIES = {
    "tax", "insurance", "rent", "bank", "health", "government",
    "court", "utilities", "telecom", "work", "education", "other",
}

DEVICE_ID = f"test-feature-rollout-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"
TARGET_LANGUAGE = "en"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_image(lines, size=(1100, 1500), font_size=30) -> bytes:
    img = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)
    y = 60
    for line in lines:
        draw.text((60, y), line, fill="black", font=font)
        # measure height
        try:
            bbox = draw.textbbox((60, y), line, font=font)
            h = bbox[3] - bbox[1]
        except Exception:
            h = font_size + 6
        y += h + 14
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def post_analyze(image_bytes: bytes, label: str) -> dict:
    payload = {
        "device_id": DEVICE_ID,
        "target_language": TARGET_LANGUAGE,
        "file_base64": b64(image_bytes),
        "mime_type": "image/png",
    }
    print(f"\n--- POST /api/analyze [{label}] device_id={DEVICE_ID} ---")
    t0 = time.time()
    r = requests.post(f"{API_BASE}/analyze", json=payload, timeout=180)
    dt = time.time() - t0
    print(f"HTTP {r.status_code} in {dt:.1f}s")
    if r.status_code != 200:
        print("Body:", r.text[:1500])
        raise AssertionError(f"/api/analyze [{label}] failed with {r.status_code}")
    body = r.json()
    return body


def assert_record_fields(rec: dict, label: str) -> dict:
    assert "id" in rec, f"[{label}] missing id"
    assert "result" in rec, f"[{label}] missing result"
    res = rec["result"]
    # Pre-existing fields still present
    for f in ["sender", "summary_translated", "document_type", "risk_level",
              "key_points", "deadlines", "required_actions",
              "german_reply_draft", "disclaimer", "uncertainties"]:
        assert f in res, f"[{label}] result missing pre-existing field '{f}'"
    # New fields present
    assert "category" in res, f"[{label}] result MISSING new field 'category' (P0)"
    assert "scam_warning" in res, f"[{label}] result MISSING new field 'scam_warning' (P0)"
    assert "scam_reason" in res, f"[{label}] result MISSING new field 'scam_reason' (P0)"
    return res


def run() -> int:
    failures = []

    # ---------------- Health check ----------------
    print(f"Backend: {API_BASE}")
    try:
        r = requests.get(f"{API_BASE}/", timeout=15)
        print(f"GET /api/ -> {r.status_code} {r.text[:120]}")
        assert r.status_code == 200
    except Exception as e:
        failures.append(f"Health check failed: {e}")
        print("FATAL: backend health check failed; aborting", e)
        return 1

    # ---------------- Test 1: Normal harmless German document ----------------
    normal_lines = [
        "Techniker Krankenkasse",
        "Bramfelder Strasse 140",
        "22305 Hamburg",
        "",
        "Mitgliedsnummer: 1234567890",
        "Datum: 12.03.2026",
        "",
        "Information zur Beitragserhoehung",
        "",
        "Sehr geehrte Frau Mustermann,",
        "",
        "wir moechten Sie informieren, dass sich der",
        "Zusatzbeitrag Ihrer Krankenkasse zum 01.04.2026",
        "von 1,2 Prozent auf 1,4 Prozent erhoeht.",
        "",
        "Sie muessen nichts unternehmen. Der Beitrag wird",
        "automatisch ueber Ihren Arbeitgeber abgerechnet.",
        "",
        "Bei Fragen erreichen Sie uns unter 0800 - 285 85 85.",
        "",
        "Mit freundlichen Gruessen",
        "Ihre Techniker Krankenkasse",
    ]
    normal_img = make_image(normal_lines)
    test1_record = None
    try:
        test1_record = post_analyze(normal_img, "normal Krankenkasse")
        res = assert_record_fields(test1_record, "test1")
        print(f"  category       = {res.get('category')!r}")
        print(f"  scam_warning   = {res.get('scam_warning')!r}")
        print(f"  scam_reason    = {res.get('scam_reason')!r}")
        print(f"  risk_level     = {res.get('risk_level')!r}")
        print(f"  sender         = {res.get('sender')!r}")
        print(f"  document_type  = {res.get('document_type')!r}")
        print(f"  summary[:140]  = {(res.get('summary_translated') or '')[:140]!r}")

        # Validations
        cat = res.get("category")
        if cat not in VALID_CATEGORIES:
            failures.append(f"Test1: category {cat!r} NOT in valid enum")
        if not isinstance(res.get("scam_warning"), bool):
            failures.append(f"Test1: scam_warning is not a real boolean (got {type(res.get('scam_warning')).__name__})")
        if res.get("scam_warning") is True:
            failures.append("Test1: scam_warning is True for a benign Krankenkasse letter (expected False)")
        # scam_reason should be empty string when scam_warning is False
        if res.get("scam_warning") is False and (res.get("scam_reason") or "") != "":
            failures.append(f"Test1: scam_reason should be empty when scam_warning False, got {res.get('scam_reason')!r}")
        # Expect category to plausibly be insurance or health (informational, but not enforced)
        if cat not in ("insurance", "health"):
            print(f"  NOTE: category for Krankenkasse letter came back as {cat!r} (expected 'insurance' typically — informational)")
        # Pre-existing core fields
        if not (res.get("summary_translated") or "").strip():
            failures.append("Test1: summary_translated is empty")
        if not (res.get("sender") or "").strip():
            failures.append("Test1: sender is empty")
    except AssertionError as e:
        failures.append(str(e))
    except Exception as e:
        failures.append(f"Test1 unexpected error: {e}")

    # ---------------- Test 2: Obvious scam document ----------------
    scam_lines = [
        "DRINGEND !!! BUNDESPOLIZEI - SOFORTIGE ZAHLUNG ERFORDERLICH",
        "",
        "Sehr geehrter Buerger,",
        "",
        "Sie schulden 950 EUR Strafgebuehr wegen illegaler Aktivitaeten.",
        "Wenn Sie nicht innerhalb von 24 Stunden zahlen, werden Sie",
        "VERHAFTET und Ihr Konto wird GESPERRT!",
        "",
        "Zahlen Sie SOFORT 950 EUR auf folgende IBAN in Nigeria:",
        "IBAN: NG12 0000 0000 0000 0000 0000 00",
        "BIC: SCAMNG22",
        "",
        "Alternativ: Bitte zahlen Sie in Bitcoin an Wallet:",
        "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
        "",
        "Oder kaufen Sie Google Play / Amazon Geschenkkarten",
        "im Wert von 950 EUR und senden Sie uns die Codes per E-Mail",
        "an: bundespolizei-zahlung@gmail.com",
        "",
        "Geben Sie uns auch Ihre TAN, PIN und Online-Banking-Logindaten,",
        "damit wir die Zahlung schneller bearbeiten koennen.",
        "",
        "Bei Nichtzahlung: SOFORTIGE VERHAFTUNG und ABSCHIEBUNG!",
        "",
        "Bundespolizei Spezialeinheit",
    ]
    scam_img = make_image(scam_lines)
    test2_record = None
    try:
        test2_record = post_analyze(scam_img, "obvious scam")
        res = assert_record_fields(test2_record, "test2")
        print(f"  category       = {res.get('category')!r}")
        print(f"  scam_warning   = {res.get('scam_warning')!r}")
        print(f"  scam_reason    = {res.get('scam_reason')!r}")
        print(f"  risk_level     = {res.get('risk_level')!r}")
        print(f"  document_type  = {res.get('document_type')!r}")
        print(f"  summary[:140]  = {(res.get('summary_translated') or '')[:140]!r}")

        cat = res.get("category")
        if cat not in VALID_CATEGORIES:
            failures.append(f"Test2: category {cat!r} NOT in valid enum")
        if not isinstance(res.get("scam_warning"), bool):
            failures.append(f"Test2: scam_warning is not a real boolean (got {type(res.get('scam_warning')).__name__})")
        if res.get("scam_warning") is not True:
            failures.append("Test2: scam_warning is NOT True for an obvious scam letter (P0 - scam detection failed)")
        else:
            sr = (res.get("scam_reason") or "").strip()
            if not sr:
                failures.append("Test2: scam_reason is empty when scam_warning=True (must be populated)")
        # risk_level expected red but not enforced
        if res.get("risk_level") != "red":
            print(f"  NOTE: risk_level came back as {res.get('risk_level')!r} (expected 'red' typically — informational)")
    except AssertionError as e:
        failures.append(str(e))
    except Exception as e:
        failures.append(f"Test2 unexpected error: {e}")

    # ---------------- Test 3: GET /api/analyses ----------------
    try:
        print(f"\n--- GET /api/analyses?device_id={DEVICE_ID} ---")
        r = requests.get(f"{API_BASE}/analyses", params={"device_id": DEVICE_ID}, timeout=30)
        print(f"HTTP {r.status_code}")
        assert r.status_code == 200, f"Body: {r.text[:500]}"
        items = r.json()
        assert isinstance(items, list), "list endpoint did not return JSON array"
        print(f"Returned {len(items)} item(s)")
        if not items:
            failures.append("Test3: list endpoint returned no items even though analyses were just created")
        else:
            for i, it in enumerate(items):
                print(f"  item[{i}] id={it.get('id')[:8]}.. category={it.get('category')!r} "
                      f"scam_warning={it.get('scam_warning')!r} risk={it.get('risk_level')!r} "
                      f"sender={it.get('sender')!r}")
                if "category" not in it:
                    failures.append(f"Test3: list item[{i}] MISSING 'category' field (P0)")
                if "scam_warning" not in it:
                    failures.append(f"Test3: list item[{i}] MISSING 'scam_warning' field (P0)")
                if it.get("category") not in VALID_CATEGORIES:
                    failures.append(f"Test3: list item[{i}] category {it.get('category')!r} NOT in valid enum")
                if not isinstance(it.get("scam_warning"), bool):
                    failures.append(f"Test3: list item[{i}] scam_warning is not a real boolean")
            # cross-check at least one of items shows scam_warning True (the scam doc)
            if test2_record is not None and test2_record.get("result", {}).get("scam_warning") is True:
                if not any(it.get("scam_warning") is True for it in items):
                    failures.append("Test3: list does not surface any scam_warning=True item, "
                                    "but Test2 analyze response had scam_warning=True (data inconsistency)")
    except AssertionError as e:
        failures.append(f"Test3: {e}")
    except Exception as e:
        failures.append(f"Test3 unexpected error: {e}")

    # ---------------- Test 4: Validation summary ----------------
    print("\n--- Test 4: Validation (boolean + enum) ---")
    # Already covered piecemeal above, but confirm overall presence on both records.
    for label, rec in [("normal", test1_record), ("scam", test2_record)]:
        if rec is None:
            continue
        res = rec.get("result", {})
        sw = res.get("scam_warning")
        cat = res.get("category")
        ok_bool = isinstance(sw, bool)
        ok_enum = cat in VALID_CATEGORIES
        print(f"  [{label}] scam_warning is bool? {ok_bool}; category in enum? {ok_enum}")

    # ---------------- Cleanup ----------------
    try:
        r = requests.delete(f"{API_BASE}/analyses", params={"device_id": DEVICE_ID}, timeout=30)
        print(f"\nCleanup DELETE /api/analyses -> {r.status_code} {r.text[:120]}")
    except Exception as e:
        print(f"Cleanup failed (non-fatal): {e}")

    # ---------------- Summary ----------------
    print("\n" + "=" * 70)
    if failures:
        print(f"FAILED: {len(failures)} issue(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(run())
