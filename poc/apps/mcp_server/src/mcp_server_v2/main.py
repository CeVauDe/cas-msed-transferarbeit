"""MCP server v2 entrypoint — simplified Jahresbericht data access via pandas."""

import logging
import os
from typing import Annotated, Literal

import pandas as pd
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from mcp_server_v2.glossary import GLOSSARY_MD

type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type Transport = Literal["stdio", "sse", "streamable-http"]

logger = logging.getLogger(__name__)

_DEFAULT_PARQUET = "apps/mcp_server/data/Jahresbericht_v2.parquet"


class Sortierung(BaseModel):
    """Sort specification for a single column."""

    spalte: str = Field(description="Spalte, nach der sortiert wird.")
    richtung: Literal["aufsteigend", "absteigend"] = Field(
        default="aufsteigend",
        description="Sortierrichtung.",
    )


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
        jahr: Annotated[
            list[int] | None,
            Field(description="Jahr(e). Erlaubt: 2018, 2019, 2020, 2021"),
        ] = None,
        region: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Sprachregion(en). Erlaubt: Deutschschweiz, Suisse romande, Svizzera italiana"
                ),
            ),
        ] = None,
        zeitschiene: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Zeitschiene(n). Beispiele: 'Ganzer Tag', '18-23h', '20:00:00 - 20:15:00'"
                ),
            ),
        ] = None,
        kenngroesse: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Kenngrösse(n). Erlaubt: "
                    "Rating in 1'000, Rating in %, "
                    "Nettoreichweite in 1'000, "
                    "Nettoreichweite in %, "
                    "Marktanteil in %, "
                    "durchschnittliche Sehdauer in Sekunden, "
                    "durchschnittliche Verweildauer in Sekunden"
                ),
            ),
        ] = None,
        sender: Annotated[
            list[str] | None,
            Field(
                description=(
                    "TV-Sender. Beispiele: SRF 1, SRF zwei, RTS 1, RSI LA 1, ARD, ZDF, ORF 1"
                ),
            ),
        ] = None,
        spalten: Annotated[
            list[str] | None,
            Field(
                description=(
                    "Spalten im Ergebnis. "
                    "Erlaubt: Jahr, Region, Zeitschiene, "
                    "Kenngrösse, Sender, Wert. "
                    "Standard: alle Spalten."
                ),
            ),
        ] = None,
        limit: Annotated[
            int,
            Field(
                description="Maximale Anzahl Zeilen. Standard: 20, Maximum: 200.",
                ge=1,
                le=200,
            ),
        ] = 20,
        zeilen: Annotated[
            str | None,
            Field(
                description=(
                    "Pivot-Modus: Spalte für die Zeilen. "
                    "Beispiel: 'Sender'. "
                    "Nur zusammen mit spalten_pivot verwenden."
                ),
            ),
        ] = None,
        spalten_pivot: Annotated[
            str | None,
            Field(
                description=(
                    "Pivot-Modus: Spalte für die Spaltenköpfe. "
                    "Beispiel: 'Jahr'. "
                    "Nur zusammen mit zeilen verwenden."
                ),
            ),
        ] = None,
        sortierung: Annotated[
            list[Sortierung] | None,
            Field(
                description=(
                    "Sortierung: Liste von Objekten mit 'spalte' und "
                    "'richtung' (aufsteigend/absteigend). "
                    'Beispiel: [{"spalte": "Wert", "richtung": "absteigend"}]'
                ),
            ),
        ] = None,
    ) -> str:
        logger.info(
            "abfrage_jahresbericht called: jahr=%s, region=%s, "
            "zeitschiene=%s, kenngroesse=%s, sender=%s, "
            "spalten=%s, limit=%s, zeilen=%s, spalten_pivot=%s, "
            "sortierung=%s",
            jahr,
            region,
            zeitschiene,
            kenngroesse,
            sender,
            spalten,
            limit,
            zeilen,
            spalten_pivot,
            sortierung,
        )

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
            logger.info("No data matched the filters.")
            return "Keine Daten gefunden."

        row_limit = min(limit, 200)

        if sortierung:
            by = [s.spalte for s in sortierung if s.spalte in result.columns]
            asc = [s.richtung == "aufsteigend" for s in sortierung if s.spalte in result.columns]
            if by:
                result = result.sort_values(by=by, ascending=asc)

        if zeilen and spalten_pivot:
            pivot = result.pivot_table(
                index=zeilen,
                columns=spalten_pivot,
                values="Wert",
            )
            if sortierung:
                for s in reversed(sortierung):
                    if s.spalte == pivot.index.name:
                        pivot = pivot.sort_index(ascending=(s.richtung == "aufsteigend"))
                    elif s.spalte in pivot.columns:
                        pivot = pivot.sort_values(
                            by=s.spalte, ascending=(s.richtung == "aufsteigend")
                        )
            table = pivot.head(row_limit).to_markdown()
            logger.info(
                "Returning pivot (%d rows):\n%s",
                min(row_limit, len(pivot)),
                table,
            )
            return table

        if spalten:
            result = result[[c for c in spalten if c in result.columns]]

        table = result.head(row_limit).to_markdown(index=False)
        logger.info(
            "Returning %d rows (of %d matched):\n%s",
            min(row_limit, len(result)),
            len(result),
            table,
        )
        return table

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
        logger.info("glossar called")

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
