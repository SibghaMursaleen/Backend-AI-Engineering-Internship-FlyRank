class LLMError(Exception):
    """Base class for all LLM client exceptions."""
    pass

class LLMDisabledError(LLMError):
    """Raised when the LLM service is disabled via LLM_ENABLED=false."""
    pass

class LLMTimeoutError(LLMError):
    """Raised when the LLM call times out."""
    pass

class LLMTransientError(LLMError):
    """Raised for transient failures that can be retried (e.g., HTTP 429, 5xx)."""
    pass

class LLMPermanentError(LLMError):
    """Raised for permanent failures that should not be retried (e.g., HTTP 401, 403)."""
    pass

class LLMValidationError(LLMError):
    """Raised when the LLM output fails validation and cannot be repaired."""
    pass
