"""KlarPost backend API tests."""
import pytest
import requests


# ---------------- Health & Languages ----------------
class TestHealth:
    def test_root(self, base_url, api_client):
        r = api_client.get(f"{base_url}/api/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("app") == "KlarPost"
        assert data.get("status") == "ok"

    def test_languages(self, base_url, api_client):
        r = api_client.get(f"{base_url}/api/languages")
        assert r.status_code == 200
        items = r.json()
        codes = {it["code"] for it in items}
        assert codes == {"zh", "vi", "tr", "ru", "en", "es"}
        # Ensure label is present and non-empty
        for it in items:
            assert it.get("label")


# ---------------- Validation errors (no LLM hit) ----------------
class TestAnalyzeValidation:
    def test_unsupported_language(self, base_url, api_client, german_letter_jpeg_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "xx",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload)
        assert r.status_code == 400
        assert "language" in r.json().get("detail", "").lower()

    def test_unsupported_mime(self, base_url, api_client, german_letter_jpeg_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/svg+xml",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload)
        assert r.status_code == 400
        assert "unsupported" in r.json().get("detail", "").lower()

    def test_empty_file(self, base_url, api_client, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": "",
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload)
        assert r.status_code == 400


# ---------------- Analyze (LLM-backed) ----------------
class TestAnalyzeFlow:
    def test_analyze_jpeg_english(self, base_url, api_client, german_letter_jpeg_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["target_language"] == "en"
        assert data["target_language_label"] == "English"
        assert data["device_id"] == device_id
        assert "id" in data and data["id"]
        assert "created_at" in data and data["created_at"]
        assert "_id" not in data

        result = data["result"]
        assert result["risk_level"] in {"green", "yellow", "red"}
        assert result["summary_translated"], "summary_translated must be non-empty"
        assert result["disclaimer"], "disclaimer must be non-empty"
        assert isinstance(result["key_points"], list)
        assert isinstance(result["deadlines"], list)
        assert isinstance(result["required_actions"], list)
        # document_type & sender should typically be filled
        assert result["document_type"], "document_type should be set"

        # Save id for downstream tests in this class instance via module-scoped store
        pytest.shared_record_id = data["id"]
        pytest.shared_device_id = device_id

    def test_analyze_chinese_translation(self, base_url, api_client, german_letter_jpeg_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "zh",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/jpeg",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data["result"].get("summary_translated", "")
        assert summary, "summary_translated must be non-empty for zh"
        # Best-effort: at least one CJK char present, OR not pure ASCII
        is_ascii_only = all(ord(c) < 128 for c in summary)
        assert not is_ascii_only, f"summary_translated should not be ASCII-only for zh; got: {summary[:120]}"
        assert data["target_language_label"].startswith("Chinese")

    def test_analyze_pdf(self, base_url, api_client, german_letter_pdf_b64, device_id):
        payload = {
            "device_id": device_id,
            "target_language": "en",
            "file_base64": german_letter_pdf_b64,
            "mime_type": "application/pdf",
        }
        r = api_client.post(f"{base_url}/api/analyze", json=payload, timeout=180)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["mime_type"] == "application/pdf"
        assert data["result"]["summary_translated"]


# ---------------- Listing / Get / Delete ----------------
class TestPersistence:
    def test_list_and_get_and_delete(self, base_url, api_client, german_letter_jpeg_b64):
        import uuid
        dev = f"TEST_DEVICE_{uuid.uuid4()}"
        # Create one
        r = api_client.post(f"{base_url}/api/analyze", json={
            "device_id": dev,
            "target_language": "en",
            "file_base64": german_letter_jpeg_b64,
            "mime_type": "image/jpeg",
        }, timeout=180)
        assert r.status_code == 200
        rec = r.json()
        rid = rec["id"]

        # List
        r = api_client.get(f"{base_url}/api/analyses", params={"device_id": dev})
        assert r.status_code == 200
        lst = r.json()
        assert len(lst) >= 1
        assert any(it["id"] == rid for it in lst)
        # No _id field
        for it in lst:
            assert "_id" not in it
        # sorted desc - timestamps should be in order
        if len(lst) >= 2:
            assert lst[0]["created_at"] >= lst[1]["created_at"]

        # GET single - correct device
        r = api_client.get(f"{base_url}/api/analyses/{rid}", params={"device_id": dev})
        assert r.status_code == 200
        full = r.json()
        assert full["id"] == rid
        assert "_id" not in full
        assert full["result"]["summary_translated"]

        # GET single - wrong device -> 404
        r = api_client.get(f"{base_url}/api/analyses/{rid}", params={"device_id": "WRONG_DEVICE"})
        assert r.status_code == 404

        # GET single - unknown id -> 404
        r = api_client.get(f"{base_url}/api/analyses/nonexistent-id-xyz", params={"device_id": dev})
        assert r.status_code == 404

        # DELETE single
        r = api_client.delete(f"{base_url}/api/analyses/{rid}", params={"device_id": dev})
        assert r.status_code == 200
        assert r.json().get("deleted") == 1

        # Verify gone
        r = api_client.get(f"{base_url}/api/analyses/{rid}", params={"device_id": dev})
        assert r.status_code == 404

        r = api_client.get(f"{base_url}/api/analyses", params={"device_id": dev})
        assert r.status_code == 200
        assert all(it["id"] != rid for it in r.json())

    def test_delete_all_isolated_by_device(self, base_url, api_client, german_letter_jpeg_b64):
        import uuid
        dev_a = f"TEST_DEVICE_A_{uuid.uuid4()}"
        dev_b = f"TEST_DEVICE_B_{uuid.uuid4()}"

        # Create one on each device
        for dev in (dev_a, dev_b):
            r = api_client.post(f"{base_url}/api/analyze", json={
                "device_id": dev,
                "target_language": "en",
                "file_base64": german_letter_jpeg_b64,
                "mime_type": "image/jpeg",
            }, timeout=180)
            assert r.status_code == 200, f"create failed for {dev}: {r.text}"

        # Delete all for A
        r = api_client.delete(f"{base_url}/api/analyses", params={"device_id": dev_a})
        assert r.status_code == 200
        assert r.json().get("deleted", 0) >= 1

        # A should be empty
        r = api_client.get(f"{base_url}/api/analyses", params={"device_id": dev_a})
        assert r.status_code == 200
        assert r.json() == []

        # B should still have its record
        r = api_client.get(f"{base_url}/api/analyses", params={"device_id": dev_b})
        assert r.status_code == 200
        assert len(r.json()) >= 1

        # Cleanup B
        api_client.delete(f"{base_url}/api/analyses", params={"device_id": dev_b})
