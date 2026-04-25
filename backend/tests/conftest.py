import os
import io
import base64
import pytest
import requests
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF


BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL")
if not BASE_URL:
    # Read from frontend .env as fallback
    try:
        env_path = "/app/frontend/.env"
        with open(env_path) as f:
            for line in f:
                if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"')
                    break
    except Exception:
        pass

if not BASE_URL:
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL must be set")

BASE_URL = BASE_URL.rstrip("/")


def _get_font(size: int = 22):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_german_letter_image(fmt: str = "JPEG") -> bytes:
    """Generate a synthetic German letter image with realistic content."""
    width, height = 1000, 1300
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    title_font = _get_font(28)
    head_font = _get_font(22)
    body_font = _get_font(20)

    # Sender header
    draw.text((60, 60), "AOK Bayern - Die Gesundheitskasse", fill="black", font=title_font)
    draw.text((60, 100), "Carl-Wery-Strasse 28, 81739 Muenchen", fill="black", font=body_font)
    draw.line([(60, 140), (940, 140)], fill="black", width=2)

    # Recipient
    draw.text((60, 170), "Herr Max Mustermann", fill="black", font=body_font)
    draw.text((60, 200), "Musterstrasse 12", fill="black", font=body_font)
    draw.text((60, 230), "80331 Muenchen", fill="black", font=body_font)

    # Date and reference
    draw.text((700, 170), "15.01.2026", fill="black", font=body_font)
    draw.text((60, 290), "Versichertennummer: A123456789", fill="black", font=body_font)

    # Subject
    draw.text((60, 340), "Betreff: Mahnung - Ausstehender Krankenkassenbeitrag",
              fill="black", font=head_font)

    # Body
    body = [
        "Sehr geehrter Herr Mustermann,",
        "",
        "trotz unserer Zahlungserinnerung haben wir bis heute keinen",
        "Zahlungseingang fuer Ihren Krankenkassenbeitrag fuer den",
        "Monat Dezember 2025 in Hoehe von 412,50 EUR feststellen koennen.",
        "",
        "Wir fordern Sie hiermit auf, den ausstehenden Betrag",
        "spaetestens bis zum 28.02.2026 auf das untenstehende Konto",
        "zu ueberweisen. Andernfalls muessen wir leider weitere",
        "Schritte einleiten, einschliesslich der Uebergabe an ein",
        "Inkassobuero und der Meldung an die Schufa.",
        "",
        "Bei Rueckfragen erreichen Sie uns unter 089 / 1234567 oder",
        "per E-Mail an service@aok-bayern.de.",
        "",
        "Mit freundlichen Gruessen",
        "AOK Bayern - Beitragsabteilung",
    ]
    y = 400
    for line in body:
        draw.text((60, y), line, fill="black", font=body_font)
        y += 32

    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=92)
    return buf.getvalue()


def make_german_letter_pdf() -> bytes:
    """Generate a small PDF (one page) with the same German letter content."""
    img_bytes = make_german_letter_image(fmt="PNG")
    # Create a PDF using PyMuPDF from the image bytes
    doc = fitz.open()
    img = fitz.open(stream=img_bytes, filetype="png")
    rect = img[0].rect
    page = doc.new_page(width=rect.width, height=rect.height)
    page.insert_image(rect, stream=img_bytes)
    pdf_bytes = doc.tobytes()
    doc.close()
    img.close()
    return pdf_bytes


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def german_letter_jpeg_b64():
    return base64.b64encode(make_german_letter_image("JPEG")).decode("utf-8")


@pytest.fixture(scope="session")
def german_letter_png_b64():
    return base64.b64encode(make_german_letter_image("PNG")).decode("utf-8")


@pytest.fixture(scope="session")
def german_letter_pdf_b64():
    return base64.b64encode(make_german_letter_pdf()).decode("utf-8")


@pytest.fixture()
def device_id():
    import uuid
    return f"TEST_DEVICE_{uuid.uuid4()}"
