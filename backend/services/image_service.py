"""easli — image processing service.

Responsibilities:
  • Convert multi-page PDFs to per-page PNG/base64 (via PyMuPDF / fitz).
  • Downscale large iPhone-scan images so we don't blow through Mistral's
    per-minute vision-token rate limit.

Privacy: this module never logs the binary, the base64 string, EXIF data,
or any pixel-derived value. Only sizes (input vs output) and an opaque
page index are logged.
"""

import base64
import logging
from io import BytesIO
from typing import List, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger("server")  # legacy name keeps dashboards stable

__all__ = [
    "pdf_to_images_base64",
    "compress_image_for_vision",
]


# ---------------------------------------------------------------------------
# 1. PDF → PNG/base64
# ---------------------------------------------------------------------------
def pdf_to_images_base64(pdf_bytes: bytes, max_pages: int = 5) -> List[Tuple[str, str]]:
    """Convert up to first `max_pages` pages of a PDF to PNG base64.

    Returns a list of (base64, mime) tuples in page order.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF has no pages")
    pages: List[Tuple[str, str]] = []
    page_count = min(max_pages, doc.page_count)
    matrix = fitz.Matrix(2.0, 2.0)
    for i in range(page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=matrix)
        pages.append((
            base64.b64encode(pix.tobytes("png")).decode("utf-8"),
            "image/png",
        ))
    doc.close()
    return pages


# ---------------------------------------------------------------------------
# 2. Vision-friendly image compression
# ---------------------------------------------------------------------------
# Mistral Vision charges per image-token. Large iPhone scans (4-8 MB JPEG) blow
# through both the per-request token budget AND the per-minute token-rate-limit
# very fast and have caused HTTP 429s in production. To prevent that we
# downscale any image whose base64 payload exceeds ~256 KB binary to a sane
# vision-friendly size (max 1280 x 1800 px, JPEG quality 60) BEFORE the call.
#
# Compression is lossless w.r.t. OCR readability for European letters — we've
# verified 1280px is more than enough for "Sehr geehrte Frau …" letterhead at
# Bodoni/Helvetica resolutions.

# Tuned for Mistral free-tier:
#  • Smaller dimensions reduce per-image vision-token count by ~35-50%, which
#    lets multi-page (3-5 page) scans fit inside the per-second token rate
#    on Mistral's free plan.
#  • The threshold is intentionally low so we re-compress almost everything
#    coming from iOS — even when the client did its own compression pass,
#    a second pass at our tighter target costs <100ms and reliably caps
#    vision-token usage. Anything truly small (<256 KB binary) is passed
#    through untouched.
#  • Quality 60 still produces excellent OCR for German text at 1280px width.
COMPRESS_THRESHOLD_BYTES = 256 * 1024
MAX_VISION_WIDTH_PX = 1280
MAX_VISION_HEIGHT_PX = 1800
JPEG_QUALITY_FOR_VISION = 60

# Lazy-import Pillow so import errors only surface when we actually compress.
try:
    from PIL import Image, ImageOps  # type: ignore[import-not-found]
    _PIL_AVAILABLE = True
except ImportError:  # pragma: no cover — Pillow is in requirements.txt
    _PIL_AVAILABLE = False


def compress_image_for_vision(
    page_index: int,
    b64: str,
    mime: str,
) -> Tuple[str, str]:
    """Return (compressed_b64, 'image/jpeg') if compression triggered, else
    pass-through (b64, mime).

    Idempotent: small images skip compression entirely. Errors degrade
    gracefully to the original payload — we'd rather try a slightly
    oversized image than fail the whole request.
    """
    # Cheap, accurate-enough binary-size estimate from the base64 length.
    binary_size_estimate = (len(b64) * 3) // 4
    if binary_size_estimate <= COMPRESS_THRESHOLD_BYTES:
        return b64, mime
    if not _PIL_AVAILABLE:
        logger.warning(
            "image_compress_skipped_no_pil page=%d est_bytes=%d",
            page_index, binary_size_estimate,
        )
        return b64, mime

    try:
        raw = base64.b64decode(b64, validate=False)
        before_bytes = len(raw)

        with Image.open(BytesIO(raw)) as img:
            # Honour EXIF rotation so text isn't sideways for Mistral.
            img = ImageOps.exif_transpose(img)
            # Convert to RGB (drop alpha for JPEG, normalise CMYK / palette).
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Pillow's thumbnail() preserves aspect ratio in-place, only
            # downscales (never upscales) — exactly what we want.
            img.thumbnail(
                (MAX_VISION_WIDTH_PX, MAX_VISION_HEIGHT_PX),
                Image.Resampling.LANCZOS,
            )

            buf = BytesIO()
            img.save(
                buf,
                format="JPEG",
                quality=JPEG_QUALITY_FOR_VISION,
                optimize=True,
                progressive=True,
            )
            after_bytes = buf.tell()
            new_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

        # Privacy: log only sizes — never the bytes.
        logger.info(
            "image_compressed page=%d before_bytes=%d after_bytes=%d ratio=%.2f",
            page_index, before_bytes, after_bytes,
            (after_bytes / before_bytes) if before_bytes else 1.0,
        )
        return new_b64, "image/jpeg"
    except Exception as e:
        # Never let a Pillow failure poison the whole analysis — fall back
        # to the original bytes and let Mistral decide. We log only the type.
        logger.warning(
            "image_compress_failed page=%d error_type=%s — passing original through",
            page_index, type(e).__name__,
        )
        return b64, mime
