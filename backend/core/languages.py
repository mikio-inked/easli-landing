"""
Language registries for easli.

Single source of truth for:
  • LANGUAGES         — back-compat 7-language UI hint set
  • EXPLANATION_LANGUAGES — full set the AI may explain in (must mirror
    /app/frontend/src/languages.ts)
  • resolve_explanation_label — safe label lookup for prompt building

Kept as a tiny standalone module so that prompts/, services/ and routes/
can import without dragging in the FastAPI app graph.
"""

LANGUAGES = {
    "de_simple": "Simple German (Einfaches Deutsch / Leichte Sprache)",
    "en": "English",
    "es": "Spanish (Español)",
    "vi": "Vietnamese (Tiếng Việt)",
    "tr": "Turkish (Türkçe)",
    "ru": "Russian (Русский)",
    "zh": "Chinese Simplified (简体中文)",
}

# Phase EU-1: the full set of Explanation-Languages the AI is allowed to
# write analyses, translations and chat answers in. Superset of LANGUAGES
# (which is kept around for back-compat with 7-language UI chrome hints).
#
# Keys are ISO-639-1 codes (or `zh-Hans` for simplified Chinese, mirroring
# the frontend `languages.ts` registry). Values are Mistral-friendly
# human-readable labels — always in the form "English name (Native name)"
# so the LLM writes in the right tongue AND the user recognises it.
#
# Must stay in lockstep with `/app/frontend/src/languages.ts` — any code
# added there MUST be added here too, otherwise the frontend will send a
# code the backend rejects and the user sees a 400.
EXPLANATION_LANGUAGES = {
    # First-class UI-translated (same labels as LANGUAGES).
    "de_simple": "Simple German (Einfaches Deutsch / Leichte Sprache)",
    "en": "English",
    "es": "Spanish (Español)",
    "vi": "Vietnamese (Tiếng Việt)",
    "tr": "Turkish (Türkçe)",
    "ru": "Russian (Русский)",
    "zh": "Chinese Simplified (简体中文)",
    # Alias for the explicit "simplified" subtag — some frontends send this.
    "zh-Hans": "Chinese Simplified (简体中文)",
    # German (non-simple) — for the Phase 4 picker where a user explicitly
    # chose "Deutsch" rather than "Einfaches Deutsch".
    "de": "German (Deutsch)",
    # EU-1 expansion — covers every EU / EEA + major migrant language.
    "fr": "French (Français)",
    "it": "Italian (Italiano)",
    "pt": "Portuguese (Português)",
    "nl": "Dutch (Nederlands)",
    "pl": "Polish (Polski)",
    "ro": "Romanian (Română)",
    "cs": "Czech (Čeština)",
    "hu": "Hungarian (Magyar)",
    "el": "Greek (Ελληνικά)",
    "bg": "Bulgarian (Български)",
    "hr": "Croatian (Hrvatski)",
    "sr": "Serbian (Српски / Srpski)",
    "sq": "Albanian (Shqip)",
    "uk": "Ukrainian (Українська)",
    "ar": "Arabic (العربية)",
    "fa": "Persian / Farsi (فارسی)",
    "ur": "Urdu (اردو)",
    "hi": "Hindi (हिन्दी)",
}


def resolve_explanation_label(code: str) -> str:
    """Return the Mistral-friendly label for an explanation language code.
    Safe for any input — unknown codes fall back to English. Callers MUST
    still reject unsupported codes upstream (400 BAD REQUEST); this helper
    is only a last-line safety net for prompt building."""
    if not code:
        return "English"
    return EXPLANATION_LANGUAGES.get(code) or LANGUAGES.get(code) or "English"
