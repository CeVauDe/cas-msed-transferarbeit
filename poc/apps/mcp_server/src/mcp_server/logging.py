"""Logging configuration using Python standard library.

This module provides a configured logger for the MCP server.
Logs are output as plain text to stdout for easy console reading.
"""

from __future__ import annotations

import logging
import sys


def configure_logging(log_level: str = "INFO") -> None:
    """Configure logging with a human-readable output format.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
        force=True,
    )


def get_logger(name: str | None = None) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Optional logger name. If None, returns the root logger.

    Returns:
        A configured Logger instance

    Example:
        >>> log = get_logger(__name__)
        >>> log.info("request received for tool=%s", "query_data")
    """
    return logging.getLogger(name)


# Configure logging on module import with default settings
# This can be reconfigured later by calling configure_logging() directly
configure_logging()
