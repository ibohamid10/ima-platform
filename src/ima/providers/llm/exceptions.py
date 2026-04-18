"""Domain-specific exceptions for LLM providers."""


class LLMError(Exception):
    """Base exception for LLM related failures."""


class LLMRateLimitError(LLMError):
    """Raised when an LLM provider returns a rate-limit response."""


class LLMInvalidResponseError(LLMError):
    """Raised when a provider response cannot be parsed safely."""


class LLMSchemaValidationError(LLMError):
    """Raised when a structured response does not match the contract schema."""


class LLMSchemaValidationAttemptsError(LLMSchemaValidationError):
    """Raised when schema validation fails after a known number of attempts."""

    def __init__(self, message: str, attempts: int) -> None:
        """Create a schema-validation error that carries the true attempt count."""

        super().__init__(message)
        self.attempts = attempts


class LLMBudgetExceededError(LLMError):
    """Raised when the configured daily LLM budget is exhausted."""


class LLMProviderUnavailableError(LLMError):
    """Raised when a provider is unavailable or misconfigured."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Create an unavailable-provider error with optional HTTP status metadata."""

        super().__init__(message)
        self.status_code = status_code
