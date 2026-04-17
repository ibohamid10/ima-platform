"""Domain-specific exceptions for creator source harvesting."""


class SourceHarvesterError(Exception):
    """Base exception for source harvesting failures."""


class YouTubeConfigurationError(SourceHarvesterError):
    """Raised when the YouTube harvester is missing required configuration."""


class YouTubeDataAPIError(SourceHarvesterError):
    """Raised when the YouTube Data API returns an unexpected response."""


class YouTubeChannelNotFoundError(YouTubeDataAPIError):
    """Raised when a requested YouTube channel cannot be resolved."""


class YouTubeQuotaExceededError(YouTubeDataAPIError):
    """Raised when the YouTube API quota or rate limit is exhausted."""
