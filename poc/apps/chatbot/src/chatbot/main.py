"""Minimal CLI chatbot using OpenAI tool-calling and an MCP server."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

SYSTEM_PROMPT = """\
Du bist ein Datenassistent für die Analyse von TV-Nutzungsdaten aus den \
Jahresberichten der Schweizer Mediapulse-Erhebung.

═══ REGELN ═══
• Generiere niemals SQL. Verwende ausschliesslich die bereitgestellten Tools.
• Verwende zuerst get_catalog, wenn Begriffe unklar sind.
  Wenn selection_required=true zurückkommt, bitte den Nutzer um Klärung.
• Interpretiere oder bewerte die Daten NICHT. Erstelle keine Prognosen, \
keine Trends und keine Vermutungen. Gib nur Fakten aus den Daten wieder.
• Jede Abfrage MUSS genau eine Region enthalten (DS, SR oder SI). \
Frage den Nutzer nach der Region, falls sie fehlt.
• Nenne in der Antwort immer die verwendeten Filter und Dimensionen.
• Antworte auf Deutsch, es sei denn der Nutzer schreibt auf Englisch.

═══ VERFÜGBARE DATEN ═══
Quelle: Mediapulse Jahresberichte (Panel-basierte TV-Messung Schweiz).
Zeitraum: 2018–2021.
Zielgruppe: Immer «Personen 3+» (gesamte Bevölkerung ab 3 Jahren).

Spalten im Datensatz:
  • Jahr          – Kalenderjahr (2018, 2019, 2020, 2021)
  • Region        – Sprachregion: DS (Deutsche Schweiz), SR (Suisse Romande), \
SI (Svizzera Italiana)
  • timeslot_start / timeslot_end – Start-/Endzeit (HH:MM:SS, Sendetag 02:00–26:00)
  • timeslot_duration_minutes – 15 (Viertelstunde), 300 (Primetime 18–23h), \
1440 (ganzer Sendetag)
  • Metrik         – Kennzahl:
      Rt-T   = Reichweite in Tausend Personen
      Rt-%   = Reichweite in Prozent
      NRw-T  = Netto-Reichweite in Tausend
      NRw-%  = Netto-Reichweite in Prozent
      MA-%   = Marktanteil in Prozent
      SD Ø   = Sehdauer Durchschnitt (Minuten)
      VD Ø   = Verweildauer Durchschnitt (Minuten)
  • Sender        – z.B. SRF 1, SRF zwei, RTS 1, RSI LA 1, ARD, ZDF, \
Andere Sender, SRG SSR Total, SRF Total …
  • Wert          – Numerischer Messwert

═══ NICHT VERFÜGBARE DATEN ═══
Die Daten enthalten KEINE Informationen zu:
  • Demographischen Zielgruppen (Alter, Geschlecht) – es gibt nur «Personen 3+»
  • Einzelnen Sendungen oder Programmen
  • Streaming-Plattformen oder Web-TV
  • Empfangswegen (Kabel, IP-TV, Satellit)
  • Live- vs. zeitversetzter Nutzung (nur Overnight+7 insgesamt)
  • Inhalten (Sport, Nachrichten etc.)

Wenn eine Frage Daten betrifft, die nicht vorhanden sind, antworte freundlich: \
«Zu dieser Frage liegen in den verfügbaren Jahresbericht-Daten leider keine \
Informationen vor. Die Daten umfassen ausschliesslich aggregierte \
TV-Nutzungskennzahlen (Reichweite, Marktanteil, Sehdauer) pro Sender, \
Region und Zeitfenster für die Zielgruppe Personen 3+.»
"""


def greet(name: str = "World") -> str:
    return f"Hello, {name}! Welcome to the MCP Chatbot PoC."


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [str(item) for item in content if isinstance(item, str) and item.strip()]
        return "\n".join(parts).strip()
    return ""


def _describe_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return _describe_exception(exc.exceptions[0])
    return str(exc) or exc.__class__.__name__


def _load_openai_client() -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required.")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - dependency/runtime guard
        raise RuntimeError("Missing dependency 'openai'. Run: uv sync --all-extras") from exc

    return OpenAI(api_key=api_key)


def _build_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    tool_specs: list[dict[str, Any]] = []
    for tool in mcp_tools:
        input_schema = getattr(tool, "inputSchema", None)
        if input_schema is None:
            input_schema = getattr(tool, "input_schema", None)
        parameters = _to_jsonable(input_schema) or {"type": "object", "properties": {}}
        tool_specs.append(
            {
                "type": "function",
                "function": {
                    "name": str(getattr(tool, "name", "")),
                    "description": str(getattr(tool, "description", "")),
                    "parameters": parameters,
                },
            }
        )
    return tool_specs


async def _run_chat_loop(session: Any) -> None:
    openai_client = _load_openai_client()

    tools_result = await session.list_tools()
    tool_specs = _build_openai_tools(list(tools_result.tools))

    print(greet())
    print("Connected to MCP server. Type 'exit' to quit.")

    messages: list[dict[str, Any]] = []
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye.")
            return
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        while True:
            response = openai_client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                temperature=1,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
                tools=tool_specs,
            )

            assistant_message = response.choices[0].message
            assistant_dict: dict[str, Any] = {
                "role": "assistant",
                "content": assistant_message.content or "",
            }

            tool_calls = assistant_message.tool_calls or []
            if tool_calls:
                assistant_dict["tool_calls"] = [call.model_dump(mode="json") for call in tool_calls]

            messages.append(assistant_dict)

            if not tool_calls:
                final_text = _extract_text(assistant_message.content)
                print(f"Assistant: {final_text or '[No text output]'}")
                break

            for call in tool_calls:
                tool_name = str(getattr(call.function, "name", ""))
                arguments_raw = getattr(call.function, "arguments", "{}")
                try:
                    tool_input = json.loads(arguments_raw) if arguments_raw else {}
                except json.JSONDecodeError:
                    tool_input = {}

                print(f"Assistant is calling tool: {tool_name}")
                tool_result = await session.call_tool(name=tool_name, arguments=tool_input)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(getattr(call, "id", "")),
                        "content": json.dumps(
                            _to_jsonable(tool_result.content),
                            ensure_ascii=False,
                        ),
                    }
                )


async def main() -> None:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:  # pragma: no cover - dependency/runtime guard
        print("Missing dependencies for MCP client. Run: uv sync --all-extras")
        raise SystemExit(1) from exc

    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")

    try:
        async with (
            streamable_http_client(mcp_server_url) as (
                read_stream,
                write_stream,
                _,
            ),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            await _run_chat_loop(session)
    except Exception as exc:
        reason = _describe_exception(exc)
        print(
            "Failed to start chatbot. "
            f"Reason: {reason}. "
            f"Check MCP_SERVER_URL ({mcp_server_url}) and ensure the MCP server is running."
        )


if __name__ == "__main__":
    asyncio.run(main())
