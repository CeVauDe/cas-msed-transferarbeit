"""Tests for logging configuration."""

from __future__ import annotations

import logging

from mcp_server.logging import configure_logging, get_logger


class TestLoggingConfiguration:
    """Test logging configuration and setup."""

    def test_configure_logging_sets_level(self):
        configure_logging(log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        configure_logging(log_level="WARNING")
        assert root.level == logging.WARNING

        # Reset to INFO for other tests
        configure_logging(log_level="INFO")

    def test_get_logger_returns_stdlib_logger(self):
        log = get_logger("test")
        assert isinstance(log, logging.Logger)
        assert log.name == "test"

    def test_get_logger_without_name(self):
        log = get_logger()
        assert isinstance(log, logging.Logger)


class TestLogLevels:
    """Test that different log levels work correctly."""

    def test_debug_level(self, caplog):
        log = get_logger("test.levels")
        with caplog.at_level(logging.DEBUG, logger="test.levels"):
            log.debug("debug message: detail=%s", "verbose")
        assert "debug message: detail=verbose" in caplog.text

    def test_info_level(self, caplog):
        log = get_logger("test.levels")
        with caplog.at_level(logging.INFO):
            log.info("info message")
        assert "info message" in caplog.text

    def test_warning_level(self, caplog):
        log = get_logger("test.levels")
        with caplog.at_level(logging.WARNING):
            log.warning("warning message")
        assert "warning message" in caplog.text

    def test_error_level(self, caplog):
        log = get_logger("test.levels")
        with caplog.at_level(logging.ERROR):
            log.error("error message: code=%s", "TEST_ERROR")
        assert "error message: code=TEST_ERROR" in caplog.text


class TestExceptionLogging:
    """Test exception logging."""

    def test_exception_info_captured(self, caplog):
        log = get_logger("test.exception")
        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test exception")
            except ValueError:
                log.error("exception occurred", exc_info=True)

        assert "exception occurred" in caplog.text
        assert "ValueError" in caplog.text
        assert "Test exception" in caplog.text
