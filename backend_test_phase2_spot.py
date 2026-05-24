#!/usr/bin/env python3
"""Phase 2 spot checks: extracted_entities, detected_country_code, French CPAM letter."""
import base64, io, json, time, uuid, sys, re
import requests
from PIL import Image, ImageDraw, ImageFont

BASE = open("/app/frontend/.env").read()
m = re.search(r"EXPO_PUBLIC_BACKEND_URL=(\S+)", BASE)
BASE = m.group(1).strip().strip('"').rstrip("/")
API = f"{BASE}/api"
DEVICE_ID = f"qa-phase2-spot-{uuid.uuid4().hex[:8]}"
print(f"API={API}  DEVICE_ID={DEVICE_ID}")

def render(lines, width=900, height=1200):
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except Exception:
        font = ImageFont.load_default()
    y = 40
    for ln in lines:
        draw.text((40, y), ln, fill="black", font=font)
        y += 34
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")

DE_LINES = [
    "Finanzamt Berlin-Mitte",
    "Hauptstrasse 12, 10115 Berlin",
    "",
    "Sehr geehrter Herr Mustermann,",
    "Steuernummer 27/466/78910",
    "Aktenzeichen: FA-2026-DE-0001",
    "Bitte zahlen Sie 482,50 EUR bis 30.07.2026",
    "IBAN: DE89 3704 0044 0532 0130 00",
    "Kontakt: Frau Schulz, schulz@finanzamt-berlin.de",
    "Telefon: 030 1234567",
    "Mit freundlichen Gruessen",
    "Finanzamt Berlin-Mitte",
]

FR_LINES = [
    "CPAM de Paris",
    "Caisse Primaire d'Assurance Maladie",
    "75019 Paris, France",
    "",
    "Madame, Monsieur,",
    "Numero de securite sociale: 1 85 03 75 116 001",
    "Reference dossier: CPAM-PAR-2026-04421",
    "Objet: Demande de remboursement de soins",
    "",
    "Veuillez nous faire parvenir avant le 15.06.2026",
    "le formulaire S3125 dument complete.",
    "",
    "Contact: Mme Dupont",
    "Email: dupont@cpam-paris.fr",
    "Telephone: 01 42 00 00 00",
    "",
    "Veuillez agreer, Madame, Monsieur,",
    "nos salutations distinguees.",
    "CPAM de Paris",
]

results = []
def rec(name, ok, note=""):
    s = "PASS" if ok else "FAIL"
    print(f"[{s}] {name} — {note}")
    results.append((name, ok, note))

def post(path, **kw):
    t0=time.time(); r = requests.post(f"{API}{path}", timeout=120, **kw)
    return r, (time.time()-t0)*1000

def get(path, **kw):
    t0=time.time(); r = requests.get(f"{API}{path}", timeout=60, **kw)
    return r, (time.time()-t0)*1000

def delete_(path, **kw):
    r = requests.delete(f"{API}{path}", timeout=60, **kw)
    return r

# Cleanup
delete_(f"/history/{DEVICE_ID}")

# Step A: DE analyze → extracted_entities keys
b64de = render(DE_LINES)
payload = {"device_id": DEVICE_ID, "target_language": "en", "file_base64": b64de,
           "mime_type": "image/png", "idempotency_key": str(uuid.uuid4())}
r, ms = post("/analyze", json=payload)
de_id = None
if r.status_code != 200:
    rec("A_analyze_de", False, f"status={r.status_code} body={r.text[:200]}")
else:
    env = r.json(); res = env.get("result") or {}
    de_id = env.get("id")
    ents = res.get("extracted_entities")
    expected = {"email","subject","reference_number","contact_person","organization"}
    if not isinstance(ents, dict):
        rec("A_analyze_de", False, f"extracted_entities not a dict, type={type(ents).__name__}")
    else:
        missing = expected - set(ents.keys())
        extra = set(ents.keys()) - expected
        ok = not missing
        rec("A_extracted_entities_keys", ok,
            f"keys={sorted(ents.keys())} missing={missing} extra={extra} sample={ents}")
        # detected_country_code on AnalysisResult
        dcc = res.get("detected_country_code", None)
        rec("A_result_detected_country_code", dcc is not None,
            f"value={dcc!r}")

# Step B: FR CPAM letter
b64fr = render(FR_LINES, height=1400)
payload2 = {"device_id": DEVICE_ID, "target_language": "en", "file_base64": b64fr,
            "mime_type": "image/png", "idempotency_key": str(uuid.uuid4())}
r2, ms2 = post("/analyze", json=payload2)
fr_id = None
if r2.status_code != 200:
    rec("B_analyze_fr", False, f"status={r2.status_code} body={r2.text[:200]}")
else:
    env2 = r2.json(); res2 = env2.get("result") or {}
    fr_id = env2.get("id")
    src = res2.get("source_language_code")
    dcc = res2.get("detected_country_code", "")
    sugg = res2.get("suggested_reply_language_code", None)
    # Per request: detected_country_code='FR' (or empty) and suggested_reply_language_code='fr'
    dcc_ok = dcc in ("FR", "")
    sugg_ok = sugg == "fr"
    src_ok = src == "fr"
    rec("B_source_language_code_fr", src_ok, f"src={src!r}")
    rec("B_detected_country_code_FR_or_empty", dcc_ok, f"dcc={dcc!r}")
    rec("B_suggested_reply_language_code_fr", sugg_ok, f"sugg={sugg!r}")
    # also confirm extracted_entities again
    ents2 = res2.get("extracted_entities")
    rec("B_extracted_entities_dict", isinstance(ents2, dict) and {"email","subject","reference_number","contact_person","organization"}.issubset(ents2.keys()),
        f"keys={sorted((ents2 or {}).keys())} sample={ents2}")

# Step C: GET /api/analyses — each item has detected_country_code key
r3, ms3 = get("/analyses", params={"device_id": DEVICE_ID})
if r3.status_code != 200:
    rec("C_list", False, f"status={r3.status_code}")
else:
    items = r3.json()
    if not isinstance(items, list) or len(items) < 1:
        rec("C_list", False, f"len={len(items) if isinstance(items, list) else 'NA'}")
    else:
        missing_key = [it.get("id") for it in items if "detected_country_code" not in it]
        rec("C_each_item_has_detected_country_code", not missing_key,
            f"n={len(items)} missing_dcc_on={missing_key} sample_dcc={[(it.get('id'), it.get('detected_country_code')) for it in items]}")

# Cleanup
delete_(f"/history/{DEVICE_ID}")

# Summary
pass_n = sum(1 for _,ok,_ in results if ok)
fail_n = sum(1 for _,ok,_ in results if not ok)
print(f"\n=== SPOT CHECK SUMMARY: {pass_n} PASS / {fail_n} FAIL ===")
for n,ok,note in results:
    print(f"  {'PASS' if ok else 'FAIL'} {n} — {note[:200]}")
sys.exit(0 if fail_n==0 else 1)
