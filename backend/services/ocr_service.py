"""easli — Mistral OCR service.

Fans an N-page scan out to the dedicated `mistral-ocr-latest` model in
parallel (semaphore-limited so the free tier doesn't 429), then returns a
list of per-page markdown strings in the same order as the input.

Design trade-offs:
  • We do NOT use the retrying chat-completion helper here — OCR is its
    own dedicated endpoint and the failure mode we care about is per-page
    (a single bad page shouldn't block the rest of the scan).
  • On a per-page error we insert a localised placeholder so the downstream
    analysis can still run on the readable pages.

Privacy: only page index + chars-count are logged. Never the text itself.
"""

import asyncio
import logging
from typing import List, Tuple

from fastapi import HTTPException

from core.config import MISTRAL_OCR_MODEL, mistral_client

logger = logging.getLogger("server")

__all__ = ["ocr_pages_with_mistral"]


async def ocr_pages_with_mistral(
    images: List[Tuple[str, str]],
) -> List[str]:
    """Run Mistral OCR on every page in parallel and return per-page markdown.

    Returns a list the same length as `images`. If a single page fails we
    insert a short "[Seite N konnte nicht gelesen werden]" placeholder so the
    combined-text analysis can still run on the other pages.
    """
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    # A semaphore of 3 keeps us friendly with Mistral's per-second RPS limit
    # on the free tier while still shrinking a 4-page scan to ~2 rounds.
    sem = asyncio.Semaphore(3)

    async def ocr_one(idx: int, b64: str, mime: str) -> str:
        async with sem:
            url_mime = mime or "image/png"
            try:
                # mistralai SDK: ocr.process_async with a document = image_url.
                # We pass a data URL so no upload/file step is needed.
                resp = await mistral_client.ocr.process_async(
                    model=MISTRAL_OCR_MODEL,
                    document={
                        "type": "image_url",
                        "image_url": f"data:{url_mime};base64,{b64}",
                    },
                    include_image_base64=False,
                )
                md_pages = []
                for p in (resp.pages or []):
                    md = getattr(p, "markdown", None)
                    if isinstance(md, str) and md.strip():
                        md_pages.append(md)
                combined = "\n\n".join(md_pages).strip()
                logger.info("ocr_page_ok idx=%d chars=%d", idx, len(combined))
                if not combined:
                    return f"[Seite {idx + 1}: kein Text erkannt]"
                return combined
            except Exception as e:
                logger.warning(
                    "ocr_page_failed idx=%d error_type=%s",
                    idx, type(e).__name__,
                )
                return f"[Seite {idx + 1} konnte nicht gelesen werden]"

    tasks = [ocr_one(i, b64, mime) for i, (b64, mime) in enumerate(images)]
    return await asyncio.gather(*tasks)
