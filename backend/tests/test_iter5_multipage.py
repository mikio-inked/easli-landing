"""Iteration 5: multi-page (pages:[]) AnalyzeRequest tests."""
import base64
import io
import os
import uuid
import pytest
import fitz
from PIL import Image, ImageDraw, ImageFont


def _font(size: int = 22):
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _make_image(lines, fmt="JPEG", width=1000, height=1300):
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    body_font = _font(22)
    head_font = _font(28)
    y = 80
    for i, line in enumerate(lines):
        f = head_font if i == 0 else body_font
        draw.text((60, y), line, fill="black", font=f)
        y += 38 if i == 0 else 32
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=88)
    return buf.getvalue()


def _make_pdf(pages_lines):
    doc = fitz.open()
    for lines in pages_lines:
        img_bytes = _make_image(lines, fmt="PNG")
        img = fitz.open(stream=img_bytes, filetype="png")
        rect = img[0].rect
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(rect, stream=img_bytes)
        img.close()
    out = doc.tobytes()
    doc.close()
    return out


@pytest.fixture(scope="module")
def page1_b64():
    lines = [
        "AOK Bayern - Mahnung",
        "Sehr geehrter Herr Mustermann,",
        "wir haben bis heute keinen Zahlungseingang",
        "fuer Ihren Krankenkassenbeitrag fuer Dezember 2025",
        "in Hoehe von 412,50 EUR feststellen koennen.",
        "Frist: 28.02.2026.",
        "Personalausweis-Nummer: T01234567",
    ]
    return base64.b64encode(_make_image(lines)).decode("utf-8")


@pytest.fixture(scope="module")
def page2_b64():
    lines = [
        "Seite 2 - Kontakt",
        "Bitte erreichen Sie uns telefonisch unter:",
        "Telefon: 089-123456",
        "E-Mail: service@aok-bayern.de",
        "Mit freundlichen Gruessen",
        "AOK Bayern - Beitragsabteilung",
    ]
    return base64.b64encode(_make_image(lines)).decode("utf-8")


@pytest.fixture(scope="module")
def page3_b64():
    lines = [
        "Seite 3 - Unterlagen",
        "Bitte senden Sie uns folgende Dokumente:",
        "- Aktuelle Lohnabrechnung",
        "- Kopie des Arbeitsvertrags",
        "Frist fuer Unterlagen: 28.02.2026.",
    ]
    return base64.b64encode(_make_image(lines)).decode("utf-8")


@pytest.fixture(scope="module")
def small_pdf_b64():
    return base64.b64encode(_make_pdf([
        ["AOK PDF Seite 1", "Versicherung", "Beitrag 412,50 EUR"],
        ["AOK PDF Seite 2", "Frist 28.02.2026", "Bitte zahlen"],
    ])).decode("utf-8")


# ---------------- Iteration 5 — pages:[] shape ----------------

class TestPagesShape:
    def test_two_image_pages_combined(self, base_url, api_client, page1_b64, page2_b64):
        dev = f"TEST_DEVICE_{uuid.uuid4()}"
        payload = {
            "device_id": dev,
            "target_language": "en",
            "pages": [
                {"file_base64": page1_b64, "mime_type": "image/jpeg"},
                {"file_base64": page2_b64, "mime_type": "image/jpeg"},
            ],
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["device_id"] == dev
        assert data["target_language"] == "en"
        # mime_type is taken from the first page
        assert data["mime_type"] == "image/jpeg"
        result = data["result"]
        assert result["summary_translated"]
        haystack = " ".join([
            result.get("summary_translated", ""),
            result.get("simple_explanation_translated", ""),
            " ".join(result.get("key_points", []) or []),
            " ".join([(a.get("action", "") + " " + a.get("reason", "")) for a in (result.get("required_actions") or [])]),
            " ".join([(d.get("description", "") + " " + d.get("date", "")) for d in (result.get("deadlines") or [])]),
        ]).lower()
        # Page 1 token
        p1 = sum(k in haystack for k in ["412", "december", "mahn", "overdue", "payment", "aok", "contribution", "personalausweis", "id card", "identity"])
        # Page 2 token
        p2 = sum(k in haystack for k in ["089", "123456", "phone", "telephone", "telefon", "contact", "service@aok"])
        assert p1 >= 1, f"page 1 content missing: {haystack[:400]}"
        assert p2 >= 1, f"page 2 content missing: {haystack[:400]}"

        # Cleanup
        api_client.delete(f"{base_url}/api/analyses", params={"device_id": dev})

    def test_three_pages_chinese(self, base_url, api_client, page1_b64, page2_b64, page3_b64):
        dev = f"TEST_DEVICE_{uuid.uuid4()}"
        payload = {
            "device_id": dev,
            "target_language": "zh",
            "pages": [
                {"file_base64": page1_b64, "mime_type": "image/jpeg"},
                {"file_base64": page2_b64, "mime_type": "image/jpeg"},
                {"file_base64": page3_b64, "mime_type": "image/jpeg"},
            ],
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data["result"].get("summary_translated", "")
        assert summary
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in summary)
        assert has_cjk, f"expected CJK in summary, got: {summary[:160]}"
        assert data["target_language_label"].startswith("Chinese")
        api_client.delete(f"{base_url}/api/analyses", params={"device_id": dev})

    def test_legacy_single_file_still_works_and_listed(self, base_url, api_client, page1_b64):
        dev = f"TEST_DEVICE_{uuid.uuid4()}"
        payload = {
            "device_id": dev,
            "target_language": "en",
            "file_base64": page1_b64,
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        rec = r.json()
        rid = rec["id"]
        # listing
        r2 = api_client.get(f"{base_url}/api/analyses", params={"device_id": dev})
        assert r2.status_code == 200
        items = r2.json()
        assert any(it["id"] == rid for it in items)
        api_client.delete(f"{base_url}/api/analyses", params={"device_id": dev})

    def test_empty_pages_array_returns_400(self, base_url, api_client):
        dev = f"TEST_DEVICE_{uuid.uuid4()}"
        payload = {
            "device_id": dev,
            "target_language": "en",
            "pages": [],
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=30)
        # Empty pages -> falls through into the legacy branch (file_base64 missing) -> 400
        assert r.status_code == 400, r.text

    def test_pages_with_pdf_entry_expands(self, base_url, api_client, small_pdf_b64, page2_b64):
        dev = f"TEST_DEVICE_{uuid.uuid4()}"
        payload = {
            "device_id": dev,
            "target_language": "en",
            "pages": [
                {"file_base64": small_pdf_b64, "mime_type": "application/pdf"},
                {"file_base64": page2_b64, "mime_type": "image/jpeg"},
            ],
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["result"]["summary_translated"]
        # mime_type should reflect first page input (pdf)
        assert data["mime_type"] == "application/pdf"
        api_client.delete(f"{base_url}/api/analyses", params={"device_id": dev})
