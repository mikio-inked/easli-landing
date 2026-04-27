#!/usr/bin/env python3
"""KlarPost — Change-language-after-analysis (translate endpoint) regression.

Covers:
  1. /api/analyses/{id}/translate end-to-end for all 6 non-primary languages
  2. Cache hits (translations + primary)
  3. Invalid input + 404 scope isolation
  4. Free-analyses quota isolation across translations
  5. GET /api/analyses/{id} returns translations dict
  6. Chat target_language override
  7. Privacy log audit
  8. /app/backend/_test_retry.py regression
  9. Existing /api/analyze still works
 10. DELETE /api/history/{device_id} cleanup
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont


# ----- Config --------------------------------------------------------------

def _load_backend_url() -> str:
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL not found")


BASE_URL = _load_backend_url().rstrip("/") + "/api"
TIMEOUT_ANALYZE = 90
TIMEOUT_TRANSLATE = 60
TIMEOUT_SHORT = 30

FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

GERMAN_TEXT_LINES = [
    "Deutsche Telekom AG",
    "Sehr geehrte Frau Muster",
    "Betrag 123,45 EUR bis 28.02.2026",
    "IBAN DE89 3704 0044 0532 0130 00",
    "Aktenzeichen DE-2026-0001",
]

PII_TOKENS_LOG = [
    "Telekom",
    "Sehr geehrte",
    "28.02.2026",
    "DE89 3704 0044",
    "123,45",
    "Frau Muster",
    "Aktenzeichen",
    "DE-2026-0001",
]

# Translate-related traceback entry points
FORBIDDEN_TRACEBACK_FUNCS = [
    "translate_analysis_endpoint",
    "translate_analysis_with_mistral",
    "ocr_pages_with_mistral",
]

LANGS_TO_TRY = ["en", "es", "vi", "tr", "ru", "zh"]
LANGUAGE_LABELS = {
    "de_simple": "Simple German (Einfaches Deutsch / Leichte Sprache)",
    "en": "English",
    "es": "Spanish (Español)",
    "vi": "Vietnamese (Tiếng Việt)",
    "tr": "Turkish (Türkçe)",
    "ru": "Russian (Русский)",
    "zh": "Chinese Simplified (简体中文)",
}


# ----- Helpers -------------------------------------------------------------

def trunc(s: Any, n: int = 20) -> str:
    s = str(s)
    if len(s) <= 2 * n + 5:
        return s
    return f"{s[:n]}…{s[-n:]}(len={len(s)})"


def make_german_letter_jpeg() -> Tuple[str, str]:
    """Synthesize a single-page German JPEG (1280x1800, q=60). Returns (b64, mime)."""
    img = Image.new("RGB", (1280, 1800), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT_PATH, 36)
    except Exception:
        font = ImageFont.load_default()
    y = 120
    for line in GERMAN_TEXT_LINES:
        draw.text((80, y), line, font=font, fill="black")
        y += 80
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60)
    return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"


# ----- Reporting -----------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.entries: List[Tuple[str, bool, str, float]] = []

    def record(self, name: str, passed: bool, detail: str = "", dur: float = 0.0) -> None:
        self.entries.append((name, passed, detail, dur))
        flag = "PASS" if passed else "FAIL"
        print(f"[{flag}] {name} ({dur*1000:.0f} ms) {detail}")

    def summary(self) -> Tuple[int, int]:
        ok = sum(1 for _, p, *_ in self.entries if p)
        return ok, len(self.entries)


report = Report()


# ----- Tests ---------------------------------------------------------------

def main() -> int:
    print(f"BASE_URL = {BASE_URL}")

    device_id = f"qa-translate-{uuid.uuid4().hex[:8]}"
    print(f"device_id = {device_id}")

    # Mark a log scan window
    test_window_start = time.time()

    # ---------- (0) Sanity / GET /api/ ----------
    t0 = time.time()
    try:
        r = requests.get(f"{BASE_URL}/", timeout=TIMEOUT_SHORT)
        report.record(
            "0a-root_endpoint",
            r.status_code == 200 and r.json().get("status") == "ok",
            f"status={r.status_code}",
            time.time() - t0,
        )
    except Exception as e:
        report.record("0a-root_endpoint", False, f"exc={type(e).__name__}: {e}", time.time() - t0)
        return 2

    # ---------- (Q1) Initial usage state (pre-anything) ----------
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/usage/{device_id}", timeout=TIMEOUT_SHORT)
    pre_usage = r.json() if r.ok else {}
    report.record(
        "0b-usage_initial_zero",
        pre_usage.get("free_analyses_used") == 0
        and pre_usage.get("plus_monthly_used") == 0
        and pre_usage.get("soft_extra_used") == 0
        and pre_usage.get("translation_count") == 0,
        f"free={pre_usage.get('free_analyses_used')} plus={pre_usage.get('plus_monthly_used')} "
        f"soft={pre_usage.get('soft_extra_used')} tx={pre_usage.get('translation_count')}",
        time.time() - t0,
    )

    # ---------- (1a) Create the seed analysis ----------
    file_b64, mime = make_german_letter_jpeg()
    t0 = time.time()
    payload = {
        "device_id": device_id,
        "target_language": "de_simple",
        "idempotency_key": f"qa-tx-seed-{uuid.uuid4().hex[:6]}",
        "pages": [{"file_base64": file_b64, "mime_type": mime}],
    }
    r = requests.post(f"{BASE_URL}/analyze", json=payload, timeout=TIMEOUT_ANALYZE)
    dur = time.time() - t0
    if r.status_code != 200:
        report.record("1a-analyze_seed", False,
                      f"status={r.status_code} body={trunc(r.text, 60)}", dur)
        return 3
    seed = r.json()
    analysis_id = seed.get("id") or ""
    seed_result = seed.get("result") or {}

    primary_sender = seed_result.get("sender", "")
    primary_risk = seed_result.get("risk_level", "")
    primary_category = seed_result.get("category", "")
    primary_scam = seed_result.get("scam_warning", False)
    deadlines = seed_result.get("deadlines") or []
    primary_deadline_date = (deadlines[0] or {}).get("date", "") if deadlines else ""
    actions = seed_result.get("required_actions") or []
    primary_action_urgency = (actions[0] or {}).get("urgency", "") if actions else ""

    report.record(
        "1a-analyze_seed",
        bool(analysis_id) and seed_result.get("target_language") == "Simple German (Einfaches Deutsch / Leichte Sprache)",
        f"id={analysis_id[:8]}… sender='{trunc(primary_sender)}' risk={primary_risk} "
        f"cat={primary_category} scam={primary_scam} dl='{primary_deadline_date}' "
        f"urg='{primary_action_urgency}'",
        dur,
    )

    # ---------- Capture quota baseline AFTER the analyze (this is what
    # translation calls must NOT change) ----------
    r = requests.get(f"{BASE_URL}/usage/{device_id}", timeout=TIMEOUT_SHORT)
    baseline_usage = r.json() if r.ok else {}
    initial_free_used = baseline_usage.get("free_analyses_used", -1)
    initial_plus_used = baseline_usage.get("plus_monthly_used", -1)
    initial_soft_used = baseline_usage.get("soft_extra_used", -1)
    initial_translation_count = baseline_usage.get("translation_count", -1)
    print(f"  baseline (post-analyze): free={initial_free_used} plus={initial_plus_used} "
          f"soft={initial_soft_used} tx={initial_translation_count}")

    # ---------- (1b) Translate to each of 6 languages ----------
    last_translation_count = 0  # we'll re-read usage after each call to verify increments
    for code in LANGS_TO_TRY:
        t0 = time.time()
        try:
            r = requests.post(
                f"{BASE_URL}/analyses/{analysis_id}/translate",
                json={"device_id": device_id, "target_language": code},
                timeout=TIMEOUT_TRANSLATE,
            )
        except requests.Timeout:
            report.record(f"1b-translate[{code}]", False, "TIMEOUT >45s", time.time() - t0)
            continue
        dur = time.time() - t0
        if r.status_code != 200:
            report.record(f"1b-translate[{code}]", False,
                          f"status={r.status_code} body={trunc(r.text, 60)}", dur)
            continue
        body = r.json()
        result = body.get("result") or {}
        usage = body.get("usage") or {}

        # Preservation checks (BYTE-IDENTICAL)
        sender_ok = result.get("sender") == primary_sender
        risk_ok = result.get("risk_level") == primary_risk
        cat_ok = result.get("category") == primary_category
        scam_ok = result.get("scam_warning") == primary_scam
        new_dls = result.get("deadlines") or []
        new_dl_date = (new_dls[0] or {}).get("date", "") if new_dls else ""
        dl_ok = new_dl_date == primary_deadline_date
        new_acts = result.get("required_actions") or []
        new_urg = (new_acts[0] or {}).get("urgency", "") if new_acts else ""
        urg_ok = new_urg == primary_action_urgency

        target_label = body.get("target_language_label", "")
        label_ok = target_label == LANGUAGE_LABELS[code]
        source_ok = result.get("source_language") == "German"

        # german_reply_draft preserved as German if present
        grd = result.get("german_reply_draft", "") or ""
        grd_ok = (
            (not grd.strip())
            or any(tok in grd for tok in [
                "ä", "ö", "ü", "ß", "Sehr", "Ihnen", "freundlichen",
                "Mit", "Hochachtungsvoll", "geehrte",
            ])
        )

        # usage counters
        new_tx_count = usage.get("translation_count", -1)
        translated = usage.get("translated_languages") or []
        count_increment_ok = new_tx_count == last_translation_count + 1
        in_list_ok = code in translated
        last_translation_count = new_tx_count

        # Free quota MUST not have changed
        free_ok = usage.get("free_analyses_used", -1) == initial_free_used
        plus_ok = usage.get("plus_monthly_used", -1) == initial_plus_used
        soft_ok = usage.get("soft_extra_used", -1) == initial_soft_used

        all_ok = (
            sender_ok and risk_ok and cat_ok and scam_ok and dl_ok and urg_ok
            and label_ok and source_ok and grd_ok and count_increment_ok
            and in_list_ok and free_ok and plus_ok and soft_ok
        )
        detail = (
            f"st=200 sender={sender_ok} risk={risk_ok} cat={cat_ok} scam={scam_ok} "
            f"dl={dl_ok} urg={urg_ok} label={label_ok} src={source_ok} grd={grd_ok} "
            f"tx_count={new_tx_count}({'+1' if count_increment_ok else 'WRONG'}) "
            f"in_list={in_list_ok} freeQuota={free_ok}/{plus_ok}/{soft_ok}"
        )
        report.record(f"1b-translate[{code}]", all_ok, detail, dur)

    # ---------- (2) Cache hits (twice) for 'en' ----------
    cached_durs = []
    cached_oks = []
    for i in range(2):
        t0 = time.time()
        r = requests.post(
            f"{BASE_URL}/analyses/{analysis_id}/translate",
            json={"device_id": device_id, "target_language": "en"},
            timeout=TIMEOUT_TRANSLATE,
        )
        dur = time.time() - t0
        cached_durs.append(dur)
        usage = (r.json() or {}).get("usage", {}) if r.ok else {}
        new_tx_count = usage.get("translation_count", -1)
        ok = (
            r.status_code == 200
            and dur < 5.0  # spec says < 2s but allow some slack on remote
            and new_tx_count == last_translation_count
        )
        cached_oks.append(ok)
        report.record(
            f"2-cache_hit_en_call{i+1}",
            ok,
            f"st={r.status_code} dur={dur*1000:.0f}ms tx_count={new_tx_count} (no-increment={new_tx_count==last_translation_count})",
            dur,
        )

    # ---------- (3) Primary target ----------
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/{analysis_id}/translate",
        json={"device_id": device_id, "target_language": "de_simple"},
        timeout=TIMEOUT_TRANSLATE,
    )
    dur = time.time() - t0
    body = r.json() if r.ok else {}
    primary_returned = (body.get("result") or {})
    same_sender = primary_returned.get("sender") == primary_sender
    same_risk = primary_returned.get("risk_level") == primary_risk
    report.record(
        "3-primary_target_cache",
        r.status_code == 200 and dur < 5.0 and same_sender and same_risk,
        f"st={r.status_code} dur={dur*1000:.0f}ms primary_match=sender:{same_sender}/risk:{same_risk}",
        dur,
    )

    # ---------- (4) Invalid input ----------
    cases = [
        ({"device_id": device_id, "target_language": "xx"}, 400, "4a-bad_lang_xx"),
        ({"device_id": device_id, "target_language": ""}, 400, "4b-bad_lang_empty"),
        ({"device_id": "", "target_language": "en"}, 400, "4c-empty_device"),
    ]
    for body, expected, name in cases:
        t0 = time.time()
        r = requests.post(
            f"{BASE_URL}/analyses/{analysis_id}/translate",
            json=body, timeout=TIMEOUT_SHORT,
        )
        report.record(name, r.status_code == expected,
                      f"got={r.status_code} expected={expected}", time.time() - t0)

    # Unknown analysis_id → 404
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/nonexistent-id-{uuid.uuid4().hex}/translate",
        json={"device_id": device_id, "target_language": "en"},
        timeout=TIMEOUT_SHORT,
    )
    report.record("4d-unknown_id", r.status_code == 404,
                  f"got={r.status_code}", time.time() - t0)

    # device_id mismatch → 404 (scope isolation)
    other_device = f"qa-tx-other-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/{analysis_id}/translate",
        json={"device_id": other_device, "target_language": "en"},
        timeout=TIMEOUT_SHORT,
    )
    report.record("4e-device_mismatch", r.status_code == 404,
                  f"got={r.status_code}", time.time() - t0)

    # ---------- (5) Free-analysis quota isolation ----------
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/usage/{device_id}", timeout=TIMEOUT_SHORT)
    final_usage = r.json() if r.ok else {}
    free_unchanged = final_usage.get("free_analyses_used", -1) == initial_free_used
    plus_unchanged = final_usage.get("plus_monthly_used", -1) == initial_plus_used
    soft_unchanged = final_usage.get("soft_extra_used", -1) == initial_soft_used
    tx_count_final = final_usage.get("translation_count", -1)
    # We made 6 misses + 3 cache hits + 1 primary → only 6 increments expected
    tx_count_correct = tx_count_final == 6
    report.record(
        "5-quota_isolation",
        free_unchanged and plus_unchanged and soft_unchanged and tx_count_correct,
        f"free={final_usage.get('free_analyses_used')} plus={final_usage.get('plus_monthly_used')} "
        f"soft={final_usage.get('soft_extra_used')} tx_count={tx_count_final}(want=6)",
        time.time() - t0,
    )

    # ---------- (6) GET /api/analyses/{id} includes translations dict ----------
    t0 = time.time()
    r = requests.get(
        f"{BASE_URL}/analyses/{analysis_id}",
        params={"device_id": device_id}, timeout=TIMEOUT_SHORT,
    )
    body = r.json() if r.ok else {}
    translations = body.get("translations") or {}
    expected_codes = set(LANGS_TO_TRY)
    has_all = expected_codes.issubset(set(translations.keys()))
    # validate one shape — pick 'tr'
    tr_shape_ok = False
    if "tr" in translations:
        tr = translations["tr"]
        tr_shape_ok = (
            isinstance(tr, dict)
            and "summary_translated" in tr
            and "deadlines" in tr
            and "risk_level" in tr
            and "category" in tr
            and tr.get("sender") == primary_sender
        )
    report.record(
        "6-get_analysis_translations",
        r.status_code == 200 and has_all and tr_shape_ok,
        f"st={r.status_code} keys={sorted(translations.keys())} tr_shape={tr_shape_ok}",
        time.time() - t0,
    )

    # ---------- (7) Chat target_language override ----------
    # 7a: target_language='tr' → Turkish reply
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/{analysis_id}/chat",
        json={"device_id": device_id, "message": "Was ist die Frist?", "target_language": "tr"},
        timeout=TIMEOUT_TRANSLATE,
    )
    dur = time.time() - t0
    content = (r.json() or {}).get("content", "") if r.ok else ""
    has_tr = bool(re.search(r"[çşğıöüÇŞĞİÖÜ]", content)) or any(
        w in content.lower() for w in ["tarih", "ödeme", "son ", "lütfen"]
    )
    report.record(
        "7a-chat_override_tr",
        r.status_code == 200 and has_tr,
        f"st={r.status_code} content={trunc(content, 30)}",
        dur,
    )

    # 7b: target_language='ru' → Russian Cyrillic reply
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/{analysis_id}/chat",
        json={"device_id": device_id, "message": "Was ist die Frist?", "target_language": "ru"},
        timeout=TIMEOUT_TRANSLATE,
    )
    dur = time.time() - t0
    content = (r.json() or {}).get("content", "") if r.ok else ""
    has_cyr = bool(re.search(r"[\u0400-\u04FF]", content))
    report.record(
        "7b-chat_override_ru",
        r.status_code == 200 and has_cyr,
        f"st={r.status_code} content={trunc(content, 30)}",
        dur,
    )

    # 7c: no target_language → primary (de_simple → German)
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/{analysis_id}/chat",
        json={"device_id": device_id, "message": "Was ist die Frist?"},
        timeout=TIMEOUT_TRANSLATE,
    )
    dur = time.time() - t0
    content = (r.json() or {}).get("content", "") if r.ok else ""
    looks_german = (
        bool(re.search(r"[äöüÄÖÜß]", content))
        or any(w in content for w in ["der ", "die ", "das ", "ist ", "Frist", "Sie ", "Brief"])
    )
    report.record(
        "7c-chat_no_override_primary",
        r.status_code == 200 and looks_german,
        f"st={r.status_code} content={trunc(content, 30)}",
        dur,
    )

    # 7d: invalid target_language='xx' → silent fallback to primary, NOT 400
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/analyses/{analysis_id}/chat",
        json={"device_id": device_id, "message": "Was ist die Frist?", "target_language": "xx"},
        timeout=TIMEOUT_TRANSLATE,
    )
    dur = time.time() - t0
    content = (r.json() or {}).get("content", "") if r.ok else ""
    looks_german_again = (
        bool(re.search(r"[äöüÄÖÜß]", content))
        or any(w in content for w in ["der ", "die ", "das ", "ist ", "Frist", "Sie ", "Brief"])
    )
    report.record(
        "7d-chat_invalid_silent_fallback",
        r.status_code == 200 and looks_german_again,
        f"st={r.status_code} content={trunc(content, 30)}",
        dur,
    )

    # ---------- (8) Privacy log audit ----------
    test_window_end = time.time()
    log_text = ""
    for log_path in [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ]:
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", errors="replace") as f:
                    log_text += f.read()
            except Exception as e:
                print(f"[warn] cannot read {log_path}: {e}")

    # Quick filter: keep only "recent-ish" lines via timestamp string match.
    # Easier: search the whole tail; the synthetic strings are unique enough.
    # PII tokens
    pii_findings: List[str] = []
    for tok in PII_TOKENS_LOG:
        # Strip out HTTP request/response lines (typical INFO httpx) — these
        # never carry our document content; do a coarse scan.
        for line in log_text.splitlines():
            if tok in line:
                # Allow spurious 'Telekom' only if it comes from non-payload
                # context — be strict: report ANY occurrence in our window.
                pii_findings.append(f"{tok!r} in: {trunc(line, 40)}")
                break
    report.record(
        "8a-privacy_no_pii_in_logs",
        len(pii_findings) == 0,
        f"hits={len(pii_findings)} {pii_findings[:3]}",
        0.0,
    )

    # Tracebacks from translate / ocr funcs
    tb_findings: List[str] = []
    if "Traceback" in log_text:
        # split into traceback blocks
        idx = 0
        while True:
            i = log_text.find("Traceback", idx)
            if i == -1:
                break
            block = log_text[i : i + 4000]
            for fn in FORBIDDEN_TRACEBACK_FUNCS:
                if fn in block:
                    tb_findings.append(f"{fn}: {trunc(block, 40)}")
            idx = i + 9
    report.record(
        "8b-privacy_no_translate_tracebacks",
        len(tb_findings) == 0,
        f"hits={len(tb_findings)} {tb_findings[:2]}",
        0.0,
    )

    # translation_requested == translation_success + translation_cache_hit + translation_failed
    tx_req = len(re.findall(r"translation_requested device=", log_text))
    tx_success = len(re.findall(r"translation_success device=", log_text))
    tx_cache = len(re.findall(r"translation_cache_hit device=", log_text))
    tx_failed = len(re.findall(r"translation_failed device=", log_text))
    # We made 6 misses + 3 cache hits + 1 primary + 5 invalid = 15 calls.
    # But invalid-input requests fail BEFORE the logger.info "translation_requested"
    # line (the validators raise first). Let's check:
    #   - invalid lang xx, lang empty, empty device, unknown id, device mismatch.
    #     The logger line is *after* the find_one but BEFORE the cache. Unknown
    #     id and device mismatch raise 404 before the log line. Empty
    #     device_id raises 400 before. So we expect ~10 "translation_requested" lines.
    # Successful 200 calls = 6 misses + 3 cache hits + 1 primary = 10.
    # That matches → translation_requested == 10
    expected_tx_req_min = 6 + 3 + 1  # only the successful ones reach the log
    cache_count_ok = tx_cache >= 3 + 1  # 3 en cache + 1 primary
    success_count_ok = tx_success >= 6  # 6 unique translations
    report.record(
        "8c-translation_log_lines",
        tx_req >= expected_tx_req_min and cache_count_ok and success_count_ok,
        f"requested={tx_req} success={tx_success} cache_hit={tx_cache} failed={tx_failed}",
        0.0,
    )

    # ---------- (9) Retry test regression ----------
    t0 = time.time()
    try:
        proc = subprocess.run(
            ["python3", "_test_retry.py"],
            cwd="/app/backend",
            capture_output=True, text=True, timeout=180,
        )
        passed = (
            proc.returncode == 0
            and "ALL 6 TESTS PASSED" in (proc.stdout + proc.stderr)
        )
        report.record(
            "9-retry_unit_tests",
            passed,
            f"rc={proc.returncode} tail={trunc((proc.stdout + proc.stderr)[-200:], 60)}",
            time.time() - t0,
        )
    except Exception as e:
        report.record("9-retry_unit_tests", False, f"exc={type(e).__name__}: {e}", time.time() - t0)

    # ---------- (10) Existing /analyze regression ----------
    t0 = time.time()
    file_b64_2, mime_2 = make_german_letter_jpeg()
    payload2 = {
        "device_id": device_id,
        "target_language": "en",
        "idempotency_key": f"qa-tx-regress-{uuid.uuid4().hex[:6]}",
        "pages": [{"file_base64": file_b64_2, "mime_type": mime_2}],
    }
    r = requests.post(f"{BASE_URL}/analyze", json=payload2, timeout=TIMEOUT_ANALYZE)
    dur = time.time() - t0
    ok = False
    if r.status_code == 200:
        body = r.json()
        result = body.get("result") or {}
        ok = (
            "summary_translated" in result
            and "deadlines" in result
            and "risk_level" in result
            and result.get("source_language") == "German"
        )
    report.record(
        "10-analyze_regression",
        ok,
        f"st={r.status_code} dur={dur*1000:.0f}ms keys_ok={ok}",
        dur,
    )

    # ---------- (11) Cleanup ----------
    t0 = time.time()
    r = requests.delete(f"{BASE_URL}/history/{device_id}", timeout=TIMEOUT_SHORT)
    body = r.json() if r.ok else {}
    report.record(
        "11-cleanup",
        r.status_code == 200 and body.get("deleted_analyses", -1) >= 1,
        f"st={r.status_code} body={body}",
        time.time() - t0,
    )

    # ----- Summary -----
    ok, total = report.summary()
    print("\n" + "=" * 60)
    print(f"RESULT: {ok}/{total} PASS  ({total-ok} FAIL)")
    if ok != total:
        print("\nFailing items:")
        for name, passed, detail, dur in report.entries:
            if not passed:
                print(f"  ❌ {name}  ({dur*1000:.0f} ms) {detail}")
    print("=" * 60)
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
