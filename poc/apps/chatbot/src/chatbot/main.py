"""Main entry point for the MCP Chatbot."""

import asyncio


def greet(name: str = "World") -> str:
    """Return a greeting message.

    Args:
        name: The name to greet.

    Returns:
        A greeting string.
    """
    return f"Hello, {name}! Welcome to the MCP Chatbot PoC."


async def main() -> None:
    """Run the chatbot main loop."""
    print(greet())
    print("MCP Chatbot is starting...")
    print("This is a placeholder for the actual chatbot implementation.")
    print("The chatbot will connect to MCP servers and handle user queries.")


if __name__ == "__main__":
    asyncio.run(main())
