"""Minimal CLI chatbot using OpenAI tool-calling and an MCP server."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any


SYSTEM_PROMPT = (
    "You are a data assistant for Jahresbericht analytics. "
    "Never generate SQL. Only use the provided tools. "
    "Use get_catalog first when user terms are unclear. "
    "If a glossary term is ambiguous and selection_required is true, ask the user to choose. "
    "In final answers, mention the filters and dimensions you used."
)


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
        raise RuntimeError(
            "Missing dependency 'openai'. Run: uv sync --all-extras"
        ) from exc

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
        async with streamable_http_client(mcp_server_url) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
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
