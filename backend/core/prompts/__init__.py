"""easli — prompt sub-package facade.

Re-exports every public symbol the rest of the codebase imported from the
old `core/prompts.py` single-file module, plus the new Phase-6 data
structures (country packs + salutations).

All callers that used `from core.prompts import …` keep working unchanged.
New code SHOULD prefer the specific sub-module path for clarity, e.g.
`from core.prompts.analyze import build_system_prompt` — but the flat
import remains the supported public API.
"""

from core.prompts._intents import (
    DEFAULT_REPLY_OPTIONS,
    INTENT_DESCRIPTIONS,
    REPLY_LANG_CODE_TO_ENGLISH,
    resolve_reply_language,
)
from core.prompts._common import CANONICAL_INTENT_IDS
from core.prompts._country_packs import (
    COUNTRY_PACKS,
    CountryPack,
    country_pack,
    country_pack_by_language,
)
from core.prompts._salutations import (
    DEFAULT_FALLBACK_SALUTATION,
    REPLY_SALUTATIONS,
    Salutation,
    salutation_for,
)
from core.prompts.analyze import build_system_prompt
from core.prompts.chat import build_chat_system_prompt
from core.prompts.reply import build_reply_generation_prompt
from core.prompts.translate import build_translation_system_prompt

__all__ = [
    # Legacy public API
    "DEFAULT_REPLY_OPTIONS",
    "INTENT_DESCRIPTIONS",
    "REPLY_LANG_CODE_TO_ENGLISH",
    "build_chat_system_prompt",
    "build_reply_generation_prompt",
    "build_system_prompt",
    "build_translation_system_prompt",
    "resolve_reply_language",
    # New Phase-6 data structures
    "CANONICAL_INTENT_IDS",
    "COUNTRY_PACKS",
    "CountryPack",
    "DEFAULT_FALLBACK_SALUTATION",
    "REPLY_SALUTATIONS",
    "Salutation",
    "country_pack",
    "country_pack_by_language",
    "salutation_for",
]
