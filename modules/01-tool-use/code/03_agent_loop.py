"""An agent loop from scratch with the Anthropic SDK.

while the model asks for tools: run them, send results back, call again.
All tool results of one turn go back in a single user message.
"""

import json

import anthropic
from dotenv import load_dotenv

from crm import FUNCTIONS, TOOLS

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"
MAX_TURNS = 10
SYSTEM = "You are a support operations agent. Use the tools to answer. Be brief."


def run_tool(name: str, args: dict) -> dict:
    """Return a tool_result content dict. Errors go back to the model, not up the stack."""
    try:
        return {"content": FUNCTIONS[name](**args)}
    except Exception as e:  # noqa: BLE001 - every failure becomes feedback for the model
        return {"content": f"{type(e).__name__}: {e}", "is_error": True}


def agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]
    for turn in range(1, MAX_TURNS + 1):
        response = client.messages.create(
            model=MODEL, max_tokens=8192, system=SYSTEM, tools=TOOLS, messages=messages
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return next((b.text for b in response.content if b.type == "text"), f"[stopped: {response.stop_reason}]")

        results = []
        for block in response.content:
            if block.type == "tool_use":
                result = run_tool(block.name, block.input)
                print(f"turn {turn}: {block.name}({json.dumps(block.input)}) -> {result['content'][:80]}")
                results.append({"type": "tool_result", "tool_use_id": block.id, **result})
        messages.append({"role": "user", "content": results})
    return "[gave up: too many turns]"


print(agent("Acme says the CSV export is fixed. Close that ticket and tell me what is still open for them."))
