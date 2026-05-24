"""easli — JSON normalisation helpers for Mistral responses.

Pure functions only — no Mistral calls, no HTTP, no DB. The analyse and
translate flows pipe their raw `parsed` dict through these helpers BEFORE
feeding it to `AnalysisResult(**parsed)`. Keeping the normalisation in a
separate module makes it trivial to unit-test the contract without
talking to an LLM.

The two main entry points are:
  • normalize_analysis_payload(parsed, target_language_label, target_language_code)
      — applied after /api/analyze parses the LLM response.
  • apply_translation_invariants(parsed, slim_source, new_target_label)
      — applied after /api/translate parses the LLM response, to enforce
        that factual fields (sender, dates, risk, IDs, reply_options ids)
        are byte-identical to the source.
"""

from __future__ import annotations

from typing import Iterable

from core.prompts import INTENT_DESCRIPTIONS
from utils.json_utils import sanitize_literal_fields

# Localised reply-option labels used when Mistral returned no `reply_options`
# or all options were invalid. Keeps the Reply tab in the UI usable.
REPLY_OPTION_LABELS_EN: dict[str, str] = {
    "inquiry": "Ask for clarification",
    "extension": "Ask for more time",
    "confirm": "Confirm receipt",
    "objection": "File an objection",
}
REPLY_OPTION_LABELS_DE: dict[str, str] = {
    "inquiry": "Nachfrage stellen",
    "extension": "Frist verlängern",
    "confirm": "Bestätigung",
    "objection": "Widerspruch einlegen",
}

# When translating an existing analysis we drop every server-only field
# and only forward what AnalysisResult cares about. Prevents the LLM from
# getting confused by metadata it shouldn't see.
ALLOWED_TRANSLATION_KEYS: frozenset[str] = frozenset({
    "source_language", "source_language_code", "target_language",
    "document_type", "sender",
    "summary_translated", "simple_explanation_translated", "key_points",
    "deadlines", "required_actions", "risk_level", "risk_reason",
    "reply_draft", "german_reply_draft", "reply_draft_explanation_translated",
    "questions_to_ask", "uncertainties", "disclaimer", "category",
    "scam_warning", "scam_reason",
    # Phase R5 — preserved invariant fields. Reply_options labels DO get
    # translated, but ids + recommended booleans stay byte-identical.
    "extracted_entities", "reply_options",
})

# Factual fields that must NEVER change when translating an analysis.
# Belt-and-braces against the model "helpfully" localising a sender name
# or editing a deadline date.
TRANSLATION_INVARIANT_KEYS: tuple[str, ...] = (
    "sender",
    "risk_level",
    "category",
    "scam_warning",
    "reply_draft",
    "german_reply_draft",
    "source_language",
    "source_language_code",
    # Phase R5 — preserve extracted entities byte-identical.
    "extracted_entities",
)


def _coerce_str(value, default: str = "") -> str:
    return value.strip() if isinstance(value, str) else default


def _normalise_reply_options(parsed: dict, target_language_code: str) -> None:
    """Validate, dedupe and pad `parsed['reply_options']` in place so the
    Reply tab is never empty and never tiny. Guarantees at least 4 distinct
    canonical options with exactly one `recommended=True`.
    """
    labels = (
        REPLY_OPTION_LABELS_DE
        if target_language_code == "de_simple"
        else REPLY_OPTION_LABELS_EN
    )
    raw_options = parsed.get("reply_options")

    if not isinstance(raw_options, list) or not raw_options:
        parsed["reply_options"] = [
            {"id": k, "label": v, "reason": "", "recommended": (k == "inquiry")}
            for k, v in labels.items()
        ]
        return

    cleaned: list[dict] = []
    for opt in raw_options:
        if not isinstance(opt, dict):
            continue
        oid = (opt.get("id") or "").strip().lower()
        if oid not in INTENT_DESCRIPTIONS:
            continue
        cleaned.append({
            "id": oid,
            "label": (opt.get("label") or "").strip(),
            "reason": (opt.get("reason") or "").strip(),
            "recommended": bool(opt.get("recommended")),
        })

    if not cleaned:
        cleaned = [
            {"id": k, "label": v, "reason": "", "recommended": (k == "inquiry")}
            for k, v in labels.items()
        ]
    else:
        if not any(o["recommended"] for o in cleaned):
            cleaned[0]["recommended"] = True
        # "Never empty / never tiny" guarantee: pad with missing canonical
        # ids until the user has at least 4 distinct options.
        if len(cleaned) < 4:
            existing_ids = {o["id"] for o in cleaned}
            for canonical_id, label in labels.items():
                if canonical_id in existing_ids:
                    continue
                cleaned.append({
                    "id": canonical_id,
                    "label": label,
                    "reason": "",
                    "recommended": False,
                })
                if len(cleaned) >= 4:
                    break

    parsed["reply_options"] = cleaned


def normalize_analysis_payload(
    parsed: dict,
    target_language_label: str,
    target_language_code: str = "",
) -> dict:
    """Normalise a freshly-parsed analyse-response dict in place.

    Steps (the order matters — Phase EU-1 country normalisation depends on
    `detected_country_code` being canonicalised before `jurisdiction_confidence`
    is gated on it):
      1. Inject the user's chosen target_language label.
      2. Default string fields that the model may have omitted.
      3. Canonicalise source_language_code and EU-1 country fields.
      4. Default suggested_reply_language_code to source_language_code.
      5. Clamp confidence_score to [0.0, 1.0].
      6. Mirror reply_draft ↔ german_reply_draft for back-compat.
      7. Validate / pad reply_options.
      8. Normalise extracted_entities to the canonical 5-key shape.
      9. Coerce Literal fields (risk_level, urgency, confidence, …).

    Returns the SAME dict for call-chaining convenience.
    """
    parsed["target_language"] = target_language_label

    if not isinstance(parsed.get("source_language"), str):
        parsed["source_language"] = ""
    if not isinstance(parsed.get("source_language_code"), str):
        parsed["source_language_code"] = ""
    parsed["source_language_code"] = (parsed.get("source_language_code") or "").strip().lower()

    # ─── Phase EU-1: normalise the multilingual fields ──────────────────────
    cc = parsed.get("detected_country_code") or ""
    if not isinstance(cc, str):
        cc = ""
    parsed["detected_country_code"] = cc.strip().upper()
    if not isinstance(parsed.get("detected_country_name"), str):
        parsed["detected_country_name"] = ""
    parsed["detected_country_name"] = (parsed.get("detected_country_name") or "").strip()

    jc = (parsed.get("jurisdiction_confidence") or "").strip().lower()
    if jc not in ("low", "medium", "high"):
        jc = ""
    if not parsed["detected_country_code"]:
        # No country detected → confidence MUST be empty (the schema
        # explicitly says "low|medium|high|''").
        jc = ""
    parsed["jurisdiction_confidence"] = jc

    srlc = (parsed.get("suggested_reply_language_code") or "").strip().lower()
    if not srlc:
        srlc = parsed.get("source_language_code") or ""
    parsed["suggested_reply_language_code"] = srlc

    cs = parsed.get("confidence_score")
    try:
        cs_f = float(cs) if cs is not None else 0.0
    except (TypeError, ValueError):
        cs_f = 0.0
    parsed["confidence_score"] = max(0.0, min(1.0, cs_f))

    if not isinstance(parsed.get("safety_disclaimer"), str):
        parsed["safety_disclaimer"] = ""

    # Back-compat alias: mirror `reply_draft` ↔ `german_reply_draft`.
    rd = parsed.get("reply_draft")
    grd = parsed.get("german_reply_draft")
    if isinstance(rd, str) and rd.strip() and not (isinstance(grd, str) and grd.strip()):
        parsed["german_reply_draft"] = rd
    elif isinstance(grd, str) and grd.strip() and not (isinstance(rd, str) and rd.strip()):
        parsed["reply_draft"] = grd

    _normalise_reply_options(parsed, target_language_code)

    # Normalise extracted_entities to the canonical 5-key shape.
    ee = parsed.get("extracted_entities")
    if not isinstance(ee, dict):
        ee = {}
    parsed["extracted_entities"] = {
        "email": _coerce_str(ee.get("email")),
        "subject": _coerce_str(ee.get("subject")),
        "reference_number": _coerce_str(ee.get("reference_number")),
        "contact_person": _coerce_str(ee.get("contact_person")),
        "organization": _coerce_str(ee.get("organization")),
    }

    sanitize_literal_fields(parsed)
    return parsed


def slim_for_translation(source_result: dict) -> dict:
    """Drop every server-only field and return only what AnalysisResult
    needs for the translate prompt. Also back-fills `reply_draft` from
    the legacy `german_reply_draft` when the source record was old.
    """
    slim = {
        k: v for k, v in (source_result or {}).items() if k in ALLOWED_TRANSLATION_KEYS
    }
    if slim.get("german_reply_draft") and not slim.get("reply_draft"):
        slim["reply_draft"] = slim["german_reply_draft"]
    return slim


def _preserve_reply_options_invariants(
    parsed_options, src_options,
) -> list | None:
    """Force `id` and `recommended` to match the source for each reply_option.
    Allows the model to localise `label` and `reason`. Returns the new list
    or None if neither side had a valid list.
    """
    if isinstance(parsed_options, list) and isinstance(src_options, list):
        src_by_id = {o.get("id"): o for o in src_options if isinstance(o, dict)}
        for opt in parsed_options:
            if not isinstance(opt, dict):
                continue
            src_o = src_by_id.get(opt.get("id"))
            if src_o:
                opt["id"] = src_o.get("id", opt.get("id", ""))
                opt["recommended"] = bool(
                    src_o.get("recommended", opt.get("recommended", False))
                )
        return parsed_options
    if isinstance(src_options, list):
        return src_options
    return None


def _preserve_sub_fields(
    parsed_list, src_list, sub_field_defaults: Iterable[tuple[str, str]],
) -> None:
    """Deep-preserve specific sub-fields from `src_list` into `parsed_list`.
    Used for deadlines (date, confidence) and required_actions (urgency).
    """
    if not (isinstance(parsed_list, list) and isinstance(src_list, list)):
        return
    for i, item in enumerate(parsed_list):
        if not isinstance(item, dict) or i >= len(src_list):
            continue
        src = src_list[i] or {}
        for key, default in sub_field_defaults:
            item[key] = src.get(key, item.get(key, default))


def apply_translation_invariants(
    parsed: dict,
    slim_source: dict,
    new_target_label: str,
) -> dict:
    """Enforce factual invariants on a freshly-parsed translation response.

    Whatever the model returned for the listed `TRANSLATION_INVARIANT_KEYS`
    is overwritten with the source's values. reply_options ids and
    recommended-flags are preserved; labels/reasons are kept as the model
    localised them. Deadlines.date/confidence and required_actions.urgency
    are deep-preserved index-by-index.

    Mutates `parsed` in place AND returns it for call-chaining convenience.
    """
    for k in TRANSLATION_INVARIANT_KEYS:
        if k in slim_source:
            parsed[k] = slim_source[k]

    src_options = slim_source.get("reply_options")
    new_options = parsed.get("reply_options")
    new_options = _preserve_reply_options_invariants(new_options, src_options)
    if new_options is not None:
        parsed["reply_options"] = new_options

    # Keep reply_draft ↔ german_reply_draft in sync after invariants applied.
    if parsed.get("reply_draft") and not parsed.get("german_reply_draft"):
        parsed["german_reply_draft"] = parsed["reply_draft"]
    elif parsed.get("german_reply_draft") and not parsed.get("reply_draft"):
        parsed["reply_draft"] = parsed["german_reply_draft"]

    _preserve_sub_fields(
        parsed.get("deadlines"), slim_source.get("deadlines"),
        (("date", ""), ("confidence", "low")),
    )
    _preserve_sub_fields(
        parsed.get("required_actions"), slim_source.get("required_actions"),
        (("urgency", "low"),),
    )

    parsed["target_language"] = new_target_label
    sanitize_literal_fields(parsed)
    return parsed


DEFAULT_DISCLAIMER: str = (
    "easli provides general information only and does not give legal, tax, "
    "financial, or medical advice. Please verify with the sender or a "
    "qualified professional."
)
