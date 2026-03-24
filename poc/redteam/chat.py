# Custom provider for promptfoo red teaming against Gradio ChatInterface
# Docs: https://promptfoo.dev/docs/red-team/configuration/#providers

import http.client
import json
import os


def _parse_prompt(prompt):
    """Normalize a promptfoo prompt into (message, history) for Gradio.

    Single-turn: prompt is a string → (prompt, [])
    Multi-turn:  prompt is a list of message dicts → (last_user_msg, prior_history)
    """
    if isinstance(prompt, str):
        return prompt, []

    if isinstance(prompt, list):
        # Keep only user/assistant roles (system prompt is managed server-side)
        messages = [
            msg
            for msg in prompt
            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant")
        ]
        # Last user message becomes the new message; everything before it is history
        for i in range(len(messages) - 1, -1, -1):
            if messages[i]["role"] == "user":
                return messages[i]["content"], messages[:i]
        return "", messages

    return str(prompt), []


def call_api(prompt, _options, _context):
    host = os.environ.get("GRADIO_HOST", "localhost")
    port = int(os.environ.get("GRADIO_PORT", "7860"))

    conn = http.client.HTTPConnection(host, port, timeout=120)
    headers = {"Content-Type": "application/json"}

    # Step 1: Submit the call — Gradio returns an event_id
    message, history = _parse_prompt(prompt)
    payload = json.dumps({"data": [message, history]})
    conn.request("POST", "/gradio_api/call/respond", body=payload, headers=headers)
    resp = conn.getresponse()
    body = json.loads(resp.read().decode())
    event_id = body.get("event_id")
    if not event_id:
        return {"output": f"Error: no event_id in response: {body}"}

    # Step 2: Read the SSE stream for the result
    conn = http.client.HTTPConnection(host, port, timeout=120)
    conn.request("GET", f"/gradio_api/call/respond/{event_id}")
    resp = conn.getresponse()
    raw = resp.read().decode()

    # Parse SSE: look for the last "data:" line
    output = None
    for line in raw.strip().splitlines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if isinstance(data, list) and len(data) > 0:
                    output = data[0]
            except json.JSONDecodeError:
                pass

    if output is None:
        return {"output": f"Error: could not parse Gradio SSE response: {raw[:500]}"}

    return {"output": output}
