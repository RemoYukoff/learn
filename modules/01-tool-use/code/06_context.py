"""Context growth in an agent and two ways to contain it.

Runs the same task three times and prints input tokens per turn:
  none   - full history resent every turn (input grows with every tool result)
  trim   - client side: old tool results replaced with a short placeholder
  server - server side (beta): context editing clears old tool results for you
"""

import anthropic
from dotenv import load_dotenv

import crm

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"

# Make tool results bulky, like a real API response with many fields.
crm.TICKETS.update({
    f"T-{i}": {"id": f"T-{i}", "customer_id": "C-100", "subject": f"Issue {i} " + "x" * 300, "status": "open"}
    for i in range(4, 40)
})

TASK = (
    "One tool call per turn: list Acme's open tickets, then Acme's closed tickets, "
    "then Globex's open tickets, then Globex's closed ones. Finally give me the four counts."
)
CONTEXT_EDITS = {
    "edits": [{
        "type": "clear_tool_uses_20250919",
        "trigger": {"type": "tool_uses", "value": 2},  # start clearing after 2 tool uses (demo value)
        "keep": {"type": "tool_uses", "value": 1},     # always keep the most recent one
    }]
}


def trim_old_tool_results(messages: list[dict], keep_last: int = 1) -> None:
    seen = 0
    for msg in reversed(messages):
        if msg["role"] != "user" or not isinstance(msg["content"], list):
            continue
        for part in msg["content"]:
            if part.get("type") == "tool_result":
                seen += 1
                if seen > keep_last:
                    part["content"] = "[old tool result removed to save context]"


def call(messages: list[dict], mode: str):
    if mode == "server":
        return client.beta.messages.create(
            model=MODEL, max_tokens=4096, tools=crm.TOOLS, messages=messages,
            betas=["context-management-2025-06-27"], context_management=CONTEXT_EDITS,
        )
    if mode == "trim":
        trim_old_tool_results(messages)
    return client.messages.create(model=MODEL, max_tokens=4096, tools=crm.TOOLS, messages=messages)


def run(mode: str) -> None:
    print(f"\n=== {mode} ===")
    messages = [{"role": "user", "content": TASK}]
    for turn in range(1, 10):
        response = call(messages, mode)
        extra = ""
        if mode == "server" and response.context_management:
            cleared = sum(e.cleared_input_tokens for e in response.context_management.applied_edits)
            extra = f" (server cleared {cleared} tokens)"
        print(f"turn {turn}: input_tokens={response.usage.input_tokens}{extra}")
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            print(next((b.text for b in response.content if b.type == "text"), ""))
            return
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": crm.FUNCTIONS[b.name](**b.input)}
                for b in response.content
                if b.type == "tool_use"
            ],
        })


for mode in ("none", "trim", "server"):
    run(mode)
