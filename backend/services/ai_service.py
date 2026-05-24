"""easli — Mistral AI service.

Owns every interaction with the Mistral API:
  • The retry-with-backoff helper that handles HTTP 429.
  • The full document-analysis pipeline (`analyze_from_ocr_text`).
  • The language-gate (`detect_document_language`).
  • The chat-about-document pipeline.
  • The translate-an-existing-analysis pipeline.

Privacy: every log line in this module is metadata-only (model id, chars
count, attempt number, exception type). NEVER logs the message bodies,
the response text, or any field that could carry user content.

The route handlers in `routers/*` translate Mistral failures into HTTP
status codes; we surface `HTTPException` here for the SAME shape as the
pre-refactor code so the byte-identical contract holds.
"""

import asyncio
import json
import logging
from typing import List, Optional, Tuple

from fastapi import HTTPException

from core.config import (
    MISTRAL_ANALYSIS_MODEL,
    MISTRAL_CHAT_MODEL,
    mistral_client,
)
from core.exceptions import MistralRateLimited
from core.prompts import (
    INTENT_DESCRIPTIONS,
    build_chat_system_prompt,
    build_system_prompt,
    build_translation_system_prompt,
)
from models import AnalysisResult, ChatResponse
from utils.json_utils import extract_json_from_text, sanitize_literal_fields
from utils.retry_utils import (
    RATE_LIMIT_DEFAULT_BACKOFF_SECONDS,
    RATE_LIMIT_FALLBACK_CLIENT_HINT,
    RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS,
    RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS,
    is_rate_limit_error,
    parse_retry_after_seconds,
)

logger = logging.getLogger("server")

__all__ = [
    "mistral_complete_with_retry",
    "analyze_from_ocr_text",
    "detect_document_language",
    "chat_about_document",
    "translate_analysis_with_mistral",
]


# ===========================================================================
# 1. Mistral retry helper
# ===========================================================================
async def mistral_complete_with_retry(
    *,
    label: str,  # 'vision' or 'chat' — for logs only
    model: str,
    **kwargs,
):
    """Call mistral_client.chat.complete_async with retries on HTTP 429.

    Retry strategy:
      1) If the 429 response carries a `Retry-After` header, honour it
         (capped at RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS to avoid keeping a
         mobile upload connection open too long).
      2) Otherwise fall back to an exponential schedule: 2s, 4s, 8s.
      3) Stop retrying as soon as the cumulative wait would exceed
         RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS.

    On final failure we raise MistralRateLimited(retry_after=...) where
    retry_after is the LAST hint Mistral gave us, so the iOS toast says
    "try again in N seconds" with the same N the server told us.
    """
    last_exc: Optional[Exception] = None
    last_client_hint: int = RATE_LIMIT_FALLBACK_CLIENT_HINT
    total_waited: int = 0
    max_attempts = len(RATE_LIMIT_DEFAULT_BACKOFF_SECONDS) + 1  # 4 total

    for attempt in range(max_attempts):
        try:
            return await mistral_client.chat.complete_async(model=model, **kwargs)
        except Exception as e:
            if not is_rate_limit_error(e):
                # Non-429 → propagate so existing 502 handler runs.
                raise
            last_exc = e

            # Decide how long to wait before the next attempt.
            server_hint = parse_retry_after_seconds(e)
            if server_hint is not None:
                wait = min(server_hint, RATE_LIMIT_MAX_SINGLE_WAIT_SECONDS)
                # Remember the *uncapped* server hint so we can forward
                # the truthful number to the iOS client when we give up.
                last_client_hint = server_hint
            elif attempt < len(RATE_LIMIT_DEFAULT_BACKOFF_SECONDS):
                wait = RATE_LIMIT_DEFAULT_BACKOFF_SECONDS[attempt]
                last_client_hint = wait
            else:
                wait = None  # no more attempts left

            attempts_left = attempt + 1 < max_attempts
            within_budget = (
                wait is not None
                and (total_waited + wait) <= RATE_LIMIT_MAX_TOTAL_WAIT_SECONDS
            )

            if attempts_left and within_budget:
                logger.warning(
                    "mistral_rate_limited label=%s model=%s attempt=%d/%d "
                    "retry_in=%ds server_hint=%s total_waited=%ds",
                    label, model, attempt + 1, max_attempts,
                    wait, server_hint if server_hint is not None else "none",
                    total_waited,
                )
                await asyncio.sleep(wait)
                total_waited += wait
                continue

            # Out of attempts or out of budget — surface a clean exception
            # so the route handler can return HTTP 429 with the truthful
            # Retry-After hint to the iOS client.
            logger.error(
                "mistral_rate_limited_final label=%s model=%s attempts=%d "
                "total_waited=%ds final_hint=%ds",
                label, model, attempt + 1, total_waited, last_client_hint,
            )
            raise MistralRateLimited(retry_after=last_client_hint) from e

    # Defensive — the loop always returns or raises.
    if last_exc is not None:
        raise MistralRateLimited(retry_after=last_client_hint) from last_exc
    raise RuntimeError("mistral_complete_with_retry: unreachable")


# ===========================================================================
# 2. Document analysis (post-OCR)
# ===========================================================================
async def analyze_from_ocr_text(
    page_texts: List[str],
    target_language_label: str,
    target_language_code: str = "",
) -> AnalysisResult:
    """Second half of the 2-stage pipeline: given already-OCR'd per-page
    text, produce a structured analysis in the user's language.

    Extracted out so the /api/analyze route can interpose a cheap
    language-gate step between OCR and full analysis.
    """
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    # Combine per-page markdown into one text block. Page separators help
    # the analysis model handle multi-page context correctly.
    if len(page_texts) > 1:
        combined_text = "\n\n".join(
            f"--- Seite {i + 1} ---\n\n{txt}" for i, txt in enumerate(page_texts)
        )
    else:
        combined_text = page_texts[0] if page_texts else ""

    # Guardrail: if OCR extracted literally nothing readable, bail out with
    # a clean 422.
    all_readable = any(
        txt and not txt.startswith("[Seite ") for txt in page_texts
    )
    if not all_readable or not combined_text.strip():
        logger.warning(
            "analysis_unreadable pages=%d total_chars=%d",
            len(page_texts), len(combined_text),
        )
        raise HTTPException(
            status_code=422,
            detail="No readable text was found. Please retry with a clearer photo.",
        )

    page_note = (
        f"The document has {len(page_texts)} page(s). "
        "Treat them as ONE document and produce a single combined analysis."
        if len(page_texts) > 1
        else ""
    )

    user_text = (
        f"Analyze this document and respond ONLY with the JSON object as specified. "
        f"Detect the source language of the document yourself from the text. "
        f"The user's selected target language for the explanation is {target_language_label}. "
        f"Write `reply_draft` and `german_reply_draft` in the SAME language as the source document. "
        f"{page_note}\n\n"
        f"--- EXTRACTED DOCUMENT TEXT (from OCR) ---\n{combined_text}"
    ).strip()

    messages = [
        {
            "role": "system",
            "content": build_system_prompt(target_language_label, target_language_code),
        },
        {"role": "user", "content": user_text},
    ]

    try:
        response = await mistral_complete_with_retry(
            label="analysis",
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        logger.exception(
            "Mistral analysis call failed (model=%s, error_type=%s)",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI analysis failed.")

    response_text = ""
    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception(
            "Unexpected Mistral response shape (model=%s, choices=%d)",
            MISTRAL_ANALYSIS_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        raise HTTPException(status_code=502, detail="AI returned an empty response")

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error(
            "Could not parse JSON from Mistral analyze response (model=%s, length=%d)",
            MISTRAL_ANALYSIS_MODEL, len(response_text or ""),
        )
        raise HTTPException(
            status_code=502,
            detail="AI returned an invalid response. Please try again.",
        )

    parsed["target_language"] = target_language_label
    if not isinstance(parsed.get("source_language"), str):
        parsed["source_language"] = ""
    if not isinstance(parsed.get("source_language_code"), str):
        parsed["source_language_code"] = ""
    parsed["source_language_code"] = (parsed.get("source_language_code") or "").strip().lower()

    # ─── Phase EU-1: normalise the new multilingual fields ──────────────────
    cc = (parsed.get("detected_country_code") or "")
    if not isinstance(cc, str):
        cc = ""
    parsed["detected_country_code"] = cc.strip().upper()
    if not isinstance(parsed.get("detected_country_name"), str):
        parsed["detected_country_name"] = ""
    parsed["detected_country_name"] = (parsed.get("detected_country_name") or "").strip()

    jc = (parsed.get("jurisdiction_confidence") or "").strip().lower()
    if jc not in ("low", "medium", "high"):
        jc = ""
    if not parsed["detected_country_code"]:
        jc = ""
    parsed["jurisdiction_confidence"] = jc

    srlc = (parsed.get("suggested_reply_language_code") or "").strip().lower()
    if not srlc:
        srlc = parsed.get("source_language_code") or ""
    parsed["suggested_reply_language_code"] = srlc

    cs = parsed.get("confidence_score")
    try:
        cs_f = float(cs) if cs is not None else 0.0
    except (TypeError, ValueError):
        cs_f = 0.0
    parsed["confidence_score"] = max(0.0, min(1.0, cs_f))

    if not isinstance(parsed.get("safety_disclaimer"), str):
        parsed["safety_disclaimer"] = ""

    # Back-compat alias: mirror `reply_draft` ↔ `german_reply_draft`.
    rd = parsed.get("reply_draft")
    grd = parsed.get("german_reply_draft")
    if isinstance(rd, str) and rd.strip() and not (isinstance(grd, str) and grd.strip()):
        parsed["german_reply_draft"] = rd
    elif isinstance(grd, str) and grd.strip() and not (isinstance(rd, str) and rd.strip()):
        parsed["reply_draft"] = grd

    # Reply Assistant fallback: if Mistral returned nothing we provide a
    # safe localised fallback so the Reply tab in the UI is never empty.
    REPLY_OPTION_LABELS_EN = {
        "inquiry": "Ask for clarification",
        "extension": "Ask for more time",
        "confirm": "Confirm receipt",
        "objection": "File an objection",
    }
    REPLY_OPTION_LABELS_DE = {
        "inquiry": "Nachfrage stellen",
        "extension": "Frist verlängern",
        "confirm": "Bestätigung",
        "objection": "Widerspruch einlegen",
    }
    raw_options = parsed.get("reply_options")
    if not isinstance(raw_options, list) or not raw_options:
        labels = REPLY_OPTION_LABELS_DE if target_language_code == "de_simple" else REPLY_OPTION_LABELS_EN
        parsed["reply_options"] = [
            {"id": k, "label": v, "reason": "", "recommended": (k == "inquiry")}
            for k, v in labels.items()
        ]
    else:
        cleaned = []
        for opt in raw_options:
            if not isinstance(opt, dict):
                continue
            oid = (opt.get("id") or "").strip().lower()
            if oid not in INTENT_DESCRIPTIONS:
                continue
            cleaned.append({
                "id": oid,
                "label": (opt.get("label") or "").strip(),
                "reason": (opt.get("reason") or "").strip(),
                "recommended": bool(opt.get("recommended")),
            })
        if not cleaned:
            labels = REPLY_OPTION_LABELS_DE if target_language_code == "de_simple" else REPLY_OPTION_LABELS_EN
            cleaned = [
                {"id": k, "label": v, "reason": "", "recommended": (k == "inquiry")}
                for k, v in labels.items()
            ]
        else:
            if not any(o["recommended"] for o in cleaned):
                cleaned[0]["recommended"] = True
            # "Never empty / never tiny" guarantee: pad with missing
            # canonical ids until the user has at least 4 distinct options.
            if len(cleaned) < 4:
                labels = REPLY_OPTION_LABELS_DE if target_language_code == "de_simple" else REPLY_OPTION_LABELS_EN
                existing_ids = {o["id"] for o in cleaned}
                for canonical_id, label in labels.items():
                    if canonical_id in existing_ids:
                        continue
                    cleaned.append({
                        "id": canonical_id,
                        "label": label,
                        "reason": "",
                        "recommended": False,
                    })
                    if len(cleaned) >= 4:
                        break
        parsed["reply_options"] = cleaned

    # Normalise extracted_entities.
    ee = parsed.get("extracted_entities")
    if not isinstance(ee, dict):
        ee = {}
    parsed["extracted_entities"] = {
        "email": (ee.get("email") or "").strip(),
        "subject": (ee.get("subject") or "").strip(),
        "reference_number": (ee.get("reference_number") or "").strip(),
        "contact_person": (ee.get("contact_person") or "").strip(),
        "organization": (ee.get("organization") or "").strip(),
    }

    sanitize_literal_fields(parsed)

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception(
            "Validation failed for AI response (model=%s, error_type=%s, top_keys=%d)",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
            len(parsed.keys()) if isinstance(parsed, dict) else 0,
        )
        raise HTTPException(
            status_code=502,
            detail="AI response did not match expected format.",
        )

    if not result.disclaimer:
        result.disclaimer = (
            "easli provides general information only and does not give legal, tax, financial, or medical advice. "
            "Please verify with the sender or a qualified professional."
        )
    return result


# ===========================================================================
# 3. Language gate
# ===========================================================================
# Cheap, lightweight pre-analysis check: is this document actually primarily
# German? Reject clearly-non-German docs BEFORE burning a full analysis call
# and BEFORE consuming the user's quota. Aim: <1s and <~200 output tokens.

_LANG_GATE_SAMPLE_CHARS = 1500  # First ~1.5KB of extracted text is plenty

_LANG_GATE_SYSTEM_PROMPT = (
    "You are a language classifier for a German-documents assistant. "
    "You will receive the OCR-extracted text of the FIRST page of a document. "
    "Decide whether the document is primarily German.\n\n"
    "IMPORTANT nuances:\n"
    " - A German letter that contains some English product names, technical "
    "terms, legal phrases, company names, URLs, or short English "
    "attachments is STILL German. Classify it as 'de'.\n"
    " - A document written primarily in a non-German language (English, "
    "French, Spanish, Italian, Turkish, Polish, Russian, Chinese, etc.) "
    "is 'non_de'.\n"
    " - If the text is too short, blurry, or ambiguous to decide confidently, "
    "use 'unknown'.\n\n"
    "Respond ONLY with a compact JSON object with exactly these keys:\n"
    "  document_language: 'de' | 'non_de' | 'unknown'\n"
    "  detected_language_code: ISO-639-1 code ('de','en','fr','es','it',"
    "'tr','pl','ru','zh',...) or null\n"
    "  confidence: 'low' | 'medium' | 'high'\n"
    "NO prose, NO code fences."
)


async def detect_document_language(
    page0_text: str,
) -> Tuple[str, Optional[str], str]:
    """Run the lightweight language gate on page-1 OCR text.

    Returns (document_language, detected_language_code, confidence).
    Never raises — on Mistral errors or timeouts returns ('unknown', None,
    'low') so the caller can safely fall through to full analysis.
    """
    if not mistral_client or not page0_text:
        return ("unknown", None, "low")

    sample = page0_text[:_LANG_GATE_SAMPLE_CHARS]

    messages = [
        {"role": "system", "content": _LANG_GATE_SYSTEM_PROMPT},
        {"role": "user", "content": sample},
    ]

    try:
        # We deliberately DO NOT use mistral_complete_with_retry here — the
        # gate must be cheap and fast, and if it's rate-limited or slow we'd
        # rather fall through to full analysis than stall the user.
        response = await mistral_client.chat.complete_async(
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=80,
        )
        response_text = (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.info(
            "language_gate_failed error_type=%s model=%s",
            type(e).__name__, MISTRAL_ANALYSIS_MODEL,
        )
        return ("unknown", None, "low")

    parsed = extract_json_from_text(response_text) or {}
    dl = parsed.get("document_language") or "unknown"
    if dl not in ("de", "non_de", "unknown"):
        dl = "unknown"
    code = parsed.get("detected_language_code")
    if isinstance(code, str):
        code = code.strip().lower() or None
    else:
        code = None
    conf = parsed.get("confidence") or "low"
    if conf not in ("low", "medium", "high"):
        conf = "low"
    return (dl, code, conf)


# ===========================================================================
# 4. Chat about document
# ===========================================================================
async def chat_about_document(
    record_dict: dict,
    history: List[dict],
    user_message: str,
    target_language_label: str,
    target_language_code: str = "",
) -> ChatResponse:
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    system_prompt = build_chat_system_prompt(record_dict, target_language_label, target_language_code)

    # Build a proper Mistral message list — system + last 12 turns + current user.
    messages: List[dict] = [{"role": "system", "content": system_prompt}]
    for m in (history or [])[-12:]:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content") or ""
        if not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                f"{user_message}\n\n"
                f"Reply now as the assistant in {target_language_label}, following ALL rules. "
                "Output ONLY the JSON object."
            ),
        }
    )

    try:
        response = await mistral_complete_with_retry(
            label="chat",
            model=MISTRAL_CHAT_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        # Privacy: only log the model + exception type, never the messages.
        logger.exception(
            "Mistral chat call failed (model=%s, error_type=%s)",
            MISTRAL_CHAT_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="AI chat failed.")

    response_text = ""
    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        # Privacy: never log the raw chat response.
        logger.exception(
            "Unexpected Mistral chat response shape (model=%s, choices=%d)",
            MISTRAL_CHAT_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        return ChatResponse(reply="", off_topic=False)

    parsed = extract_json_from_text(response_text)
    if not parsed or "reply" not in parsed:
        # Fall back to treating the raw text as the reply if parsing fails.
        return ChatResponse(reply=(response_text or "").strip()[:1500], off_topic=False)

    return ChatResponse(
        reply=str(parsed.get("reply", "")).strip(),
        off_topic=bool(parsed.get("off_topic", False)),
    )


# ===========================================================================
# 5. Translate an existing analysis into another language
# ===========================================================================
async def translate_analysis_with_mistral(
    source_result: dict,
    current_target_label: str,
    new_target_label: str,
    new_target_code: str,
) -> AnalysisResult:
    """Re-localise a previously-analysed AnalysisResult into a new language.

    Text-only Mistral call — no OCR, no vision, no original-image access.
    Cheap (~2-3s) and safe to cache.
    """
    if not mistral_client:
        raise HTTPException(
            status_code=500,
            detail="Mistral API key not configured. Please set MISTRAL_API_KEY in backend/.env",
        )

    # Minimal slimmed-down view of the source — we drop any server-side-only
    # fields and keep only what AnalysisResult needs. Ensures the model
    # doesn't get confused by extras.
    ALLOWED_KEYS = {
        "source_language", "source_language_code", "target_language",
        "document_type", "sender",
        "summary_translated", "simple_explanation_translated", "key_points",
        "deadlines", "required_actions", "risk_level", "risk_reason",
        "reply_draft", "german_reply_draft", "reply_draft_explanation_translated",
        "questions_to_ask", "uncertainties", "disclaimer", "category",
        "scam_warning", "scam_reason",
        # Phase R5 — preserved invariant fields (no translation needed for
        # extracted entities; reply_options labels DO get translated though).
        "extracted_entities", "reply_options",
    }
    slim = {k: v for k, v in (source_result or {}).items() if k in ALLOWED_KEYS}
    # If the source only has the legacy `german_reply_draft` (old DB record),
    # also expose it as `reply_draft` so the prompt preserves it correctly.
    if slim.get("german_reply_draft") and not slim.get("reply_draft"):
        slim["reply_draft"] = slim["german_reply_draft"]

    messages = [
        {
            "role": "system",
            "content": build_translation_system_prompt(
                current_target_label, new_target_label, new_target_code,
            ),
        },
        {
            "role": "user",
            "content": (
                f"Re-localise this analysis into {new_target_label}. "
                "Return ONLY the JSON object.\n\n"
                f"INPUT_JSON:\n{json.dumps(slim, ensure_ascii=False)}"
            ),
        },
    ]

    try:
        response = await mistral_complete_with_retry(
            label="translate",
            model=MISTRAL_ANALYSIS_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except MistralRateLimited as rl:
        raise HTTPException(
            status_code=429,
            detail="AI is rate-limited. Please try again in a moment.",
            headers={"Retry-After": str(rl.retry_after)},
        )
    except Exception as e:
        logger.exception(
            "translation_failed model=%s error_type=%s",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(status_code=502, detail="Translation failed.")

    response_text = ""
    try:
        response_text = (response.choices[0].message.content or "").strip()
    except Exception:
        logger.exception(
            "translation_failed_shape model=%s choices=%d",
            MISTRAL_ANALYSIS_MODEL,
            len(getattr(response, "choices", []) or []),
        )
        raise HTTPException(status_code=502, detail="Translation returned empty response")

    parsed = extract_json_from_text(response_text)
    if not parsed:
        logger.error(
            "translation_failed_parse model=%s length=%d",
            MISTRAL_ANALYSIS_MODEL, len(response_text or ""),
        )
        raise HTTPException(
            status_code=502,
            detail="Translation returned invalid JSON.",
        )

    # Enforce factual invariants: regardless of what the model returned,
    # we OVERWRITE the factual fields with the source's values. Belt-and-
    # braces safety net in case the model "helpfully" localised a sender
    # name or edited a deadline date.
    for k in (
        "sender",
        "risk_level",
        "category",
        "scam_warning",
        "reply_draft",
        "german_reply_draft",
        "source_language",
        "source_language_code",
        # Phase R5 — preserve extracted entities byte-identical.
        "extracted_entities",
    ):
        if k in slim:
            parsed[k] = slim[k]
    # reply_options: keep ids + recommended booleans intact, allow the
    # model to localise `label` and `reason` into the new target language.
    src_options = slim.get("reply_options")
    new_options = parsed.get("reply_options")
    if isinstance(src_options, list) and isinstance(new_options, list):
        src_by_id = {o.get("id"): o for o in src_options if isinstance(o, dict)}
        for opt in new_options:
            if not isinstance(opt, dict):
                continue
            src_o = src_by_id.get(opt.get("id"))
            if src_o:
                opt["id"] = src_o.get("id", opt.get("id", ""))
                opt["recommended"] = bool(src_o.get("recommended", opt.get("recommended", False)))
    elif isinstance(src_options, list):
        # Model didn't re-emit reply_options, fall back to source.
        parsed["reply_options"] = src_options
    # Keep reply_draft ↔ german_reply_draft in sync after invariants applied.
    if parsed.get("reply_draft") and not parsed.get("german_reply_draft"):
        parsed["german_reply_draft"] = parsed["reply_draft"]
    elif parsed.get("german_reply_draft") and not parsed.get("reply_draft"):
        parsed["reply_draft"] = parsed["german_reply_draft"]
    # Deep-preserve factual sub-fields of deadlines/required_actions.
    if isinstance(slim.get("deadlines"), list) and isinstance(parsed.get("deadlines"), list):
        src_deadlines = slim["deadlines"]
        for i, d in enumerate(parsed["deadlines"]):
            if isinstance(d, dict) and i < len(src_deadlines):
                src = src_deadlines[i] or {}
                d["date"] = src.get("date", d.get("date", ""))
                d["confidence"] = src.get("confidence", d.get("confidence", "low"))
    if isinstance(slim.get("required_actions"), list) and isinstance(parsed.get("required_actions"), list):
        src_actions = slim["required_actions"]
        for i, a in enumerate(parsed["required_actions"]):
            if isinstance(a, dict) and i < len(src_actions):
                src = src_actions[i] or {}
                a["urgency"] = src.get("urgency", a.get("urgency", "low"))

    # Source language stays whatever the source record had (already copied
    # above via the invariant loop). target_language is always the new one.
    parsed["target_language"] = new_target_label

    sanitize_literal_fields(parsed)

    try:
        result = AnalysisResult(**parsed)
    except Exception as e:
        logger.exception(
            "translation_failed_validation model=%s error_type=%s",
            MISTRAL_ANALYSIS_MODEL, type(e).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Translation did not match expected format.",
        )

    if not result.disclaimer:
        result.disclaimer = (
            "easli provides general information only and does not give legal, tax, financial, or medical advice. "
            "Please verify with the sender or a qualified professional."
        )
    return result
