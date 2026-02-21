"""Structured logging configuration for Team Assistant."""

import json
import logging
import logging.config
import logging.handlers
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import DEFAULT_LOG_PATH


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra context if present
        if hasattr(record, "context"):
            log_data["context"] = record.context

        return json.dumps(log_data)


def setup_logging(
    log_level: str | None = None,
    log_file: str | None = None,
) -> None:
    """
    Setup structured logging for the application.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
                   Defaults to LOG_LEVEL env var or INFO.
        log_file: Path to log file. Defaults to 04_logs/app.log.
    """
    # Determine log level
    if log_level is None:
        log_level = os.getenv("LOG_LEVEL", "INFO")

    # Determine log file path
    if log_file is None:
        log_file = str(DEFAULT_LOG_PATH)

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "core.logging_config.JSONFormatter",
            },
        },
        "handlers": {
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file,
                "maxBytes": 10 * 1024 * 1024,  # 10 MB
                "backupCount": 5,
                "formatter": "json",
                "encoding": "utf-8",
            },
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": log_level.upper(),
            "handlers": ["file", "console"],
        },
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
