"""easli — reply-generation prompt (intent-based)."""

from __future__ import annotations

import json
from typing import Optional

from core.prompts._intents import (
    INTENT_DESCRIPTIONS,
    REPLY_LANG_CODE_TO_ENGLISH,
    resolve_reply_language,
)
from core.prompts._salutations import (
    DEFAULT_FALLBACK_SALUTATION,
    salutation_for,
)


def _extract_last_name(contact_person: str) -> str:
    """Best-effort last-name extraction from a `contact_person` string.

    The OCR-extracted `contact_person` may take any of these forms:
      - "Dr. Anna Schmidt"     →  "Schmidt"
      - "Schmidt"              →  "Schmidt"
      - "Anna Maria Schmidt"   →  "Schmidt"
      - "Herr Schmidt"         →  "Schmidt"
      - "Frau Dr. Müller"      →  "Müller"
      - ""                     →  ""

    We strip a handful of common honorifics (de/fr/es/it/nl/en), then take
    the last token. Cheap, deterministic, language-aware enough for our
    salutation placeholder. The LLM never sees the raw `contact_person`
    again — it only sees the pre-rendered opener line, so this function
    is the single source of truth.
    """
    if not contact_person:
        return ""
    cleaned = contact_person.strip()
    # Strip up to two leading honorifics.
    honorifics = {
        "herr", "frau", "dr.", "dr", "prof.", "prof", "dipl.-ing.",
        "dipl.", "mag.", "ing.",
        "mr.", "mr", "mrs.", "mrs", "ms.", "ms", "miss",
        "m.", "mme", "mlle", "monsieur", "madame", "mademoiselle",
        "sr.", "sra.", "sr", "sra", "don", "doña",
        "sig.", "sig", "sig.ra", "egr.", "spett.",
        "dhr.", "mevr.", "heer", "mevrouw",
    }
    tokens = cleaned.split()
    while tokens and tokens[0].lower().rstrip(",.") in honorifics:
        tokens.pop(0)
    if not tokens:
        return ""
    return tokens[-1].rstrip(",.")


def _build_salutation_block(
    reply_code: str,
    contact_person: str,
) -> str:
    """Render the MANDATORY SALUTATION block for the reply prompt.

    Phase 6d: deterministically produces the opener + sign-off so the LLM
    cannot invent its own (which historically caused inconsistent formality
    levels across languages — e.g. "Hallo" for German tax-authority replies).

    Returns a fully-rendered prompt section ready to be inlined.
    """
    sal = salutation_for(reply_code) or DEFAULT_FALLBACK_SALUTATION
    last_name = _extract_last_name(contact_person)

    # ---- Opener: pick the right template & pre-substitute the last name ----
    formal_named_tpl = sal.get("formal_named") or ""
    formal_unknown = sal.get("formal_unknown") or DEFAULT_FALLBACK_SALUTATION["formal_unknown"]

    if last_name and formal_named_tpl:
        rendered_named = formal_named_tpl.replace("{nachname}", last_name)
        opener_directive = (
            f'Open the email with EXACTLY this line (no variation):\n'
            f'    {rendered_named}'
        )
    else:
        opener_directive = (
            f'Open the email with EXACTLY this line (no variation):\n'
            f'    {formal_unknown}'
        )

    # ---- Sign-off: prefer the more formal variant for authority/legal letters,
    # but the standard one is always a safe default ---------------------------
    sign_off = sal.get("sign_off_formal") or sal.get("sign_off") or DEFAULT_FALLBACK_SALUTATION["sign_off"]
    sign_off_directive = (
        f'End the email with EXACTLY this sign-off on its own line, followed '
        f'by a blank signature line (no "[Your Name]" placeholder):\n'
        f'    {sign_off}'
    )

    return (
        "MANDATORY SALUTATION RULES (apply to reply_text only — non-negotiable):\n"
        f"- {opener_directive}\n"
        f"- {sign_off_directive}\n"
        f"- NEVER invent a different salutation or sign-off. The two lines above "
        f"are the only allowed forms for this reply language. Do not translate "
        f"them, do not paraphrase them, do not add an extra greeting line.\n"
        f"- The opener goes on the first line of the body. Leave ONE blank line "
        f"between the opener and the first sentence of the reply.\n"
        f"- The sign-off is the last meaningful line. Do not add 'easli', do "
        f"not add your own name, do not add a job title."
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

    Phase 6d: opener + sign-off are deterministically pre-rendered from
    `_salutations.REPLY_SALUTATIONS` and injected as a MANDATORY block, so
    the model can no longer invent inconsistent salutations.
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

    contact_person = ee.get("contact_person", "") or ""
    salutation_block = _build_salutation_block(reply_code, contact_person)

    context = {
        "document_type": result.get("document_type", ""),
        "sender": result.get("sender", ""),
        "summary": result.get("summary_translated", ""),
        "deadlines": result.get("deadlines", [])[:3],
        "required_actions": result.get("required_actions", [])[:3],
        "reference_number": ee.get("reference_number", ""),
        "contact_person": contact_person,
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
- Reference the document briefly (use `reference_number` if present).
- Keep it 80 to 180 words, no bullet lists, no markdown.

{salutation_block}

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
