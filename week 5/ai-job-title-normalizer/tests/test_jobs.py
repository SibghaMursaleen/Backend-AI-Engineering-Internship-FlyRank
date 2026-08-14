import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from src.main import app
from src.config import settings
from src.routes.jobs import jobs_db, JobStatus
from src.llm.client import LLMClient

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_jobs_db():
    jobs_db.clear()
    yield
    jobs_db.clear()

@pytest.fixture(autouse=True)
def reset_settings():
    orig_enabled = settings.llm_enabled
    orig_stub = settings.llm_stub
    orig_api_key = settings.openrouter_api_key
    yield
    settings.llm_enabled = orig_enabled
    settings.llm_stub = orig_stub
    settings.openrouter_api_key = orig_api_key

def test_submit_job_success():
    """Verify that POST /jobs returns 202, response contains a job_id, and job is queued/completed."""
    settings.llm_enabled = True
    settings.llm_stub = True

    response = client.post("/jobs", json={"text": "Backend Developer"})
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    
    job_id = data["job_id"]
    
    # Verify GET /jobs/{job_id} works and reaches completed since background tasks run synchronously in TestClient
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    status_data = get_response.json()
    assert status_data["job_id"] == job_id
    assert status_data["status"] == "completed"
    assert status_data["result"] is not None
    assert status_data["result"]["canonical_title"] == "Backend Engineer"
    assert status_data["result"]["level"] == "mid"
    assert status_data["error"] is None

def test_job_transitions_to_running():
    """Verify that newly created job transitions to queued and then running during processing."""
    settings.llm_enabled = True
    settings.llm_stub = True

    original_normalize = LLMClient.normalize_job_title
    
    async def mock_normalize(self, text):
        # Find the active job in jobs_db
        assert len(jobs_db) == 1
        job_id = list(jobs_db.keys())[0]
        # Verify the background worker set it to running before invoking the LLM logic
        assert jobs_db[job_id]["status"] == "running"
        return await original_normalize(self, text)
        
    with patch("src.llm.client.LLMClient.normalize_job_title", mock_normalize):
        response = client.post("/jobs", json={"text": "Backend Developer"})
        assert response.status_code == 202
        data = response.json()
        job_id = data["job_id"]
        
        # Verify it completed successfully in the end
        assert jobs_db[job_id]["status"] == "completed"

def test_job_failed_status():
    """Verify that background processing failure marks the job as failed and stores the error."""
    settings.llm_enabled = True
    settings.llm_stub = False
    settings.openrouter_api_key = "test_key"
    
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        response = client.post("/jobs", json={"text": "Backend Developer"})
        assert response.status_code == 202
        job_id = response.json()["job_id"]
        
        get_response = client.get(f"/jobs/{job_id}")
        assert get_response.status_code == 200
        status_data = get_response.json()
        assert status_data["status"] == "failed"
        assert "Connection refused" in status_data["error"]
        assert status_data["result"] is None

def test_get_job_not_found():
    """Verify that querying an unknown job_id returns HTTP 404."""
    response = client.get("/jobs/non-existent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_submit_job_invalid_input():
    """Verify that an invalid input schema returns HTTP 400."""
    response = client.post("/jobs", json={"text": ""})
    assert response.status_code == 400
    assert "Invalid input schema" in response.json()["detail"]

import asyncio
from src.routes.jobs import process_job_task
from src.llm.exceptions import LLMTimeoutError, LLMTransientError, LLMPermanentError
from src.schemas import NormalizeResponse, CanonicalTitleEnum, SeniorityLevelEnum

def test_job_idempotency_called_once():
    """Verify that calling process_job_task twice with the same job_id executes the LLM call exactly once."""
    settings.llm_enabled = True
    settings.llm_stub = True
    
    # Create a job in queued state
    job_id = "test-idempotency-uuid"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    llm_client = LLMClient()
    
    with patch.object(LLMClient, "normalize_job_title", wraps=llm_client.normalize_job_title) as mock_normalize:
        async def run_tasks():
            await process_job_task(job_id, "Backend Developer", llm_client)
            await process_job_task(job_id, "Backend Developer", llm_client)
            
        asyncio.run(run_tasks())
        
        assert mock_normalize.call_count == 1
        assert jobs_db[job_id]["status"] == JobStatus.COMPLETED
        assert jobs_db[job_id]["attempts"] == 1
        assert jobs_db[job_id]["result"] is not None
        assert jobs_db[job_id]["result"].canonical_title == "Backend Engineer"

def test_job_successful_no_retry():
    """Verify that a successful job is processed in 1 attempt without retrying."""
    settings.llm_enabled = True
    settings.llm_stub = True
    
    response = client.post("/jobs", json={"text": "Backend Developer"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["status"] == "completed"
    assert data["attempts"] == 1
    assert data["error"] is None

def test_job_transient_failure_retry_success():
    """Verify that a job with transient failures retries and eventually succeeds, recording attempts."""
    settings.llm_enabled = True
    settings.llm_stub = False
    
    mock_response = NormalizeResponse(
        canonical_title=CanonicalTitleEnum.BACKEND_ENGINEER,
        level=SeniorityLevelEnum.MID,
        confidence=0.95,
        reason="Success after retries"
    )
    
    calls = [
        LLMTimeoutError("Timeout"),
        LLMTransientError("Transient 429"),
        mock_response
    ]
    
    call_idx = 0
    async def mock_normalize(self, text):
        nonlocal call_idx
        val = calls[call_idx]
        call_idx += 1
        if isinstance(val, Exception):
            raise val
        return val
        
    llm_client = LLMClient()
    job_id = "test-transient-retry"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        with patch.object(LLMClient, "normalize_job_title", mock_normalize):
            asyncio.run(process_job_task(job_id, "Backend Developer", llm_client))
            
            assert jobs_db[job_id]["status"] == JobStatus.COMPLETED
            assert jobs_db[job_id]["attempts"] == 3
            assert jobs_db[job_id]["result"] == mock_response
            assert jobs_db[job_id]["error"] is None
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)

def test_job_transient_failure_retries_exhausted():
    """Verify that a job with continuous transient failures fails after max retries, recording attempts=4."""
    settings.llm_enabled = True
    settings.llm_stub = False
    
    async def mock_normalize(self, text):
        raise LLMTimeoutError("Continuous timeout")
        
    llm_client = LLMClient()
    job_id = "test-transient-exhausted"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        with patch.object(LLMClient, "normalize_job_title", mock_normalize):
            asyncio.run(process_job_task(job_id, "Backend Developer", llm_client))
            
            assert jobs_db[job_id]["status"] == JobStatus.FAILED
            assert jobs_db[job_id]["attempts"] == 4
            assert "Continuous timeout" in jobs_db[job_id]["error"]
            assert jobs_db[job_id]["result"] is None
            assert mock_sleep.call_count == 3
            mock_sleep.assert_any_call(1.0)
            mock_sleep.assert_any_call(2.0)
            mock_sleep.assert_any_call(4.0)

def test_job_permanent_failure_no_retry():
    """Verify that a job with a permanent failure fails immediately without retry."""
    settings.llm_enabled = True
    settings.llm_stub = False
    
    async def mock_normalize(self, text):
        raise LLMPermanentError("Invalid API key")
        
    llm_client = LLMClient()
    job_id = "test-permanent-fail"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    with patch("asyncio.sleep", return_value=None) as mock_sleep:
        with patch.object(LLMClient, "normalize_job_title", mock_normalize):
            asyncio.run(process_job_task(job_id, "Backend Developer", llm_client))
            
            assert jobs_db[job_id]["status"] == JobStatus.FAILED
            assert jobs_db[job_id]["attempts"] == 1
            assert "Invalid API key" in jobs_db[job_id]["error"]
            assert jobs_db[job_id]["result"] is None
            assert mock_sleep.call_count == 0

def test_permanent_failure_logging_alert(caplog):
    """Verify that a permanent failure produces an ERROR-level alert containing the required fields."""
    import logging
    settings.llm_enabled = True
    settings.llm_stub = False
    
    async def mock_normalize(self, text):
        raise LLMPermanentError("Invalid credentials")
        
    llm_client = LLMClient()
    job_id = "test-alert-permanent"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    with caplog.at_level(logging.ERROR):
        with patch.object(LLMClient, "normalize_job_title", mock_normalize):
            asyncio.run(process_job_task(job_id, "Backend Developer", llm_client))
            
            # Check the alert logs
            alert_logs = [r.message for r in caplog.records if "BACKGROUND_JOB_FAILED" in r.message]
            assert len(alert_logs) == 1
            log_msg = alert_logs[0]
            
            assert "BACKGROUND_JOB_FAILED" in log_msg
            assert f"job_id={job_id}" in log_msg
            assert "attempts=1" in log_msg
            assert "error=Invalid credentials" in log_msg
            
            # Verify the failed job is still visible via GET
            get_response = client.get(f"/jobs/{job_id}")
            assert get_response.status_code == 200
            data = get_response.json()
            assert data["status"] == "failed"
            assert data["attempts"] == 1
            assert data["error"] == "Invalid credentials"

def test_transient_exhaustion_logging_alert(caplog):
    """Verify that a transient failure that exhausts retries produces an ERROR-level alert."""
    import logging
    settings.llm_enabled = True
    settings.llm_stub = False
    
    async def mock_normalize(self, text):
        raise LLMTimeoutError("Continuous timeout")
        
    llm_client = LLMClient()
    job_id = "test-alert-transient-exhausted"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    with caplog.at_level(logging.ERROR):
        with patch("asyncio.sleep", return_value=None):
            with patch.object(LLMClient, "normalize_job_title", mock_normalize):
                asyncio.run(process_job_task(job_id, "Backend Developer", llm_client))
                
                # Check the alert logs
                alert_logs = [r.message for r in caplog.records if "BACKGROUND_JOB_FAILED" in r.message]
                assert len(alert_logs) == 1
                log_msg = alert_logs[0]
                
                assert "BACKGROUND_JOB_FAILED" in log_msg
                assert f"job_id={job_id}" in log_msg
                assert "attempts=4" in log_msg
                assert "error=Continuous timeout" in log_msg

def test_transient_success_no_alert(caplog):
    """Verify that a transient failure that eventually succeeds does NOT log a failure alert."""
    import logging
    settings.llm_enabled = True
    settings.llm_stub = False
    
    mock_response = NormalizeResponse(
        canonical_title=CanonicalTitleEnum.BACKEND_ENGINEER,
        level=SeniorityLevelEnum.MID,
        confidence=0.95,
        reason="Mock success"
    )
    
    calls = [
        LLMTimeoutError("Transient timeout"),
        mock_response
    ]
    
    call_idx = 0
    async def mock_normalize(self, text):
        nonlocal call_idx
        val = calls[call_idx]
        call_idx += 1
        if isinstance(val, Exception):
            raise val
        return val
        
    llm_client = LLMClient()
    job_id = "test-success-no-alert"
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    
    with caplog.at_level(logging.ERROR):
        with patch("asyncio.sleep", return_value=None):
            with patch.object(LLMClient, "normalize_job_title", mock_normalize):
                asyncio.run(process_job_task(job_id, "Backend Developer", llm_client))
                
                # Ensure no failure alert logs
                alert_logs = [r.message for r in caplog.records if "BACKGROUND_JOB_FAILED" in r.message]
                assert len(alert_logs) == 0
                assert jobs_db[job_id]["status"] == JobStatus.COMPLETED


