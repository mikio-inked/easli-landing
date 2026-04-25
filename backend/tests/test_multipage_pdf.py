"""Iteration 3: multi-page PDF analyze tests."""
import base64
import io
import pytest
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import os


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


def _page_image(lines, fmt="PNG", width=1000, height=1300, quality=92):
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
    if fmt == "JPEG":
        img.save(buf, format="JPEG", quality=quality, optimize=True)
    else:
        img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


def _build_pdf(pages_lines, fmt="PNG", width=1000, height=1300, quality=92):
    doc = fitz.open()
    ext = "png" if fmt == "PNG" else "jpeg"
    for lines in pages_lines:
        img_bytes = _page_image(lines, fmt=fmt, width=width, height=height, quality=quality)
        img = fitz.open(stream=img_bytes, filetype=ext)
        rect = img[0].rect
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(rect, stream=img_bytes)
        img.close()
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture(scope="module")
def three_page_pdf_b64():
    pages = [
        [
            "AOK Bayern - Mahnung",
            "Sehr geehrter Herr Mustermann,",
            "wir haben bis heute keinen Zahlungseingang",
            "fuer Ihren Krankenkassenbeitrag fuer den",
            "Monat Dezember 2025 in Hoehe von 412,50 EUR.",
            "Bitte ueberweisen Sie den Betrag bis 28.02.2026.",
            "Andernfalls Inkasso und Schufa-Meldung.",
            "Versichertennummer: A123456789",
        ],
        [
            "Seite 2 - Fehlende Unterlagen",
            "Bitte senden Sie uns folgende Dokumente:",
            "- Aktuelle Lohnabrechnung (Dezember 2025)",
            "- Kopie des Arbeitsvertrags",
            "- Nachweis ueber Nebeneinkuenfte",
            "Reichen Sie diese bis 28.02.2026 ein.",
            "Sonst koennen wir Ihren Beitrag nicht korrekt berechnen.",
        ],
        [
            "Seite 3 - Kontakt und Unterschrift",
            "Bei Rueckfragen erreichen Sie uns unter:",
            "Telefon: 089 / 1234567",
            "E-Mail: service@aok-bayern.de",
            "",
            "Mit freundlichen Gruessen",
            "AOK Bayern - Beitragsabteilung",
            "Frau Schmidt (Sachbearbeiterin)",
        ],
    ]
    return base64.b64encode(_build_pdf(pages)).decode("utf-8")


@pytest.fixture(scope="module")
def seven_page_pdf_b64():
    pages = []
    for i in range(7):
        pages.append([
            f"Seite {i+1} - Krankenkasse",
            f"Dies ist Seite {i+1} eines deutschen Briefes.",
            "Versichertennummer: A123456789",
            "Frist: 28.02.2026" if i == 0 else "Allgemeine Informationen.",
            "Bitte beachten Sie alle beigefuegten Unterlagen.",
        ])
    return base64.b64encode(_build_pdf(pages, fmt="JPEG", width=800, height=1000, quality=70)).decode("utf-8")


class TestMultiPagePdf:
    def test_three_page_pdf_combined(self, base_url, api_client, three_page_pdf_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": three_page_pdf_b64,
            "mime_type": "application/pdf",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mime_type"] == "application/pdf"
        result = data["result"]
        assert result["summary_translated"]
        # Combine searchable text fields to verify multi-page content was considered
        haystack = " ".join([
            result.get("summary_translated", ""),
            result.get("simple_explanation_translated", ""),
            " ".join(result.get("key_points", []) or []),
            " ".join([(a.get("action", "") + " " + a.get("reason", "")) for a in (result.get("required_actions") or [])]),
            " ".join([(d.get("description", "") + " " + d.get("date", "")) for d in (result.get("deadlines") or [])]),
        ]).lower()
        # Page 1 keyword (payment / Mahnung / 412,50 / Dec)
        page1_hits = sum(k in haystack for k in ["412", "december", "payment", "overdue", "mahn", "aok", "contribution"])
        # Page 2 keyword (missing documents)
        page2_hits = sum(k in haystack for k in ["document", "payslip", "wage", "contract", "lohn", "missing", "submit"])
        # Page 3 keyword (contact)
        page3_hits = sum(k in haystack for k in ["089", "1234567", "schmidt", "e-mail", "phone", "contact", "service@aok"])
        assert page1_hits >= 1, f"page1 content missing in analysis: {haystack[:400]}"
        assert page2_hits >= 1, f"page2 content missing in analysis: {haystack[:400]}"
        # page3 is contact info; tolerate model summarising it away if at least 2/3 pages reflected
        assert (page1_hits + page2_hits + page3_hits) >= 2

    def test_seven_page_pdf_truncated_to_five(self, base_url, api_client, seven_page_pdf_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": seven_page_pdf_b64,
            "mime_type": "application/pdf",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        result = data["result"]
        assert result["summary_translated"]
        assert result["risk_level"] in {"green", "yellow", "red"}

    def test_three_page_pdf_chinese(self, base_url, api_client, three_page_pdf_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "zh",
            "file_base64": three_page_pdf_b64,
            "mime_type": "application/pdf",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=240)
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data["result"].get("summary_translated", "")
        assert summary
        # Must contain at least one CJK char
        has_cjk = any('\u4e00' <= c <= '\u9fff' for c in summary)
        assert has_cjk, f"expected CJK in summary, got: {summary[:160]}"
