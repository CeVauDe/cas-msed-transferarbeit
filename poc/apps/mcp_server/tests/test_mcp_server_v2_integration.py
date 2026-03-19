"""Integration tests for MCP Server v2 using testcontainers.

These tests build and run the mcp_server_v2 Docker container, connect via
MCP streamable-http, and verify the server's tool responses.
"""

import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from testcontainers.core.container import DockerContainer

_DESKTOP_SOCK = Path.home() / ".docker" / "desktop" / "docker.sock"
if _DESKTOP_SOCK.exists():
    os.environ.setdefault("DOCKER_HOST", f"unix://{_DESKTOP_SOCK}")
    os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", str(_DESKTOP_SOCK))

# Disable Ryuk reaper — we handle cleanup ourselves in fixture teardown.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# poc/ directory — Docker build context
_POC_DIR = Path(__file__).resolve().parents[3]
_DOCKERFILE = "docker/mcp_server_v2/Dockerfile"
_SRC_DIR = str(_POC_DIR / "apps" / "mcp_server" / "src")

_IMAGE_TAG = "mcp-server-v2-test:latest"
_CONTAINER_PORT = 8081


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def mcp_image():
    """Build the mcp_server_v2 Docker image once per test module using the docker CLI."""
    subprocess.run(
        ["docker", "build", "-t", _IMAGE_TAG, "-f", _DOCKERFILE, "."],
        cwd=str(_POC_DIR),
        check=True,
    )
    yield _IMAGE_TAG


@pytest.fixture(scope="module")
def mcp_container(mcp_image):
    """Start the mcp_server_v2 container with source mounted."""
    container = DockerContainer(mcp_image)
    container.with_exposed_ports(_CONTAINER_PORT)
    container.with_volume_mapping(_SRC_DIR, "/app/apps/mcp_server/src", mode="ro")
    container.with_env("MCP_SERVER_V2_PORT", str(_CONTAINER_PORT))
    container.with_env("MCP_SERVER_V2_HOST", "0.0.0.0")
    container.with_env("MCP_SERVER_V2_TRANSPORT", "streamable-http")
    container.with_env(
        "MCP_DATA_V2_PARQUET_PATH",
        "/app/apps/mcp_server/data/Jahresbericht_v2.parquet",
    )
    container.start()
    yield container
    container.stop()


def _wait_for_http(url: str, timeout: float = 30.0) -> None:
    """Block until the MCP endpoint responds to HTTP POST (returns non-connection-error)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx.post(url, json={}, timeout=2)
            # Any HTTP response (even 4xx) means the server is up.
            return
        except httpx.HTTPError:
            time.sleep(0.5)
    raise TimeoutError(f"Server at {url} not ready after {timeout}s")


@pytest.fixture(scope="module")
def mcp_url(mcp_container):
    """Return the MCP server URL for the running container."""
    host = mcp_container.get_container_host_ip()
    port = mcp_container.get_exposed_port(_CONTAINER_PORT)
    url = f"http://{host}:{port}/mcp"
    _wait_for_http(url)
    return url


# ---------------------------------------------------------------------------
# Iteration 1: Server starts and exposes tools
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_tools_returns_expected_tools(mcp_url):
    """The server should expose exactly 2 tools with descriptive names."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.list_tools()

        tool_names = {t.name for t in result.tools}
        assert len(result.tools) == 2, f"Expected 2 tools, got {len(result.tools)}: {tool_names}"

        # Both tools should have non-empty descriptions
        for tool in result.tools:
            assert tool.description, f"Tool {tool.name!r} has no description"
            assert len(tool.description) > 20, (
                f"Tool {tool.name!r} description too short: {tool.description!r}"
            )
