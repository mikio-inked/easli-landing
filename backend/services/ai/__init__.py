"""easli — Mistral AI service sub-package.

Phase 7 refactor: the former monolithic `services/ai_service.py` (744 lines)
is split into focused modules. The public surface is preserved via this
facade so every existing caller keeps working unchanged:

    from services.ai_service import analyze_from_ocr_text, ...   # legacy
    from services.ai          import analyze_from_ocr_text, ...   # new

New code SHOULD prefer the specific sub-module path, e.g.
    from services.ai.analyze import analyze_from_ocr_text

Module map (single-responsibility):
  client          → Mistral client access + retry-with-backoff helper
  language_gate   → cheap pre-analysis language classifier
  normalizers     → JSON sanitisation, EU-1 defaults, reply-options padding
  analyze         → /api/analyze orchestration (post-OCR)
  chat            → /api/analyses/{id}/chat
  translate       → /api/analyses/{id}/translate

Privacy contract is unchanged: every log line in this sub-package is
metadata-only (model id, char counts, attempt numbers, exception types).
NEVER logs message bodies, response text, or any user-content field.
"""

from services.ai.analyze import analyze_from_ocr_text
from services.ai.chat import chat_about_document
from services.ai.client import mistral_complete_with_retry
from services.ai.language_gate import detect_document_language
from services.ai.translate import translate_analysis_with_mistral

__all__ = [
    "analyze_from_ocr_text",
    "chat_about_document",
    "detect_document_language",
    "mistral_complete_with_retry",
    "translate_analysis_with_mistral",
]
