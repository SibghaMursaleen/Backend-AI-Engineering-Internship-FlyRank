import logging
from inngest import Inngest
from openai import OpenAI
from app.core.config import settings

# Configure logging
logger = logging.getLogger("uvicorn")

# Initialize Inngest client
inngest_client = Inngest(
    app_id="ai_decision_flow",
    logger=logger
)

# Initialize OpenAI client
openai_client = OpenAI(
    api_key=settings.OPENAI_API_KEY
)
