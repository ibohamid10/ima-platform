"""Domain-specific exceptions for LLM providers."""


class LLMError(Exception):
    """Base exception for LLM related failures."""


class LLMRateLimitError(LLMError):
    """Raised when an LLM provider returns a rate-limit response."""


class LLMInvalidResponseError(LLMError):
    """Raised when a provider response cannot be parsed safely."""


class LLMSchemaValidationError(LLMError):
    """Raised when a structured response does not match the contract schema."""


class LLMBudgetExceededError(LLMError):
    """Raised when the configured daily LLM budget is exhausted."""


class LLMProviderUnavailableError(LLMError):
    """Raised when a provider is unavailable or misconfigured."""
