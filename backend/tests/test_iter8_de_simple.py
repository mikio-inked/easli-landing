"""Iter 8: Simple German (de_simple) backend tests.

Coverage:
- GET /api/languages returns 7 languages in alphabetical order.
- POST /api/analyze with target_language='de_simple' produces Simple German output.
- POST /api/analyze with unsupported language → 400.
- POST /api/analyses/{id}/chat on de_simple analysis → reply in Simple German.
- Regression: 'en' analyze still works.
"""
import os
import re
import time
import pytest


EXPECTED_ORDER = ["de_simple", "en", "es", "vi", "tr", "ru", "zh"]
EXPECTED_DE_SIMPLE_LABEL = "Simple German (Einfaches Deutsch / Leichte Sprache)"


# ---------- /api/languages ----------
class TestLanguagesEndpoint:
    def test_languages_order_and_count(self, api_client, base_url):
        r = api_client.get(f"{base_url}/api/languages")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        codes = [d["code"] for d in data]
        assert codes == EXPECTED_ORDER, f"Languages not in expected order: {codes}"
        # de_simple label
        de_simple = next((d for d in data if d["code"] == "de_simple"), None)
        assert de_simple is not None
        assert de_simple["label"] == EXPECTED_DE_SIMPLE_LABEL


# ---------- /api/analyze unsupported ----------
class TestAnalyzeUnsupported:
    def test_unsupported_language_returns_400(self, api_client, base_url, german_letter_jpeg_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "unsupported_xx",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=30)
        assert r.status_code == 400, r.text
        assert "Unsupported" in r.text or "unsupported" in r.text.lower()


# ---------- /api/analyze de_simple ----------
@pytest.fixture(scope="module")
def de_simple_analysis(api_client, german_letter_jpeg_b64):
    """Create one de_simple analysis and reuse it across tests in this module."""
    base_url = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL") or "").rstrip("/")
    if not base_url:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("EXPO_PUBLIC_BACKEND_URL"):
                        base_url = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                        break
        except Exception:
            pass
    device_id = "TEST_de_simple_iter8"
    payload = {
        "device_id": device_id,
        "target_language": "de_simple",
        "file_base64": german_letter_jpeg_b64,
        "mime_type": "image/jpeg",
    }
    r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=180)
    assert r.status_code == 200, f"de_simple analyze failed: {r.status_code} {r.text[:500]}"
    data = r.json()
    yield {"base_url": base_url, "device_id": device_id, "data": data}
    # Cleanup
    try:
        api_client.delete(f"{base_url}/api/analyses?device_id={device_id}", timeout=30)
    except Exception:
        pass


class TestAnalyzeDeSimple:
    def test_label_is_simple_german(self, de_simple_analysis):
        data = de_simple_analysis["data"]
        assert data["target_language"] == "de_simple"
        assert data["target_language_label"] == EXPECTED_DE_SIMPLE_LABEL

    def test_summary_is_german_text(self, de_simple_analysis):
        result = de_simple_analysis["data"]["result"]
        summary = result.get("summary_translated", "")
        explanation = result.get("simple_explanation_translated", "")
        combined = f"{summary} {explanation}".lower()
        assert summary, "summary_translated empty"
        # Should contain common German words (Sie form, common articles, etc.)
        german_signals = ["sie", "der", "die", "das", "ist", "und", "nicht", "müssen", "können", "haben", "ihr"]
        hits = sum(1 for w in german_signals if re.search(rf"\b{w}\b", combined))
        assert hits >= 3, f"Output does not look like German. Summary: {summary[:200]}"

    def test_short_sentences_for_leichte_sprache(self, de_simple_analysis):
        result = de_simple_analysis["data"]["result"]
        text = result.get("simple_explanation_translated", "") or result.get("summary_translated", "")
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
        if not sentences:
            pytest.skip("No sentences to evaluate")
        avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
        # Leichte Sprache target ~8-12 words; allow up to ~16 average for leniency
        assert avg_words <= 16, f"Sentences too long for Leichte Sprache (avg {avg_words:.1f} words)"

    def test_inline_explanation_of_formal_terms(self, de_simple_analysis):
        """Spot-check: Leichte Sprache directive requires inline explanations of formal terms.
        We check that SOMEWHERE in the output a formal German term is explained either via
        parenthetical clause `(...)` or via 'X bedeutet: ...' / 'X heißt: ...' pattern."""
        result = de_simple_analysis["data"]["result"]
        all_text = " ".join([
            result.get("summary_translated", ""),
            result.get("simple_explanation_translated", ""),
            " ".join(result.get("key_points", []) or []),
            " ".join(a.get("reason", "") for a in result.get("required_actions", []) or []),
            result.get("risk_reason", ""),
        ]).lower()
        has_paren_explanation = bool(re.search(r"\([a-zäöüß ,.\-]{6,}\)", all_text))
        has_bedeutet = "bedeutet" in all_text or "heißt" in all_text or "heisst" in all_text
        assert has_paren_explanation or has_bedeutet, (
            "Leichte Sprache directive: no inline explanation of any formal term found. "
            f"Text: {all_text[:400]}"
        )


# ---------- /api/analyses/{id}/chat in de_simple ----------
class TestChatDeSimple:
    def test_chat_reply_is_simple_german(self, api_client, de_simple_analysis):
        base_url = de_simple_analysis["base_url"]
        device_id = de_simple_analysis["device_id"]
        analysis_id = de_simple_analysis["data"]["id"]

        payload = {"device_id": device_id, "message": "Was soll ich machen?"}
        r = api_client.post(
            f"{base_url}/api/analyses/{analysis_id}/chat",
            json=payload,
            timeout=120,
        )
        assert r.status_code == 200, f"chat failed: {r.status_code} {r.text[:500]}"
        body = r.json()
        reply = body.get("content", "")
        assert reply, "empty chat reply"

        # German signal check
        german_signals = ["sie", "der", "die", "das", "ist", "und", "nicht", "können", "müssen", "ihr", "bitte"]
        hits = sum(1 for w in german_signals if re.search(rf"\b{w}\b", reply.lower()))
        assert hits >= 2, f"Chat reply not in German: {reply[:300]}"

        # Short sentence check (Leichte Sprache)
        sentences = [s.strip() for s in re.split(r"[.!?]+", reply) if s.strip()]
        if sentences:
            avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
            assert avg_words <= 18, f"Chat sentences too long (avg {avg_words:.1f}): {reply[:300]}"


# ---------- Regression: 'en' analyze ----------
class TestAnalyzeEnRegression:
    def test_en_analyze_still_works(self, api_client, base_url, german_letter_jpeg_b64):
        device_id = "TEST_en_iter8_regression"
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=180)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data["target_language"] == "en"
        assert data["target_language_label"] == "English"
        result = data["result"]
        # English signal: should contain common English words
        text = (result.get("summary_translated", "") + " " + result.get("simple_explanation_translated", "")).lower()
        english_signals = ["the", "this", "you", "is", "are", "to", "of", "and", "letter", "payment"]
        hits = sum(1 for w in english_signals if re.search(rf"\b{w}\b", text))
        assert hits >= 3, f"en analysis text does not look English: {text[:300]}"
        # Cleanup
        try:
            api_client.delete(f"{base_url}/api/analyses?device_id={device_id}", timeout=30)
        except Exception:
            pass
