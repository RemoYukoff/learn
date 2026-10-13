"""The same loop in OpenAI format through OpenRouter.

Tool results go back as one message per call with role "tool" and tool_call_id.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from crm import FUNCTIONS, TOOLS, to_openai

load_dotenv()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ.get("OPENROUTER_API_KEY"))
MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-5.5")
MAX_TURNS = 10


def agent(task: str) -> str:
    messages = [
        {"role": "system", "content": "You are a support operations agent. Use the tools to answer. Be brief."},
        {"role": "user", "content": task},
    ]
    for turn in range(1, MAX_TURNS + 1):
        completion = client.chat.completions.create(
            model=MODEL, max_tokens=8192, tools=to_openai(TOOLS), messages=messages
        )
        message = completion.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            return message.content or f"[stopped: {completion.choices[0].finish_reason}]"

        for call in message.tool_calls:
            try:
                result = FUNCTIONS[call.function.name](**json.loads(call.function.arguments))
            except Exception as e:  # noqa: BLE001
                result = f"ERROR {type(e).__name__}: {e}"
            print(f"turn {turn}: {call.function.name}({call.function.arguments}) -> {result[:80]}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "[gave up: too many turns]"


print(agent("Acme says the CSV export is fixed. Close that ticket and tell me what is still open for them."))
