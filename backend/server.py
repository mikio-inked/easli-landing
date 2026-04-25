from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import json
import base64
import logging
import re
import tempfile
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Tuple
import uuid
from datetime import datetime, timezone

import fitz  # PyMuPDF
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Create the main app without a prefix
app = FastAPI(title="KlarPost API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== MODELS ====================

LANGUAGES = {
    "zh": "Chinese Simplified (简体中文)",
    "vi": "Vietnamese (Tiếng Việt)",
    "tr": "Turkish (Türkçe)",
    "ru": "Russian (Русский)",
    "en": "English",
    "es": "Spanish (Español)",
}


class Deadline(BaseModel):
    date: str = ""
    description: str = ""
    confidence: Literal["low", "medium", "high"] = "low"


class RequiredAction(BaseModel):
    action: str = ""
    urgency: Literal["low", "medium", "high"] = "low"
    reason: str = ""


class AnalysisResult(BaseModel):
    source_language: str = "German"
    target_language: str = ""
    document_type: str = ""
    sender: str = ""
    summary_translated: str = ""
    simple_explanation_translated: str = ""
    key_points: List[str] = []
    deadlines: List[Deadline] = []
    required_actions: List[RequiredAction] = []
    risk_level: Literal["green", "yellow", "red"] = "green"
    risk_reason: str = ""
    german_reply_draft: str = ""
    reply_draft_explanation_translated: str = ""
    questions_to_ask: List[str] = []
    uncertainties: List[str] = []
    disclaimer: str = ""


class AnalyzeRequest(BaseModel):
    device_id: str
    target_language: str  # one of LANGUAGES keys
    file_base64: str
    mime_type: str  # image/jpeg, image/png, image/webp, application/pdf


class AnalysisRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str
    target_language: str
    target_language_label: str
    mime_type: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: AnalysisResult


class AnalysisListItem(BaseModel):
    id: str
    created_at: str
    target_language: str
    target_language_label: str
    document_type: str
    sender: str
    risk_level: str
    summary_translated: str


# ==================== HELPERS ====================

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
        pages.append((base64.b64encode(pix.tobytes("png")).decode("utf-8"), "image/png"))
    doc.close()
    return pages


def build_system_prompt(target_language_label: str) -> str:
    return f"""You are KlarPost, a careful, trustworthy assistant that helps people in Germany understand German documents.

Your job:
1. Carefully read the German document in the provided image.
2. Explain it clearly in {target_language_label}.
3. Identify deadlines, required actions, and risk level.
4. Provide a neutral German reply draft if useful.
5. Translate the explanation of the reply draft into {target_language_label}.

CRITICAL RULES:
- You MUST NOT provide legal, tax, financial, or medical advice.
- You MUST NOT diagnose medical conditions or recommend treatment.
- You MUST NOT tell the user whether they must or must not pay.
- You MUST clearly mark uncertainty when text is unclear or scan quality is low.
- You MUST never invent missing information.
- For medical documents: always recommend discussing diagnosis, treatment, medication with a qualified doctor.
- For legal/tax/immigration/housing/debt/government documents: always recommend contacting the relevant authority, qualified advisor, legal aid service, tax advisor, lawyer, or counseling center.
- If the document could have serious consequences and the user is unsure, recommend contacting the sender.

Risk levels:
- green: informational only, no urgent action detected
- yellow: may require action, review, payment, appointment, document submission, or follow-up
- red: contains a deadline, payment demand, warning, cancellation, legal/official consequence, missing document request, health-related urgency, or other time-sensitive issue

If the image does NOT appear to be a German document or text is unreadable:
- Set document_type to "Unbekannt / Unknown" (or equivalent)
- Set risk_level to "yellow"
- Add a clear note in uncertainties explaining the issue.
- Use empty strings/lists for fields you cannot fill.

You MUST respond ONLY with a single valid JSON object that matches the schema below. Do NOT include any text before or after the JSON. Do NOT wrap it in markdown code fences.

JSON Schema:
{{
  "source_language": "German",
  "target_language": "{target_language_label}",
  "document_type": "string - the type of document (e.g. 'Krankenkasse Brief', 'Mietvertrag Kündigung', 'Rundfunkbeitrag', 'Mahnung', etc.) — write it briefly in {target_language_label}",
  "sender": "string - sender or organization, as written on the document (keep proper names in original)",
  "summary_translated": "string - one short paragraph in {target_language_label} summarising the document",
  "simple_explanation_translated": "string - simple, non-technical explanation in {target_language_label} of what this document means for the recipient",
  "key_points": ["short bullet points in {target_language_label}"],
  "deadlines": [
    {{
      "date": "ISO date or human-readable date as written",
      "description": "short description in {target_language_label}",
      "confidence": "low|medium|high"
    }}
  ],
  "required_actions": [
    {{
      "action": "what the user may need to do, in {target_language_label}",
      "urgency": "low|medium|high",
      "reason": "short reason in {target_language_label}"
    }}
  ],
  "risk_level": "green|yellow|red",
  "risk_reason": "short reason in {target_language_label} explaining the risk level",
  "german_reply_draft": "polite neutral reply draft in German (only if relevant; otherwise empty string)",
  "reply_draft_explanation_translated": "short explanation in {target_language_label} of what the reply draft says",
  "questions_to_ask": ["helpful, neutral questions the user could ask the sender or a qualified advisor — in {target_language_label}"],
  "uncertainties": ["clearly note anything uncertain, unreadable, or low-confidence — in {target_language_label}"],
  "disclaimer": "short disclaimer in {target_language_label} stating: KlarPost does not provide legal, tax, financial or medical advice; always confirm with a qualified professional or the sender."
}}

Use ONLY the {target_language_label} for translated fields. Keep document_type concise. Be conservative with deadlines and risk levels. If unsure, say so in uncertainties.
"""


def extract_json_from_text(text: str) -> Optional[dict]:
    """Try to find a JSON object in the LLM response."""
    if not text:
        return None
    text = text.strip()
    # If wrapped in code fences, strip them
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    # First, try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


async def analyze_with_gpt(images: List[Tuple[str, str]], target_language_label: str) -> AnalysisResult:
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="LLM key not configured")
    if not images:
        raise HTTPException(status_code=400, detail="No image content to analyze")

    session_id = f"klarpost-{uuid.uuid4()}"
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=build_system_prompt(target_language_label),
    ).with_model("openai", "gpt-5.2")

    image_contents = [ImageContent(image_base64=b64) for b64, _ in images]
    page_note = (
        f"This document has {len(images)} page(s). They are provided in order from page 1. "
        "Treat them as ONE document and produce a single combined analysis."
        if len(images) > 1
        else ""
    )
    user_message = UserMessage(
        text=(
            f"Please analyze this German document and respond ONLY with the JSON object as specified. "
            f"The user's selected target language is {target_language_label}. {page_note}"
        ).strip(),
        file_contents=image_contents,
    )

    try:
        response_text = await chat.send_message(user_message)
    except Exception as e:
        logger.exception("LLM call failed")
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {str(e)}")

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error("Could not parse JSON from LLM response. Raw: %s", response_text[:500] if response_text else "")
        raise HTTPException(status_code=502, detail="AI returned an invalid response. Please try again.")

    # Ensure target_language is set
    parsed["target_language"] = target_language_label
    parsed["source_language"] = "German"

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception("Validation failed for AI response: %s", parsed)
        raise HTTPException(status_code=502, detail=f"AI response did not match expected format: {str(e)}")

    # Always enforce a default disclaimer if empty
    if not result.disclaimer:
        result.disclaimer = (
            "KlarPost provides general information only and does not give legal, tax, financial, or medical advice. "
            "Please verify with the sender or a qualified professional."
        )
    return result


# ==================== ROUTES ====================

@api_router.get("/")
async def root():
    return {"app": "KlarPost", "status": "ok"}


@api_router.get("/languages")
async def get_languages():
    return [{"code": k, "label": v} for k, v in LANGUAGES.items()]


@api_router.post("/analyze", response_model=AnalysisRecord)
async def analyze_document(req: AnalyzeRequest):
    # Validate language
    if req.target_language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported target language")

    target_language_label = LANGUAGES[req.target_language]

    # Validate base64
    try:
        raw_bytes = base64.b64decode(req.file_base64, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 file content")

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty file content")

    if len(raw_bytes) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large. Please use a file under 12MB.")

    mime = (req.mime_type or "").lower().strip()
    images: List[Tuple[str, str]] = []

    if mime == "application/pdf" or mime == "pdf":
        try:
            images = pdf_to_images_base64(raw_bytes, max_pages=5)
        except Exception as e:
            logger.exception("PDF conversion failed")
            raise HTTPException(status_code=400, detail=f"Could not read PDF: {str(e)}")
    elif mime in ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic", "image/heif"):
        image_mime = "image/jpeg" if mime == "image/jpg" else mime
        images = [(req.file_base64, image_mime)]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {req.mime_type}. Use JPEG, PNG, WEBP or PDF.")

    # Call GPT
    result = await analyze_with_gpt(images, target_language_label)

    record = AnalysisRecord(
        device_id=req.device_id,
        target_language=req.target_language,
        target_language_label=target_language_label,
        mime_type=req.mime_type,
        result=result,
    )

    # Store analysis result only — never the original document
    doc = record.dict()
    await db.analyses.insert_one(doc)

    return record


@api_router.get("/analyses", response_model=List[AnalysisListItem])
async def list_analyses(device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    cursor = db.analyses.find(
        {"device_id": device_id},
        {"_id": 0, "id": 1, "created_at": 1, "target_language": 1, "target_language_label": 1, "result": 1}
    ).sort("created_at", -1).limit(200)
    items: List[AnalysisListItem] = []
    async for doc in cursor:
        result = doc.get("result", {}) or {}
        items.append(AnalysisListItem(
            id=doc.get("id", ""),
            created_at=doc.get("created_at", ""),
            target_language=doc.get("target_language", ""),
            target_language_label=doc.get("target_language_label", ""),
            document_type=result.get("document_type", ""),
            sender=result.get("sender", ""),
            risk_level=result.get("risk_level", "green"),
            summary_translated=result.get("summary_translated", ""),
        ))
    return items


@api_router.get("/analyses/{analysis_id}", response_model=AnalysisRecord)
async def get_analysis(analysis_id: str, device_id: str):
    doc = await db.analyses.find_one(
        {"id": analysis_id, "device_id": device_id},
        {"_id": 0}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return AnalysisRecord(**doc)


@api_router.delete("/analyses/{analysis_id}")
async def delete_analysis(analysis_id: str, device_id: str):
    res = await db.analyses.delete_one({"id": analysis_id, "device_id": device_id})
    return {"deleted": res.deleted_count}


@api_router.delete("/analyses")
async def delete_all_analyses(device_id: str):
    if not device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    res = await db.analyses.delete_many({"device_id": device_id})
    return {"deleted": res.deleted_count}


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
