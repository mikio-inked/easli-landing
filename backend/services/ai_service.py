"""easli — legacy facade for the Mistral AI service.

Phase 7 refactored the former 744-line monolith into a focused sub-package
under `services/ai/`. This module is now a thin compatibility shim so the
historical public API keeps working unchanged:

    from services.ai_service import analyze_from_ocr_text, ...   # ← still works
    from services.ai          import analyze_from_ocr_text, ...   # ← preferred

New call-sites SHOULD import from the specific sub-module path:
    from services.ai.analyze       import analyze_from_ocr_text
    from services.ai.chat          import chat_about_document
    from services.ai.client        import mistral_complete_with_retry
    from services.ai.language_gate import detect_document_language
    from services.ai.translate     import translate_analysis_with_mistral

The shim also re-exports `mistral_client` so test files that historically
patched `services.ai_service.mistral_client = Stub()` keep loading without
ImportError — but note that since Phase 7 the canonical patch point is
`core.config.mistral_client`. Patching this shim is now a no-op.
"""

from services.ai import (  # noqa: F401  (re-export façade)
    analyze_from_ocr_text,
    chat_about_document,
    detect_document_language,
    mistral_complete_with_retry,
    translate_analysis_with_mistral,
)
from services.ai.client import mistral_client  # noqa: F401

__all__ = [
    "analyze_from_ocr_text",
    "chat_about_document",
    "detect_document_language",
    "mistral_client",
    "mistral_complete_with_retry",
    "translate_analysis_with_mistral",
]
