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
from mcp.types import TextContent, TextResourceContents
from pydantic import AnyUrl
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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_list_tools_returns_expected_tools(mcp_url):
    """The server should expose exactly 1 tool with a descriptive name."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.list_tools()

        tool_names = {t.name for t in result.tools}
        assert len(result.tools) == 1, f"Expected 1 tool, got {len(result.tools)}: {tool_names}"
        assert "abfrage_jahresbericht" in tool_names

        tool = result.tools[0]
        assert tool.description, f"Tool {tool.name!r} has no description"
        assert len(tool.description) > 20, (
            f"Tool {tool.name!r} description too short: {tool.description!r}"
        )


@pytest.mark.integration
async def test_glossar_resource_returns_domain_terms(mcp_url):
    """The glossar resource should return markdown explaining domain terms."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        # Verify resource is listed
        resources = await session.list_resources()
        uris = {str(r.uri) for r in resources.resources}
        assert "glossar://mediapulse" in uris

        # Read the resource
        result = await session.read_resource(AnyUrl("glossar://mediapulse"))
        assert len(result.contents) == 1
        content = result.contents[0]
        assert isinstance(content, TextResourceContents)
        text = content.text

        # Must contain glossary term explanations
        for term in [
            "Zeitschiene",
            "Verweildauer",
            "Sehdauer",
            "Rating",
            "Nettoreichweite",
            "Marktanteil",
            "Fact",
        ]:
            assert term in text, f"Missing glossary term {term!r}"

        # Must NOT contain usage instructions for the query tool
        assert "abfrage_jahresbericht" not in text.lower(), (
            "Glossary should not contain usage instructions for the query tool"
        )


@pytest.mark.integration
async def test_query_data_returns_markdown_table(mcp_url):
    """The query tool should return a markdown table with filtered data."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "jahr": [2020],
                "region": ["Deutschschweiz"],
                "kenngroesse": ["Rating in 1'000"],
                "zeitschiene": ["Ganzer Tag"],
            },
        )

        assert len(result.content) == 1
        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text

        # Must be a markdown table
        lines = text.strip().splitlines()
        assert any("|" in line for line in lines), "No markdown table found"
        assert any("---" in line for line in lines), "No header separator found"

        # Must contain expected columns
        header = lines[0]
        assert "Sender" in header
        assert "Wert" in header


@pytest.mark.integration
async def test_query_data_filter_by_sender(mcp_url):
    """Filtering by sender should return only rows for that sender."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "jahr": [2020],
                "region": ["Deutschschweiz"],
                "kenngroesse": ["Rating in 1'000"],
                "zeitschiene": ["Ganzer Tag"],
                "sender": ["SRF 1"],
            },
        )

        assert len(result.content) == 1
        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text

        # Parse data rows (skip header and separator)
        lines = text.strip().splitlines()
        data_rows = [line for line in lines[2:] if line.strip()]
        assert len(data_rows) >= 1, "Expected at least one data row"

        for row in data_rows:
            assert "SRF 1" in row, f"Row does not contain 'SRF 1': {row}"


@pytest.mark.integration
async def test_query_data_select_columns(mcp_url):
    """Requesting specific columns should return only those columns."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "jahr": [2020],
                "region": ["Deutschschweiz"],
                "kenngroesse": ["Rating in 1'000"],
                "zeitschiene": ["Ganzer Tag"],
                "spalten": ["Sender", "Wert"],
            },
        )

        assert len(result.content) == 1
        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text

        header = text.strip().splitlines()[0]
        columns = [c.strip() for c in header.split("|") if c.strip()]
        assert columns == ["Sender", "Wert"], f"Expected ['Sender', 'Wert'], got {columns}"


def _count_data_rows(markdown_table: str) -> int:
    """Count data rows in a markdown table (excludes header and separator)."""
    lines = markdown_table.strip().splitlines()
    return len([line for line in lines[2:] if line.strip()])


@pytest.mark.integration
async def test_query_data_respects_default_limit(mcp_url):
    """Broad query without explicit limit should return at most 20 rows."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "jahr": [2020],
                "region": ["Deutschschweiz"],
                "kenngroesse": ["Rating in 1'000"],
            },
        )

        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text
        assert _count_data_rows(text) <= 20


@pytest.mark.integration
async def test_query_data_respects_custom_limit(mcp_url):
    """Explicit limit parameter should cap the number of rows."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "jahr": [2020],
                "region": ["Deutschschweiz"],
                "kenngroesse": ["Rating in 1'000"],
                "limit": 5,
            },
        )

        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text
        assert _count_data_rows(text) == 5


@pytest.mark.integration
async def test_query_data_limit_capped_at_200(mcp_url):
    """Requesting more than 200 rows should still cap at 200."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "jahr": [2020],
                "region": ["Deutschschweiz"],
                "limit": 999,
            },
        )

        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text
        assert _count_data_rows(text) <= 200


@pytest.mark.integration
async def test_query_data_pivot_table(mcp_url):
    """Pivot mode should return Sender as rows and Jahr as columns."""
    async with (
        streamable_http_client(mcp_url) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.call_tool(
            "abfrage_jahresbericht",
            {
                "region": ["Deutschschweiz"],
                "kenngroesse": ["Marktanteil in %"],
                "zeitschiene": ["Ganzer Tag"],
                "sender": ["SRF 1", "SRF zwei"],
                "zeilen": "Sender",
                "spalten_pivot": "Jahr",
            },
        )

        assert len(result.content) == 1
        content = result.content[0]
        assert isinstance(content, TextContent)
        text = content.text

        lines = text.strip().splitlines()
        header = lines[0]

        # Header should contain year columns
        assert "2018" in header
        assert "2021" in header

        # Header should contain Sender (row index)
        assert "Sender" in header

        # Header should NOT contain filter columns (they are fixed)
        assert "Region" not in header
        assert "Kenngrösse" not in header

        # Should have exactly 2 data rows (SRF 1 and SRF zwei)
        data_rows = [line for line in lines[2:] if line.strip()]
        assert len(data_rows) == 2

        row_text = "\n".join(data_rows)
        assert "SRF 1" in row_text
        assert "SRF zwei" in row_text
