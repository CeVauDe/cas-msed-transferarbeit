from __future__ import annotations

import json
import os
from collections.abc import Callable, Coroutine

import gradio as gr
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

SYSTEM_PROMPT = (
    "You are a weather assistant for Switzerland using live SRF Meteo data. "
    "Never invent or guess weather data — only use the provided tools. "
    "When a user mentions a location, call search_location first to resolve it to a "
    "geolocation_id. "
    "If search_location returns multiple candidates, ask the user to confirm which one. "
    "Then call get_forecast with the geolocation_id and the appropriate forecast_type "
    "('daily' for day-level overview, '3hourly' for more detail, "
    "'hourly' for precise hourly data). "
    "In your final answer, always state the location name, the forecast date(s), "
    "and the data source."
)


_MAX_TOOL_ROUNDS = 15


def _to_jsonable(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")  # type: ignore[union-attr]
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _content_to_str(content: object) -> str:
    """Extract plain text from MCP tool result content for OpenAI."""
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if hasattr(block, "text"):
                parts.append(str(block.text))
            else:
                parts.append(json.dumps(_to_jsonable(block), ensure_ascii=False))
        return "\n".join(parts)
    return json.dumps(_to_jsonable(content), ensure_ascii=False)


def _describe_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return _describe_exception(exc.exceptions[0])
    return str(exc) or exc.__class__.__name__


def _build_openai_tools(mcp_tools: list[object]) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for tool in mcp_tools:
        input_schema = getattr(tool, "inputSchema", None)
        if input_schema is None:
            input_schema = getattr(tool, "input_schema", None)
        parameters = _to_jsonable(input_schema) or {"type": "object", "properties": {}}
        specs.append(
            {
                "type": "function",
                "function": {
                    "name": str(getattr(tool, "name", "")),
                    "description": str(getattr(tool, "description", "")),
                    "parameters": parameters,
                },
            }
        )
    return specs


def _history_to_openai(history: list[dict[str, str]]) -> list[ChatCompletionMessageParam]:
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
    session: ClientSession,
    openai_client: OpenAI,
) -> str:
    tools_result = await session.list_tools()
    tool_specs = _build_openai_tools(list(tools_result.tools))

    messages: list[ChatCompletionMessageParam] = []
    messages.extend(_history_to_openai(history))
    messages.append({"role": "user", "content": message})

    for _ in range(_MAX_TOOL_ROUNDS):
        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            tools=tool_specs,
        )

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            messages.append({"role": "assistant", "content": assistant_message.content or ""})
            return assistant_message.content or "[No response]"

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [c.model_dump(mode="json") for c in tool_calls],
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
                    "content": _content_to_str(tool_result.content),
                }
            )

    return "[Max tool rounds reached without a final answer]"


def _make_respond_fn(
    openai_client: OpenAI, mcp_server_url: str
) -> Callable[[str, list[dict[str, str]]], Coroutine[object, object, str]]:
    async def respond(message: str, history: list[dict[str, str]]) -> str:
        try:
            async with (
                streamable_http_client(mcp_server_url) as (read, write, _),
                ClientSession(read, write) as session,
            ):
                await session.initialize()
                return await _agent_turn(message, history, session, openai_client)
        except Exception as exc:
            reason = _describe_exception(exc)
            return f"Could not reach the MCP server at `{mcp_server_url}`. Reason: {reason}"

    return respond


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")

    openai_client = OpenAI(api_key=api_key)
    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8081/mcp")
    respond = _make_respond_fn(openai_client, mcp_server_url)

    demo = gr.ChatInterface(
        fn=respond,
        title="SRF Meteo Chat",
        description=(
            "Ask questions about the weather in Switzerland. "
            "Powered by the SRF Meteo API and OpenAI."
        ),
        examples=[
            "What's the weather like in Zurich tomorrow?",
            "Show me the hourly forecast for Bern today.",
            "Will it rain in Geneva this week?",
            "What's the UV index in Lugano?",
        ],
        cache_examples=False,
    )

    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_PORT", "7860")),
    )


if __name__ == "__main__":
    main()
