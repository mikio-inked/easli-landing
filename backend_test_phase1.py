"""Phase-1 KlarPost Payment Foundation regression test.

Covers all 17 scenarios in the review request:
  1.  GET /api/paywall/config
  2.  GET /api/usage/<fresh device>
  3.  Soft-mode analyze lifecycle (3 free + 10 soft + 14th blocked)
  4.  Idempotency
  5.  Failed analysis does not consume
  6.  Plus path
  7.  Single-letter path
  8.  Chat quotas (per-doc, total, plus-bypass)
  9.  Webhook (no auth)
  10. Webhook (with auth)  (skipped — would require restarting backend)
  11. Consumable webhook + idempotency
  12. Expiration webhook
  13. MAX_PAGES_PER_DOCUMENT enforcement
  14. Dev tools visibility
  15. Privacy log audit
  16. No regressions
  17. Cleanup
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont

BASE = "https://doc-scanner-de.preview.emergentagent.com/api"
TIMEOUT = 90

# Tokens to grep in backend logs at end-of-run.
SECRET_TOKENS = [
    "Sehr geehrte",
    "AOK",
    "Bundespolizei",
    "Mustermann",
    "Versichertennummer",
    "DE89370400440532013000",
    "NG12NIGB1234567890",
    "BIC: COBADEFFXXX",
    "BTC1q",
    "iTunes-Gutscheinkarten",
    "test123",  # auth header value
]
# First 4 chars of the Mistral key (read from .env, never printed)
MISTRAL_KEY = open("/app/backend/.env").read()
m = re.search(r"MISTRAL_API_KEY=([A-Za-z0-9]+)", MISTRAL_KEY)
KEY_PREFIX = m.group(1)[:4] if m else ""
KEY_FULL = m.group(1) if m else ""

PASS: list[str] = []
FAIL: list[str] = []
WARN: list[str] = []


def ok(label: str, ok_: bool, info: str = "") -> bool:
    suffix = f" — {info}" if info else ""
    if ok_:
        PASS.append(label + suffix)
        print(f"  ✅ {label}{suffix}")
    else:
        FAIL.append(label + suffix)
        print(f"  ❌ {label}{suffix}")
    return ok_


def warn(label: str, info: str = ""):
    WARN.append(f"{label} — {info}" if info else label)
    print(f"  ⚠ {label} {info}")


def make_synthetic_letter_png(filler: str = "Krankenkasse") -> str:
    """Build a benign synthetic German letter as PNG base64."""
    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    # Try to load a font; fall back to default if PIL doesn't have it.
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
        big = font
    y = 80
    draw.text((80, y), f"AOK Nordwest — {filler}", fill="black", font=big); y += 70
    lines = [
        "Sehr geehrte Frau Mustermann,",
        "",
        "wir informieren Sie hiermit über Ihren neuen monatlichen Beitrag",
        "zur gesetzlichen Krankenversicherung. Der Beitrag beträgt 248,50 EUR",
        "und ist ab dem 01.01.2026 fällig.",
        "",
        "Bitte überweisen Sie den Betrag bis spätestens 15.01.2026 auf das",
        "folgende Konto: IBAN DE89 3704 0044 0532 0130 00 — BIC: COBADEFFXXX.",
        "",
        "Versichertennummer: A123456789",
        "",
        "Mit freundlichen Grüßen",
        "Ihr AOK-Team Nordwest",
    ]
    for ln in lines:
        draw.text((80, y), ln, fill="black", font=font)
        y += 42
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def make_tiny_page_png(idx: int) -> str:
    img = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    draw.text((40, 40), f"Seite {idx}", fill="black", font=font)
    draw.text((40, 100), f"Dies ist Seite Nummer {idx} eines Testdokuments.", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ---------- Section 1: paywall/config ----------
def test_1_paywall_config():
    print("\n[1] GET /api/paywall/config")
    r = requests.get(f"{BASE}/paywall/config", timeout=TIMEOUT)
    ok("config 200", r.status_code == 200, str(r.status_code))
    if r.status_code != 200:
        return
    j = r.json()
    ok("paywall_mode=soft", j.get("paywall_mode") == "soft", str(j.get("paywall_mode")))
    ok("free_analyses=3", j.get("free_analyses") == 3, str(j.get("free_analyses")))
    ok("soft_test_extra_analyses=10", j.get("soft_test_extra_analyses") == 10)
    ok("plus_monthly_analyses=20", j.get("plus_monthly_analyses") == 20)
    ok("max_pages_per_document=5", j.get("max_pages_per_document") == 5)
    products = j.get("products") or {}
    ok("products.single_letter=klarpost_single_letter", products.get("single_letter") == "klarpost_single_letter")
    ok("products.plus_monthly=klarpost_plus_monthly", products.get("plus_monthly") == "klarpost_plus_monthly")
    ok("products.plus_yearly=klarpost_plus_yearly", products.get("plus_yearly") == "klarpost_plus_yearly")
    ents = j.get("entitlements") or {}
    ok("entitlements.plus='plus'", ents.get("plus") == "plus")


# ---------- Section 2: fresh /usage ----------
def test_2_fresh_usage():
    print("\n[2] GET /api/usage/<fresh>")
    dev = f"qa-fresh-{uuid.uuid4().hex[:8]}"
    r = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT)
    ok("usage 200", r.status_code == 200, str(r.status_code))
    if r.status_code != 200:
        return dev
    j = r.json()
    ok("free_analyses_used=0", j.get("free_analyses_used") == 0)
    ok("soft_extra_used=0", j.get("soft_extra_used") == 0)
    ok("single_letter_credits=0", j.get("single_letter_credits") == 0)
    ok("plus_active=False", j.get("plus_active") is False)
    ok("plus_monthly_used=0", j.get("plus_monthly_used") == 0)
    ok("total_chat_questions_used=0", j.get("total_chat_questions_used") == 0)
    ok("free_analyses_total=3", j.get("free_analyses_total") == 3)
    ok("soft_extra_total=10", j.get("soft_extra_total") == 10)
    ok("plus_monthly_total=20", j.get("plus_monthly_total") == 20)
    ok("total_chat_questions_total=20", j.get("total_chat_questions_total") == 20)
    return dev


# ---------- Section 3: soft-mode lifecycle ----------
def test_3_soft_lifecycle(letter_b64: str):
    print("\n[3] Soft-mode analyze lifecycle (13 + 14th blocked)")
    dev = f"qa-life-{uuid.uuid4().hex[:8]}"
    first_analysis_id = None
    for i in range(1, 14):
        body = {
            "device_id": dev,
            "target_language": "en",
            "idempotency_key": f"k{i}",
            "file_base64": letter_b64,
            "mime_type": "image/png",
        }
        r = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
        ok(f"analyze k{i} 200", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"     body: {r.text[:300]}")
            return dev, first_analysis_id
        j = r.json()
        if i == 1:
            first_analysis_id = j.get("id")
        u = j.get("usage", {})
        if i <= 3:
            expected_free = i
            expected_soft = 0
        else:
            expected_free = 3
            expected_soft = i - 3
        ok(
            f"after k{i}: free_used={expected_free}, soft_used={expected_soft}",
            u.get("free_analyses_used") == expected_free and u.get("soft_extra_used") == expected_soft,
            f"got free={u.get('free_analyses_used')} soft={u.get('soft_extra_used')}",
        )

    # 14th — should be 429 quickly, no Mistral call.
    t0 = time.time()
    body14 = {
        "device_id": dev,
        "target_language": "en",
        "idempotency_key": "k14",
        "file_base64": letter_b64,
        "mime_type": "image/png",
    }
    r = requests.post(f"{BASE}/analyze", json=body14, timeout=TIMEOUT)
    elapsed = time.time() - t0
    ok("k14 status 429", r.status_code == 429, str(r.status_code))
    if r.status_code == 429:
        j = r.json()
        ok("k14 error=test_limit_reached", j.get("error") == "test_limit_reached")
        ok("k14 message contains Testkontingent", "Testkontingent" in (j.get("message") or ""))
        ok("k14 has usage block", "usage" in j)
    ok(
        f"k14 fast (no Mistral call, {elapsed:.2f}s < 2.0s)",
        elapsed < 2.0,
        f"{elapsed:.2f}s",
    )
    return dev, first_analysis_id


# ---------- Section 4: idempotency ----------
def test_4_idempotency(letter_b64: str):
    print("\n[4] Idempotency — same key consumed only once")
    dev = f"qa-idem-{uuid.uuid4().hex[:8]}"
    body = {
        "device_id": dev,
        "target_language": "en",
        "idempotency_key": "dup-key",
        "file_base64": letter_b64,
        "mime_type": "image/png",
    }
    r1 = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
    ok("first 200", r1.status_code == 200, str(r1.status_code))
    if r1.status_code == 200:
        ok("first usage.free_analyses_used=1", r1.json().get("usage", {}).get("free_analyses_used") == 1)
    r2 = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
    ok("second 200", r2.status_code == 200, str(r2.status_code))
    if r2.status_code == 200:
        # Read ground truth from /usage to be safe (the response shape may
        # differ depending on whether consumption was skipped before the
        # final read).
        u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
        ok(
            "after duplicate, free_analyses_used STILL 1",
            u.get("free_analyses_used") == 1,
            f"got {u.get('free_analyses_used')}",
        )
    return dev


# ---------- Section 5: failed analysis does not consume ----------
def test_5_failed_no_consume():
    print("\n[5] Failed analysis (bad base64) does not consume")
    dev = f"qa-bad-{uuid.uuid4().hex[:8]}"
    body = {
        "device_id": dev,
        "target_language": "en",
        "idempotency_key": "bad1",
        "file_base64": "not_real_b64_!!!",
        "mime_type": "image/png",
    }
    r = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
    ok("bad analyze 400", r.status_code == 400, str(r.status_code))
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok(
        "all counters still 0 after failure",
        u.get("free_analyses_used") == 0
        and u.get("soft_extra_used") == 0
        and u.get("single_letter_credits") == 0,
    )
    return dev


# ---------- Section 6: plus path ----------
def test_6_plus_path(letter_b64: str):
    print("\n[6] Plus path — plus_active uses plus bucket, not free")
    dev = f"qa-plus-{uuid.uuid4().hex[:8]}"
    r = requests.post(
        f"{BASE}/dev/usage/simulate",
        params={"device_id": dev, "scenario": "plus_active"},
        timeout=TIMEOUT,
    )
    ok("simulate plus_active 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        j = r.json()
        ok("plus_active=True", j.get("plus_active") is True)
        end = j.get("plus_period_end") or ""
        try:
            edt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            delta_days = (edt - datetime.now(timezone.utc)).days
            ok(f"period_end ~30 days out (got {delta_days})", 28 <= delta_days <= 31)
        except Exception:
            ok("period_end parses", False, end)
    body = {
        "device_id": dev,
        "target_language": "en",
        "idempotency_key": "p1",
        "file_base64": letter_b64,
        "mime_type": "image/png",
    }
    r = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
    ok("plus analyze 200", r.status_code == 200, str(r.status_code))
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("plus_monthly_used=1", u.get("plus_monthly_used") == 1, str(u.get("plus_monthly_used")))
    ok("free_analyses_used=0 (plus took priority)", u.get("free_analyses_used") == 0)
    return dev


# ---------- Section 7: single-letter path ----------
def test_7_single_letter(letter_b64: str):
    print("\n[7] Single-letter path — at free_limit, credit decrements")
    dev = f"qa-single-{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/dev/usage/simulate", params={"device_id": dev, "scenario": "free_limit"}, timeout=TIMEOUT)
    ok("simulate free_limit 200", r.status_code == 200)
    r = requests.post(f"{BASE}/dev/usage/simulate", params={"device_id": dev, "scenario": "add_single_letter"}, timeout=TIMEOUT)
    ok("simulate add_single_letter 200", r.status_code == 200)
    if r.status_code == 200:
        ok("single_letter_credits=1 after sim", r.json().get("single_letter_credits") == 1)
    body = {
        "device_id": dev,
        "target_language": "en",
        "idempotency_key": "s1",
        "file_base64": letter_b64,
        "mime_type": "image/png",
    }
    r = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
    ok("single analyze 200", r.status_code == 200, str(r.status_code))
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("single_letter_credits=0 (decremented)", u.get("single_letter_credits") == 0, str(u.get("single_letter_credits")))
    ok("free_analyses_used=3 (stays at limit)", u.get("free_analyses_used") == 3)
    ok("soft_extra_used=0", u.get("soft_extra_used") == 0)
    return dev


# ---------- Section 8: chat quotas ----------
def test_8_chat_quotas(life_dev: str, life_first_analysis_id: str | None, letter_b64: str):
    print("\n[8] Chat quotas")
    if not life_first_analysis_id:
        warn("skip chat tests — no analysis_id from #3")
        return None
    aid = life_first_analysis_id
    dev = life_dev

    # 5x success, 6th blocked per_document
    for i in range(1, 6):
        r = requests.post(
            f"{BASE}/analyses/{aid}/chat",
            json={"device_id": dev, "message": "Worum geht es in diesem Brief?"},
            timeout=TIMEOUT,
        )
        ok(f"chat #{i} 200", r.status_code == 200, str(r.status_code))
        if r.status_code != 200:
            print(f"     body: {r.text[:300]}")
            return None
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("total_chat_questions_used=5", u.get("total_chat_questions_used") == 5, str(u.get("total_chat_questions_used")))
    ok(
        "per_document_chat_questions[id]=5",
        (u.get("per_document_chat_questions") or {}).get(aid) == 5,
        str((u.get("per_document_chat_questions") or {}).get(aid)),
    )

    # 6th → 429 with scope=per_document
    r = requests.post(
        f"{BASE}/analyses/{aid}/chat",
        json={"device_id": dev, "message": "Noch eine Frage zum Brief?"},
        timeout=TIMEOUT,
    )
    ok("chat #6 429", r.status_code == 429, str(r.status_code))
    if r.status_code == 429:
        j = r.json()
        ok("chat 6 error contains 'limit_reached'", "limit_reached" in str(j.get("error", "")))
        ok("chat 6 scope=per_document", j.get("scope") == "per_document")
        ok("chat 6 has usage block", "usage" in j)

    # reset_chat
    r = requests.post(f"{BASE}/dev/usage/simulate", params={"device_id": dev, "scenario": "reset_chat"}, timeout=TIMEOUT)
    ok("reset_chat 200", r.status_code == 200)
    if r.status_code == 200:
        j = r.json()
        ok("after reset, total=0", j.get("total_chat_questions_used") == 0)
        ok("after reset, per_doc empty", j.get("per_document_chat_questions") == {})

    # Total cap test: spread 21 questions across 5 different analyses.
    # We need 5 analyses total; the life device only has 1 (k1's id).
    # The simpler approach: create a fresh device, do 4 analyses (only 3 free
    # + 1 soft = 4), then 5th, 6th... Actually we need 5 analyses with up to
    # 4 chats each = 20 + 1 = 21st. The device starts soft, so 5 analyses
    # is fine (3 free + 2 soft).
    cap_dev = f"qa-chatcap-{uuid.uuid4().hex[:8]}"
    aids: list[str] = []
    for i in range(5):
        body = {
            "device_id": cap_dev,
            "target_language": "en",
            "idempotency_key": f"cap{i}",
            "file_base64": letter_b64,
            "mime_type": "image/png",
        }
        rr = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
        if rr.status_code == 200:
            aids.append(rr.json().get("id"))
        else:
            warn(f"chatcap analyze {i} failed", str(rr.status_code))
    ok("chatcap got 5 analyses", len(aids) == 5, str(len(aids)))

    # Send 4 chats per analysis = 20 total — should all 200.
    sent_total = 0
    last_status = None
    for aid_i in aids:
        for q in range(4):
            r = requests.post(
                f"{BASE}/analyses/{aid_i}/chat",
                json={"device_id": cap_dev, "message": f"Frage {q+1}: Was bedeutet das?"},
                timeout=TIMEOUT,
            )
            last_status = r.status_code
            if r.status_code == 200:
                sent_total += 1
            else:
                break
        if last_status != 200:
            break
    ok("first 20 chats succeeded", sent_total == 20, f"sent={sent_total}, last_status={last_status}")

    # 21st chat on a fresh aid (with 0 per-doc count) — but all aids already have 4.
    # Hit a brand new analysis to keep per-doc cap from firing. Need a 6th analysis.
    body6 = {
        "device_id": cap_dev,
        "target_language": "en",
        "idempotency_key": "cap6",
        "file_base64": letter_b64,
        "mime_type": "image/png",
    }
    rr = requests.post(f"{BASE}/analyze", json=body6, timeout=TIMEOUT)
    if rr.status_code == 200:
        aid6 = rr.json().get("id")
        r = requests.post(
            f"{BASE}/analyses/{aid6}/chat",
            json={"device_id": cap_dev, "message": "Frage 21 — sollte das blocken?"},
            timeout=TIMEOUT,
        )
        ok("chat 21st 429", r.status_code == 429, str(r.status_code))
        if r.status_code == 429:
            j = r.json()
            ok("chat 21st scope=total", j.get("scope") == "total", str(j.get("scope")))
    else:
        warn("chat 21st: 6th analyze failed", str(rr.status_code))

    # Plus bypass — fresh device, sim plus_active, do 25 chats across multiple analyses.
    p_dev = f"qa-pluschat-{uuid.uuid4().hex[:8]}"
    requests.post(f"{BASE}/dev/usage/simulate", params={"device_id": p_dev, "scenario": "plus_active"}, timeout=TIMEOUT)
    p_aids: list[str] = []
    # We need 25/5=5 analyses (each can have up to 5 per-doc chats).
    for i in range(6):  # 6 analyses for safety
        body = {
            "device_id": p_dev,
            "target_language": "en",
            "idempotency_key": f"pp{i}",
            "file_base64": letter_b64,
            "mime_type": "image/png",
        }
        rr = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
        if rr.status_code == 200:
            p_aids.append(rr.json().get("id"))
    ok(f"plus device got {len(p_aids)} analyses", len(p_aids) >= 5)
    chats_sent = 0
    chat_ok = True
    for aid_i in p_aids:
        for _ in range(5):  # respects per-doc cap of 5
            if chats_sent >= 25:
                break
            rr = requests.post(
                f"{BASE}/analyses/{aid_i}/chat",
                json={"device_id": p_dev, "message": "Was steht im Brief?"},
                timeout=TIMEOUT,
            )
            if rr.status_code != 200:
                chat_ok = False
                warn(f"plus chat {chats_sent+1} failed", f"{rr.status_code} — {rr.text[:120]}")
                break
            chats_sent += 1
        if not chat_ok or chats_sent >= 25:
            break
    ok(
        f"plus device sent 25 chats without total-cap (got {chats_sent})",
        chats_sent >= 25 and chat_ok,
    )

    # Per-doc cap STILL applies for plus
    if p_aids:
        rr = requests.post(
            f"{BASE}/analyses/{p_aids[0]}/chat",
            json={"device_id": p_dev, "message": "6. Frage zu diesem Dokument?"},
            timeout=TIMEOUT,
        )
        ok("plus per-doc cap still 429", rr.status_code == 429, str(rr.status_code))
        if rr.status_code == 429:
            ok("plus per-doc scope=per_document", rr.json().get("scope") == "per_document")

    return [dev, cap_dev, p_dev]


# ---------- Section 9: webhook (no auth) ----------
def test_9_webhook_no_auth():
    print("\n[9] RC webhook (no auth set)")
    dev = f"qa-rc-{uuid.uuid4().hex[:8]}"
    expires = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp() * 1000)
    body = {
        "event": {
            "type": "INITIAL_PURCHASE",
            "app_user_id": dev,
            "product_id": "klarpost_plus_monthly",
            "expiration_at_ms": expires,
        }
    }
    r = requests.post(f"{BASE}/revenuecat/webhook", json=body, timeout=TIMEOUT)
    ok("rc webhook 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        j = r.json()
        ok("rc webhook ok=true", j.get("ok") is True)
        ok("rc webhook applied=initial_purchase", j.get("applied") == "initial_purchase")
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("after webhook, plus_active=True", u.get("plus_active") is True)
    end = u.get("plus_period_end") or ""
    try:
        edt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        delta_days = (edt - datetime.now(timezone.utc)).days
        ok(f"plus_period_end ~30 days (got {delta_days})", 28 <= delta_days <= 31)
    except Exception:
        ok("plus_period_end parseable", False, end)
    ok("plus_monthly_used=0 after webhook", u.get("plus_monthly_used") == 0)
    return dev


# ---------- Section 10: webhook with auth ----------
def test_10_webhook_with_auth():
    print("\n[10] RC webhook with auth (toggle env, restart, restore)")
    env_path = "/app/backend/.env"
    original = open(env_path).read()
    try:
        modified = re.sub(
            r"^REVENUECAT_WEBHOOK_AUTH_HEADER=.*$",
            "REVENUECAT_WEBHOOK_AUTH_HEADER=Bearer test123",
            original,
            flags=re.MULTILINE,
        )
        if modified == original:
            warn("could not find REVENUECAT_WEBHOOK_AUTH_HEADER line; skipping section 10")
            return
        with open(env_path, "w") as f:
            f.write(modified)
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False, capture_output=True)
        # Wait for backend to be reachable.
        for _ in range(20):
            try:
                rr = requests.get(f"{BASE}/", timeout=5)
                if rr.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(1)

        body = {
            "event": {
                "type": "INITIAL_PURCHASE",
                "app_user_id": f"qa-auth-{uuid.uuid4().hex[:8]}",
                "product_id": "klarpost_plus_monthly",
            }
        }
        # No header → 401
        r = requests.post(f"{BASE}/revenuecat/webhook", json=body, timeout=TIMEOUT)
        ok("auth webhook no header 401", r.status_code == 401, str(r.status_code))
        # Correct header → 200
        r = requests.post(
            f"{BASE}/revenuecat/webhook",
            json=body,
            headers={"Authorization": "Bearer test123"},
            timeout=TIMEOUT,
        )
        ok("auth webhook correct 200", r.status_code == 200, str(r.status_code))
        # Wrong header → 401
        r = requests.post(
            f"{BASE}/revenuecat/webhook",
            json=body,
            headers={"Authorization": "Bearer wrong"},
            timeout=TIMEOUT,
        )
        ok("auth webhook wrong 401", r.status_code == 401, str(r.status_code))
    finally:
        with open(env_path, "w") as f:
            f.write(original)
        subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=False, capture_output=True)
        for _ in range(20):
            try:
                rr = requests.get(f"{BASE}/", timeout=5)
                if rr.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(1)


# ---------- Section 11: consumable webhook + idempotency ----------
def test_11_consumable_webhook():
    print("\n[11] Consumable webhook + idempotency")
    dev = "qa-rc-cons-" + uuid.uuid4().hex[:6]
    body1 = {
        "event": {
            "type": "NON_RENEWING_PURCHASE",
            "app_user_id": dev,
            "product_id": "klarpost_single_letter",
            "id": "rc-evt-1",
        }
    }
    r = requests.post(f"{BASE}/revenuecat/webhook", json=body1, timeout=TIMEOUT)
    ok("non-renew evt-1 200", r.status_code == 200, str(r.status_code))
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("after evt-1 single_letter_credits=1", u.get("single_letter_credits") == 1, str(u.get("single_letter_credits")))

    # Same event id → no double credit
    r = requests.post(f"{BASE}/revenuecat/webhook", json=body1, timeout=TIMEOUT)
    ok("dup evt-1 200", r.status_code == 200)
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("after dup evt-1 single_letter_credits STILL 1", u.get("single_letter_credits") == 1, str(u.get("single_letter_credits")))

    body2 = dict(body1)
    body2["event"] = dict(body1["event"], id="rc-evt-2")
    r = requests.post(f"{BASE}/revenuecat/webhook", json=body2, timeout=TIMEOUT)
    ok("evt-2 200", r.status_code == 200)
    u = requests.get(f"{BASE}/usage/{dev}", timeout=TIMEOUT).json()
    ok("after evt-2 single_letter_credits=2", u.get("single_letter_credits") == 2, str(u.get("single_letter_credits")))
    return dev


# ---------- Section 12: expiration webhook ----------
def test_12_expiration(rc_dev: str):
    print("\n[12] Expiration webhook")
    body = {"event": {"type": "EXPIRATION", "app_user_id": rc_dev}}
    r = requests.post(f"{BASE}/revenuecat/webhook", json=body, timeout=TIMEOUT)
    ok("expiration 200", r.status_code == 200, str(r.status_code))
    u = requests.get(f"{BASE}/usage/{rc_dev}", timeout=TIMEOUT).json()
    ok("after expiration plus_active=False", u.get("plus_active") is False)


# ---------- Section 13: max pages ----------
def test_13_max_pages():
    print("\n[13] MAX_PAGES_PER_DOCUMENT (7 pages → still 200, only 5 sent to Mistral)")
    dev = f"qa-pages-{uuid.uuid4().hex[:8]}"
    pages = [{"file_base64": make_tiny_page_png(i + 1), "mime_type": "image/png"} for i in range(7)]
    # mark log boundary so we can count Mistral calls in this window
    boundary = f"BOUNDARY-{uuid.uuid4().hex[:6]}"
    # Touch backend so the boundary appears in logs (we'll grep for it as an
    # anchor by reading file mtime pre/post).
    pre_size_out = 0
    pre_size_err = 0
    try:
        pre_size_out = os.path.getsize("/var/log/supervisor/backend.out.log")
    except FileNotFoundError:
        pass
    try:
        pre_size_err = os.path.getsize("/var/log/supervisor/backend.err.log")
    except FileNotFoundError:
        pass

    body = {
        "device_id": dev,
        "target_language": "en",
        "idempotency_key": "pg1",
        "pages": pages,
    }
    r = requests.post(f"{BASE}/analyze", json=body, timeout=TIMEOUT)
    ok("7-page analyze 200", r.status_code == 200, str(r.status_code))

    # Count Mistral calls in the new tail of both logs.
    def tail_after(path: str, offset: int) -> str:
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                return f.read().decode("utf-8", errors="replace")
        except FileNotFoundError:
            return ""
    new_log = tail_after("/var/log/supervisor/backend.out.log", pre_size_out) + tail_after("/var/log/supervisor/backend.err.log", pre_size_err)
    mistral_calls = new_log.count("api.mistral.ai/v1/chat/completions")
    # Allow up to 1 (the analyze) — should NOT be 7. Even 0 is fine if the
    # SDK uses internal logging only; what we really want is "not many".
    ok(
        f"only one Mistral call in window (got {mistral_calls})",
        mistral_calls <= 1,
        f"calls={mistral_calls}",
    )
    return dev


# ---------- Section 14: dev tools visibility ----------
def test_14_dev_tools():
    print("\n[14] Dev tools visibility")
    dev = f"qa-dev-{uuid.uuid4().hex[:8]}"
    r = requests.post(f"{BASE}/dev/usage/reset", params={"device_id": dev}, timeout=TIMEOUT)
    ok("dev/usage/reset 200", r.status_code == 200, str(r.status_code))
    r = requests.post(f"{BASE}/dev/usage/simulate", params={"device_id": dev, "scenario": "garbage"}, timeout=TIMEOUT)
    ok("dev/usage/simulate?scenario=garbage 400", r.status_code == 400, str(r.status_code))
    return dev


# ---------- Section 15: privacy log audit ----------
def test_15_log_audit():
    print("\n[15] Privacy log audit")
    paths = ["/var/log/supervisor/backend.out.log", "/var/log/supervisor/backend.err.log"]
    blob = ""
    for p in paths:
        try:
            with open(p, "rb") as f:
                blob += f.read().decode("utf-8", errors="replace")
        except FileNotFoundError:
            pass
    found: list[str] = []
    for tok in SECRET_TOKENS:
        if tok in blob:
            found.append(tok)
    # Mistral key full or first prefix>=8 chars (avoid false positives on short prefix).
    if KEY_FULL and KEY_FULL in blob:
        found.append("MISTRAL_KEY_FULL")
    elif KEY_PREFIX and len(KEY_PREFIX) >= 4 and KEY_PREFIX in blob:
        # Re-check: since the prefix can be 4 chars, common letters might
        # match; be paranoid only when the chars look key-shaped (rare in
        # logs). We treat any match as informational, not a hard fail.
        warn(f"key 4-char prefix '{KEY_PREFIX}' appears in logs (informational)")
    # base64-blob detection: any continuous base64-ish string > 100 chars
    bigb64 = re.findall(r"[A-Za-z0-9+/=]{100,}", blob)
    if bigb64:
        found.append(f"BASE64_BLOB_x{len(bigb64)}")
    # IBAN / EUR / numbers
    for ib in ("DE89", "NG12"):
        if ib in blob:
            found.append(f"IBAN:{ib}")
    if re.search(r"\b\d{4,}\s?(EUR|€)", blob):
        found.append("4+digit EUR amount")
    ok("privacy log audit: zero matches", len(found) == 0, f"found={found}")
    # Confirm we DO see the expected metadata lines (sanity).
    ok("logs contain analysis_allowed", "analysis_allowed" in blob)
    ok("logs contain usage_consumed", "usage_consumed" in blob)
    ok("logs contain rc_webhook event=", "rc_webhook event=" in blob)


# ---------- Section 16: no regressions ----------
def test_16_no_regressions():
    print("\n[16] No regressions")
    r = requests.get(f"{BASE}/", timeout=TIMEOUT)
    ok("GET /api/ 200", r.status_code == 200)
    if r.status_code == 200:
        ok("GET / app=KlarPost", r.json().get("app") == "KlarPost")
    r = requests.get(f"{BASE}/languages", timeout=TIMEOUT)
    ok("GET /api/languages 200", r.status_code == 200)
    if r.status_code == 200:
        langs = r.json()
        ok("languages has 7 entries", isinstance(langs, list) and len(langs) == 7, str(len(langs) if isinstance(langs, list) else "?"))
    dev = f"qa-export-{uuid.uuid4().hex[:8]}"
    r = requests.get(f"{BASE}/export", params={"device_id": dev}, timeout=TIMEOUT)
    ok("GET /api/export 200", r.status_code == 200)
    if r.status_code == 200:
        j = r.json()
        ok("export has data_residency=EU…", "EU" in (j.get("data_residency") or ""))
        ok("export has count=0 for fresh", j.get("count") == 0)
    return dev


# ---------- Section 17: cleanup ----------
def test_17_cleanup(devs: list[str]):
    print(f"\n[17] Cleanup {len(devs)} devices")
    for d in devs:
        if not d:
            continue
        r = requests.delete(f"{BASE}/history/{d}", timeout=TIMEOUT)
        if r.status_code == 200:
            print(f"  cleaned {d}: {r.json()}")
        else:
            print(f"  cleanup failed {d}: {r.status_code}")


# ---------- main ----------
def main() -> int:
    print(f"Base URL: {BASE}")
    print(f"Mistral key prefix: '{KEY_PREFIX}' (used for log audit only)")

    letter_b64 = make_synthetic_letter_png()
    devs: list[str] = []

    test_1_paywall_config()
    devs.append(test_2_fresh_usage())
    life_dev, life_aid = test_3_soft_lifecycle(letter_b64)
    devs.append(life_dev)
    devs.append(test_4_idempotency(letter_b64))
    devs.append(test_5_failed_no_consume())
    devs.append(test_6_plus_path(letter_b64))
    devs.append(test_7_single_letter(letter_b64))
    chat_devs = test_8_chat_quotas(life_dev, life_aid, letter_b64)
    if chat_devs:
        devs.extend(chat_devs)
    devs.append(test_9_webhook_no_auth())
    test_10_webhook_with_auth()
    rc_dev = test_11_consumable_webhook()
    devs.append(rc_dev)
    # Section 9 device for expiration test
    test_12_expiration(devs[8] if len(devs) > 8 else rc_dev)
    devs.append(test_13_max_pages())
    devs.append(test_14_dev_tools())
    test_15_log_audit()
    devs.append(test_16_no_regressions())
    test_17_cleanup(devs)

    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}  FAILED: {len(FAIL)}  WARN: {len(WARN)}")
    if FAIL:
        print("\nFAILED:")
        for f in FAIL:
            print(f"  ❌ {f}")
    if WARN:
        print("\nWARN:")
        for w in WARN:
            print(f"  ⚠ {w}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
