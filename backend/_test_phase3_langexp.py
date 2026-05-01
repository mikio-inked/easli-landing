"""Phase-3 multi-source-language expansion regression tests for /api/analyze.

Runs against the public preview URL (EXPO_PUBLIC_BACKEND_URL + /api) or
http://localhost:8001/api as a fallback. Requires MISTRAL_API_KEY to be set
in /app/backend/.env — otherwise affected tests are SKIPPED.

Privacy: This script NEVER prints base64 blobs, OCR text, or full JSON result
payloads. Only short status strings and heuristics.
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Optional, Tuple

import httpx
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont


# ----------------------- env / url -----------------------------------------
ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or "http://localhost:8001"
).rstrip("/")
API = f"{BASE_URL}/api"

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "").strip()
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "klarpost_database")

TIMEOUT = httpx.Timeout(180.0, connect=15.0)


# ----------------------- tiny-PNG letter renderer --------------------------
def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_letter_png_b64(body: str, *, width: int = 1280, height: int = 900) -> str:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = _load_font(24)
    margin = 60
    x = margin
    y = margin
    line_gap = 8

    # Simple word-wrap
    max_w = width - 2 * margin
    for paragraph in body.split("\n"):
        if not paragraph.strip():
            y += 18
            continue
        words = paragraph.split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            w = draw.textlength(test, font=font)
            if w > max_w and line:
                draw.text((x, y), line, fill=(0, 0, 0), font=font)
                y += font.size + line_gap
                line = word
            else:
                line = test
        if line:
            draw.text((x, y), line, fill=(0, 0, 0), font=font)
            y += font.size + line_gap
        if y > height - margin - 40:
            break

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ----------------------- fixtures ------------------------------------------
ENGLISH_LETTER = (
    "HMRC\nHM Revenue & Customs\nBX9 1AS\n\n"
    "Dear Mr. Smith,\n\n"
    "Reference: PAYE/2024/UK-778901\n\n"
    "We have reviewed your tax return for the year ending 5 April 2024. "
    "According to our records, you have an outstanding balance of 342.50 GBP. "
    "Please make payment by 28 February 2026 to avoid late payment penalties "
    "and interest charges. You can pay online at gov.uk/pay-self-assessment "
    "or by bank transfer using the details above.\n\n"
    "If you believe this is incorrect, please contact us within 30 days.\n\n"
    "Yours sincerely,\n"
    "HM Revenue & Customs Compliance Team"
)

GERMAN_LETTER = (
    "Techniker Krankenkasse\nPostfach 640629\n22348 Hamburg\n\n"
    "Sehr geehrte Frau Mustermann,\n\n"
    "Mitgliedsnummer: A123456789\n\n"
    "mit diesem Schreiben moechten wir Sie ueber die Anpassung Ihres "
    "Krankenversicherungsbeitrags informieren. Ab dem 01.01.2026 betraegt "
    "Ihr monatlicher Beitrag 248,50 EUR. Bitte ueberweisen Sie den neuen "
    "Betrag rechtzeitig auf unser Konto.\n\n"
    "Bei Rueckfragen erreichen Sie uns unter 0800-285-85-85.\n\n"
    "Mit freundlichen Gruessen,\n"
    "Ihre Techniker Krankenkasse"
)

FRENCH_LETTER = (
    "Caisse d'Allocations Familiales\n75019 Paris\n\n"
    "Madame, Monsieur,\n\n"
    "Numero d'allocataire: FR-2026-44521\n\n"
    "Nous vous informons que votre dossier d'allocations familiales a ete "
    "examine. A compter du 1er mars 2026, le montant mensuel de vos "
    "prestations s'eleve a 185,40 euros. Ce montant sera verse "
    "automatiquement sur le compte bancaire enregistre dans votre dossier.\n\n"
    "Pour toute question, vous pouvez nous contacter au 3230 ou consulter "
    "votre espace personnel sur caf.fr.\n\n"
    "Veuillez agreer nos salutations distinguees,\n"
    "Le Directeur de la CAF"
)


# ----------------------- helpers -------------------------------------------
EN_STOP = {"the", "of", "and", "to", "your", "please", "we", "you", "this", "that", "have", "is"}
FR_COMMON = {"le", "la", "les", "de", "des", "votre", "vous", "nous", "pour", "sur", "par", "est", "au", "aux", "cette"}
DE_COMMON = {"der", "die", "das", "und", "sie", "ihr", "mit", "wir", "fuer", "für", "bis", "auf", "bei", "ist"}


def contains_any(text: str, words) -> bool:
    t = text.lower()
    return any(f" {w} " in f" {t} " for w in words)


def count_umlauts(text: str) -> int:
    return sum(1 for c in text if c in "äöüÄÖÜß")


def short(s: str, n: int = 80) -> str:
    s = (s or "").replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s


class TestOutcome:
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIPPED"


results: list[tuple[str, str, str]] = []  # (name, outcome, reason)


def record(name: str, outcome: str, reason: str = "") -> None:
    results.append((name, outcome, reason))
    tag = {"PASS": "✅", "FAIL": "❌", "SKIPPED": "⚠️"}.get(outcome, "•")
    print(f"  {tag} {outcome}: {name} — {reason}" if reason else f"  {tag} {outcome}: {name}")


def fail(name: str, reason: str) -> None:
    record(name, TestOutcome.FAIL, reason)


def skip(name: str, reason: str) -> None:
    record(name, TestOutcome.SKIP, reason)


def ok(name: str, reason: str = "") -> None:
    record(name, TestOutcome.PASS, reason)


# ----------------------- Mistral quota detection ---------------------------
def is_mistral_rate_limited(resp: httpx.Response) -> bool:
    if resp.status_code != 429:
        return False
    try:
        body = resp.json()
    except Exception:
        return "rate" in resp.text.lower()
    # Could be Mistral 429 (forwarded as 429 by our retry-exhaust path) or
    # our internal paywall 'test_limit_reached' — separate them.
    err = (body.get("error") or "").lower()
    if err in ("test_limit_reached", "translation_limit_reached"):
        return False  # our own paywall, not a Mistral quota issue
    msg = (body.get("message") or body.get("detail") or "").lower()
    return "rate" in msg or err in ("rate_limited", "")


# ----------------------- POST /api/analyze wrapper -------------------------
async def post_analyze(
    client: httpx.AsyncClient,
    device_id: str,
    body: str,
    *,
    target_language: str = "en",
) -> Tuple[int, dict | str]:
    b64 = render_letter_png_b64(body)
    payload = {
        "device_id": device_id,
        "target_language": target_language,
        "idempotency_key": str(uuid.uuid4()),
        "pages": [{"file_base64": b64, "mime_type": "image/png"}],
    }
    resp = await client.post(f"{API}/analyze", json=payload)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, resp.text[:200]


# ======================== tests ============================================
async def test_english_letter_analyze(client: httpx.AsyncClient) -> Optional[dict]:
    name = "test_english_letter_analyze"
    device_id = f"qa-phase3-en-{uuid.uuid4().hex[:8]}"

    status, body = await post_analyze(client, device_id, ENGLISH_LETTER, target_language="en")
    if status == 422 and isinstance(body, dict) and (body.get("error") == "unsupported_document_language"):
        fail(name, "422 unsupported_document_language — language gate still rejecting non-German")
        return None
    if isinstance(body, dict) and status == 429 and is_mistral_rate_limited_from_body(body):
        skip(name, "mistral_rate_limited")
        return None
    if status != 200:
        fail(name, f"HTTP {status} body={short(str(body), 200)}")
        return None

    if not isinstance(body, dict):
        fail(name, f"non-JSON body: {short(str(body), 200)}")
        return None

    result = body.get("result") or {}
    slc = (result.get("source_language_code") or "").lower()
    sl = result.get("source_language") or ""
    reply = result.get("reply_draft") or ""
    german_reply = result.get("german_reply_draft") or ""
    summary = result.get("summary_translated") or ""
    usage = body.get("usage") or {}

    checks = []
    checks.append(("source_language_code == 'en'", slc == "en"))
    checks.append(("source_language non-empty", bool(sl.strip())))
    checks.append(("reply_draft non-empty", bool(reply.strip())))
    checks.append(
        (
            "reply_draft looks English (stopwords, few umlauts)",
            contains_any(reply, EN_STOP) and count_umlauts(reply) <= 2,
        )
    )
    checks.append(("german_reply_draft == reply_draft", german_reply == reply))
    checks.append(("summary_translated non-empty", bool(summary.strip())))
    checks.append(("usage.free_analyses_used == 1", int(usage.get("free_analyses_used", 0)) == 1))

    failed = [desc for desc, passed in checks if not passed]
    if failed:
        fail(name, f"checks failed: {failed} | slc='{slc}' sl='{sl}' usage_free={usage.get('free_analyses_used')}")
        return None

    ok(name, f"slc='{slc}' reply_len={len(reply)} umlauts={count_umlauts(reply)} free_used={usage.get('free_analyses_used')}")
    # Attach IDs we need downstream
    body["_device_id"] = device_id
    return body


def is_mistral_rate_limited_from_body(body: dict) -> bool:
    err = (body.get("error") or "").lower()
    if err in ("test_limit_reached", "translation_limit_reached"):
        return False
    msg = (body.get("message") or body.get("detail") or "").lower()
    return "rate" in msg or err == "rate_limited" or "try again" in msg


async def test_german_letter_still_works(client: httpx.AsyncClient) -> Optional[dict]:
    name = "test_german_letter_still_works"
    device_id = f"qa-phase3-de-{uuid.uuid4().hex[:8]}"

    status, body = await post_analyze(client, device_id, GERMAN_LETTER, target_language="en")
    if isinstance(body, dict) and status == 429 and is_mistral_rate_limited_from_body(body):
        skip(name, "mistral_rate_limited")
        return None
    if status != 200 or not isinstance(body, dict):
        fail(name, f"HTTP {status} body={short(str(body), 200)}")
        return None

    result = body.get("result") or {}
    slc = (result.get("source_language_code") or "").lower()
    reply = result.get("reply_draft") or ""
    german_reply = result.get("german_reply_draft") or ""
    category = result.get("category") or ""
    risk_level = result.get("risk_level") or ""
    scam_warning = result.get("scam_warning")

    german_markers = (
        contains_any(reply, DE_COMMON)
        or count_umlauts(reply) >= 1
        or any(p in reply.lower() for p in ["sehr geehrte", "mit freundlichen", "grüßen", "gruessen", "beitrag"])
    )

    checks = [
        ("source_language_code == 'de'", slc == "de"),
        ("reply_draft non-empty", bool(reply.strip())),
        ("reply_draft in German", german_markers),
        ("german_reply_draft == reply_draft", german_reply == reply),
        ("category is a string", isinstance(category, str) and len(category) > 0),
        ("risk_level is one of green/yellow/red", risk_level in ("green", "yellow", "red")),
        ("scam_warning is bool", isinstance(scam_warning, bool)),
    ]
    failed = [desc for desc, passed in checks if not passed]
    if failed:
        fail(name, f"checks failed: {failed} | slc='{slc}' cat='{category}' risk='{risk_level}' scam={scam_warning}")
        return None

    ok(name, f"slc='{slc}' cat='{category}' risk='{risk_level}' scam={scam_warning} umlauts={count_umlauts(reply)}")
    body["_device_id"] = device_id
    return body


async def test_french_letter(client: httpx.AsyncClient) -> None:
    name = "test_french_letter"
    device_id = f"qa-phase3-fr-{uuid.uuid4().hex[:8]}"

    status, body = await post_analyze(client, device_id, FRENCH_LETTER, target_language="en")
    if isinstance(body, dict) and status == 429 and is_mistral_rate_limited_from_body(body):
        skip(name, "mistral_rate_limited")
        return
    if status != 200 or not isinstance(body, dict):
        fail(name, f"HTTP {status} body={short(str(body), 200)}")
        return

    result = body.get("result") or {}
    slc = (result.get("source_language_code") or "").lower()
    reply = result.get("reply_draft") or ""
    german_reply = result.get("german_reply_draft") or ""

    french_markers = contains_any(reply, FR_COMMON) or any(
        p in reply.lower() for p in ["madame", "monsieur", "cordialement", "veuillez", "bonjour"]
    )

    checks = [
        ("source_language_code == 'fr'", slc == "fr"),
        ("reply_draft non-empty", bool(reply.strip())),
        ("reply_draft in French", french_markers),
        ("german_reply_draft == reply_draft", german_reply == reply),
    ]
    failed = [desc for desc, passed in checks if not passed]
    if failed:
        fail(name, f"checks failed: {failed} | slc='{slc}' reply_len={len(reply)}")
        return

    ok(name, f"slc='{slc}' reply_len={len(reply)}")


async def test_translate_preserves_reply_draft_language(
    client: httpx.AsyncClient, english_body: Optional[dict]
) -> None:
    name = "test_translate_preserves_reply_draft_language"
    if not english_body:
        skip(name, "no english analysis from test 1")
        return

    analysis_id = english_body.get("id")
    device_id = english_body.get("_device_id")
    orig_result = english_body.get("result") or {}
    orig_reply = orig_result.get("reply_draft") or ""
    orig_german_reply = orig_result.get("german_reply_draft") or ""
    orig_summary = orig_result.get("summary_translated") or ""
    orig_slc = (orig_result.get("source_language_code") or "").lower()

    payload = {"device_id": device_id, "target_language": "tr"}
    try:
        resp = await client.post(f"{API}/analyses/{analysis_id}/translate", json=payload)
    except Exception as e:
        fail(name, f"POST /translate raised {type(e).__name__}: {e}")
        return

    if resp.status_code == 429:
        try:
            body = resp.json()
        except Exception:
            body = {}
        if is_mistral_rate_limited_from_body(body):
            skip(name, "mistral_rate_limited on /translate")
            return

    if resp.status_code != 200:
        fail(name, f"HTTP {resp.status_code} body={short(resp.text, 200)}")
        return

    try:
        body = resp.json()
    except Exception:
        fail(name, f"non-JSON body: {short(resp.text, 200)}")
        return

    result = body.get("result") or {}
    new_reply = result.get("reply_draft") or ""
    new_german_reply = result.get("german_reply_draft") or ""
    new_summary = result.get("summary_translated") or ""
    new_slc = (result.get("source_language_code") or "").lower()

    checks = [
        ("reply_draft unchanged (byte-identical)", new_reply == orig_reply),
        ("german_reply_draft unchanged", new_german_reply == orig_german_reply),
        ("summary_translated DIFFERENT (now Turkish)", new_summary and new_summary != orig_summary),
        ("source_language_code still 'en'", new_slc == "en"),
    ]
    failed = [desc for desc, passed in checks if not passed]
    if failed:
        fail(
            name,
            (
                f"checks failed: {failed} | new_slc='{new_slc}' "
                f"reply_changed={new_reply != orig_reply} "
                f"summary_changed={new_summary != orig_summary}"
            ),
        )
        return

    ok(name, f"slc='{new_slc}' reply unchanged, summary translated (len {len(new_summary)})")


async def test_legacy_german_reply_draft_still_read(client: httpx.AsyncClient) -> None:
    name = "test_legacy_german_reply_draft_still_read"
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except Exception as e:
        skip(name, f"motor not importable: {e}")
        return

    device_id = f"qa-phase3-legacy-{uuid.uuid4().hex[:8]}"
    analysis_id = str(uuid.uuid4())

    legacy_doc = {
        "id": analysis_id,
        "device_id": device_id,
        "target_language": "de_simple",
        "target_language_label": "Simple German (Einfaches Deutsch / Leichte Sprache)",
        "mime_type": "image/png",
        "created_at": "2024-01-01T00:00:00+00:00",
        "result": {
            "source_language": "German",
            # no source_language_code (legacy)
            "target_language": "Simple German (Einfaches Deutsch / Leichte Sprache)",
            "document_type": "Krankenkassenschreiben",
            "sender": "Techniker Krankenkasse",
            "summary_translated": "Ihre Krankenkasse aendert den Beitrag.",
            "simple_explanation_translated": "Sie zahlen ab Januar mehr.",
            "key_points": [],
            "deadlines": [],
            "required_actions": [],
            "risk_level": "yellow",
            "risk_reason": "",
            # LEGACY: only german_reply_draft, no reply_draft
            "german_reply_draft": "Sehr geehrte Damen und Herren, ich bitte um eine Bestaetigung. Mit freundlichen Gruessen.",
            "reply_draft_explanation_translated": "",
            "questions_to_ask": [],
            "uncertainties": [],
            "disclaimer": "KlarPost gibt keine Rechtsberatung.",
            "category": "insurance",
            "scam_warning": False,
            "scam_reason": "",
        },
        "translations": {},
    }

    motor_client = AsyncIOMotorClient(MONGO_URL)
    try:
        dbh = motor_client[DB_NAME]
        await dbh.analyses.insert_one(legacy_doc)

        resp = await client.get(f"{API}/analyses/{analysis_id}", params={"device_id": device_id})
        if resp.status_code == 500:
            fail(name, f"HTTP 500 from /analyses/{{id}} — legacy doc broke validation: {short(resp.text, 200)}")
            return
        if resp.status_code != 200:
            fail(name, f"HTTP {resp.status_code} body={short(resp.text, 200)}")
            return

        body = resp.json()
        result = body.get("result") or {}
        german_reply = result.get("german_reply_draft") or ""
        checks = [
            ("response validates (200)", True),
            ("german_reply_draft present", bool(german_reply.strip())),
        ]
        failed = [desc for desc, passed in checks if not passed]
        if failed:
            fail(name, f"checks failed: {failed}")
            return
        ok(name, f"german_reply_draft len={len(german_reply)}, reply_draft len={len(result.get('reply_draft') or '')}")
    finally:
        # cleanup
        try:
            await motor_client[DB_NAME].analyses.delete_one({"id": analysis_id, "device_id": device_id})
        except Exception:
            pass
        motor_client.close()


async def test_language_gate_no_more_422(client: httpx.AsyncClient) -> None:
    name = "test_language_gate_no_more_422"
    device_id = f"qa-phase3-gate-{uuid.uuid4().hex[:8]}"

    status, body = await post_analyze(client, device_id, ENGLISH_LETTER, target_language="en")
    if isinstance(body, dict) and status == 429 and is_mistral_rate_limited_from_body(body):
        skip(name, "mistral_rate_limited")
        return
    # The spec: MUST NOT be 422 unsupported_document_language.
    if status == 422:
        err = ""
        if isinstance(body, dict):
            err = (body.get("error") or body.get("detail") or "") or ""
        fail(name, f"still returning 422 (error='{err}') — hard-reject branch not removed")
        return
    if status != 200:
        fail(name, f"expected 200, got {status}, body={short(str(body), 200)}")
        return
    ok(name, f"HTTP {status} (no language-gate reject)")


async def test_retry_helper_regression() -> None:
    name = "test_retry_helper_regression (_test_retry.py)"
    script = ROOT / "_test_retry.py"
    if not script.exists():
        skip(name, f"{script} not found")
        return
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(ROOT),
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=180)
    except asyncio.TimeoutError:
        proc.kill()
        fail(name, "subprocess timeout (>180s)")
        return
    rc = proc.returncode
    out = (stdout or b"").decode("utf-8", errors="replace")
    if rc != 0:
        fail(name, f"rc={rc} stderr={(stderr or b'').decode('utf-8', errors='replace')[:200]}")
        return
    # Expect "ALL 6 TESTS PASSED" or similar
    m = re.search(r"(ALL\s+\d+\s+TESTS\s+PASSED|6/6|ALL.*PASSED)", out, re.IGNORECASE)
    if m:
        ok(name, m.group(0))
    else:
        ok(name, f"rc=0, out_tail={out.strip().splitlines()[-1] if out.strip() else '(empty)'}")


# ----------------------- driver --------------------------------------------
async def main() -> int:
    print(f"BASE_URL = {BASE_URL}")
    print(f"API      = {API}")

    if not MISTRAL_KEY:
        print("⚠️  MISTRAL_API_KEY not set — all Mistral-dependent tests will be SKIPPED.")

    # Smoke check the backend is reachable
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.get(f"{API}/")
            print(f"GET {API}/ -> {r.status_code}")
        except Exception as e:
            print(f"backend unreachable at {API}: {type(e).__name__}: {e}")
            return 2

        if not MISTRAL_KEY:
            skip("test_english_letter_analyze", "no MISTRAL_API_KEY")
            skip("test_german_letter_still_works", "no MISTRAL_API_KEY")
            skip("test_french_letter", "no MISTRAL_API_KEY")
            skip("test_translate_preserves_reply_draft_language", "no MISTRAL_API_KEY")
            skip("test_language_gate_no_more_422", "no MISTRAL_API_KEY")
            english_body = None
        else:
            print("\n[1/7] test_english_letter_analyze")
            english_body = await test_english_letter_analyze(client)

            print("\n[2/7] test_german_letter_still_works")
            await test_german_letter_still_works(client)

            print("\n[3/7] test_french_letter")
            await test_french_letter(client)

            print("\n[4/7] test_translate_preserves_reply_draft_language")
            await test_translate_preserves_reply_draft_language(client, english_body)

            print("\n[6/7] test_language_gate_no_more_422")
            await test_language_gate_no_more_422(client)

        print("\n[5/7] test_legacy_german_reply_draft_still_read")
        await test_legacy_german_reply_draft_still_read(client)

        # cleanup: wipe any device_ids we created
        try:
            for _, outcome, reason in results:
                pass
        except Exception:
            pass

    print("\n[7/7] test_retry_helper_regression")
    await test_retry_helper_regression()

    # ---- summary ----
    print("\n" + "=" * 72)
    passed = sum(1 for _, o, _ in results if o == "PASS")
    failed = sum(1 for _, o, _ in results if o == "FAIL")
    skipped = sum(1 for _, o, _ in results if o == "SKIPPED")
    total = len(results)
    print(f"SUMMARY: {passed}/{total} PASS  |  {failed} FAIL  |  {skipped} SKIPPED")
    for name, outcome, reason in results:
        tag = {"PASS": "✅", "FAIL": "❌", "SKIPPED": "⚠️"}.get(outcome, "•")
        print(f"  {tag} {outcome:>7}  {name}  {('— ' + reason) if reason else ''}")
    print("=" * 72)

    # cleanup any phase3 device_ids we created
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mc = AsyncIOMotorClient(MONGO_URL)
        r1 = await mc[DB_NAME].analyses.delete_many({"device_id": {"$regex": r"^qa-phase3-"}})
        r2 = await mc[DB_NAME].usage_records.delete_many({"device_id": {"$regex": r"^qa-phase3-"}})
        mc.close()
        print(f"cleanup: deleted {r1.deleted_count} analyses, {r2.deleted_count} usage_records")
    except Exception as e:
        print(f"cleanup skipped: {type(e).__name__}: {e}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
