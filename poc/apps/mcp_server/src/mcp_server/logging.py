"""Structured logging configuration using structlog.

This module provides a configured structlog instance for the MCP server.
Logs are output as structured JSON to stdout with proper log levels and context binding.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON output and proper processors.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Configure standard library logging as the backend
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog processors
    structlog.configure(
        processors=[
            # Add the log level to the event dict
            structlog.stdlib.add_log_level,
            # Add logger name
            structlog.stdlib.add_logger_name,
            # Add timestamp in ISO format
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            # If exception info is present, format it
            structlog.processors.format_exc_info,
            # Render stack info if present
            structlog.processors.StackInfoRenderer(),
            # Render the final event dict as JSON
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        # Use dict for context
        context_class=dict,
        # Use standard library logging
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Use BoundLogger for better type hints and methods
        wrapper_class=structlog.stdlib.BoundLogger,
        # Cache loggers for better performance
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """Get a configured structlog logger instance.

    Args:
        name: Optional logger name. If None, uses the calling module's name.

    Returns:
        A configured structlog BoundLogger instance

    Example:
        >>> log = get_logger(__name__)
        >>> log.info("request_received", tool="query_data")
    """
    return structlog.get_logger(name)


def bind_request_context(
    logger: FilteringBoundLogger,
    request_id: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    **extra_context: Any,
) -> FilteringBoundLogger:
    """Bind request tracking context to a logger.

    Creates a new logger with the request context bound to it. All subsequent
    log calls on the returned logger will automatically include this context.

    Args:
        logger: The logger to bind context to
        request_id: Unique request identifier
        trace_id: Optional distributed tracing trace ID
        span_id: Optional distributed tracing span ID
        **extra_context: Additional context fields to bind

    Returns:
        A new logger instance with bound context

    Example:
        >>> log = get_logger(__name__)
        >>> log = bind_request_context(log, request_id="abc-123", trace_id="xyz")
        >>> log.info("validated")  # Will include request_id and trace_id
    """
    context = {"request_id": request_id}
    if trace_id is not None:
        context["trace_id"] = trace_id
    if span_id is not None:
        context["span_id"] = span_id
    context.update(extra_context)

    return logger.bind(**context)


# Configure logging on module import with default settings
# This can be reconfigured later by calling configure_logging() directly
configure_logging()
