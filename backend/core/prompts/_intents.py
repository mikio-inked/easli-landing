"""easli — reply-intent tables + language-code map.

Owns the small constant tables that the analyser / reply prompts share:
  • DEFAULT_REPLY_OPTIONS  — fallback intents (legacy de/en labels).
  • INTENT_DESCRIPTIONS    — what each canonical intent id means.
  • REPLY_LANG_CODE_TO_ENGLISH — ISO-639-1 → English name (used by the
                                 reply-draft prompt to tell Mistral the
                                 reply language by name as well as code).
  • resolve_reply_language(record, explicit_code) — cascading resolver.
"""

from __future__ import annotations

from typing import Optional


DEFAULT_REPLY_OPTIONS = [
    {"id": "inquiry",   "label_de": "Nachfrage stellen",        "label_en": "Ask for clarification"},
    {"id": "extension", "label_de": "Frist verlängern",         "label_en": "Ask for more time"},
    {"id": "confirm",   "label_de": "Bestätigung",              "label_en": "Confirm / acknowledge"},
    {"id": "objection", "label_de": "Widerspruch einlegen",     "label_en": "File an objection"},
]


INTENT_DESCRIPTIONS = {
    "inquiry":          "Politely ask the sender to clarify a specific point in the letter that is unclear.",
    "extension":        "Politely request more time to respond / pay / submit, with a brief reason if helpful.",
    "confirm":          "Briefly confirm receipt and/or acknowledge what the letter requests, no further questions.",
    "objection":        "Calmly state that the recipient disagrees with the decision/claim and intends to formally object. Keep it short and factual.",
    "submit_documents": "Acknowledge the request and state that the missing documents will be supplied. List placeholders for which documents.",
    "cancel":           "State the intention to cancel / withdraw / terminate the contract or service. Reference the sender's letter as context.",
}


# ISO-639-1 → English language name. Used by the reply-draft prompt to
# tell Mistral which language to write the draft in.
REPLY_LANG_CODE_TO_ENGLISH: dict = {
    "de": "German", "en": "English", "fr": "French", "es": "Spanish",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "ro": "Romanian", "cs": "Czech", "hu": "Hungarian", "el": "Greek",
    "bg": "Bulgarian", "hr": "Croatian", "sk": "Slovak", "sl": "Slovenian",
    "lt": "Lithuanian", "lv": "Latvian", "et": "Estonian", "sv": "Swedish",
    "da": "Danish", "fi": "Finnish", "ga": "Irish", "mt": "Maltese",
    "no": "Norwegian", "is": "Icelandic", "sr": "Serbian", "sq": "Albanian",
    "bs": "Bosnian", "uk": "Ukrainian", "ru": "Russian", "tr": "Turkish",
    "ar": "Arabic", "fa": "Persian (Farsi)", "ur": "Urdu", "hi": "Hindi",
    "zh-hans": "Chinese (Simplified)", "vi": "Vietnamese",
}


def resolve_reply_language(
    record: dict,
    explicit_code: Optional[str] = None,
) -> tuple[str, str]:
    """Return (code, english_name) for the reply draft.
    Cascade: explicit override → suggested_reply_language_code →
    source_language_code → empty. English name falls back to the raw code
    in upper-case if not in our table (Mistral can still use the code)."""
    result = record.get("result", {}) or {}
    code = (
        (explicit_code or "").strip().lower()
        or (result.get("suggested_reply_language_code") or "").strip().lower()
        or (result.get("source_language_code") or "").strip().lower()
    )
    if not code:
        return ("", "")
    name = REPLY_LANG_CODE_TO_ENGLISH.get(code) or code.upper()
    return (code, name)

