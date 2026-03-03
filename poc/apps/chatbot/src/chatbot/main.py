"""Web chatbot using Gradio UI, OpenAI tool-calling, and an MCP server."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Coroutine
from typing import Any

import gradio as gr
from openai.types.chat import ChatCompletionMessageParam

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

_MAX_TOOL_ROUNDS = 15


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


def _history_to_openai(
    history: list[dict[str, str]],
) -> list[ChatCompletionMessageParam]:
    messages: list[ChatCompletionMessageParam] = []
    for turn in history:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            messages.append({"role": "assistant", "content": content})
    return messages


async def _agent_turn(
    message: str,
    history: list[dict[str, str]],
    session: Any,
    openai_client: Any,
) -> str:
    tools_result = await session.list_tools()
    tool_specs = _build_openai_tools(list(tools_result.tools))

    messages: list[ChatCompletionMessageParam] = []
    messages.extend(_history_to_openai(history))
    messages.append({"role": "user", "content": message})

    for _ in range(_MAX_TOOL_ROUNDS):
        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=1,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            tools=tool_specs,
        )

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            return _extract_text(assistant_message.content) or "[Keine Antwort]"

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [call.model_dump(mode="json") for call in tool_calls],
            }
        )

        for call in tool_calls:
            tool_name = str(getattr(call.function, "name", ""))
            arguments_raw = getattr(call.function, "arguments", "{}")
            try:
                tool_input = json.loads(arguments_raw) if arguments_raw else {}
            except json.JSONDecodeError:
                tool_input = {}

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

    return "[Maximale Tool-Runden erreicht ohne abschliessende Antwort]"


def _make_respond_fn(
    openai_client: Any, mcp_server_url: str
) -> Callable[[str, list[dict[str, str]]], Coroutine[Any, Any, str]]:
    async def respond(message: str, history: list[dict[str, str]]) -> str:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client

            async with (
                streamable_http_client(mcp_server_url) as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await _agent_turn(message, history, session, openai_client)
        except Exception as exc:
            reason = _describe_exception(exc)
            return f"MCP-Server unter `{mcp_server_url}` nicht erreichbar. Grund: {reason}"

    return respond


def main() -> None:
    openai_client = _load_openai_client()
    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")
    respond = _make_respond_fn(openai_client, mcp_server_url)

    demo = gr.ChatInterface(
        fn=respond,
        title="SRF Jahresbericht Chat",
        description=(
            "Stellen Sie Fragen zu den TV-Nutzungsdaten der Schweizer "
            "Mediapulse-Jahresberichte (2018–2021). "
            "Datenquelle: SRF/SRG Jahresbericht, Panel-basierte TV-Messung."
        ),
        examples=[
            "Was war der durchschnittliche Marktanteil von SRF 1 in der Deutschen Schweiz 2021?",
            "Zeige mir die Reichweite aller Sender in der Deutschen Schweiz für 2020.",
            "Welcher Sender hatte den höchsten Marktanteil in der Suisse Romande 2019?",
            "Wie war die Sehdauer für SRF zwei in der Deutschen Schweiz in der Primetime 2021?",
        ],
        cache_examples=False,
    )

    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_PORT", "7860")),
    )


if __name__ == "__main__":
    main()
