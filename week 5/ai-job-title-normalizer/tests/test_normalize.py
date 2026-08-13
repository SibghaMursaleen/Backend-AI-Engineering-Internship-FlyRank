import os
import shutil
import pytest
import asyncio
import httpx
import json
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from src.main import app
from src.config import settings
from src.schemas import CanonicalTitleEnum, SeniorityLevelEnum
from src.llm.client import LLMClient
from src.llm.exceptions import (
    LLMDisabledError,
    LLMTimeoutError,
    LLMTransientError,
    LLMPermanentError,
    LLMValidationError,
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_settings():
    orig_enabled = settings.llm_enabled
    orig_stub = settings.llm_stub
    orig_api_key = settings.openrouter_api_key
    yield
    settings.llm_enabled = orig_enabled
    settings.llm_stub = orig_stub
    settings.openrouter_api_key = orig_api_key

@pytest.fixture(autouse=True)
def clean_quarantine():
    # Remove quarantine directory before and after tests to keep them isolated
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    quarantine_dir = os.path.join(base_dir, "quarantine")
    if os.path.exists(quarantine_dir):
        shutil.rmtree(quarantine_dir)
    yield
    if os.path.exists(quarantine_dir):
        shutil.rmtree(quarantine_dir)


# ================= STAGE 1 TESTS =================

def test_normalize_valid_backend():
    """Verify stub mode returns correct mid backend engineer for Backend Developer."""
    settings.llm_enabled = True
    settings.llm_stub = True
    
    response = client.post("/normalize", json={"text": "Backend Developer"})
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_title"] == "Backend Engineer"
    assert data["level"] == "mid"
    assert data["confidence"] == 0.95
    assert "[STUB]" in data["reason"]

def test_normalize_valid_senior():
    """Verify stub mode returns senior software engineer for Sr. SWE II."""
    settings.llm_enabled = True
    settings.llm_stub = True
    
    response = client.post("/normalize", json={"text": "Sr. SWE II"})
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_title"] == "Software Engineer"
    assert data["level"] == "senior"
    assert data["confidence"] == 0.98

def test_normalize_unsure():
    """Verify stub mode returns Other/unknown for highly ambiguous titles."""
    settings.llm_enabled = True
    settings.llm_stub = True
    
    response = client.post("/normalize", json={"text": "Ninja Guru"})
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_title"] == "Other"
    assert data["level"] == "unknown"
    assert data["confidence"] == 0.20

def test_normalize_empty_input():
    """Verify that an empty input or missing input returns HTTP 400."""
    response = client.post("/normalize", json={"text": ""})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "Invalid input schema."

def test_normalize_missing_text():
    """Verify that a request missing 'text' returns HTTP 400."""
    response = client.post("/normalize", json={})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data

def test_normalize_too_long_input():
    """Verify that input over 200 characters returns HTTP 400."""
    long_text = "a" * 201
    response = client.post("/normalize", json={"text": long_text})
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data

def test_normalize_kill_switch():
    """Verify that setting LLM_ENABLED=false returns HTTP 503."""
    settings.llm_enabled = False
    
    response = client.post("/normalize", json={"text": "Backend Developer"})
    assert response.status_code == 503
    data = response.json()
    assert "disabled" in data["detail"]

def test_health_check():
    """Verify the health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ================= STAGE 2 TESTS =================

def test_llm_client_timeout_retry():
    """Verify that transient timeout/network failures are retried 3 times and raise LLMTimeoutError."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()

    async def run_test():
        with patch("src.llm.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout occurred")) as mock_post:
                with pytest.raises(LLMTimeoutError):
                    await client_instance.normalize_job_title("Backend Developer")
                
                # Called 1 original + 3 retries = 4 times
                assert mock_post.call_count == 4
                assert mock_sleep.call_count == 3

    asyncio.run(run_test())


def test_llm_client_transient_http_retry_success():
    """Verify that a transient error (e.g. HTTP 429) retries and succeeds if a later call succeeds."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    
    mock_fail = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
    mock_success = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"canonical_title": "Backend Engineer", "level": "mid", "confidence": 0.95, "reason": "Mock success"}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}
        }
    )

    async def run_test():
        with patch("src.llm.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("httpx.AsyncClient.post", side_effect=[mock_fail, mock_fail, mock_success]) as mock_post:
                response = await client_instance.normalize_job_title("Backend Developer")
                
                assert response.canonical_title == CanonicalTitleEnum.BACKEND_ENGINEER
                assert response.level == SeniorityLevelEnum.MID
                assert response.confidence == 0.95
                assert mock_post.call_count == 3
                assert mock_sleep.call_count == 2

    asyncio.run(run_test())


def test_llm_client_permanent_http_error():
    """Verify that permanent errors (e.g. HTTP 401 Unauthorized) are not retried and fail immediately."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    mock_response = httpx.Response(
        status_code=401,
        content="Unauthorized",
        request=httpx.Request("POST", "http://test")
    )

    async def run_test():
        with patch("src.llm.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
                with pytest.raises(LLMPermanentError):
                    await client_instance.normalize_job_title("Backend Developer")
                
                assert mock_post.call_count == 1
                assert mock_sleep.call_count == 0

    asyncio.run(run_test())


def test_llm_client_retry_after_handling():
    """Verify that transient HTTP 429 with a Retry-After header respects the sleep duration."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    
    mock_fail = httpx.Response(
        status_code=429,
        headers={"Retry-After": "5.5"},
        request=httpx.Request("POST", "http://test")
    )
    mock_success = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={
            "choices": [
                {
                    "message": {
                        "content": '{"canonical_title": "Backend Engineer", "level": "mid", "confidence": 0.95, "reason": "Mock success"}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}
        }
    )

    async def run_test():
        with patch("src.llm.client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with patch("httpx.AsyncClient.post", side_effect=[mock_fail, mock_success]) as mock_post:
                response = await client_instance.normalize_job_title("Backend Developer")
                
                assert response.canonical_title == CanonicalTitleEnum.BACKEND_ENGINEER
                assert mock_post.call_count == 2
                assert mock_sleep.call_count == 1
                mock_sleep.assert_called_once_with(5.5)

    asyncio.run(run_test())


# ================= STAGE 3 TESTS =================

def test_llm_client_valid_json_no_repair():
    """Verify that a valid JSON output matching Pydantic schema skips the repair flow entirely."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    mock_response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={
            "choices": [{
                "message": {
                    "content": '{"canonical_title": "Backend Engineer", "level": "mid", "confidence": 0.95, "reason": "Valid"}'
                }
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 15, "total_tokens": 25}
        }
    )

    async def run_test():
        with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            response = await client_instance.normalize_job_title("Backend Developer")
            assert response.canonical_title == CanonicalTitleEnum.BACKEND_ENGINEER
            assert response.level == SeniorityLevelEnum.MID
            # Should call OpenRouter exactly once (no repair attempts)
            assert mock_post.call_count == 1

    asyncio.run(run_test())


def test_llm_client_malformed_json_repair_success():
    """Verify that a malformed JSON response triggers a repair attempt and succeeds if the second call is valid."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    
    mock_malformed = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": "{ malformed json: true }"}}]}
    )
    mock_repaired = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={
            "choices": [{
                "message": {
                    "content": '{"canonical_title": "Backend Engineer", "level": "mid", "confidence": 0.95, "reason": "Repaired"}'
                }
            }],
            "usage": {"prompt_tokens": 15, "completion_tokens": 20, "total_tokens": 35}
        }
    )

    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=[mock_malformed, mock_repaired]) as mock_post:
            response = await client_instance.normalize_job_title("Backend Developer")
            assert response.canonical_title == CanonicalTitleEnum.BACKEND_ENGINEER
            assert response.level == SeniorityLevelEnum.MID
            # Initial attempt + exactly one repair attempt = 2 calls
            assert mock_post.call_count == 2

    asyncio.run(run_test())


def test_llm_client_schema_invalid_repair_success():
    """Verify that schema-invalid JSON (bad enum values) triggers a repair attempt and succeeds if the second call is valid."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    
    # "InvalidTitle" is not in CanonicalTitleEnum
    mock_bad_schema = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": '{"canonical_title": "InvalidTitle", "level": "mid", "confidence": 0.95, "reason": "Bad"}'}}]}
    )
    mock_repaired = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={
            "choices": [{
                "message": {
                    "content": '{"canonical_title": "Backend Engineer", "level": "mid", "confidence": 0.95, "reason": "Repaired schema"}'
                }
            }]
        }
    )

    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=[mock_bad_schema, mock_repaired]) as mock_post:
            response = await client_instance.normalize_job_title("Backend Developer")
            assert response.canonical_title == CanonicalTitleEnum.BACKEND_ENGINEER
            assert mock_post.call_count == 2

    asyncio.run(run_test())


def test_llm_client_malformed_json_repair_fails_quarantine():
    """Verify that when repair fails (re-malformed), it raises LLMValidationError, exactly one repair happens, and it is quarantined."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    
    mock_malformed_1 = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": "{ malformed 1: true }"}}]}
    )
    mock_malformed_2 = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": "{ malformed 2: true }"}}]}
    )

    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=[mock_malformed_1, mock_malformed_2]) as mock_post:
            with pytest.raises(LLMValidationError):
                await client_instance.normalize_job_title("Backend Developer")
            
            # Should call exactly 2 times (1 initial, exactly 1 repair)
            assert mock_post.call_count == 2
            
            # Verify quarantine folder has a failed log file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            quarantine_dir = os.path.join(base_dir, "quarantine")
            assert os.path.exists(quarantine_dir)
            files = os.listdir(quarantine_dir)
            assert len(files) == 1
            
            # Verify quarantine content
            with open(os.path.join(quarantine_dir, files[0]), "r", encoding="utf-8") as f:
                data = json.load(f)
                assert data["input_text"] == "Backend Developer"
                assert data["initial_response"] == "{ malformed 1: true }"
                assert "initial_error" in data
                assert data["repair_response"] == "{ malformed 2: true }"
                assert "repair_error" in data

    asyncio.run(run_test())


def test_llm_client_schema_invalid_repair_fails_quarantine():
    """Verify that when repair returns invalid schema again, it raises LLMValidationError and triggers quarantine."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    client_instance = LLMClient()
    
    mock_bad_schema_1 = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": '{"canonical_title": "InvalidTitle1", "level": "mid", "confidence": 0.95, "reason": "Bad1"}'}}]}
    )
    mock_bad_schema_2 = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": '{"canonical_title": "InvalidTitle2", "level": "mid", "confidence": 0.95, "reason": "Bad2"}'}}]}
    )

    async def run_test():
        with patch("httpx.AsyncClient.post", side_effect=[mock_bad_schema_1, mock_bad_schema_2]) as mock_post:
            with pytest.raises(LLMValidationError):
                await client_instance.normalize_job_title("Backend Developer")
            
            assert mock_post.call_count == 2
            
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            quarantine_dir = os.path.join(base_dir, "quarantine")
            assert os.path.exists(quarantine_dir)
            files = os.listdir(quarantine_dir)
            assert len(files) == 1

    asyncio.run(run_test())


def test_endpoint_repair_fails_http_422():
    """Verify that the API route returns HTTP 422 when repair fails and hides raw model output from response."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_api_key"

    mock_malformed_1 = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": "{ malformed 1: true }"}}]}
    )
    mock_malformed_2 = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://test"),
        json={"choices": [{"message": {"content": "{ malformed 2: true }"}}]}
    )

    with patch("httpx.AsyncClient.post", side_effect=[mock_malformed_1, mock_malformed_2]) as mock_post:
        response = client.post("/normalize", json={"text": "Backend Developer"})
        assert response.status_code == 422
        
        # Verify response message details do not expose raw malformed model output
        data = response.json()
        assert "detail" in data
        assert "{ malformed 1: true }" not in data["detail"]
        assert "{ malformed 2: true }" not in data["detail"]
        assert mock_post.call_count == 2
