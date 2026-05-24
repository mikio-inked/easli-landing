"""easli — reply-generation prompt (intent-based)."""

from __future__ import annotations

import json
from typing import Optional

from core.prompts._intents import (
    INTENT_DESCRIPTIONS,
    REPLY_LANG_CODE_TO_ENGLISH,
    resolve_reply_language,
)


def build_reply_generation_prompt(
    record: dict,
    intent: str,
    target_language_label: str,
    custom_instruction: str = "",
    reply_language_code: Optional[str] = None,
) -> str:
    """Return a concise system prompt for Mistral to generate a single
    reply-draft tailored to one intent. The reply text is produced in the
    explicit `reply_language_code` if provided, otherwise in the SOURCE
    document's language (so it can actually be sent to the sender).

    Phase R6: returns a JSON object with TWO fields:
      - reply_text:        the email body in the sender's language.
      - reply_explanation: a short explanation of what the user is about
                           to send, in the user's Explanation-Language
                           (`target_language_label`). This lets a user
                           who doesn't fully master the sender's language
                           know what they're agreeing to / asking for.
    """
    result = record.get("result", {}) or {}
    ee = result.get("extracted_entities") or {}
    intent_desc = INTENT_DESCRIPTIONS.get(intent, "")
    reply_code, reply_name = resolve_reply_language(record, reply_language_code)
    # Display label for the prompt — fallback for unknown codes.
    if reply_name:
        reply_lang_clause = f"{reply_name} ({reply_code})"
    else:
        reply_lang_clause = (
            result.get("source_language") or "the source language"
        )

    context = {
        "document_type": result.get("document_type", ""),
        "sender": result.get("sender", ""),
        "summary": result.get("summary_translated", ""),
        "deadlines": result.get("deadlines", [])[:3],
        "required_actions": result.get("required_actions", [])[:3],
        "reference_number": ee.get("reference_number", ""),
        "contact_person": ee.get("contact_person", ""),
        "organization": ee.get("organization", ""),
    }
    instruction_block = (
        f"\n\nADDITIONAL USER INSTRUCTION (must be followed):\n{custom_instruction}"
        if custom_instruction.strip()
        else ""
    )

    return f"""You are easli's reply-draft writer. Produce ONE polite, calm, ready-to-send reply email for the following intent, AND a short explanation of what that reply says, so the user (who may not speak the sender's language fluently) knows what they are about to send.

INTENT: {intent}
{intent_desc}

OUTPUT FORMAT — return a STRICT JSON object with exactly these two keys:
{{
  "reply_text": "the email body, written in {reply_lang_clause}",
  "reply_explanation": "a short 2-4 sentence explanation of what reply_text says and what the user is asking/confirming/objecting — written in {target_language_label}"
}}

No markdown, no code fences, no leading or trailing commentary — ONLY the raw JSON object.

RULES FOR reply_text (the email body going to the sender):
- Written entirely in {reply_lang_clause}.
- Calm, clear, direct. No emotion, no AI phrases ("Based on…", "I analyzed…", "It appears that…").
- B1-level everyday language. No legal jargon unless strictly needed.
- Never use em-dashes (— or –). Use comma, period, or colon.
- Do not mention easli, AI, models, or how this draft was made.
- Address a specific person if known (use `contact_person`); otherwise use a neutral salutation appropriate for {reply_lang_clause}.
- Reference the document briefly (use `reference_number` if present).
- Keep it 80 to 180 words, no bullet lists, no markdown.
- End with a simple polite sign-off. No "[Your Name]" placeholder — leave the signature line blank.

RULES FOR reply_explanation (the in-app explainer):
- Written entirely in {target_language_label}. This is CRITICAL — the user reads this to understand their own reply, so it MUST be in {target_language_label}, not in the sender's language.
- 2 to 4 short sentences, plain-language, no legal jargon.
- Start with what the reply does ("You are confirming…", "You are asking…", "You are objecting…").
- Mention the one or two key points the user is committing to (e.g. a deadline, a request, a confirmation). Keep numbers/dates exactly.
- No disclaimers, no "you should consult a lawyer", no mention of AI.
- Do not repeat the whole reply — summarise its effect.

DOCUMENT CONTEXT (JSON):
{json.dumps(context, ensure_ascii=False)}{instruction_block}
"""
