"""Human-in-the-loop: sensitive tools need a human "yes" before they run.

The gate lives in the tool executor, not in the prompt. A "no" goes back to the
model as a normal tool result so it can explain or choose another path.
"""

import json

import anthropic
from dotenv import load_dotenv

import crm

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"
NEEDS_APPROVAL = {"issue_refund", "update_ticket_status"}


def approve(name: str, args: dict) -> tuple[bool, str]:
    print(f"\nThe agent wants to run {name} with {json.dumps(args)}")
    answer = input("Approve? [y/N or a note for the agent] ").strip()
    if answer.lower() in {"y", "yes", "s", "si"}:
        return True, ""
    return False, answer or "no reason given"


def run_tool(name: str, args: dict) -> dict:
    if name in NEEDS_APPROVAL:
        ok, note = approve(name, args)
        if not ok:
            return {"content": f"The human operator rejected this action. Their note: {note}"}
    try:
        return {"content": crm.FUNCTIONS[name](**args)}
    except Exception as e:  # noqa: BLE001
        return {"content": f"{type(e).__name__}: {e}", "is_error": True}


messages = [{"role": "user", "content": "Acme was double charged in October (49 USD). Refund it and close the ticket."}]
for _ in range(8):
    response = client.messages.create(model=MODEL, max_tokens=8192, tools=crm.TOOLS, messages=messages)
    messages.append({"role": "assistant", "content": response.content})
    if response.stop_reason != "tool_use":
        print("\n" + next((b.text for b in response.content if b.type == "text"), ""))
        break
    results = [
        {"type": "tool_result", "tool_use_id": b.id, **run_tool(b.name, b.input)}
        for b in response.content
        if b.type == "tool_use"
    ]
    messages.append({"role": "user", "content": results})

print("\nRefunds:", crm.REFUNDS)
print("Tickets:", {k: v["status"] for k, v in crm.TICKETS.items()})
