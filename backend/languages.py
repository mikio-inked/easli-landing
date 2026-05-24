"""easli — legacy re-export shim for `core.languages`.

The actual language registries live in `core/languages.py` since Phase 3a
of the backend refactor. This file is kept so existing imports
(`from languages import LANGUAGES`) keep working. Will be removed once
all consumers migrate to `core.languages`.

DO NOT add new code here. Import from `core.languages` in any new module.
"""

from core.languages import (  # noqa: F401
    EXPLANATION_LANGUAGES,
    LANGUAGES,
    resolve_explanation_label,
)

__all__ = ["EXPLANATION_LANGUAGES", "LANGUAGES", "resolve_explanation_label"]
