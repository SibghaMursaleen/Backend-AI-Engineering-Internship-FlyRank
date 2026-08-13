import os
import time
import json
import random
import logging
import asyncio
import uuid
from datetime import datetime, timezone
import httpx
from pydantic import ValidationError

from src.config import settings
from src.schemas import NormalizeResponse, CanonicalTitleEnum, SeniorityLevelEnum
from src.llm.exceptions import (
    LLMDisabledError,
    LLMTimeoutError,
    LLMTransientError,
    LLMPermanentError,
    LLMValidationError,
)

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.enabled = settings.llm_enabled
        self.stub = settings.llm_stub
        self.model = settings.openrouter_model
        self.timeout = settings.openrouter_timeout
        self.api_key = settings.openrouter_api_key

        # Resolve prompt file path relative to workspace
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.prompt_path = os.path.join(base_dir, "prompts", "normalize-v1.md")
        self._prompt_content = None

    def load_prompt(self) -> str:
        """Loads and caches the versioned system prompt."""
        if self._prompt_content is not None:
            return self._prompt_content

        try:
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                self._prompt_content = f.read()
            return self._prompt_content
        except FileNotFoundError as e:
            logger.error(f"Prompt template not found at {self.prompt_path}")
            raise LLMPermanentError(f"Prompt template missing: {e}")
        except Exception as e:
            logger.error(f"Error reading prompt template: {e}")
            raise LLMPermanentError(f"Failed to load prompt template: {e}")

    async def normalize_job_title(self, text: str) -> NormalizeResponse:
        """
        Normalizes a job title. Supports stub mode, kill switch, and real OpenRouter calls
        with validation, exponential backoff retries, and a single repair attempt.
        """
        if not self.enabled:
            logger.warning("LLM call attempted but LLM is disabled via LLM_ENABLED=false")
            raise LLMDisabledError("LLM normalizer is disabled.")

        if self.stub:
            logger.info(f"Using deterministic LLM Stub for input: {text}")
            return self._get_stub_response(text)

        if not self.api_key or "your_openrouter_api_key" in self.api_key:
            raise LLMPermanentError("OPENROUTER_API_KEY environment variable is not configured.")

        system_prompt = self.load_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        # First request attempt
        content_str, retries = await self._execute_llm_request(messages)

        # Parse & Validate initial response
        try:
            parsed_json = json.loads(content_str)
            return NormalizeResponse(**parsed_json)
        except (json.JSONDecodeError, ValidationError) as initial_error:
            logger.warning(
                f"Initial validation failed for input '{text}' (Error: {initial_error}). "
                f"Triggering exactly one repair attempt..."
            )
            
            # Construct conversational repair instructions
            repair_instruction = (
                f"Your previous response failed validation with the following error:\n"
                f"{str(initial_error)}\n\n"
                f"Please correct the response and return a valid JSON object matching the requested schema. "
                f"Ensure all required fields exist and use only the allowed values. Return ONLY raw JSON."
            )
            repair_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
                {"role": "assistant", "content": content_str},
                {"role": "user", "content": repair_instruction}
            ]

            # Exactly ONE repair request
            repair_content_str, repair_retries = await self._execute_llm_request(repair_messages)

            # Validate the repair response
            try:
                parsed_repair_json = json.loads(repair_content_str)
                return NormalizeResponse(**parsed_repair_json)
            except (json.JSONDecodeError, ValidationError) as repair_error:
                logger.error(f"Repair attempt failed validation: {repair_error}")
                # Quarantine the failed attempt sequence for debugging
                self._quarantine_invalid_response(
                    text=text,
                    initial_response=content_str,
                    initial_error=initial_error,
                    repair_response=repair_content_str,
                    repair_error=repair_error
                )
                raise LLMValidationError(
                    f"LLM normalization failed validation after repair. "
                    f"Original validation error: {initial_error}. "
                    f"Repair validation error: {repair_error}"
                )

    async def _execute_llm_request(self, messages: list) -> tuple[str, int]:
        """
        Executes an HTTP request to OpenRouter with a transient retry policy,
        explicit timeout, and logging. Returns a tuple of (response_content, retry_count).
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Job Title Normalizer API",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 1000
        }

        url = "https://openrouter.ai/api/v1/chat/completions"
        max_retries = 3
        base_delay = 1.0
        max_delay = 10.0

        for attempt in range(max_retries + 1):
            start_time = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.info(f"Sending LLM request to OpenRouter (attempt {attempt + 1}/{max_retries + 1})")
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()

                # Request succeeded, parse and calculate stats
                latency = time.perf_counter() - start_time
                response_json = response.json()
                
                # Retrieve token usage
                usage = response_json.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)

                # Estimate cost for gemini-2.5-flash
                cost = 0.0
                if "gemini-2.5-flash" in self.model.lower():
                    cost = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)

                logger.info(
                    f"LLM Request Succeeded | Model: {self.model} | Latency: {latency:.2f}s | "
                    f"Tokens: {total_tokens} (P: {prompt_tokens}, C: {completion_tokens}) | "
                    f"Est. Cost: ${cost:.6f} | Retry Count: {attempt}"
                )

                choices = response_json.get("choices", [])
                if not choices:
                    logger.error("OpenRouter response did not contain 'choices'")
                    raise LLMValidationError("Empty LLM choice output")

                content_str = choices[0].get("message", {}).get("content", "").strip()
                return content_str, attempt

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                latency = time.perf_counter() - start_time
                logger.warning(f"Network/Timeout error on attempt {attempt + 1} ({latency:.2f}s): {e}")
                
                if attempt == max_retries:
                    logger.error("Max retries exceeded for transient network/timeout errors")
                    raise LLMTimeoutError(f"LLM call timed out: {e}") from e

                # Bounded exponential backoff with jitter
                backoff = min(max_delay, base_delay * (2 ** attempt))
                sleep_time = backoff * random.uniform(0.5, 1.5)
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                await asyncio.sleep(sleep_time)

            except httpx.HTTPStatusError as e:
                latency = time.perf_counter() - start_time
                status_code = e.response.status_code
                logger.warning(f"HTTP error {status_code} on attempt {attempt + 1} ({latency:.2f}s)")

                if status_code in (429, 500, 502, 503, 504):
                    if attempt == max_retries:
                        logger.error(f"Max retries exceeded for transient HTTP {status_code}")
                        raise LLMTransientError(f"Transient HTTP error: {status_code}") from e

                    # Check for Retry-After header specifically for HTTP 429
                    sleep_time = None
                    if status_code == 429:
                        retry_after = e.response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                sleep_time = float(retry_after)
                                logger.info(f"Respecting Retry-After header. Waiting {sleep_time:.2f} seconds...")
                                sleep_time = min(sleep_time, max_delay)
                            except ValueError:
                                pass

                    if sleep_time is None:
                        # Bounded exponential backoff with jitter
                        backoff = min(max_delay, base_delay * (2 ** attempt))
                        sleep_time = backoff * random.uniform(0.5, 1.5)

                    logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                    await asyncio.sleep(sleep_time)
                else:
                    # Non-retryable HTTP errors (400, 401, 403, etc.)
                    logger.error(f"Permanent HTTP error {status_code}: {e.response.text}")
                    raise LLMPermanentError(f"Permanent error: {status_code} - {e.response.text}") from e

            except Exception as e:
                if isinstance(e, (LLMValidationError, LLMTimeoutError, LLMTransientError, LLMPermanentError, LLMDisabledError)):
                    raise e
                logger.error(f"Unexpected error in LLM client request: {e}")
                raise LLMPermanentError(f"Unexpected error: {e}") from e

    def _quarantine_invalid_response(self, text: str, initial_response: str, initial_error: Exception, repair_response: str, repair_error: Exception):
        """Saves detailed debugging info about a failed validation sequence to the quarantine/ folder."""
        # Resolve workspace directory
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        quarantine_dir = os.path.join(base_dir, "quarantine")
        
        try:
            os.makedirs(quarantine_dir, exist_ok=True)
            quarantine_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "input_text": text,
                "initial_response": initial_response,
                "initial_error": str(initial_error),
                "repair_response": repair_response,
                "repair_error": str(repair_error),
                "model": self.model
            }
            
            file_path = os.path.join(quarantine_dir, f"failed_{uuid.uuid4().hex}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(quarantine_data, f, indent=2)
            logger.error(f"Failed validation flow quarantined successfully to: {file_path}")
        except Exception as e:
            logger.error(f"Error executing quarantine sequence: {e}")

    def _get_stub_response(self, text: str) -> NormalizeResponse:
        text_lower = text.lower()
        if "backend developer" in text_lower:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.BACKEND_ENGINEER,
                level=SeniorityLevelEnum.MID,
                confidence=0.95,
                reason="[STUB] Matches Mid Backend Engineer."
            )
        elif "sr. swe ii" in text_lower or "senior software" in text_lower:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.SOFTWARE_ENGINEER,
                level=SeniorityLevelEnum.SENIOR,
                confidence=0.98,
                reason="[STUB] Matches Senior Software Engineer."
            )
        elif "junior python" in text_lower:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.SOFTWARE_ENGINEER,
                level=SeniorityLevelEnum.JUNIOR,
                confidence=0.92,
                reason="[STUB] Matches Junior Software Engineer."
            )
        elif "intern" in text_lower:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.SOFTWARE_ENGINEER,
                level=SeniorityLevelEnum.INTERN,
                confidence=0.99,
                reason="[STUB] Matches Software Engineering Intern."
            )
        elif "lead ml" in text_lower:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.ML_ENGINEER,
                level=SeniorityLevelEnum.LEAD,
                confidence=0.96,
                reason="[STUB] Matches Lead ML Engineer."
            )
        elif "unsure" in text_lower or "ninja" in text_lower:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.OTHER,
                level=SeniorityLevelEnum.UNKNOWN,
                confidence=0.20,
                reason="[STUB] Highly ambiguous title, returning Other/unknown."
            )
        else:
            return NormalizeResponse(
                canonical_title=CanonicalTitleEnum.SOFTWARE_ENGINEER,
                level=SeniorityLevelEnum.MID,
                confidence=0.85,
                reason="[STUB] Default deterministic software engineering response."
            )
