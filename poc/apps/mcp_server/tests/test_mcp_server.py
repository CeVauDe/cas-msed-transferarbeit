"""Tests for the MCP server module."""

from mcp_server import main as mcp_main


class TestMCPServer:
    """Tests for the MCP server."""

    def test_module_exists(self) -> None:
        """Test that the mcp_server module exists."""
        assert hasattr(mcp_main, "run_server")
        assert hasattr(mcp_main, "main")
