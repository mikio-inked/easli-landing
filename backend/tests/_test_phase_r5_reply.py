"""
Phase-R5 Reply Assistant backend test suite.

Covers:
  1. /api/analyze returns new fields (extracted_entities, reply_options)
  2. Fallback options kick in on simple documents
  3. /api/analyses/{id}/generate-reply for canonical intents
  4. Invalid intent → 400
  5. Unknown analysis id → 404
  6. Reply contains no em-dash / en-dash
  7. /translate preserves extracted_entities and reply_options ids
  8. Regression: _test_phase3_langexp.py and _test_retry.py still pass

Usage:
  cd /app/backend && python3 _test_phase_r5_reply.py

Privacy: never prints base64, full OCR text, or full reply_text.
"""

import asyncio
import base64
import io
import os
import subprocess
import sys
import uuid
from typing import Any, Dict, List, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "http://localhost:8001"
API = BASE_URL.rstrip("/") + "/api"

# Mistral key must be present for most tests.
MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
try:
    with open("/app/backend/.env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("MISTRAL_API_KEY="):
                MISTRAL_KEY = line.strip().split("=", 1)[1].strip().strip('"')
                break
except Exception:
    pass


# ---------- small helpers ----------

def _preview(s: str, n: int = 80) -> str:
    if not s:
        return "''"
    s = s.replace("\n", " ")
    return (s[:n] + "…") if len(s) > n else s


def _render_png(lines: List[str], w: int = 1200, h: int = 1600) -> str:
    """Render the given lines to a PNG and return base64 (no data-url prefix)."""
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

# A truly "neutral info-only" letter — no deadline, no ask, no threat.
INFO_ONLY_LETTER = [
    "Stadtbibliothek München",
    "Sendlinger Straße 1",
    "",
    "Liebe Leserin, lieber Leser,",
    "",
    "wir freuen uns, Ihnen mitteilen zu dürfen, dass unsere",
    "Bibliothek ab dem 01. Juni 2026 ihre Öffnungszeiten",
    "erweitert. Neue Zeiten finden Sie auf unserer Webseite.",
    "",
    "Freundliche Grüße",
    "Ihr Bibliotheks-Team",
]


async def _post_analyze(
    client: httpx.AsyncClient, b64: str, device_id: str, target_language: str = "en"
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
    custom_instruction: str = "",
) -> httpx.Response:
    body: Dict[str, Any] = {"device_id": device_id, "intent": intent}
    if custom_instruction:
        body["custom_instruction"] = custom_instruction
    return await client.post(
        f"{API}/analyses/{analysis_id}/generate-reply", json=body, timeout=60
    )


# ---------- result tracking ----------

class Results:
    def __init__(self) -> None:
        self.items: List[Tuple[str, str, str]] = []  # (name, status, reason)

    def add(self, name: str, status: str, reason: str = "") -> None:
        self.items.append((name, status, reason))
        marker = {"PASS": "✓", "FAIL": "✗", "SKIPPED": "○"}.get(status, "?")
        print(f"  {marker} {status:8s} {name}  — {reason}")

    def summary(self) -> Tuple[int, int, int]:
        p = sum(1 for _, s, _ in self.items if s == "PASS")
        f = sum(1 for _, s, _ in self.items if s == "FAIL")
        sk = sum(1 for _, s, _ in self.items if s == "SKIPPED")
        return p, f, sk


# ---------- tests ----------

CANONICAL_IDS = {"inquiry", "extension", "confirm", "objection", "submit_documents", "cancel"}


async def test_analyze_returns_new_fields(
    client: httpx.AsyncClient, results: Results
) -> Dict[str, Any]:
    """Test 1 — returns populated extracted_entities + non-empty reply_options."""
    name = "test_analyze_returns_new_fields"
    device_id = f"qa-r5-{uuid.uuid4().hex[:12]}"
    b64 = _render_png(GERMAN_LETTER)
    try:
        r = await _post_analyze(client, b64, device_id, target_language="en")
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return {}
        if r.status_code == 500:
            results.add(name, "FAIL", f"HTTP 500 body={r.text[:200]}")
            return {}
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return {}
        data = r.json()
        result = data.get("result", {})
        analysis_id = data.get("id")

        # extracted_entities
        ee = result.get("extracted_entities")
        if not isinstance(ee, dict):
            results.add(name, "FAIL", f"extracted_entities not a dict: {type(ee).__name__}")
            return {}
        required = {"email", "subject", "reference_number", "contact_person", "organization"}
        missing = required - set(ee.keys())
        if missing:
            results.add(name, "FAIL", f"extracted_entities missing keys: {missing}")
            return {}
        for k in required:
            if not isinstance(ee.get(k), str):
                results.add(name, "FAIL", f"extracted_entities.{k} is not str")
                return {}

        # reply_options
        ro = result.get("reply_options")
        if not isinstance(ro, list) or not (2 <= len(ro) <= 6):
            results.add(name, "FAIL", f"reply_options length out of bounds: {len(ro) if isinstance(ro, list) else 'not-a-list'}")
            return {}
        for opt in ro:
            if not all(k in opt for k in ("id", "label", "reason", "recommended")):
                results.add(name, "FAIL", f"reply_option missing fields: {list(opt.keys())}")
                return {}
            if opt["id"] not in CANONICAL_IDS:
                results.add(name, "FAIL", f"non-canonical id: {opt['id']}")
                return {}
            if not isinstance(opt["label"], str) or not opt["label"].strip():
                results.add(name, "FAIL", f"empty label for id={opt['id']}")
                return {}
        rec_count = sum(1 for o in ro if o.get("recommended"))
        if rec_count != 1:
            results.add(name, "FAIL", f"expected exactly 1 recommended, got {rec_count}")
            return {}

        # privacy: do not print full content
        print(
            f"    → analysis_id={analysis_id[:8]}… reply_options ids="
            f"{[o['id'] for o in ro]} ee.email='{_preview(ee.get('email',''),40)}'"
        )
        results.add(name, "PASS", f"{len(ro)} reply_options, 1 recommended, all canonical")
        return {
            "analysis_id": analysis_id,
            "device_id": device_id,
            "result": result,
        }
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")
        return {}


async def test_analyze_fallback_options_on_simple_doc(
    client: httpx.AsyncClient, results: Results
) -> None:
    """Test 2 — even an info-only neutral notice gets reply_options (fallback)."""
    name = "test_analyze_fallback_options_on_simple_doc"
    device_id = f"qa-r5-fb-{uuid.uuid4().hex[:12]}"
    b64 = _render_png(INFO_ONLY_LETTER)
    try:
        r = await _post_analyze(client, b64, device_id, target_language="en")
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return
        if r.status_code == 500:
            results.add(name, "FAIL", f"HTTP 500 body={r.text[:200]}")
            return
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return
        ro = r.json().get("result", {}).get("reply_options", [])
        if not isinstance(ro, list) or len(ro) < 4:
            results.add(
                name, "FAIL",
                f"expected >=4 reply_options (fallback), got {len(ro) if isinstance(ro, list) else 'not-a-list'}",
            )
            return
        ids = [o.get("id") for o in ro]
        all_canonical = all(i in CANONICAL_IDS for i in ids)
        if not all_canonical:
            results.add(name, "FAIL", f"non-canonical ids in fallback: {ids}")
            return
        results.add(name, "PASS", f"reply_options len={len(ro)} ids={ids}")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


GERMAN_HINTS = ("sehr geehrte", "mit freundlichen", "grüßen", "grüssen", "grüß")
UMLAUTS = set("äöüÄÖÜß")


async def test_generate_reply_canonical_intents(
    client: httpx.AsyncClient, results: Results, ctx: Dict[str, Any]
) -> Dict[str, str]:
    """Test 3 — generate-reply for inquiry + extension returns 200 + non-empty + source-language reply."""
    name = "test_generate_reply_canonical_intents"
    if not ctx:
        results.add(name, "SKIPPED", "prereq analyze failed")
        return {}
    analysis_id = ctx["analysis_id"]
    device_id = ctx["device_id"]
    drafts: Dict[str, str] = {}
    try:
        for intent in ("inquiry", "extension"):
            r = await _post_generate_reply(client, analysis_id, device_id, intent)
            if r.status_code == 429 and "rate" in (r.text or "").lower():
                results.add(name, "SKIPPED", f"mistral_rate_limited on intent={intent}")
                return {}
            if r.status_code == 500:
                results.add(name, "FAIL", f"HTTP 500 on intent={intent} body={r.text[:200]}")
                return {}
            if r.status_code != 200:
                results.add(
                    name, "FAIL",
                    f"intent={intent} expected 200 got {r.status_code} body={r.text[:200]}",
                )
                return {}
            data = r.json()
            reply_text = data.get("reply_text", "")
            if not isinstance(reply_text, str) or len(reply_text) <= 50:
                results.add(name, "FAIL", f"intent={intent} reply_text too short: len={len(reply_text)}")
                return {}
            echoed = data.get("intent")
            if echoed != intent:
                results.add(name, "FAIL", f"intent mismatch: sent={intent} echoed={echoed}")
                return {}
            # Must NOT start with markdown / subject noise.
            lowered = reply_text.lstrip().lower()
            for bad in ("subject:", "betreff:", "```"):
                if lowered.startswith(bad):
                    results.add(
                        name, "FAIL",
                        f"intent={intent} reply_text starts with forbidden prefix {bad!r}",
                    )
                    return {}
            drafts[intent] = reply_text
            print(f"    → intent={intent} len={len(reply_text)} preview='{_preview(reply_text, 80)}'")

        # Divergence check
        if drafts["inquiry"].strip() == drafts["extension"].strip():
            results.add(name, "FAIL", "inquiry and extension returned IDENTICAL reply_text")
            return {}

        # Source-language heuristic: German source → German reply.
        combined = (drafts["inquiry"] + drafts["extension"]).lower()
        has_umlaut = any(c in UMLAUTS for c in (drafts["inquiry"] + drafts["extension"]))
        has_ger_phrase = any(h in combined for h in GERMAN_HINTS)
        if not (has_umlaut or has_ger_phrase):
            # Soft warning per spec
            print(
                f"    ⚠ SOFT WARNING: German source document produced a reply with "
                f"no umlauts and no German polite phrases. Might be English by mistake."
            )
            results.add(
                name, "PASS",
                "200 OK; differ; soft-warn: no German markers detected in reply",
            )
            return drafts
        results.add(
            name, "PASS",
            f"200 OK for inquiry+extension; divergent; German markers present (umlaut={has_umlaut}, phrase={has_ger_phrase})",
        )
        return drafts
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")
        return {}


async def test_generate_reply_invalid_intent(
    client: httpx.AsyncClient, results: Results, ctx: Dict[str, Any]
) -> None:
    """Test 4 — intent='foo_bar' → 400 with detail mentioning 'intent'."""
    name = "test_generate_reply_invalid_intent"
    if not ctx:
        results.add(name, "SKIPPED", "prereq analyze failed")
        return
    try:
        r = await _post_generate_reply(client, ctx["analysis_id"], ctx["device_id"], "foo_bar")
        if r.status_code != 400:
            results.add(name, "FAIL", f"expected 400 got {r.status_code} body={r.text[:200]}")
            return
        detail = ""
        try:
            detail = (r.json().get("detail") or "")
        except Exception:
            detail = r.text or ""
        if "intent" not in detail.lower():
            results.add(name, "FAIL", f"400 but detail missing 'intent': {detail[:120]!r}")
            return
        results.add(name, "PASS", f"400 with detail={detail[:80]!r}")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


async def test_generate_reply_unknown_analysis(
    client: httpx.AsyncClient, results: Results
) -> None:
    """Test 5 — unknown analysis id → 404."""
    name = "test_generate_reply_unknown_analysis"
    device_id = f"qa-r5-404-{uuid.uuid4().hex[:12]}"
    try:
        r = await _post_generate_reply(client, "does-not-exist", device_id, "inquiry")
        if r.status_code != 404:
            results.add(name, "FAIL", f"expected 404 got {r.status_code} body={r.text[:200]}")
            return
        results.add(name, "PASS", f"404 as expected")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


async def test_generate_reply_em_dash_clean(
    client: httpx.AsyncClient, results: Results, drafts: Dict[str, str]
) -> None:
    """Test 6 — reply_text contains NO em-dash or en-dash."""
    name = "test_generate_reply_em_dash_clean"
    if not drafts:
        results.add(name, "SKIPPED", "no drafts from test 3")
        return
    try:
        offences: List[str] = []
        for intent, text in drafts.items():
            if "—" in text:
                i = text.find("—")
                snippet = text[max(0, i - 20): i + 20]
                offences.append(f"intent={intent} em-dash at pos {i}: …{snippet}…")
            if "–" in text:
                i = text.find("–")
                snippet = text[max(0, i - 20): i + 20]
                offences.append(f"intent={intent} en-dash at pos {i}: …{snippet}…")
        if offences:
            results.add(name, "FAIL", "; ".join(offences)[:300])
            return
        results.add(name, "PASS", f"no em-/en-dash in {len(drafts)} drafts")
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


async def test_translate_preserves_extracted_entities(
    client: httpx.AsyncClient, results: Results, ctx: Dict[str, Any]
) -> None:
    """Test 7 — /translate to tr preserves extracted_entities and reply_options ids."""
    name = "test_translate_preserves_extracted_entities"
    if not ctx:
        results.add(name, "SKIPPED", "prereq analyze failed")
        return
    try:
        src = ctx["result"]
        src_ee = src.get("extracted_entities") or {}
        src_ro = src.get("reply_options") or []
        src_reply_draft = src.get("reply_draft") or ""
        src_german_reply = src.get("german_reply_draft") or ""

        r = await client.post(
            f"{API}/analyses/{ctx['analysis_id']}/translate",
            json={"device_id": ctx["device_id"], "target_language": "tr"},
            timeout=120,
        )
        if r.status_code == 429 and "rate" in (r.text or "").lower():
            results.add(name, "SKIPPED", "mistral_rate_limited")
            return
        if r.status_code == 500:
            results.add(name, "FAIL", f"HTTP 500 body={r.text[:200]}")
            return
        if r.status_code != 200:
            results.add(name, "FAIL", f"expected 200 got {r.status_code} body={r.text[:200]}")
            return

        tr_res = r.json().get("result") or r.json()
        tr_ee = tr_res.get("extracted_entities") or {}
        tr_ro = tr_res.get("reply_options") or []

        # (a) extracted_entities must be byte-identical
        for k in ("email", "subject", "reference_number", "contact_person", "organization"):
            if (src_ee.get(k) or "") != (tr_ee.get(k) or ""):
                results.add(
                    name, "FAIL",
                    f"extracted_entities.{k} changed: '{_preview(src_ee.get(k,''),40)}' -> '{_preview(tr_ee.get(k,''),40)}'",
                )
                return

        # (b) reply_options ids and recommended flags unchanged
        if len(tr_ro) != len(src_ro):
            results.add(name, "FAIL", f"reply_options length changed: {len(src_ro)} -> {len(tr_ro)}")
            return
        src_ids = [o.get("id") for o in src_ro]
        tr_ids = [o.get("id") for o in tr_ro]
        if src_ids != tr_ids:
            results.add(name, "FAIL", f"reply_options ids changed: {src_ids} -> {tr_ids}")
            return
        src_rec = [bool(o.get("recommended")) for o in src_ro]
        tr_rec = [bool(o.get("recommended")) for o in tr_ro]
        if src_rec != tr_rec:
            results.add(name, "FAIL", f"reply_options recommended flags changed: {src_rec} -> {tr_rec}")
            return

        # (c) labels may now be in Turkish — soft check.
        any_tr_char = any(any(c in "çğıöşüÇĞİÖŞÜ" for c in (o.get("label") or "")) for o in tr_ro)
        labels_changed = any(
            (src_o.get("label") or "") != (tr_o.get("label") or "")
            for src_o, tr_o in zip(src_ro, tr_ro)
        )
        label_note = (
            f"labels_changed={labels_changed} turkish_chars={any_tr_char}"
        )

        # (d) reply_draft / german_reply_draft unchanged
        if (tr_res.get("reply_draft") or "") != src_reply_draft:
            results.add(
                name, "FAIL",
                f"reply_draft changed after translate (should stay in source language)",
            )
            return
        if (tr_res.get("german_reply_draft") or "") != src_german_reply:
            results.add(
                name, "FAIL",
                f"german_reply_draft changed after translate",
            )
            return

        results.add(
            name, "PASS",
            f"ee byte-identical; ids+recommended unchanged; reply_draft stable; {label_note}",
        )
    except Exception as exc:
        results.add(name, "FAIL", f"exception: {type(exc).__name__}: {str(exc)[:200]}")


def run_existing_suite(path: str) -> Tuple[bool, str]:
    """Run an existing test script as a subprocess. Return (ok, tail)."""
    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=240, cwd="/app/backend",
        )
        ok = proc.returncode == 0
        tail = (proc.stdout or "").splitlines()
        last = tail[-1] if tail else ""
        return ok, last[:200]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def main() -> int:
    results = Results()
    print("=" * 78)
    print(f"Phase-R5 Reply Assistant backend tests — BASE_URL={BASE_URL}")
    print("=" * 78)

    if not MISTRAL_KEY:
        print("MISTRAL_API_KEY not found — skipping live Mistral tests.")
        results.add("mistral_key_available", "SKIPPED", "no key in env or .env")
        print()
        print("SUMMARY: 0 PASS / 0 FAIL / 1 SKIPPED")
        return 0

    # Sanity ping
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{API}/", timeout=10)
            if r.status_code != 200:
                print(f"!! /api/ not 200 (got {r.status_code}); proceeding anyway.")
        except Exception as exc:
            print(f"!! /api/ ping failed: {exc}")

        print("\n[1] test_analyze_returns_new_fields")
        ctx = await test_analyze_returns_new_fields(client, results)

        print("\n[2] test_analyze_fallback_options_on_simple_doc")
        await test_analyze_fallback_options_on_simple_doc(client, results)

        print("\n[3] test_generate_reply_canonical_intents")
        drafts = await test_generate_reply_canonical_intents(client, results, ctx)

        print("\n[4] test_generate_reply_invalid_intent")
        await test_generate_reply_invalid_intent(client, results, ctx)

        print("\n[5] test_generate_reply_unknown_analysis")
        await test_generate_reply_unknown_analysis(client, results)

        print("\n[6] test_generate_reply_em_dash_clean")
        await test_generate_reply_em_dash_clean(client, results, drafts)

        print("\n[7] test_translate_preserves_extracted_entities")
        await test_translate_preserves_extracted_entities(client, results, ctx)

        # Cleanup
        try:
            if ctx.get("device_id"):
                await client.delete(
                    f"{API}/history/{ctx['device_id']}", timeout=30
                )
        except Exception:
            pass

    print("\n[8] regression: _test_phase3_langexp.py")
    ok, tail = run_existing_suite("/app/backend/_test_phase3_langexp.py")
    results.add(
        "regression_phase3_langexp",
        "PASS" if ok else "FAIL",
        f"subprocess rc ok={ok} tail='{tail}'",
    )

    print("\n[9] regression: _test_retry.py")
    ok, tail = run_existing_suite("/app/backend/_test_retry.py")
    results.add(
        "regression_retry_helper",
        "PASS" if ok else "FAIL",
        f"subprocess rc ok={ok} tail='{tail}'",
    )

    p, f, s = results.summary()
    print()
    print("=" * 78)
    print(f"SUMMARY: {p} PASS / {f} FAIL / {s} SKIPPED  (total {p+f+s})")
    print("=" * 78)
    return 0 if f == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
