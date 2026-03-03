"""Tests for the MCP server module."""

from mcp_server.main import main, run_server


class TestMCPServer:
    """Tests for the MCP server."""

    def test_module_exists(self) -> None:
        """Test that the mcp_server module exists."""
        assert callable(run_server)
        assert callable(main)
