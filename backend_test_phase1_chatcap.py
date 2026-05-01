"""Retry-friendly version of chat-cap + plus-bypass tests.

The original Phase-1 run tripped Mistral's free-tier rate limit when blasting
20+ chat calls back-to-back. This script paces calls and retries on 502,
purely to verify the *quota logic*, not the LLM.
"""
import base64
import io
import time
import uuid
from typing import Any
import requests
from PIL import Image, ImageDraw, ImageFont

BASE = "https://doc-scanner-de.preview.emergentagent.com/api"
TIMEOUT = 90


def make_letter():
    img = Image.new("RGB", (1000, 1400), "white")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    txt = [
        "AOK Nordwest — Beitragsanpassung",
        "",
        "Sehr geehrte Frau Mustermann,",
        "der monatliche Beitrag beträgt 248,50 EUR ab 01.01.2026.",
        "Versichertennummer: A123456789",
    ]
    y = 80
    for ln in txt:
        d.text((60, y), ln, fill="black", font=font); y += 38
    buf = io.BytesIO(); img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def call_with_retry(method: str, url: str, max_attempts: int = 4, **kw) -> Any:
    last = None
    for i in range(max_attempts):
        r = requests.request(method, url, timeout=TIMEOUT, **kw)
        last = r
        if r.status_code == 502 or (r.status_code == 429 and "rate" in r.text.lower()):
            time.sleep(3 + i * 3)
            continue
        return r
    return last


def main():
    letter = make_letter()
    PASS = []; FAIL = []
    def ok(label, cond, info=""):
        (PASS if cond else FAIL).append(f"{label}{(' — '+info) if info else ''}")
        print(f"  {'✅' if cond else '❌'} {label}{(' — '+info) if info else ''}")

    # ===== A. Chat TOTAL cap (21st blocks) =====
    print("\n[A] Chat TOTAL cap (5 analyses × 4 chats = 20 then 1 more on 6th = 21st blocks)")
    dev = f"qa-tcap-{uuid.uuid4().hex[:6]}"
    aids = []
    for i in range(5):
        body = {"device_id": dev, "target_language": "en", "idempotency_key": f"ta{i}",
                "file_base64": letter, "mime_type": "image/png"}
        r = call_with_retry("POST", f"{BASE}/analyze", json=body)
        if r.status_code == 200:
            aids.append(r.json().get("id"))
        time.sleep(1.5)
    ok("got 5 analyses", len(aids) == 5, str(len(aids)))
    sent = 0
    for aid in aids:
        for q in range(4):
            r = call_with_retry("POST", f"{BASE}/analyses/{aid}/chat",
                                json={"device_id": dev, "message": f"Frage {q+1}: Was steht im Brief?"})
            if r.status_code == 200:
                sent += 1
            else:
                print(f"     chat aid={aid[:8]} q={q+1} status={r.status_code} body={r.text[:120]}")
            time.sleep(1.2)
    ok("first 20 chats succeeded", sent == 20, str(sent))

    # 6th analysis to test 21st chat
    body6 = {"device_id": dev, "target_language": "en", "idempotency_key": "ta6",
             "file_base64": letter, "mime_type": "image/png"}
    r = call_with_retry("POST", f"{BASE}/analyze", json=body6)
    ok("6th analyze 200", r.status_code == 200, str(r.status_code))
    if r.status_code == 200:
        aid6 = r.json().get("id")
        time.sleep(1.5)
        r = call_with_retry("POST", f"{BASE}/analyses/{aid6}/chat",
                            json={"device_id": dev, "message": "Frage 21 — sollte das blocken?"})
        ok("21st chat is 429", r.status_code == 429, str(r.status_code))
        if r.status_code == 429:
            j = r.json()
            ok("21st scope=total", j.get("scope") == "total", str(j.get("scope")))
            ok("21st error contains 'limit_reached'", "limit_reached" in str(j.get("error", "")))

    # ===== B. Plus bypass — 25 chats across multiple analyses =====
    print("\n[B] Plus bypass (sim plus_active) — should NOT hit total cap")
    pdev = f"qa-plusbp-{uuid.uuid4().hex[:6]}"
    r = call_with_retry("POST", f"{BASE}/dev/usage/simulate", params={"device_id": pdev, "scenario": "plus_active"})
    ok("sim plus_active", r.status_code == 200)
    paids = []
    for i in range(6):
        body = {"device_id": pdev, "target_language": "en", "idempotency_key": f"pb{i}",
                "file_base64": letter, "mime_type": "image/png"}
        r = call_with_retry("POST", f"{BASE}/analyze", json=body)
        if r.status_code == 200:
            paids.append(r.json().get("id"))
        time.sleep(1.5)
    ok("got >=5 plus analyses", len(paids) >= 5, str(len(paids)))

    chats = 0
    for aid in paids:
        if chats >= 25:
            break
        for _ in range(5):
            if chats >= 25:
                break
            r = call_with_retry("POST", f"{BASE}/analyses/{aid}/chat",
                                json={"device_id": pdev, "message": "Was steht im Brief?"})
            if r.status_code == 200:
                chats += 1
            else:
                print(f"     plus chat status={r.status_code} body={r.text[:140]}")
                break
            time.sleep(1.2)
    ok(f"plus 25 chats across docs without total-cap (got {chats})", chats >= 25)

    # Per-doc cap should still apply to plus
    if paids:
        r = call_with_retry("POST", f"{BASE}/analyses/{paids[0]}/chat",
                            json={"device_id": pdev, "message": "6. Frage zu diesem Dokument?"})
        ok("plus per-doc 6th = 429", r.status_code == 429, str(r.status_code))
        if r.status_code == 429:
            ok("plus per-doc scope=per_document", r.json().get("scope") == "per_document")

    # cleanup
    for d in (dev, pdev):
        requests.delete(f"{BASE}/history/{d}", timeout=TIMEOUT)

    print("\n=" * 30)
    print(f"PASS={len(PASS)}  FAIL={len(FAIL)}")
    for f in FAIL: print(" ❌", f)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
