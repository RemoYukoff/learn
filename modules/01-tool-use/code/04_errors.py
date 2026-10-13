"""Errors, validation and limits in an agent loop.

- Tool inputs are validated with Pydantic before running; a validation error goes
  back to the model as is_error so it can fix the call.
- Unknown tools and exceptions also become error results instead of crashing.
- The loop has a turn limit and a per-tool call limit to stop runaway agents.
"""

import json
from collections import Counter

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

import crm

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"


class RefundInput(BaseModel):
    customer_id: str = Field(pattern=r"^C-\d+$")
    amount_usd: float = Field(gt=0, le=500)  # business rule the JSON Schema does not express
    reason: str = Field(min_length=5)


VALIDATORS = {"issue_refund": RefundInput}
MAX_CALLS_PER_TOOL = 3


def run_tool(name: str, args: dict, calls: Counter) -> dict:
    calls[name] += 1
    if calls[name] > MAX_CALLS_PER_TOOL:
        return {"content": f"Tool {name} called too many times. Stop and report to the user.", "is_error": True}
    if name not in crm.FUNCTIONS:
        return {"content": f"Unknown tool {name}. Available: {list(crm.FUNCTIONS)}", "is_error": True}
    if name in VALIDATORS:
        try:
            args = VALIDATORS[name](**args).model_dump()
        except ValidationError as e:
            return {"content": f"Invalid input: {e.errors(include_url=False)}", "is_error": True}
    try:
        return {"content": crm.FUNCTIONS[name](**args)}
    except Exception as e:  # noqa: BLE001
        return {"content": f"{type(e).__name__}: {e}", "is_error": True}


def agent(task: str, max_turns: int = 8) -> str:
    messages = [{"role": "user", "content": task}]
    calls: Counter = Counter()
    for _ in range(max_turns):
        response = client.messages.create(model=MODEL, max_tokens=8192, tools=crm.TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "max_tokens":
            return "[truncated: raise max_tokens]"
        if response.stop_reason != "tool_use":
            return next((b.text for b in response.content if b.type == "text"), f"[{response.stop_reason}]")
        results = []
        for block in (b for b in response.content if b.type == "tool_use"):
            result = run_tool(block.name, block.input, calls)
            flag = "ERROR" if result.get("is_error") else "ok"
            print(f"{flag:5} {block.name}({json.dumps(block.input)}) -> {result['content'][:100]}")
            results.append({"type": "tool_result", "tool_use_id": block.id, **result})
        messages.append({"role": "user", "content": results})
    return "[gave up: max_turns reached]"


# 900 USD breaks the le=500 rule: watch the model receive the error and react.
print(agent("Refund Globex 900 USD for the SSO delay."))
print("Refunds issued:", crm.REFUNDS)
