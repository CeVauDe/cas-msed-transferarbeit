"""Web chatbot using Gradio UI, OpenAI tool-calling, and an MCP server."""

from __future__ import annotations

import json
import logging
import os
import sys
from collections.abc import Callable, Coroutine
from typing import Any

import gradio as gr
from openai.types.chat import ChatCompletionMessageParam

log = logging.getLogger(__name__)

# To switch back to v1: change this import to system_prompt_v1
from chatbot.system_prompt_v2_prognose import SYSTEM_PROMPT  # noqa: E402

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


async def _read_resources(session: Any) -> str:
    """Read all text resources from the MCP server and return as a single string."""
    try:
        resources_result = await session.list_resources()
        parts: list[str] = []
        for resource in resources_result.resources:
            result = await session.read_resource(resource.uri)
            for content in result.contents:
                if hasattr(content, "text"):
                    parts.append(content.text)
        return "\n\n".join(parts)
    except Exception:
        log.warning("Failed to read MCP resources, continuing without them.", exc_info=True)
        return ""


async def _agent_turn(
    message: str,
    history: list[dict[str, str]],
    session: Any,
    openai_client: Any,
) -> str:
    tools_result = await session.list_tools()
    tool_specs = _build_openai_tools(list(tools_result.tools))

    resource_text = await _read_resources(session)
    system_content = SYSTEM_PROMPT
    if resource_text:
        system_content = f"{SYSTEM_PROMPT}\n\n{resource_text}"

    messages: list[ChatCompletionMessageParam] = []
    messages.extend(_history_to_openai(history))
    messages.append({"role": "user", "content": message})

    for round_num in range(_MAX_TOOL_ROUNDS):
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        log.debug(
            ">>> LLM request (model=%s, messages=%d, round=%d)",
            model,
            len(messages),
            round_num + 1,
        )

        response = openai_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_content}, *messages],
            tools=tool_specs,
        )

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            log.debug("<<< LLM response: final text answer")
            return _extract_text(assistant_message.content) or "[Keine Antwort]"

        log.debug("<<< LLM response: %d tool call(s)", len(tool_calls))

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

            log.debug(
                ">>> Tool call: %s(%s)",
                tool_name,
                json.dumps(tool_input, indent=2, ensure_ascii=False),
            )

            tool_result = await session.call_tool(name=tool_name, arguments=tool_input)
            result_content = json.dumps(_to_jsonable(tool_result.content), ensure_ascii=False)

            log.debug("<<< Tool result from %s (%d chars)", tool_name, len(result_content))

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(getattr(call, "id", "")),
                    "content": result_content,
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
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
    openai_client = _load_openai_client()
    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")
    respond = _make_respond_fn(openai_client, mcp_server_url)

    demo = gr.ChatInterface(
        fn=respond,
        title="Jahreszahlen TV Nutzung Schweiz",
        description=(
            "Stellen Sie Fragen zu den TV-Nutzungsdaten der Schweizer "
            "Mediapulse-Jahresberichte (2018-2021)."
        ),
        examples=[
            "Was war der Marktanteil von SRF 1 in der Deutschschweiz 2021?",
            "Vergleiche die Sehdauer von SRF 1, SRF zwei und ARD in der Deutschschweiz 2020.",
            "Wie hat sich der Marktanteil von SRF 1 und ZDF in der Deutschschweiz von 2018 bis "
            "2021 entwickelt?",
            "Zeige mir Reichweite und Marktanteil aller Sender in der Suisse romande 2019.",
        ],
        cache_examples=False,
        concurrency_limit=4,
    )

    port = int(os.environ.get("GRADIO_PORT", "7860"))
    print(f"\n  Open the chatbot: \033[4;94mhttp://localhost:{port}\033[0m\n", flush=True)
    demo.launch(
        server_name="0.0.0.0",
        server_port=port,
    )


if __name__ == "__main__":
    main()
