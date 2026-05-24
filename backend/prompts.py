"""easli — legacy re-export shim for `core.prompts`.

The actual prompt templates live in `core/prompts.py` since Phase 1 of the
backend refactor. This file is kept so existing imports (`from prompts
import build_system_prompt`) keep working without a sweeping rename across
the codebase, tests, and any out-of-tree scripts.

DO NOT add new code here. Import from `core.prompts` in any new module.
Will be removed once Phase 3 (routers extraction) finishes and we can
sweep the remaining `from prompts import …` call sites.
"""

from core.prompts import (  # noqa: F401
    DEFAULT_REPLY_OPTIONS,
    INTENT_DESCRIPTIONS,
    REPLY_LANG_CODE_TO_ENGLISH,
    build_chat_system_prompt,
    build_reply_generation_prompt,
    build_system_prompt,
    build_translation_system_prompt,
    resolve_reply_language,
)

__all__ = [
    "DEFAULT_REPLY_OPTIONS",
    "INTENT_DESCRIPTIONS",
    "REPLY_LANG_CODE_TO_ENGLISH",
    "build_chat_system_prompt",
    "build_reply_generation_prompt",
    "build_system_prompt",
    "build_translation_system_prompt",
    "resolve_reply_language",
]
