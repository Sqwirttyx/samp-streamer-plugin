"""Logging configuration."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, ensure_ascii=False)


class StandardFormatter(logging.Formatter):
    """Standard log formatter for development."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


def get_logger(
    name: str,
    level: Optional[str] = None,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Get or create a logger with the specified name.

    Args:
        name: Logger name (usually module name)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format type ('json' or 'standard')

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    # Import here to avoid circular imports
    try:
        from common.config import settings

        level = level or settings.log_level
        log_format = log_format or settings.log_format
    except Exception:
        level = level or "INFO"
        log_format = log_format or "standard"

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(StandardFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter for adding context to log messages."""

    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        extra = kwargs.get("extra", {})
        extra["extra_data"] = {**self.extra, **extra.get("extra_data", {})}
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(
    name: str,
    context: Dict[str, Any],
    level: Optional[str] = None,
    log_format: Optional[str] = None,
) -> LoggerAdapter:
    """
    Get a logger with context data attached.

    Args:
        name: Logger name
        context: Context data to include in all log messages
        level: Log level
        log_format: Format type

    Returns:
        Logger adapter with context
    """
    base_logger = get_logger(name, level, log_format)
    return LoggerAdapter(base_logger, context)
