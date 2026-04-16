"""Domain-specific exceptions for mail providers."""


class MailError(Exception):
    """Base exception for mail related failures."""


class MailProviderUnavailableError(MailError):
    """Raised when a mail provider is not configured or unavailable."""


class MailRateLimitError(MailError):
    """Raised when a mail provider rate-limits a request."""
