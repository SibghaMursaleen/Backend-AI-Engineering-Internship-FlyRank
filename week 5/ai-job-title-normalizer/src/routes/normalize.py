from fastapi import APIRouter, Depends, HTTPException, status
from src.schemas import NormalizeRequest, NormalizeResponse
from src.llm.client import LLMClient
from src.llm.exceptions import (
    LLMDisabledError,
    LLMTimeoutError,
    LLMTransientError,
    LLMPermanentError,
    LLMValidationError,
)

router = APIRouter()

def get_llm_client() -> LLMClient:
    return LLMClient()

@router.post(
    "/normalize",
    response_model=NormalizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Normalize a messy job title into a canonical software engineering title."
)
async def normalize_job_title(
    request: NormalizeRequest,
    llm_client: LLMClient = Depends(get_llm_client)
):
    try:
        response = await llm_client.normalize_job_title(request.text)
        return response
    except LLMDisabledError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except LLMTimeoutError as e:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(e)
        )
    except LLMValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except LLMTransientError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except LLMPermanentError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
