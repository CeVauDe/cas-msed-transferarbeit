"""Tests for the main module."""

import pytest

from chatbot.main import greet


class TestGreet:
    """Tests for the greet function."""

    def test_greet_default(self) -> None:
        """Test greeting with default name."""
        result = greet()
        assert result == "Hello, World! Welcome to the MCP Chatbot PoC."

    def test_greet_custom_name(self) -> None:
        """Test greeting with custom name."""
        result = greet("Alice")
        assert result == "Hello, Alice! Welcome to the MCP Chatbot PoC."

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Bob", "Hello, Bob! Welcome to the MCP Chatbot PoC."),
            ("MCP Agent", "Hello, MCP Agent! Welcome to the MCP Chatbot PoC."),
        ],
    )
    def test_greet_parametrized(self, name: str, expected: str) -> None:
        """Test greeting with various names."""
        assert greet(name) == expected
