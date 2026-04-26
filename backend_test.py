"""KlarPost backend regression suite — Mistral migration.

Covers all scenarios from the user's review request.
Hits the public preview URL via /api prefix.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import uuid
from typing import List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

BASE_URL = "https://klarpost-mvp.preview.emergentagent.com/api"
TIMEOUT_FAST = 30
TIMEOUT_LLM = 180

DEVICE_ID = f"qa-mistral-{uuid.uuid4()}"

results: List[Tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name} :: {detail}"[:600])


def get_font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_image_png(lines: List[str], width: int = 1240, height: int = 1754) -> bytes:
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    body_font = get_font(28)
    title_font = get_font(34)

    y = 80
    for i, line in enumerate(lines):
        font = title_font if i == 0 else body_font
        draw.text((80, y), line, fill=(0, 0, 0), font=font)
        y += 46 if i == 0 else 38

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def png_b64(lines: List[str]) -> str:
    return base64.b64encode(build_image_png(lines)).decode("ascii")


def get(path: str, params: Optional[dict] = None, timeout: int = TIMEOUT_FAST) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", params=params, timeout=timeout)


def post(path: str, payload: dict, timeout: int = TIMEOUT_FAST) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", json=payload, timeout=timeout)


def delete(path: str, params: Optional[dict] = None, timeout: int = TIMEOUT_FAST) -> requests.Response:
    return requests.delete(f"{BASE_URL}{path}", params=params, timeout=timeout)


def test_root() -> None:
    try:
        r = get("/")
        ok = r.status_code == 200 and r.json() == {"app": "KlarPost", "status": "ok"}
        record("1. GET /api/", ok, f"status={r.status_code} body={r.text[:120]}")
    except Exception as e:
        record("1. GET /api/", False, f"exception: {e}")


def test_languages() -> None:
    try:
        r = get("/languages")
        data = r.json() if r.status_code == 200 else None
        ok = (
            r.status_code == 200
            and isinstance(data, list)
            and len(data) == 7
            and all("code" in d and "label" in d for d in data)
        )
        codes = [d["code"] for d in data] if data else []
        record("2. GET /api/languages", ok, f"status={r.status_code} count={len(data) if data else 0} codes={codes}")
    except Exception as e:
        record("2. GET /api/languages", False, f"exception: {e}")


def test_analyze_benign() -> Optional[str]:
    lines = [
        "Techniker Krankenkasse",
        "Kundennummer: 123456789",
        "Postfach 11 22, 20410 Hamburg",
        "",
        "Sehr geehrte Frau Schneider,",
        "",
        "wir moechten Sie informieren, dass sich Ihr",
        "monatlicher Beitrag zur gesetzlichen Krankenversicherung",
        "ab dem 01. Januar 2026 geringfuegig aendert.",
        "",
        "Der neue Beitrag betraegt 425,80 Euro pro Monat.",
        "Eine Aktion Ihrerseits ist nicht erforderlich.",
        "",
        "Falls Sie Rueckfragen haben, erreichen Sie uns",
        "unter der Telefonnummer 0800 / 285 85 85.",
        "",
        "Mit freundlichen Gruessen",
        "Ihre Techniker Krankenkasse",
    ]
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "en",
        "pages": [{"file_base64": png_b64(lines), "mime_type": "image/png"}],
    }
    try:
        t0 = time.time()
        r = post("/analyze", payload, timeout=TIMEOUT_LLM)
        dt = time.time() - t0
        if r.status_code != 200:
            record("3. POST /api/analyze (benign)", False, f"status={r.status_code} body={r.text[:300]} t={dt:.1f}s")
            return None
        data = r.json()
        result = data.get("result", {})
        risk = result.get("risk_level")
        scam = result.get("scam_warning")
        category = result.get("category")
        summary = result.get("summary_translated", "")
        tlang = result.get("target_language")
        valid_categories = {
            "tax", "insurance", "rent", "bank", "health", "government",
            "court", "utilities", "telecom", "work", "education", "other",
        }
        ok = (
            risk in ("green", "yellow")
            and scam is False
            and category in valid_categories
            and len(summary) > 0
            and tlang == "English"
        )
        detail = (
            f"id={data.get('id')} risk={risk} scam={scam} category={category} "
            f"target_language={tlang} summary_len={len(summary)} t={dt:.1f}s"
        )
        record("3. POST /api/analyze (benign)", ok, detail)
        return data.get("id")
    except Exception as e:
        record("3. POST /api/analyze (benign)", False, f"exception: {e}")
        return None


def test_analyze_scam() -> Optional[str]:
    lines = [
        "BUNDESPOLIZEI - DRINGEND",
        "Absender: bundespolizei.notfall@gmail.com",
        "",
        "Sehr geehrter Buerger,",
        "",
        "Gegen Sie wurde eine Strafanzeige eingereicht.",
        "Sie werden innerhalb von 24 Stunden VERHAFTET,",
        "wenn Sie nicht sofort eine Geldstrafe zahlen.",
        "",
        "Zahlungsbetrag: 1500 EUR",
        "",
        "Zahlungsmethode 1: iTunes Geschenkkarten - Codes",
        "an die obige E-Mail senden.",
        "",
        "Zahlungsmethode 2: Bitcoin-Ueberweisung an Wallet",
        "bc1q9h7xs2k4l5m6n7p8q9r0s1t2u3v4w5x6y7z8",
        "",
        "Zahlungsmethode 3: SEPA-Ueberweisung an",
        "IBAN: NG24 0123 4567 8901 2345 6789 01",
        "Inhaber: Mr. Prince Okonkwo",
        "",
        "Zoegern Sie nicht. Verhaftung erfolgt binnen 24h.",
        "",
        "Bundespolizei Direktion (inoffiziell)",
    ]
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "en",
        "pages": [{"file_base64": png_b64(lines), "mime_type": "image/png"}],
    }
    try:
        t0 = time.time()
        r = post("/analyze", payload, timeout=TIMEOUT_LLM)
        dt = time.time() - t0
        if r.status_code != 200:
            record("4. POST /api/analyze (scam)", False, f"status={r.status_code} body={r.text[:300]} t={dt:.1f}s")
            return None
        data = r.json()
        result = data.get("result", {})
        scam = result.get("scam_warning")
        scam_reason = result.get("scam_reason", "")
        risk = result.get("risk_level")
        ok = scam is True and len(scam_reason) > 0 and risk == "red"
        detail = (
            f"id={data.get('id')} scam={scam} risk={risk} "
            f"reason_len={len(scam_reason)} reason='{scam_reason[:120]}' t={dt:.1f}s"
        )
        record("4. POST /api/analyze (scam)", ok, detail)
        return data.get("id")
    except Exception as e:
        record("4. POST /api/analyze (scam)", False, f"exception: {e}")
        return None


def test_analyze_invalid_lang() -> None:
    payload = {
        "device_id": DEVICE_ID,
        "target_language": "xx",
        "pages": [{"file_base64": png_b64(["Test"]), "mime_type": "image/png"}],
    }
    try:
        r = post("/analyze", payload, timeout=TIMEOUT_FAST)
        try:
            detail_msg = r.json().get("detail", "")
        except Exception:
            detail_msg = r.text
        ok = r.status_code == 400 and "Unsupported target language" in str(detail_msg)
        record("5. POST /api/analyze invalid lang", ok, f"status={r.status_code} detail={detail_msg}")
    except Exception as e:
        record("5. POST /api/analyze invalid lang", False, f"exception: {e}")


def test_analyze_no_content() -> None:
    payload = {"device_id": DEVICE_ID, "target_language": "en"}
    try:
        r = post("/analyze", payload, timeout=TIMEOUT_FAST)
        try:
            detail_msg = r.json().get("detail", "")
        except Exception:
            detail_msg = r.text
        ok = r.status_code == 400 and "No file content provided" in str(detail_msg)
        record("6. POST /api/analyze no content", ok, f"status={r.status_code} detail={detail_msg}")
    except Exception as e:
        record("6. POST /api/analyze no content", False, f"exception: {e}")


def test_list_analyses(expected_ids: List[Optional[str]]) -> None:
    try:
        r = get("/analyses", params={"device_id": DEVICE_ID})
        if r.status_code != 200:
            record("7. GET /api/analyses", False, f"status={r.status_code} body={r.text[:200]}")
            return
        data = r.json()
        ids_returned = [d["id"] for d in data]
        ex = [i for i in expected_ids if i]
        all_present = all(eid in ids_returned for eid in ex)
        each_has_fields = all(
            ("category" in d) and ("scam_warning" in d) for d in data
        )
        created_list = [d.get("created_at", "") for d in data]
        sorted_desc = created_list == sorted(created_list, reverse=True)
        ok = all_present and each_has_fields and sorted_desc and len(data) >= len(ex)
        record(
            "7. GET /api/analyses",
            ok,
            f"count={len(data)} expected={ex} all_present={all_present} fields_ok={each_has_fields} sorted_desc={sorted_desc}",
        )
    except Exception as e:
        record("7. GET /api/analyses", False, f"exception: {e}")


def test_get_analysis(analysis_id: str) -> None:
    if not analysis_id:
        record("8. GET /api/analyses/{id}", False, "no analysis_id")
        return
    try:
        r = get(f"/analyses/{analysis_id}", params={"device_id": DEVICE_ID})
        if r.status_code != 200:
            record("8. GET /api/analyses/{id}", False, f"status={r.status_code} body={r.text[:200]}")
            return
        data = r.json()
        ok = (
            data.get("id") == analysis_id
            and data.get("device_id") == DEVICE_ID
            and "result" in data
            and "category" in data["result"]
        )
        record("8. GET /api/analyses/{id}", ok, f"id_match={data.get('id') == analysis_id} has_result={'result' in data}")
    except Exception as e:
        record("8. GET /api/analyses/{id}", False, f"exception: {e}")


def test_chat_on_topic(analysis_id: str) -> None:
    if not analysis_id:
        record("9. POST chat on-topic", False, "no analysis_id")
        return
    try:
        payload1 = {"device_id": DEVICE_ID, "message": "Was bedeutet der Beitrag in diesem Brief?"}
        r1 = post(f"/analyses/{analysis_id}/chat", payload1, timeout=TIMEOUT_LLM)
        if r1.status_code != 200:
            record("9a. POST chat on-topic (1st)", False, f"status={r1.status_code} body={r1.text[:300]}")
            return
        d1 = r1.json()
        ok1 = (
            d1.get("role") == "assistant"
            and d1.get("off_topic") is False
            and len((d1.get("content") or "").strip()) > 0
        )
        record(
            "9a. POST chat on-topic (1st turn)",
            ok1,
            f"off_topic={d1.get('off_topic')} content_len={len(d1.get('content',''))} preview='{d1.get('content','')[:120]}'",
        )

        payload2 = {
            "device_id": DEVICE_ID,
            "message": "Und ab wann gilt der neue Beitrag genau?",
        }
        r2 = post(f"/analyses/{analysis_id}/chat", payload2, timeout=TIMEOUT_LLM)
        if r2.status_code != 200:
            record("9b. POST chat on-topic (2nd)", False, f"status={r2.status_code} body={r2.text[:300]}")
            return
        d2 = r2.json()
        ok2 = (
            d2.get("role") == "assistant"
            and d2.get("off_topic") is False
            and len((d2.get("content") or "").strip()) > 0
        )
        record(
            "9b. POST chat on-topic (2nd turn)",
            ok2,
            f"off_topic={d2.get('off_topic')} content_len={len(d2.get('content',''))} preview='{d2.get('content','')[:120]}'",
        )
    except Exception as e:
        record("9. POST chat on-topic", False, f"exception: {e}")


def test_chat_off_topic(analysis_id: str) -> None:
    if not analysis_id:
        record("10. POST chat off-topic", False, "no analysis_id")
        return
    try:
        payload = {"device_id": DEVICE_ID, "message": "Tell me a joke about cats please."}
        r = post(f"/analyses/{analysis_id}/chat", payload, timeout=TIMEOUT_LLM)
        if r.status_code != 200:
            record("10. POST chat off-topic", False, f"status={r.status_code} body={r.text[:300]}")
            return
        d = r.json()
        ok = d.get("off_topic") is True and len((d.get("content") or "").strip()) > 0
        record(
            "10. POST chat off-topic",
            ok,
            f"off_topic={d.get('off_topic')} preview='{d.get('content','')[:160]}'",
        )
    except Exception as e:
        record("10. POST chat off-topic", False, f"exception: {e}")


def test_list_messages(analysis_id: str) -> int:
    if not analysis_id:
        record("11. GET messages", False, "no analysis_id")
        return 0
    try:
        r = get(f"/analyses/{analysis_id}/messages", params={"device_id": DEVICE_ID})
        if r.status_code != 200:
            record("11. GET messages", False, f"status={r.status_code} body={r.text[:200]}")
            return 0
        data = r.json()
        roles = [m.get("role") for m in data]
        ok = (
            isinstance(data, list)
            and len(data) >= 6
            and roles.count("user") >= 3
            and roles.count("assistant") >= 3
        )
        record(
            "11. GET messages",
            ok,
            f"count={len(data)} user={roles.count('user')} assistant={roles.count('assistant')}",
        )
        return len(data)
    except Exception as e:
        record("11. GET messages", False, f"exception: {e}")
        return 0


def test_clear_messages(analysis_id: str) -> None:
    if not analysis_id:
        record("12. DELETE messages", False, "no analysis_id")
        return
    try:
        r = delete(f"/analyses/{analysis_id}/messages", params={"device_id": DEVICE_ID})
        if r.status_code != 200:
            record("12. DELETE messages", False, f"status={r.status_code} body={r.text[:200]}")
            return
        cleared = r.json().get("cleared", 0)
        ok1 = cleared > 0
        r2 = get(f"/analyses/{analysis_id}/messages", params={"device_id": DEVICE_ID})
        empty_now = r2.status_code == 200 and r2.json() == []
        ok = ok1 and empty_now
        record(
            "12. DELETE messages + verify empty",
            ok,
            f"cleared={cleared} after_get_count={(len(r2.json()) if r2.status_code==200 else 'err')}",
        )
    except Exception as e:
        record("12. DELETE messages", False, f"exception: {e}")


def test_delete_analysis(analysis_id: str) -> None:
    if not analysis_id:
        record("13. DELETE /api/analyses/{id}", False, "no analysis_id")
        return
    try:
        r = delete(f"/analyses/{analysis_id}", params={"device_id": DEVICE_ID})
        if r.status_code != 200:
            record("13. DELETE /api/analyses/{id}", False, f"status={r.status_code} body={r.text[:200]}")
            return
        deleted = r.json().get("deleted", 0)
        ok = deleted == 1
        record("13. DELETE /api/analyses/{id}", ok, f"deleted={deleted}")
    except Exception as e:
        record("13. DELETE /api/analyses/{id}", False, f"exception: {e}")


def test_delete_all() -> None:
    try:
        r = delete("/analyses", params={"device_id": DEVICE_ID})
        if r.status_code != 200:
            record("14. DELETE /api/analyses", False, f"status={r.status_code} body={r.text[:200]}")
            return
        deleted = r.json().get("deleted", 0)
        ok = deleted >= 0
        record("14. DELETE /api/analyses", ok, f"deleted={deleted}")
    except Exception as e:
        record("14. DELETE /api/analyses", False, f"exception: {e}")


def main() -> int:
    print(f"BASE_URL = {BASE_URL}")
    print(f"DEVICE_ID = {DEVICE_ID}")
    print()

    test_root()
    test_languages()

    benign_id = test_analyze_benign()
    scam_id = test_analyze_scam()

    test_analyze_invalid_lang()
    test_analyze_no_content()

    test_list_analyses([benign_id, scam_id])

    if benign_id:
        test_get_analysis(benign_id)
        test_chat_on_topic(benign_id)
        test_chat_off_topic(benign_id)
        test_list_messages(benign_id)
        test_clear_messages(benign_id)
        test_delete_analysis(benign_id)

    test_delete_all()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}")
        if not ok and detail:
            print(f"        -> {detail}")
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
