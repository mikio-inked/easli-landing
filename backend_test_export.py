"""Backend regression test for GET /api/export (DSGVO Art. 15 data export).

Scenarios:
1. Empty store -> count=0, schema correct
2. Populated store -> 2 analyses, sorted newest first, no _id leaks
3. Validation: empty device_id -> 400; missing param -> 422
4. Cross-device isolation: different device_id sees nothing
5. Cleanup: DELETE all analyses for the populated device
"""

import os
import io
import sys
import json
import uuid
import time
import base64
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Use the public URL from frontend/.env (per system rules)
BASE = "https://klarpost-mvp.preview.emergentagent.com/api"

# ---------- helpers ----------

def make_letter_png(lines):
    """Render a benign synthetic German letter as a PNG and return base64."""
    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    y = 80
    for ln in lines:
        draw.text((80, y), ln, fill="black", font=font)
        y += 44
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def is_iso_utc(s):
    if not isinstance(s, str):
        return False
    try:
        # python's fromisoformat handles +00:00 but not 'Z'
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return dt.tzinfo is not None
    except Exception:
        return False


def has_underscore_id(obj):
    """Recursively check for any '_id' key anywhere in the structure."""
    if isinstance(obj, dict):
        if "_id" in obj:
            return True
        return any(has_underscore_id(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_underscore_id(v) for v in obj)
    return False


# ---------- test bookkeeping ----------

results = []  # (name, ok, detail)

def record(name, ok, detail=""):
    results.append((name, ok, detail))
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name} :: {detail}")


# ---------- Scenario 1: empty store ----------

def test_empty_store():
    device_id = f"qa-export-empty-{uuid.uuid4()}"
    r = requests.get(f"{BASE}/export", params={"device_id": device_id}, timeout=30)
    if r.status_code != 200:
        record("empty.status_200", False, f"got {r.status_code}: {r.text[:200]}")
        return
    record("empty.status_200", True, "200 OK")
    body = r.json()
    expected_keys = {"app", "device_id", "exported_at", "data_residency", "count", "analyses"}
    actual_keys = set(body.keys())
    record("empty.exact_keys", actual_keys == expected_keys,
           f"expected={sorted(expected_keys)} actual={sorted(actual_keys)}")
    record("empty.app_name", body.get("app") == "KlarPost", f"app={body.get('app')!r}")
    record("empty.device_id_match", body.get("device_id") == device_id,
           f"echoed={body.get('device_id')!r}")
    record("empty.exported_at_iso_utc", is_iso_utc(body.get("exported_at", "")),
           f"exported_at={body.get('exported_at')!r}")
    record("empty.data_residency", body.get("data_residency") == "EU (Mistral AI, Paris)",
           f"residency={body.get('data_residency')!r}")
    record("empty.count_zero", body.get("count") == 0, f"count={body.get('count')}")
    record("empty.analyses_empty", body.get("analyses") == [],
           f"analyses={body.get('analyses')!r}")
    record("empty.no_underscore_id", not has_underscore_id(body), "")


# ---------- Scenario 2: populated store ----------

def post_analyze(device_id, target_language, png_b64):
    payload = {
        "device_id": device_id,
        "target_language": target_language,
        "file_base64": png_b64,
        "mime_type": "image/png",
    }
    r = requests.post(f"{BASE}/analyze", json=payload, timeout=120)
    return r


def test_populated_store():
    device_id = f"qa-export-populated-{uuid.uuid4()}"

    # Letter 1: benign Krankenkasse-style letter
    letter1 = make_letter_png([
        "Techniker Krankenkasse",
        "Bramfelder Str. 140, 22305 Hamburg",
        "",
        "Sehr geehrter Versicherter,",
        "",
        "wir moechten Sie ueber Aenderungen Ihrer Beitraege ab",
        "01.01.2026 informieren. Der monatliche Beitrag betraegt",
        "kuenftig 320,50 EUR.",
        "",
        "Bei Fragen erreichen Sie uns unter 040-12345678.",
        "",
        "Mit freundlichen Gruessen",
        "Ihre Techniker Krankenkasse",
    ])

    # Letter 2: benign Stadtwerke utility-style letter (different content)
    letter2 = make_letter_png([
        "Stadtwerke Muenchen GmbH",
        "Emmy-Noether-Str. 2, 80287 Muenchen",
        "",
        "Sehr geehrte Kundin,",
        "",
        "anbei erhalten Sie Ihre Jahresabrechnung fuer Strom",
        "fuer den Zeitraum 01.01.2025 bis 31.12.2025.",
        "Der Gesamtbetrag belaeuft sich auf 842,17 EUR.",
        "",
        "Bitte ueberpruefen Sie die Abrechnung in Ruhe.",
        "",
        "Mit freundlichen Gruessen",
        "Ihre Stadtwerke Muenchen",
    ])

    print(f"[..] populated: posting first analyze (target=en) for {device_id}")
    t0 = time.time()
    r1 = post_analyze(device_id, "en", letter1)
    record("populated.analyze1_status", r1.status_code == 200,
           f"{r1.status_code} in {time.time()-t0:.1f}s body={r1.text[:200]}")
    if r1.status_code != 200:
        return device_id

    # Tiny gap to guarantee distinct created_at ordering
    time.sleep(1.5)

    print(f"[..] populated: posting second analyze (target=de_simple) for {device_id}")
    t0 = time.time()
    r2 = post_analyze(device_id, "de_simple", letter2)
    record("populated.analyze2_status", r2.status_code == 200,
           f"{r2.status_code} in {time.time()-t0:.1f}s body={r2.text[:200]}")
    if r2.status_code != 200:
        return device_id

    rec1 = r1.json()
    rec2 = r2.json()

    # Now hit /api/export
    r = requests.get(f"{BASE}/export", params={"device_id": device_id}, timeout=30)
    record("populated.export_status_200", r.status_code == 200,
           f"{r.status_code}: {r.text[:200]}")
    if r.status_code != 200:
        return device_id

    body = r.json()
    record("populated.exact_keys",
           set(body.keys()) == {"app", "device_id", "exported_at", "data_residency", "count", "analyses"},
           f"keys={sorted(body.keys())}")
    record("populated.count_2", body.get("count") == 2, f"count={body.get('count')}")
    analyses = body.get("analyses", [])
    record("populated.analyses_len_2", isinstance(analyses, list) and len(analyses) == 2,
           f"len={len(analyses) if isinstance(analyses, list) else 'N/A'}")
    if not (isinstance(analyses, list) and len(analyses) == 2):
        return device_id

    # Each record has required fields, device_id matches, etc.
    required_top = {"id", "device_id", "target_language", "target_language_label",
                    "created_at", "result"}
    for i, rec in enumerate(analyses):
        missing = required_top - set(rec.keys())
        record(f"populated.rec[{i}].required_fields_present", not missing,
               f"missing={sorted(missing)}")
        record(f"populated.rec[{i}].device_id_match",
               rec.get("device_id") == device_id,
               f"got={rec.get('device_id')!r}")
        result = rec.get("result", {}) or {}
        record(f"populated.rec[{i}].result.category_present",
               isinstance(result.get("category"), str) and result.get("category") != "",
               f"category={result.get('category')!r}")
        record(f"populated.rec[{i}].result.scam_warning_bool",
               isinstance(result.get("scam_warning"), bool),
               f"scam_warning={result.get('scam_warning')!r}")

    # Sorted newest first by created_at
    ca0 = analyses[0].get("created_at", "")
    ca1 = analyses[1].get("created_at", "")
    record("populated.sorted_newest_first", ca0 > ca1,
           f"[0]={ca0} should be > [1]={ca1}")

    # First in export should be the SECOND analyze call (later)
    record("populated.first_is_letter2",
           analyses[0].get("id") == rec2.get("id"),
           f"first.id={analyses[0].get('id')} rec2.id={rec2.get('id')}")
    record("populated.second_is_letter1",
           analyses[1].get("id") == rec1.get("id"),
           f"second.id={analyses[1].get('id')} rec1.id={rec1.get('id')}")

    # No _id anywhere
    record("populated.no_underscore_id_anywhere", not has_underscore_id(body),
           "scanned full payload recursively")

    # exported_at is ISO UTC
    record("populated.exported_at_iso_utc", is_iso_utc(body.get("exported_at", "")),
           f"exported_at={body.get('exported_at')!r}")
    record("populated.data_residency", body.get("data_residency") == "EU (Mistral AI, Paris)",
           f"residency={body.get('data_residency')!r}")
    record("populated.app_name", body.get("app") == "KlarPost",
           f"app={body.get('app')!r}")

    return device_id


# ---------- Scenario 3: validation ----------

def test_validation():
    # Empty device_id (string) -> 400
    r = requests.get(f"{BASE}/export", params={"device_id": ""}, timeout=15)
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text[:200]
    record("validation.empty_device_id_400",
           r.status_code == 400 and detail == "device_id is required",
           f"status={r.status_code} detail={detail!r}")

    # Missing query param entirely -> 422 (FastAPI Pydantic)
    r = requests.get(f"{BASE}/export", timeout=15)
    record("validation.missing_param_422",
           r.status_code == 422,
           f"status={r.status_code} body={r.text[:200]}")


# ---------- Scenario 4: cross-device isolation ----------

def test_isolation(populated_device_id):
    # Sanity: populated device still has 2 records right now
    r = requests.get(f"{BASE}/export", params={"device_id": populated_device_id}, timeout=30)
    record("isolation.populated_still_has_2",
           r.status_code == 200 and r.json().get("count") == 2,
           f"status={r.status_code} count={r.json().get('count') if r.ok else 'N/A'}")

    other = f"qa-export-other-{uuid.uuid4()}"
    r = requests.get(f"{BASE}/export", params={"device_id": other}, timeout=30)
    if r.status_code != 200:
        record("isolation.other_device_200", False, f"{r.status_code}: {r.text[:200]}")
        return
    body = r.json()
    record("isolation.other_device_count_zero", body.get("count") == 0,
           f"count={body.get('count')}")
    record("isolation.other_device_analyses_empty", body.get("analyses") == [],
           f"analyses={body.get('analyses')!r}")
    record("isolation.other_device_id_echoed", body.get("device_id") == other,
           f"echoed={body.get('device_id')!r}")


# ---------- Scenario 5: cleanup ----------

def test_cleanup(device_id):
    if not device_id:
        record("cleanup.skipped", True, "no populated device id was created")
        return
    r = requests.delete(f"{BASE}/analyses", params={"device_id": device_id}, timeout=30)
    if r.status_code != 200:
        record("cleanup.delete_status_200", False, f"{r.status_code}: {r.text[:200]}")
        return
    deleted = r.json().get("deleted")
    record("cleanup.delete_status_200", True, f"deleted={deleted}")
    record("cleanup.deleted_count_2", deleted == 2, f"deleted={deleted}")

    # And export now shows 0
    r = requests.get(f"{BASE}/export", params={"device_id": device_id}, timeout=30)
    record("cleanup.post_delete_count_zero",
           r.status_code == 200 and r.json().get("count") == 0,
           f"status={r.status_code} count={r.json().get('count') if r.ok else 'N/A'}")


# ---------- main ----------

def main():
    print(f"Running export regression against {BASE}\n")
    test_empty_store()
    populated_device = None
    try:
        populated_device = test_populated_store()
    except Exception as e:
        record("populated.exception", False, repr(e))
    test_validation()
    if populated_device:
        try:
            test_isolation(populated_device)
        except Exception as e:
            record("isolation.exception", False, repr(e))
        try:
            test_cleanup(populated_device)
        except Exception as e:
            record("cleanup.exception", False, repr(e))

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print("\n" + "=" * 60)
    print(f"SUMMARY: {passed}/{total} assertions passed")
    print("=" * 60)
    failed = [(n, d) for n, ok, d in results if not ok]
    if failed:
        print("\nFAILED ASSERTIONS:")
        for n, d in failed:
            print(f"  - {n} :: {d}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
