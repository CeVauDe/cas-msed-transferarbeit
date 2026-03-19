"""MCP server v2 entrypoint — simplified Jahresbericht data access via pandas."""

import os
from typing import Literal

import pandas as pd
from mcp.server.fastmcp import FastMCP

from mcp_server_v2.glossary import GLOSSARY_MD

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type Transport = Literal["stdio", "sse", "streamable-http"]

_DEFAULT_PARQUET = "apps/mcp_server/data/Jahresbericht_v2.parquet"


def _load_dataframe() -> pd.DataFrame:
    path = os.environ.get("MCP_DATA_V2_PARQUET_PATH", _DEFAULT_PARQUET)
    return pd.read_parquet(path)


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

    df = _load_dataframe()

    @server.tool(
        name="abfrage_jahresbericht",
        description=(
            "Abfrage des Mediapulse TV-Jahresberichts. "
            "Gibt eine Markdown-Tabelle mit TV-Zuschauerdaten zurück "
            "(Ratings, Marktanteile, Reichweiten, Sehdauer) "
            "für Schweizer TV-Sender. "
            "Verwende dieses Tool, wenn nach TV-Zuschauerdaten, "
            "Einschaltquoten, Marktanteilen oder Sehverhalten "
            "gefragt wird. "
            "Unterstützt Filterung nach Jahr, Region, Zeitschiene, "
            "Kenngrösse und Sender. "
            "Gibt Rohdaten zurück — "
            "es wird keine Aggregation durchgeführt."
        ),
    )
    def abfrage_jahresbericht(
        jahr: list[int] | None = None,
        region: list[str] | None = None,
        zeitschiene: list[str] | None = None,
        kenngroesse: list[str] | None = None,
        sender: list[str] | None = None,
    ) -> str:
        result = df
        if jahr:
            result = result[result["Jahr"].isin(jahr)]
        if region:
            result = result[result["Region"].isin(region)]
        if zeitschiene:
            result = result[result["Zeitschiene"].isin(zeitschiene)]
        if kenngroesse:
            result = result[result["Kenngrösse"].isin(kenngroesse)]
        if sender:
            result = result[result["Sender"].isin(sender)]

        if result.empty:
            return "Keine Daten gefunden."

        return result.head(20).to_markdown(index=False)

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
