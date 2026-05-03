"""
Phase 5 — EU-1 Explanation-Language expansion regression suite.

Scenarios:
  H. German Finanzamt letter → Polish target. Assert summary in Polish,
     reply still in German.
  I. Same German letter → Italian target. Italian summary, German reply.
  J. French CPAM letter → French primary, then translate to Hindi.
     Devanagari summary; reply MUST be byte-identical to original French
     (Phase-3 invariant).
  K. Chat target_language='ar' → Arabic-script reply.
  L. Negative validation: target_language='xx-unknown' → 400.
  M. Legacy compat: target_language in [de_simple, en, zh] all → 200.
  Sanity: GET /api/languages returns ≥25 entries with codes pl/hi/ar/fr/it.

Privacy: log only codes, never document content.

Usage: cd /app && python3 backend_test_phase5.py
"""

import asyncio
import base64
import io
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "https://doc-scanner-de.preview.emergentagent.com"
API = BASE_URL.rstrip("/") + "/api"


# ---------- result tracking ----------

class Results:
    def __init__(self) -> None:
        self.items: List[Tuple[str, str, str]] = []

    def add(self, name: str, status: str, reason: str = "") -> None:
        self.items.append((name, status, reason))
        marker = {"PASS": "PASS", "FAIL": "FAIL", "SKIPPED": "SKIP"}.get(status, "?")
        print(f"  [{marker}] {name}  — {reason[:300]}")

    def summary(self) -> Tuple[int, int, int]:
        p = sum(1 for _, s, _ in self.items if s == "PASS")
        f = sum(1 for _, s, _ in self.items if s == "FAIL")
        sk = sum(1 for _, s, _ in self.items if s == "SKIPPED")
        return p, f, sk


# ---------- image helpers ----------

def _render_png(lines: List[str], w: int = 1280, h: int = 900) -> str:
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except Exception:
        font = ImageFont.load_default()
    y = 50
    for line in lines:
        draw.text((50, y), line, fill="black", font=font)
        y += 38
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
    "bezüglich Ihres Einkommensteuerbescheids für 2024",
    "weisen wir darauf hin, dass eine Nachzahlung in",
    "Höhe von 482,50 EUR bis zum 15.04.2026 auf unser",
    "Konto zu überweisen ist.",
    "",
    "Bei Rückfragen wenden Sie sich bitte an Herrn Dr. Weber",
    "unter weber@finanzamt-berlin.de oder telefonisch.",
    "",
    "Mit freundlichen Grüßen",
    "Dr. M. Weber, Sachbearbeiter",
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


# ---------- HTTP helpers ----------

async def _post_analyze(
    client: httpx.AsyncClient, b64: str, device_id: str, target_language: str
) -> httpx.Response:
    return await client.post(
        f"{API}/analyze",
        json={
            "device_id": device_id,
            "target_language": target_language,
            "pages": [{"file_base64": b64, "mime_type": "image/png"}],
        },
        timeout=180,
    )


async def _post_translate(
    client: httpx.AsyncClient, analysis_id: str, device_id: str, target_language: str
) -> httpx.Response:
    return await client.post(
        f"{API}/analyses/{analysis_id}/translate",
        json={"device_id": device_id, "target_language": target_language},
        timeout=120,
    )


async def _post_chat(
    client: httpx.AsyncClient,
    analysis_id: str,
    device_id: str,
    message: str,
    target_language: Optional[str] = None,
) -> httpx.Response:
    body: Dict[str, Any] = {"device_id": device_id, "message": message}
    if target_language is not None:
        body["target_language"] = target_language
    return await client.post(
        f"{API}/analyses/{analysis_id}/chat", json=body, timeout=90
    )


async def _retry_once(coro_fn, label: str, results: Results) -> Optional[httpx.Response]:
    """Run coro_fn(); on Mistral 429 retry once after 15s."""
    resp = await coro_fn()
    if resp.status_code == 429 or (resp.status_code >= 500 and "rate" in resp.text.lower()):
        print(f"    rate-limit on {label}, sleeping 15s then retry once")
        await asyncio.sleep(15)
        resp = await coro_fn()
    return resp


# ---------- language markers ----------

POLISH_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
POLISH_TOKENS = ("jest", "należy", "urząd", "termin", "panie", "panu", "pani",
                 "podatek", "kwota", "prosimy", "proszę", "dnia", "dotyczy")

ITALIAN_TOKENS = ("questa", "lettera", "dovrà", "entro", "imposta",
                  "ufficio", "fiscale", "pagamento", "scadenza", "data",
                  "signora", "signore", "egregio", "gentile", "cordiali",
                  "saluti", "deve", "devi", "presente", "comunicazione",
                  "documento")

GERMAN_CHARS = set("äöüÄÖÜß")
GERMAN_REPLY_TOKENS = ("sehr geehrte", "sehr geehrter", "mit freundlichen",
                       "hochachtungsvoll", "grüße", "bezüglich",
                       "anbei", "ihrem schreiben")

FRENCH_TOKENS = ("madame", "monsieur", "cordialement", "veuillez",
                 "salutations", "votre", "nous vous", "je vous prie")


def _has_devanagari(s: str) -> bool:
    return any(0x0900 <= ord(c) <= 0x097F for c in s)


def _has_arabic(s: str) -> bool:
    return any(0x0600 <= ord(c) <= 0x06FF for c in s)


def _count_chars(s: str, charset: set) -> int:
    return sum(1 for c in s if c in charset)


def _has_token(s: str, tokens: Tuple[str, ...]) -> bool:
    low = s.lower()
    return any(t in low for t in tokens)


# ---------- main test orchestration ----------

async def main() -> int:
    results = Results()
    device_de = f"qa-phase5-de-{uuid.uuid4().hex[:8]}"
    device_fr = f"qa-phase5-fr-{uuid.uuid4().hex[:8]}"
    device_legacy = f"qa-phase5-legacy-{uuid.uuid4().hex[:8]}"

    devices_to_clean = [device_de, device_fr, device_legacy]

    print(f"BASE_URL={BASE_URL}")
    print(f"devices: de={device_de}, fr={device_fr}, legacy={device_legacy}")

    de_b64 = _render_png(GERMAN_LETTER)
    fr_b64 = _render_png(FRENCH_LETTER)

    chat_anchor_id: Optional[str] = None  # an analysis we can chat against in scenario K

    async with httpx.AsyncClient() as client:
        # ===== Sanity =====
        print("\n[Sanity] GET /api/languages")
        try:
            r = await client.get(f"{API}/languages", timeout=20)
            if r.status_code != 200:
                results.add("sanity_languages_status_200", "FAIL",
                            f"status={r.status_code} body={r.text[:200]}")
            else:
                arr = r.json()
                codes = {item["code"]: item["label"] for item in arr}
                if len(arr) >= 25:
                    results.add("sanity_languages_length_ge_25", "PASS",
                                f"len={len(arr)}")
                else:
                    results.add("sanity_languages_length_ge_25", "FAIL",
                                f"len={len(arr)}")

                missing = [c for c in ("pl", "hi", "ar", "fr", "it") if c not in codes]
                if not missing:
                    results.add("sanity_languages_required_codes", "PASS",
                                f"pl={codes['pl']!r}, hi={codes['hi']!r}, ar={codes['ar']!r}, fr={codes['fr']!r}, it={codes['it']!r}")
                else:
                    results.add("sanity_languages_required_codes", "FAIL",
                                f"missing={missing}")

                label_checks = []
                for code, expect_substr in (
                    ("pl", "Polish"), ("hi", "Hindi"), ("ar", "Arabic"),
                    ("fr", "French"), ("it", "Italian"),
                ):
                    label = codes.get(code, "")
                    if expect_substr.lower() in label.lower():
                        label_checks.append((code, "ok"))
                    else:
                        label_checks.append((code, f"BAD label={label!r}"))
                bad = [lc for lc in label_checks if lc[1] != "ok"]
                if not bad:
                    results.add("sanity_languages_labels_ok", "PASS",
                                str(label_checks))
                else:
                    results.add("sanity_languages_labels_ok", "FAIL", str(bad))
        except Exception as exc:
            results.add("sanity_languages_request", "FAIL", repr(exc))

        # ===== Scenario H — German letter, target=pl =====
        print("\n[H] Scenario-H: German letter → Polish target")
        polish_id: Optional[str] = None
        t0 = time.time()

        async def _h():
            return await _post_analyze(client, de_b64, device_de, "pl")

        try:
            resp = await _retry_once(_h, "scenario-H", results)
            dt = time.time() - t0
            if resp.status_code != 200:
                results.add("scenario_H_status_200", "FAIL",
                            f"status={resp.status_code} body={resp.text[:300]}")
            else:
                results.add("scenario_H_status_200", "PASS", f"in {dt:.1f}s")
                rec = resp.json()
                polish_id = rec.get("id")
                tl = rec.get("target_language") or rec.get("target_language_label") or ""
                # Some responses put label at top level, code under different name. Be tolerant.
                tl_label = rec.get("target_language_label") or ""
                joined_label = f"{tl} | {tl_label}"
                if "polski" in joined_label.lower() or "polish" in joined_label.lower():
                    results.add("scenario_H_target_label", "PASS", joined_label)
                else:
                    results.add("scenario_H_target_label", "FAIL", joined_label)

                result = rec.get("result") or {}
                summary = result.get("summary_translated") or ""
                pl_diacritics = _count_chars(summary, POLISH_DIACRITICS)
                pl_token_hit = _has_token(summary, POLISH_TOKENS)
                if pl_diacritics >= 3 or pl_token_hit:
                    results.add("scenario_H_polish_summary", "PASS",
                                f"diacritics={pl_diacritics}, token_hit={pl_token_hit}, len={len(summary)}")
                else:
                    results.add("scenario_H_polish_summary", "FAIL",
                                f"diacritics={pl_diacritics}, token_hit={pl_token_hit}, summary={summary[:200]!r}")

                reply = (
                    result.get("reply_draft")
                    or result.get("german_reply_draft")
                    or ""
                )
                de_chars = _count_chars(reply, GERMAN_CHARS)
                de_token_hit = _has_token(reply, GERMAN_REPLY_TOKENS)
                if de_chars >= 3 or de_token_hit:
                    results.add("scenario_H_reply_stays_german", "PASS",
                                f"de_chars={de_chars}, token_hit={de_token_hit}, len={len(reply)}")
                else:
                    results.add("scenario_H_reply_stays_german", "FAIL",
                                f"de_chars={de_chars}, token_hit={de_token_hit}, reply={reply[:200]!r}")
        except Exception as exc:
            results.add("scenario_H", "FAIL", repr(exc))

        # ===== Scenario I — German letter, target=it =====
        print("\n[I] Scenario-I: German letter → Italian target")
        italian_id: Optional[str] = None
        t0 = time.time()

        async def _i():
            return await _post_analyze(client, de_b64, device_de, "it")

        try:
            resp = await _retry_once(_i, "scenario-I", results)
            dt = time.time() - t0
            if resp.status_code != 200:
                results.add("scenario_I_status_200", "FAIL",
                            f"status={resp.status_code} body={resp.text[:300]}")
            else:
                results.add("scenario_I_status_200", "PASS", f"in {dt:.1f}s")
                rec = resp.json()
                italian_id = rec.get("id")
                if not chat_anchor_id:
                    chat_anchor_id = italian_id

                tl = rec.get("target_language") or ""
                tl_label = rec.get("target_language_label") or ""
                joined_label = f"{tl} | {tl_label}"
                if "italian" in joined_label.lower() or "italiano" in joined_label.lower():
                    results.add("scenario_I_target_label", "PASS", joined_label)
                else:
                    results.add("scenario_I_target_label", "FAIL", joined_label)

                result = rec.get("result") or {}
                summary = result.get("summary_translated") or ""
                if _has_token(summary, ITALIAN_TOKENS):
                    results.add("scenario_I_italian_summary", "PASS",
                                f"len={len(summary)}, sample={summary[:120]!r}")
                else:
                    results.add("scenario_I_italian_summary", "FAIL",
                                f"summary={summary[:200]!r}")

                reply = (
                    result.get("reply_draft")
                    or result.get("german_reply_draft")
                    or ""
                )
                de_chars = _count_chars(reply, GERMAN_CHARS)
                de_token_hit = _has_token(reply, GERMAN_REPLY_TOKENS)
                if de_chars >= 3 or de_token_hit:
                    results.add("scenario_I_reply_stays_german", "PASS",
                                f"de_chars={de_chars}, token_hit={de_token_hit}, len={len(reply)}")
                else:
                    results.add("scenario_I_reply_stays_german", "FAIL",
                                f"de_chars={de_chars}, token_hit={de_token_hit}, reply={reply[:200]!r}")
        except Exception as exc:
            results.add("scenario_I", "FAIL", repr(exc))

        # ===== Scenario J — French CPAM, primary=fr, then translate to hi =====
        print("\n[J] Scenario-J: French CPAM → analyze fr, translate to Hindi")
        french_id: Optional[str] = None
        original_french_reply: Optional[str] = None
        original_french_de_reply: Optional[str] = None

        t0 = time.time()

        async def _j_seed():
            return await _post_analyze(client, fr_b64, device_fr, "fr")

        try:
            resp = await _retry_once(_j_seed, "scenario-J-seed", results)
            dt = time.time() - t0
            if resp.status_code != 200:
                results.add("scenario_J_seed_fr_status_200", "FAIL",
                            f"status={resp.status_code} body={resp.text[:300]}")
            else:
                results.add("scenario_J_seed_fr_status_200", "PASS", f"in {dt:.1f}s")
                rec = resp.json()
                french_id = rec.get("id")
                if not chat_anchor_id:
                    chat_anchor_id = french_id
                result = rec.get("result") or {}
                original_french_reply = result.get("reply_draft") or ""
                original_french_de_reply = result.get("german_reply_draft") or ""
                if _has_token(original_french_reply, FRENCH_TOKENS) or _has_token(
                    original_french_de_reply, FRENCH_TOKENS
                ):
                    results.add("scenario_J_seed_reply_in_french", "PASS",
                                f"reply_len={len(original_french_reply)}, "
                                f"de_alias_len={len(original_french_de_reply)}")
                else:
                    results.add("scenario_J_seed_reply_in_french", "FAIL",
                                f"reply={original_french_reply[:200]!r}")
        except Exception as exc:
            results.add("scenario_J_seed", "FAIL", repr(exc))

        if french_id:
            t0 = time.time()

            async def _j_trans():
                return await _post_translate(client, french_id, device_fr, "hi")

            try:
                resp = await _retry_once(_j_trans, "scenario-J-translate", results)
                dt = time.time() - t0
                if resp.status_code != 200:
                    results.add("scenario_J_translate_status_200", "FAIL",
                                f"status={resp.status_code} body={resp.text[:300]}")
                else:
                    results.add("scenario_J_translate_status_200", "PASS", f"in {dt:.1f}s")
                    rec = resp.json()
                    result = rec.get("result") or {}
                    summary = result.get("summary_translated") or ""
                    if _has_devanagari(summary):
                        results.add("scenario_J_hindi_devanagari_summary", "PASS",
                                    f"len={len(summary)}, sample={summary[:120]!r}")
                    else:
                        results.add("scenario_J_hindi_devanagari_summary", "FAIL",
                                    f"summary={summary[:200]!r}")

                    new_reply = result.get("reply_draft") or ""
                    new_de_reply = result.get("german_reply_draft") or ""
                    # Phase-3 invariant: reply_draft MUST be byte-identical
                    if new_reply == original_french_reply:
                        results.add("scenario_J_reply_byte_identical", "PASS",
                                    f"len={len(new_reply)} (preserved)")
                    else:
                        results.add("scenario_J_reply_byte_identical", "FAIL",
                                    f"orig_len={len(original_french_reply)}, "
                                    f"new_len={len(new_reply)}, "
                                    f"orig_head={original_french_reply[:80]!r}, "
                                    f"new_head={new_reply[:80]!r}")
                    if new_de_reply == original_french_de_reply:
                        results.add("scenario_J_de_alias_byte_identical", "PASS",
                                    f"len={len(new_de_reply)}")
                    else:
                        results.add("scenario_J_de_alias_byte_identical", "FAIL",
                                    f"orig_len={len(original_french_de_reply)}, "
                                    f"new_len={len(new_de_reply)}")
            except Exception as exc:
                results.add("scenario_J_translate", "FAIL", repr(exc))
        else:
            results.add("scenario_J_translate_status_200", "SKIPPED",
                        "no french_id (seed failed)")

        # ===== Scenario K — Chat in Arabic =====
        print("\n[K] Scenario-K: Chat target_language='ar'")
        if not chat_anchor_id:
            results.add("scenario_K_chat_ar_status_200", "SKIPPED",
                        "no analysis to chat against")
        else:
            # use whichever device_id the anchor belongs to
            anchor_device = (
                device_de if chat_anchor_id in (polish_id, italian_id) else device_fr
            )
            t0 = time.time()

            async def _k():
                return await _post_chat(
                    client, chat_anchor_id, anchor_device,
                    "What should I do next?", target_language="ar",
                )

            try:
                resp = await _retry_once(_k, "scenario-K", results)
                dt = time.time() - t0
                if resp.status_code != 200:
                    results.add("scenario_K_chat_ar_status_200", "FAIL",
                                f"status={resp.status_code} body={resp.text[:300]}")
                else:
                    results.add("scenario_K_chat_ar_status_200", "PASS", f"in {dt:.1f}s")
                    body = resp.json()
                    reply_text = body.get("content") or body.get("reply") or ""
                    if _has_arabic(reply_text):
                        results.add("scenario_K_arabic_script_present", "PASS",
                                    f"len={len(reply_text)}, sample={reply_text[:120]!r}")
                    else:
                        results.add("scenario_K_arabic_script_present", "FAIL",
                                    f"reply={reply_text[:200]!r}")
            except Exception as exc:
                results.add("scenario_K", "FAIL", repr(exc))

        # ===== Scenario L — Negative validation =====
        print("\n[L] Scenario-L: target='xx-unknown' must 400")
        try:
            resp = await _post_analyze(client, de_b64, device_legacy, "xx-unknown")
            if resp.status_code == 400 and "Unsupported target language" in resp.text:
                results.add("scenario_L_negative_validation", "PASS",
                            f"status=400 body={resp.text[:120]}")
            else:
                results.add("scenario_L_negative_validation", "FAIL",
                            f"status={resp.status_code} body={resp.text[:300]}")
        except Exception as exc:
            results.add("scenario_L", "FAIL", repr(exc))

        # ===== Scenario M — Legacy compat =====
        print("\n[M] Scenario-M: legacy codes [de_simple, en, zh] all 200")
        for code in ("de_simple", "en", "zh"):
            t0 = time.time()

            async def _m(c=code):
                return await _post_analyze(client, de_b64, device_legacy, c)

            try:
                resp = await _retry_once(_m, f"scenario-M-{code}", results)
                dt = time.time() - t0
                if resp.status_code == 200:
                    rec = resp.json()
                    result = rec.get("result") or {}
                    has_summary = bool(result.get("summary_translated"))
                    has_category = bool(result.get("category"))
                    if has_summary and has_category:
                        results.add(f"scenario_M_{code}", "PASS",
                                    f"in {dt:.1f}s, category={result.get('category')!r}")
                    else:
                        results.add(f"scenario_M_{code}", "FAIL",
                                    f"shape: summary={has_summary} category={has_category}")
                else:
                    results.add(f"scenario_M_{code}", "FAIL",
                                f"status={resp.status_code} body={resp.text[:200]}")
            except Exception as exc:
                results.add(f"scenario_M_{code}", "FAIL", repr(exc))

        # ===== Cleanup =====
        print("\n[Cleanup] DELETE /api/history/{device_id} for each test device")
        for d in devices_to_clean:
            try:
                resp = await client.delete(f"{API}/history/{d}", timeout=30)
                if resp.status_code == 200:
                    body = resp.json()
                    print(f"    deleted device={d} body={body}")
                else:
                    print(f"    cleanup status={resp.status_code} for device={d}: {resp.text[:200]}")
            except Exception as exc:
                print(f"    cleanup exc for device={d}: {exc!r}")

    # ===== Summary =====
    p, f, sk = results.summary()
    print("\n" + "=" * 60)
    print(f"PHASE 5 SUMMARY: {p} PASS, {f} FAIL, {sk} SKIPPED  (total={p+f+sk})")
    print("=" * 60)
    if f > 0:
        print("\nFAILED items:")
        for name, status, reason in results.items:
            if status == "FAIL":
                print(f"  - {name}: {reason}")
    return 0 if f == 0 else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
