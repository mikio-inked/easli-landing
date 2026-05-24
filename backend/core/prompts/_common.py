"""easli — small shared constants for the prompt sub-package.

Reserved for cross-prompt configuration: anything used by 2+ of the
build_* functions. Right now intentionally minimal — Phase 6c-f will
populate this with composable blocks (PERSONA_BLOCK, CRITICAL_RULES_BLOCK,
SAFETY_DISCLAIMER_BLOCK, RISK_LEVELS_BLOCK, LANGUAGE_SEPARATION_BLOCK) that
are currently inlined inside `analyze.build_system_prompt`.

Phase 6a keeps the prompt strings byte-identical to the pre-refactor
version so the regression test stays green; the actual block extraction
happens in subsequent phases.
"""

from __future__ import annotations

# Sentinel reply-options ids — canonical names used by both the analyser
# and the reply prompts. Anywhere a route or service needs to validate
# an intent id, import this set rather than hard-coding the list.
CANONICAL_INTENT_IDS: frozenset[str] = frozenset({
    "inquiry", "extension", "confirm", "objection",
    "submit_documents", "cancel",
})
