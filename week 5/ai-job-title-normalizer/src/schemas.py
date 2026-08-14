from enum import Enum
from pydantic import BaseModel, Field

class CanonicalTitleEnum(str, Enum):
    SOFTWARE_ENGINEER = "Software Engineer"
    BACKEND_ENGINEER = "Backend Engineer"
    FRONTEND_ENGINEER = "Frontend Engineer"
    FULL_STACK_ENGINEER = "Full Stack Engineer"
    DATA_ENGINEER = "Data Engineer"
    ML_ENGINEER = "ML Engineer"
    DEVOPS_ENGINEER = "DevOps Engineer"
    OTHER = "Other"

class SeniorityLevelEnum(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    UNKNOWN = "unknown"

class NormalizeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=200, description="The job title to normalize.")

class NormalizeResponse(BaseModel):
    canonical_title: CanonicalTitleEnum = Field(..., description="The normalized software engineering job title.")
    level: SeniorityLevelEnum = Field(..., description="The seniority level.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="The confidence score of the normalization.")
    reason: str = Field(..., description="Short explanation of the classification.")

from typing import Optional

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class JobSubmissionResponse(BaseModel):
    job_id: str
    status: JobStatus

class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: Optional[NormalizeResponse] = None
    error: Optional[str] = None
    attempts: int = Field(0, description="The number of processing attempts made.")


