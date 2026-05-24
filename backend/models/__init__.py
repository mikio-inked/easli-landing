"""easli — `models` package.

Re-exports every Pydantic schema from `models.schemas` so existing call
sites that do `from models import AnalysisResult` keep working without
change. New code MAY also import directly from `models.schemas` for
better IDE go-to-definition; both paths are supported.

Added explicit `__all__` so `from models import *` only pulls the curated
set and not internal helpers.
"""

from models.schemas import (
    # Type aliases
    ConfidenceLevel,
    DocumentCategory,
    EntitlementReason,
    EntitlementSource,
    JurisdictionConfidence,
    RiskLevel,
    # Analysis-result building blocks
    Deadline,
    ExtractedEntities,
    RequiredAction,
    ReplyOption,
    AnalysisResult,
    # Request / response shapes
    AnalysisListItem,
    AnalysisRecord,
    AnalyzeRequest,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    PageInput,
    TranslateRequest,
    # Reply Assistant
    GenerateReplyRequest,
    GenerateReplyResponse,
    # Usage / paywall
    EntitlementDecision,
    UsageRecord,
    UsageResponse,
)

__all__ = [
    # Type aliases
    "ConfidenceLevel",
    "DocumentCategory",
    "EntitlementReason",
    "EntitlementSource",
    "JurisdictionConfidence",
    "RiskLevel",
    # Analysis-result building blocks
    "Deadline",
    "ExtractedEntities",
    "RequiredAction",
    "ReplyOption",
    "AnalysisResult",
    # Request / response shapes
    "AnalysisListItem",
    "AnalysisRecord",
    "AnalyzeRequest",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "PageInput",
    "TranslateRequest",
    # Reply Assistant
    "GenerateReplyRequest",
    "GenerateReplyResponse",
    # Usage / paywall
    "EntitlementDecision",
    "UsageRecord",
    "UsageResponse",
]
