"""Logging setup for local development and production-style JSON logs."""

from __future__ import annotations

import logging
from typing import Any

import structlog

SENSITIVE_KEYS = {"prompt", "body", "email", "content"}
_CONFIGURED = False


def _truncate_sensitive_fields(
    _logger: logging.Logger,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Truncate sensitive string fields at INFO level and above."""

    if logging.getLogger().level <= logging.DEBUG:
        return event_dict

    for key, value in list(event_dict.items()):
        if key.lower() in SENSITIVE_KEYS and isinstance(value, str) and len(value) > 200:
            event_dict[key] = f"{value[:200]}...[truncated]"
    return event_dict


def configure_logging(level: str = "INFO", log_format: str = "dev") -> None:
    """Configure stdlib logging and structlog once per process."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _truncate_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = (
        structlog.processors.JSONRenderer()
        if log_format == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=log_level, format="%(message)s")
    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""

    from ima.config import settings

    configure_logging(settings.log_level, settings.log_format)
    return structlog.get_logger(name)
