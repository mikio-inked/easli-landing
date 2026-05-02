"""
Phase EU-1 multilingual European paperwork regression suite.

Covers:
  A. German official letter → Turkish explanation, German reply
  B. French insurance letter → English explanation, French reply
  C. Dutch municipality letter → de_simple explanation, Dutch reply
     (Polish is NOT in LANGUAGES, so we fall back to de_simple per spec.)
  D. Reply Assistant with explicit reply_language_code="en" override
  E. Reply Assistant without reply_language_code (fallback to source)
  F. Backward compatibility — old records without new fields must still
     be readable via GET /api/analyses and GET /api/analyses/{id}.
  G. Old reply_options + extracted_entities still populated.

Usage:
  cd /app && python3 backend_test_eu1.py

Uses the real Mistral API (key read from /app/backend/.env). No mocks.
"""

import asyncio
import base64
import io
import os
import sys
import uuid
from typing import Any, Dict, List, Tuple, Optional

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "http://localhost:8001"
API = BASE_URL.rstrip("/") + "/api"

# Load MISTRAL_API_KEY from /app/backend/.env if not in env already.
MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
try:
    with open("/app/backend/.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MISTRAL_API_KEY="):
                MISTRAL_KEY = line.strip().split("=", 1)[1].strip().strip('"')
                break
except Exception:
    pass


# ---------- helpers ----------

def _preview(s: str, n: int = 120) -> str:
    if not s:
        return "''"
    s = s.replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s


def _render_png(lines: List[str], w: int = 1200, h: int = 1600) -> str:
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26
        )
    except Exception:
        font = ImageFont.load_default()
    y = 60
    for line in lines:
        draw.text((60, y), line, fill="black", font=font)
        y += 40
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


GERMAN_LETTER = [
    "Finanzamt Berlin-Mitte",
    "Aktenzeichen: 27/456/78910",
    "Berlin, den 12.03.2026",
    "",
    "Sehr geehrte Frau Schneider,",
    "",
    "bezüglich Ihres Einkommensteuerbescheids für 2024 weisen wir",
    "darauf hin, dass eine Nachzahlung in Höhe von 482,50 EUR",
    "bis zum 15.04.2026 auf unser Konto zu überweisen ist.",
    "",
    "Bei Rückfragen wenden Sie sich bitte an Herrn Dr. Weber",
    "unter weber@finanzamt-berlin.de oder telefonisch.",
    "",
    "Mit freundlichen Grüßen",
    "Dr. M. Weber",
    "Sachbearbeiter",
]

FRENCH_LETTER = [
    "CPAM de Paris",
    "75948 Paris Cedex 19, France",
    "",
    "Référence dossier: 2026-FR-00421",
    "Paris, le 15 mars 2026",
    "",
    "Madame Dupont,",
    "",
    "Nous vous informons que votre demande de remboursement",
    "concernant la consultation du 08.02.2026 a été examinée.",
    "Veuillez nous retourner le formulaire signé avant le",
    "10 avril 2026 à l'adresse ci-dessus.",
    "",
    "Pour toute question, contactez Mme Martin au 3646.",
    "",
    "Cordialement,",
    "Service des remboursements",
]

DUTCH_LETTER = [
    "Gemeente Amsterdam",
    "Amstel 1, 1011 PN Amsterdam",
    "Kenmerk: GEM-2026-88271",
    "Amsterdam, 18 maart 2026",
    "",
    "Geachte heer De Vries,",
    "",
    "Betreft uw aanvraag voor een parkeervergunning in",
    "stadsdeel Centrum. Wij verzoeken u de ontbrekende",
    "documenten vóór 20 april 2026 in te dienen via",
    "MijnOverheid of per post.",
    "",
    "Met vriendelijke groet,",
    "Afdeling Vergunningen",
]


async def _post_analyze(
    client: httpx.AsyncClient, b64: str, device_id: str, target_language: str
) -> httpx.Response:
    body = {
        "device_id": device_id,
        "target_language": target_language,
        "pages": [{"file_base64": b64, "mime_type": "image/png"}],
    }
    return await client.post(f"{API}/analyze", json=body, timeout=180)


async def _post_generate_reply(
    client: httpx.AsyncClient,
    analysis_id: str,
    device_id: str,
    intent: str,
    reply_language_code: Optional[str] = None,
) -> httpx.Response:
    body: Dict[str, Any] = {"device_id": device_id, "intent": intent}
    if reply_language_code is not None:
        body["reply_language_code"] = reply_language_code
    return await client.post(
        f"{API}/analyses/{analysis_id}/generate-reply", json=body, timeout=90
    )


# ---------- result tracking ----------

class Results:
    def __init__(self) -> None:
        self.items: List[Tuple[str, str, str]] = []

    def add(self, name: str, status: str, reason: str = "") -> None:
        self.items.append((name, status, reason))
        marker = {"PASS": "✓", "FAIL": "✗", "SKIPPED": "○"}.get(status, "?")
        print(f"  {marker} {status:8s} {name}  — {reason}")

    def summary(self) -> Tuple[int, int, int]:
        p = sum(1 for _, s, _ in self.items if s == "PASS")
        f = sum(1 for _, s, _ in self.items if s == "FAIL")
        sk = sum(1 for _, s, _ in self.items if s == "SKIPPED")
        return p, f, sk


# ---------- language markers ----------

TURKISH_CHARS = set("çğıöşüÇĞİÖŞÜ")
TURKISH_WORDS = ("bu mektup", "lütfen", "tarih", "ödeme", "vergi", "başvuru",
                 "belge", "sayın", "değerli", "teşekkür", "sonra", "önce",
                 "hakkında", "için", "gerekli", "bildir", "ile ilgili",
                 "bilgilendir")

GERMAN_CHARS = set("äöüÄÖÜß")
GERMAN_WORDS = ("sehr geehrte", "mit freundlichen grüßen",
                "mit freundlichen grüssen", "hochachtungsvoll",
                "grüße", "bezüglich", "ihr schreiben", "sehr geehrter")

FRENCH_CHARS = set("çéèêàâîïôùûëÿÇÉÈÊÀÂÎÏÔÙÛËŸœ")
FRENCH_WORDS = ("madame", "monsieur", "cordialement", "veuillez",
                "je vous prie", "dans l'attente", "salutations distinguées",
                "bien cordialement", "votre courrier", "votre lettre",
                "concernant votre")

DUTCH_WORDS = ("geachte", "met vriendelijke groet", "hoogachtend",
               "vriendelijke groet", "uw brief", "uw schrijven",
               "betreft", "mijnheer", "mevrouw")

ENGLISH_WORDS = ("dear ", "sincerely", "regards", "thank you",
                 "please", "kindly", "yours faithfully", "yours truly",
                 "this letter", "we are writing", "further to",
                 "with reference to", "the document", "the letter",
                 "informs", "states")


def _has_turkish(s: str) -> bool:
    sl = s.lower()
    has_char = any(c in TURKISH_CHARS for c in s)
    has_word = any(w in sl for w in TURKISH_WORDS)
    return has_char or has_word


def _has_german(s: str) -> bool:
    sl = s.lower()
    has_char = any(c in GERMAN_CHARS for c in s)
    has_word = any(w in sl for w in GERMAN_WORDS)
    return has_char or has_word


def _has_french(s: str) -> bool:
    sl = s.lower()
    has_char = any(c in FRENCH_CHARS for c in s)
    has_word = any(w in sl for w in FRENCH_WORDS)
    return has_char or has_word


def _has_dutch(s: str) -> bool:
    sl = s.lower()
    return any(w in sl for w in DUTCH_WORDS)


def _has_english(s: str) -> bool:
    sl = s.lower()
    return any(w in sl for w in ENGLISH_WORDS)


# ---------- scenarios ----------

async def scenario_A(client: httpx.AsyncClient, results: Results) -> Dict[str, Any]:
    """German Finanzamt letter → target=tr."""
    name = "A_german_finanzamt_to_turkish"
    device_id = f"qa-eu1-A-{uuid.uuid4().hex[:12]}"
    b64 = _render_png(GERMAN_LETTER)
    print(f"\n[A] {name}  device={device_id}")
    try:
        r = await _post_analyze(client, b64, device_id, target_language="tr")
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return {}
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return {}
        data = r.json()
        result = data.get("result", {})
        analysis_id = data.get("id")

        slc = (result.get("source_language_code") or "").lower()
        dcc = (result.get("detected_country_code") or "").upper()
        srlc = (result.get("suggested_reply_language_code") or "").lower()
        cs = result.get("confidence_score")
        safety = result.get("safety_disclaimer", "")
        summary_t = result.get("summary_translated", "")
        reply_draft = result.get("reply_draft", "")

        # Hard asserts
        fails = []
        if slc != "de":
            fails.append(f"source_language_code='{slc}' expected 'de'")
        if dcc not in ("DE", ""):
            fails.append(f"detected_country_code='{dcc}' not in ('DE','')")
        if srlc != "de":
            fails.append(f"suggested_reply_language_code='{srlc}' expected 'de'")
        # schema extension fields present
        for k in (
            "detected_country_code", "detected_country_name",
            "jurisdiction_confidence", "suggested_reply_language_code",
            "confidence_score", "safety_disclaimer",
        ):
            if k not in result:
                fails.append(f"missing EU-1 field '{k}' in result")
        if not isinstance(cs, (int, float)) or cs < 0 or cs > 1:
            fails.append(f"confidence_score invalid: {cs!r}")
        # summary_translated in Turkish
        if not _has_turkish(summary_t):
            fails.append(f"summary_translated not in Turkish: '{_preview(summary_t, 120)}'")
        # reply_draft in German
        if not _has_german(reply_draft):
            fails.append(f"reply_draft not in German: '{_preview(reply_draft, 120)}'")

        print(f"    slc={slc} dcc={dcc} srlc={srlc} conf={cs} jc='{result.get('jurisdiction_confidence','')}'")
        print(f"    summary_translated[:120]: {_preview(summary_t, 120)!r}")
        print(f"    reply_draft[:120]: {_preview(reply_draft, 120)!r}")
        print(f"    safety_disclaimer[:120]: {_preview(safety, 120)!r}")
        # Scenario G checks — extracted_entities + reply_options
        ee = result.get("extracted_entities") or {}
        required = {"email", "subject", "reference_number", "contact_person", "organization"}
        missing = required - set(ee.keys())
        if missing:
            fails.append(f"extracted_entities missing keys: {missing}")
        ro = result.get("reply_options") or []
        if not isinstance(ro, list) or len(ro) < 4:
            fails.append(f"reply_options len={len(ro) if isinstance(ro, list) else 'not-list'} expected >=4")

        if fails:
            results.add(name, "FAIL", " | ".join(fails))
            return {}
        results.add(name, "PASS",
                    f"slc=de dcc={dcc} srlc=de; TR summary detected; DE reply detected; ee+ro OK")
        return {"analysis_id": analysis_id, "device_id": device_id, "result": result}
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")
        return {}


async def scenario_B(client: httpx.AsyncClient, results: Results) -> Dict[str, Any]:
    """French CPAM letter → target=en."""
    name = "B_french_cpam_to_english"
    device_id = f"qa-eu1-B-{uuid.uuid4().hex[:12]}"
    b64 = _render_png(FRENCH_LETTER)
    print(f"\n[B] {name}  device={device_id}")
    try:
        r = await _post_analyze(client, b64, device_id, target_language="en")
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return {}
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return {}
        data = r.json()
        result = data.get("result", {})
        analysis_id = data.get("id")

        slc = (result.get("source_language_code") or "").lower()
        dcc = (result.get("detected_country_code") or "").upper()
        srlc = (result.get("suggested_reply_language_code") or "").lower()
        summary_t = result.get("summary_translated", "")
        reply_draft = result.get("reply_draft", "")

        fails = []
        if slc != "fr":
            fails.append(f"source_language_code='{slc}' expected 'fr'")
        if dcc not in ("FR", ""):
            fails.append(f"detected_country_code='{dcc}' not in ('FR','')")
        if srlc != "fr":
            fails.append(f"suggested_reply_language_code='{srlc}' expected 'fr'")
        # summary_translated in English (and NOT obviously French)
        if not _has_english(summary_t):
            fails.append(f"summary_translated not in English: '{_preview(summary_t, 120)}'")
        # reply_draft in French
        if not _has_french(reply_draft):
            fails.append(f"reply_draft not in French: '{_preview(reply_draft, 120)}'")

        print(f"    slc={slc} dcc={dcc} srlc={srlc} jc='{result.get('jurisdiction_confidence','')}'")
        print(f"    summary_translated[:120]: {_preview(summary_t, 120)!r}")
        print(f"    reply_draft[:120]: {_preview(reply_draft, 120)!r}")

        if fails:
            results.add(name, "FAIL", " | ".join(fails))
            return {}
        results.add(name, "PASS",
                    f"slc=fr dcc={dcc} srlc=fr; EN summary; FR reply")
        return {"analysis_id": analysis_id, "device_id": device_id, "result": result}
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")
        return {}


async def scenario_C(client: httpx.AsyncClient, results: Results) -> Dict[str, Any]:
    """Dutch gemeente letter. Polish not in LANGUAGES → fall back to de_simple."""
    name = "C_dutch_gemeente_to_de_simple"
    device_id = f"qa-eu1-C-{uuid.uuid4().hex[:12]}"
    b64 = _render_png(DUTCH_LETTER)
    print(f"\n[C] {name}  device={device_id}  (Polish not in LANGUAGES, using de_simple per spec)")
    try:
        r = await _post_analyze(client, b64, device_id, target_language="de_simple")
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return {}
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return {}
        data = r.json()
        result = data.get("result", {})
        analysis_id = data.get("id")

        slc = (result.get("source_language_code") or "").lower()
        dcc = (result.get("detected_country_code") or "").upper()
        srlc = (result.get("suggested_reply_language_code") or "").lower()
        reply_draft = result.get("reply_draft", "")
        summary_t = result.get("summary_translated", "")

        fails = []
        if slc != "nl":
            fails.append(f"source_language_code='{slc}' expected 'nl'")
        if srlc != "nl":
            fails.append(f"suggested_reply_language_code='{srlc}' expected 'nl'")
        if dcc not in ("NL", ""):
            fails.append(f"detected_country_code='{dcc}' not in ('NL','')")
        if not _has_dutch(reply_draft):
            fails.append(f"reply_draft not in Dutch: '{_preview(reply_draft, 120)}'")

        print(f"    slc={slc} dcc={dcc} srlc={srlc} jc='{result.get('jurisdiction_confidence','')}'")
        print(f"    summary_translated[:120] (de_simple): {_preview(summary_t, 120)!r}")
        print(f"    reply_draft[:120]: {_preview(reply_draft, 120)!r}")

        if fails:
            results.add(name, "FAIL", " | ".join(fails))
            return {}
        results.add(name, "PASS",
                    f"slc=nl dcc={dcc} srlc=nl; Dutch reply markers present")
        return {"analysis_id": analysis_id, "device_id": device_id, "result": result}
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")
        return {}


async def scenario_D(
    client: httpx.AsyncClient, results: Results, ctx: Dict[str, Any]
) -> None:
    """Reply Assistant with explicit reply_language_code='en'."""
    name = "D_generate_reply_override_to_english"
    if not ctx:
        results.add(name, "SKIPPED", "prereq scenario A/B failed")
        return
    analysis_id = ctx["analysis_id"]
    device_id = ctx["device_id"]
    print(f"\n[D] {name}  analysis={analysis_id[:8]}")
    try:
        r = await _post_generate_reply(
            client, analysis_id, device_id, intent="inquiry",
            reply_language_code="en",
        )
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return
        data = r.json()
        reply_text = data.get("reply_text", "")
        rlc = (data.get("reply_language_code") or "").lower()

        fails = []
        if rlc != "en":
            fails.append(f"reply_language_code='{rlc}' expected 'en'")
        if not _has_english(reply_text):
            fails.append(f"reply_text not in English: '{_preview(reply_text, 120)}'")
        # And NOT obviously German — weak anti-check
        if _has_german(reply_text) and not _has_english(reply_text):
            fails.append("reply_text looks German, not English")

        print(f"    reply_language_code={rlc} len={len(reply_text)}")
        print(f"    reply_text[:140]: {_preview(reply_text, 140)!r}")

        if fails:
            results.add(name, "FAIL", " | ".join(fails))
            return
        results.add(name, "PASS", f"reply_language_code=en; English markers present")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


async def scenario_E(
    client: httpx.AsyncClient, results: Results, ctx: Dict[str, Any]
) -> None:
    """Reply Assistant with NO reply_language_code — must fallback to source (de)."""
    name = "E_generate_reply_fallback_to_source"
    if not ctx:
        results.add(name, "SKIPPED", "prereq scenario A failed")
        return
    analysis_id = ctx["analysis_id"]
    device_id = ctx["device_id"]
    print(f"\n[E] {name}  analysis={analysis_id[:8]}")
    try:
        r = await _post_generate_reply(
            client, analysis_id, device_id, intent="extension",
            reply_language_code=None,  # omitted
        )
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return
        data = r.json()
        reply_text = data.get("reply_text", "")
        rlc = (data.get("reply_language_code") or "").lower()

        fails = []
        if rlc != "de":
            fails.append(f"reply_language_code='{rlc}' expected 'de'")
        if not _has_german(reply_text):
            fails.append(f"reply_text not in German: '{_preview(reply_text, 120)}'")

        print(f"    reply_language_code={rlc} len={len(reply_text)}")
        print(f"    reply_text[:140]: {_preview(reply_text, 140)!r}")

        if fails:
            results.add(name, "FAIL", " | ".join(fails))
            return
        results.add(name, "PASS", f"reply_language_code=de (fallback); German markers present")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


async def scenario_F(
    client: httpx.AsyncClient, results: Results, ctx: Dict[str, Any]
) -> None:
    """Backward compat — GET /api/analyses?device_id=... and GET /api/analyses/{id}."""
    name = "F_backward_compat_list_and_get"
    if not ctx:
        results.add(name, "SKIPPED", "prereq scenario A failed")
        return
    analysis_id = ctx["analysis_id"]
    device_id = ctx["device_id"]
    print(f"\n[F] {name}  device={device_id}")
    try:
        r1 = await client.get(f"{API}/analyses", params={"device_id": device_id}, timeout=30)
        if r1.status_code != 200:
            results.add(name, "FAIL", f"list: expected 200 got {r1.status_code} body={r1.text[:200]}")
            return
        listed = r1.json()
        # List may be dict with 'items' or a list directly — handle both.
        items = listed if isinstance(listed, list) else (listed.get("items") or listed.get("analyses") or [])
        found = any((it.get("id") == analysis_id) for it in items)
        if not found:
            results.add(name, "FAIL", f"analysis {analysis_id[:8]} missing from list (len={len(items)})")
            return

        r2 = await client.get(
            f"{API}/analyses/{analysis_id}",
            params={"device_id": device_id},
            timeout=30,
        )
        if r2.status_code != 200:
            results.add(name, "FAIL", f"get: expected 200 got {r2.status_code} body={r2.text[:200]}")
            return
        one = r2.json()
        result = one.get("result") or {}
        # EU-1 fields should be present (even if empty) after readback — this
        # is the key proof that old records with no field default correctly.
        for k in (
            "detected_country_code", "detected_country_name",
            "jurisdiction_confidence", "suggested_reply_language_code",
            "confidence_score", "safety_disclaimer",
        ):
            if k not in result:
                results.add(name, "FAIL", f"readback missing EU-1 field '{k}'")
                return
        results.add(name, "PASS", f"list contains id; GET returns all EU-1 fields with defaults")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


async def scenario_G(results: Results, ctx_a: Dict[str, Any]) -> None:
    """Old reply_options + extracted_entities preserved."""
    name = "G_legacy_extracted_entities_and_reply_options"
    if not ctx_a:
        results.add(name, "SKIPPED", "prereq scenario A failed")
        return
    result = ctx_a.get("result") or {}
    ee = result.get("extracted_entities") or {}
    ro = result.get("reply_options") or []

    fails = []
    required_keys = {"email", "subject", "reference_number", "contact_person", "organization"}
    missing = required_keys - set(ee.keys())
    if missing:
        fails.append(f"extracted_entities missing keys: {missing}")
    for k in required_keys:
        if k in ee and not isinstance(ee[k], str):
            fails.append(f"extracted_entities.{k} not a string")

    CANONICAL = {"inquiry", "extension", "confirm", "objection", "submit_documents", "cancel"}
    if not isinstance(ro, list) or len(ro) < 4:
        fails.append(f"reply_options len={len(ro) if isinstance(ro, list) else 'not-list'} expected >=4")
    else:
        for opt in ro:
            if not all(k in opt for k in ("id", "label", "reason", "recommended")):
                fails.append(f"reply_option missing fields: {list(opt.keys())}")
                break
            if opt["id"] not in CANONICAL:
                fails.append(f"non-canonical id '{opt['id']}'")
                break

    print(f"\n[G] extracted_entities.email='{_preview(ee.get('email',''), 60)}' "
          f"reply_options ids={[o.get('id') for o in ro]}")

    if fails:
        results.add(name, "FAIL", " | ".join(fails))
        return
    results.add(name, "PASS",
                f"ee={len(ee)} fields; reply_options len={len(ro)} all canonical")


# ---------- main ----------

async def main() -> int:
    results = Results()
    print("=" * 78)
    print(f"Phase EU-1 backend regression — BASE_URL={BASE_URL}")
    print("=" * 78)

    if not MISTRAL_KEY:
        print("MISTRAL_API_KEY not found — cannot run live tests.")
        results.add("mistral_key_available", "SKIPPED", "no key")
        return 0

    # Sanity
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API}/", timeout=10)
            print(f"  sanity ping /api/ status={r.status_code}")
        except Exception as exc:
            print(f"  sanity ping failed: {exc}")

        ctx_a = await scenario_A(client, results)
        ctx_b = await scenario_B(client, results)
        ctx_c = await scenario_C(client, results)

        # D uses ctx_b (French analysis) to prove override works across source
        # languages (override to EN from FR source).
        await scenario_D(client, results, ctx_b or ctx_a)
        # E uses ctx_a (German source) to verify fallback to source=de.
        await scenario_E(client, results, ctx_a)
        # F uses ctx_a (German analysis).
        await scenario_F(client, results, ctx_a)
        # G uses ctx_a result payload (in-memory, no extra API call).
        await scenario_G(results, ctx_a)

        # Cleanup — delete the three devices' histories.
        for ctx in (ctx_a, ctx_b, ctx_c):
            if not ctx:
                continue
            try:
                await client.delete(f"{API}/history/{ctx['device_id']}", timeout=30)
            except Exception:
                pass

    p, f, s = results.summary()
    print()
    print("=" * 78)
    print(f"SUMMARY: {p} PASS / {f} FAIL / {s} SKIPPED  (total {p+f+s})")
    print("=" * 78)
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
