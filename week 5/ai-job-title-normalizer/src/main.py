import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from src.config import settings
from src.routes.normalize import router as normalize_router

# Configure logging
logging.basicConfig(
    level=logging.getLevelName(settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Job Title Normalizer API",
    description="Normalize messy job titles into canonical software engineering roles and levels.",
    version="1.0.0"
)

# Custom handler to override the default 422 Unprocessable Entity with a 400 Bad Request
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Request validation failed: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": "Invalid input schema.",
            "errors": exc.errors()
        }
    )

# Include routes
app.include_router(normalize_router)

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "ok", "stub_mode": settings.llm_stub, "llm_enabled": settings.llm_enabled}
