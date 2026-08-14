import uuid
import logging
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from src.schemas import (
    NormalizeRequest,
    JobStatus,
    JobSubmissionResponse,
    JobStatusResponse,
)
from src.llm.client import LLMClient
from src.llm.exceptions import LLMTimeoutError, LLMTransientError
from src.routes.normalize import get_llm_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple in-memory database for jobs
jobs_db: Dict[str, Dict[str, Any]] = {}

async def process_job_task(job_id: str, text: str, llm_client: LLMClient):
    # Idempotency check:
    if jobs_db[job_id]["status"] != JobStatus.QUEUED:
        logger.warning(f"Job {job_id} already being processed or finished (status: {jobs_db[job_id]['status']}). Exiting.")
        return

    jobs_db[job_id]["status"] = JobStatus.RUNNING

    max_retries = 3
    base_delay = 1.0

    for attempt in range(1, max_retries + 2):
        jobs_db[job_id]["attempts"] = attempt
        try:
            response = await llm_client.normalize_job_title(text)
            jobs_db[job_id]["result"] = response
            jobs_db[job_id]["status"] = JobStatus.COMPLETED
            jobs_db[job_id]["error"] = None
            return
        except (LLMTimeoutError, LLMTransientError) as e:
            logger.warning(f"Transient error on job {job_id} attempt {attempt}: {e}")
            if attempt == max_retries + 1:
                # All retries exhausted
                jobs_db[job_id]["error"] = str(e)
                jobs_db[job_id]["status"] = JobStatus.FAILED
                logger.error(
                    f"BACKGROUND_JOB_FAILED\n"
                    f"job_id={job_id}\n"
                    f"attempts={attempt}\n"
                    f"error={str(e)}"
                )
                return
            delay = base_delay * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
        except Exception as e:
            # Permanent errors (LLMDisabledError, LLMValidationError, LLMPermanentError, or others)
            logger.error(f"Permanent/unhandled error on job {job_id} attempt {attempt}: {e}", exc_info=True)
            jobs_db[job_id]["error"] = str(e)
            jobs_db[job_id]["status"] = JobStatus.FAILED
            logger.error(
                f"BACKGROUND_JOB_FAILED\n"
                f"job_id={job_id}\n"
                f"attempts={attempt}\n"
                f"error={str(e)}"
            )
            return

@router.post(
    "/jobs",
    response_model=JobSubmissionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a job to normalize a job title in the background."
)
async def create_normalize_job(
    request: NormalizeRequest,
    background_tasks: BackgroundTasks,
    llm_client: LLMClient = Depends(get_llm_client)
):
    job_id = str(uuid.uuid4())
    jobs_db[job_id] = {
        "job_id": job_id,
        "status": JobStatus.QUEUED,
        "result": None,
        "error": None,
        "attempts": 0
    }
    background_tasks.add_task(process_job_task, job_id, request.text, llm_client)
    return JobSubmissionResponse(job_id=job_id, status=JobStatus.QUEUED)

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get the status and result of a background normalization job."
)
async def get_job_status(job_id: str):
    if job_id not in jobs_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found."
        )
    job_data = jobs_db[job_id]
    return JobStatusResponse(
        job_id=job_data["job_id"],
        status=job_data["status"],
        result=job_data["result"],
        error=job_data["error"],
        attempts=job_data["attempts"]
    )
