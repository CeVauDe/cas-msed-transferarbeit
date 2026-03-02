"""Tests for structured logging configuration."""

from __future__ import annotations

import json
import logging

import structlog
from structlog.testing import CapturingLogger

from mcp_server.logging import bind_request_context, configure_logging, get_logger


class TestLoggingConfiguration:
    """Test logging configuration and setup."""

    def test_configure_logging_sets_level(self):
        """Test that configure_logging works with different log levels."""
        # Test that configure_logging doesn't raise exceptions
        configure_logging(log_level="DEBUG")
        log = get_logger("test_debug")
        # Should be able to call debug
        log.debug("debug_message")

        configure_logging(log_level="WARNING")
        log = get_logger("test_warning")
        # Should be able to call warning
        log.warning("warning_message")

        # Reset to INFO for other tests
        configure_logging(log_level="INFO")

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        log = get_logger("test")
        # get_logger returns a lazy proxy or bound logger
        assert hasattr(log, "bind")
        assert hasattr(log, "info")
        assert hasattr(log, "error")

    def test_get_logger_without_name(self):
        """Test that get_logger works without a name parameter."""
        log = get_logger()
        assert hasattr(log, "bind")
        assert hasattr(log, "info")


class TestContextBinding:
    """Test context binding functionality."""

    def setup_method(self):
        """Set up capturing logger for each test."""
        self.cap_logger = CapturingLogger()
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
            ],
            logger_factory=lambda *_args: self.cap_logger,
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )

    def teardown_method(self):
        """Reset structlog configuration after each test."""
        # Reconfigure to default
        configure_logging()

    def test_bind_request_context_basic(self):
        """Test basic request context binding with request_id."""
        log = get_logger("test")
        log = bind_request_context(log, request_id="test-123")
        log.info("test_event", foo="bar")

        assert len(self.cap_logger.calls) == 1
        call = self.cap_logger.calls[0]
        assert call.method_name == "info"
        assert call.kwargs["event"] == "test_event"
        assert call.kwargs["request_id"] == "test-123"
        assert call.kwargs["foo"] == "bar"

    def test_bind_request_context_with_trace_ids(self):
        """Test binding request context with trace_id and span_id."""
        log = get_logger("test")
        log = bind_request_context(
            log, request_id="req-456", trace_id="trace-abc", span_id="span-xyz"
        )
        log.info("traced_event")

        assert len(self.cap_logger.calls) == 1
        call = self.cap_logger.calls[0]
        assert call.kwargs["request_id"] == "req-456"
        assert call.kwargs["trace_id"] == "trace-abc"
        assert call.kwargs["span_id"] == "span-xyz"

    def test_bind_request_context_without_optional_ids(self):
        """Test that trace_id and span_id are optional."""
        log = get_logger("test")
        log = bind_request_context(log, request_id="req-789")
        log.info("simple_event")

        call = self.cap_logger.calls[0]
        assert call.kwargs["request_id"] == "req-789"
        assert "trace_id" not in call.kwargs
        assert "span_id" not in call.kwargs

    def test_bind_request_context_with_extra_context(self):
        """Test binding additional context fields."""
        log = get_logger("test")
        log = bind_request_context(log, request_id="req-999", user_id=42, session_id="sess-abc")
        log.info("enriched_event")

        call = self.cap_logger.calls[0]
        assert call.kwargs["request_id"] == "req-999"
        assert call.kwargs["user_id"] == 42
        assert call.kwargs["session_id"] == "sess-abc"

    def test_context_persists_across_log_calls(self):
        """Test that bound context persists across multiple log calls."""
        log = get_logger("test")
        log = bind_request_context(log, request_id="persistent-123")

        log.info("first_event")
        log.info("second_event")
        log.warning("third_event")

        assert len(self.cap_logger.calls) == 3
        for call in self.cap_logger.calls:
            assert call.kwargs["request_id"] == "persistent-123"


class TestLogLevels:
    """Test different log levels."""

    def setup_method(self):
        """Set up capturing logger for each test."""
        self.cap_logger = CapturingLogger()
        structlog.configure(
            processors=[structlog.stdlib.add_log_level],
            logger_factory=lambda *_args: self.cap_logger,
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=False,
        )

    def teardown_method(self):
        """Reset structlog configuration after each test."""
        configure_logging()

    def test_debug_level(self):
        """Test debug level logging."""
        log = get_logger("test")
        log.debug("debug_message", detail="verbose")

        call = self.cap_logger.calls[0]
        assert call.method_name == "debug"
        assert call.kwargs["level"] == "debug"

    def test_info_level(self):
        """Test info level logging."""
        log = get_logger("test")
        log.info("info_message")

        call = self.cap_logger.calls[0]
        assert call.method_name == "info"
        assert call.kwargs["level"] == "info"

    def test_warning_level(self):
        """Test warning level logging."""
        log = get_logger("test")
        log.warning("warning_message")

        call = self.cap_logger.calls[0]
        assert call.method_name == "warning"
        assert call.kwargs["level"] == "warning"

    def test_error_level(self):
        """Test error level logging."""
        log = get_logger("test")
        log.error("error_message", error_code="TEST_ERROR")

        call = self.cap_logger.calls[0]
        assert call.method_name == "error"
        assert call.kwargs["level"] == "error"
        assert call.kwargs["error_code"] == "TEST_ERROR"


class TestJSONOutput:
    """Test JSON output format."""

    def test_json_output_structure(self, caplog):
        """Test that logs are output as valid JSON."""
        configure_logging()
        log = get_logger("test.json")
        log = bind_request_context(log, request_id="json-test")

        with caplog.at_level(logging.INFO):
            log.info("test_json_event", field1="value1", field2=42)

        # The message should be JSON
        assert len(caplog.records) > 0
        log_message = caplog.records[0].getMessage()

        # Parse as JSON
        log_data = json.loads(log_message)

        # Verify structure
        assert log_data["event"] == "test_json_event"
        assert log_data["request_id"] == "json-test"
        assert log_data["field1"] == "value1"
        assert log_data["field2"] == 42
        assert log_data["level"] == "info"
        assert "timestamp" in log_data

    def test_json_handles_complex_types(self, caplog):
        """Test that JSON renderer handles complex types."""
        configure_logging()
        log = get_logger("test.complex")

        with caplog.at_level(logging.INFO):
            log.info(
                "complex_event",
                list_field=[1, 2, 3],
                dict_field={"nested": "value"},
                none_field=None,
            )

        log_message = caplog.records[0].getMessage()
        log_data = json.loads(log_message)

        assert log_data["list_field"] == [1, 2, 3]
        assert log_data["dict_field"] == {"nested": "value"}
        assert log_data["none_field"] is None


class TestExceptionLogging:
    """Test exception logging."""

    def test_exception_info_captured(self, caplog):
        """Test that exception information is captured in logs."""
        configure_logging()
        log = get_logger("test.exception")

        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("Test exception")
            except ValueError:
                log.error("exception_occurred", exc_info=True)

        log_message = caplog.records[0].getMessage()
        log_data = json.loads(log_message)

        assert log_data["event"] == "exception_occurred"
        assert "exception" in log_data
        assert "ValueError" in log_data["exception"]
        assert "Test exception" in log_data["exception"]
