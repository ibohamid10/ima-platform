"""Domain-specific exceptions for agent execution."""


class AgentExecutionError(Exception):
    """Base exception for agent execution failures."""


class AgentInputValidationError(AgentExecutionError):
    """Raised when agent inputs do not match the declared input schema."""


class AgentProviderSelectionError(AgentExecutionError):
    """Raised when no configured provider can serve the requested models."""
