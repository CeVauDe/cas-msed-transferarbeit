"""MCP server v2 entrypoint — simplified Jahresbericht data access via pandas."""

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP

from mcp_server_v2.glossary import GLOSSARY_MD

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type Transport = Literal["stdio", "sse", "streamable-http"]


def _build_server() -> FastMCP:
    host = os.environ.get("MCP_SERVER_V2_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_SERVER_V2_PORT", "8081"))
    log_level: LogLevel = os.environ.get("MCP_SERVER_V2_LOG_LEVEL", "INFO")  # type: ignore[assignment]

    server = FastMCP(
        name="jahresbericht-mcp-server-v2",
        host=host,
        port=port,
        log_level=log_level,
    )

    @server.tool(
        name="abfrage_jahresbericht",
        description=(
            "Abfrage des Mediapulse TV-Jahresberichts. "
            "Gibt eine Markdown-Tabelle mit TV-Zuschauerdaten zurück "
            "(Ratings, Marktanteile, Reichweiten, Sehdauer) für Schweizer TV-Sender. "
            "Verwende dieses Tool, wenn nach TV-Zuschauerdaten, Einschaltquoten, "
            "Marktanteilen oder Sehverhalten gefragt wird. "
            "Unterstützt Filterung nach Jahr, Region, Zeitschiene, Kenngrösse und Sender. "
            "Gibt Rohdaten zurück — es wird keine Aggregation durchgeführt."
        ),
    )
    def abfrage_jahresbericht() -> str:
        return "Not yet implemented"

    @server.resource(
        uri="glossar://mediapulse",
        name="Glossar",
        description=(
            "Fachbegriffe der TV-Forschung "
            "(Zeitschiene, Rating, Marktanteil, Sehdauer, "
            "Verweildauer, Nettoreichweite)."
        ),
    )
    def glossar() -> str:
        return GLOSSARY_MD

    return server


def run_server() -> None:
    transport: Transport = os.environ.get("MCP_SERVER_V2_TRANSPORT", "streamable-http")  # type: ignore[assignment]
    server = _build_server()
    server.run(transport=transport)


def main() -> None:
    run_server()


if __name__ == "__main__":
    main()
