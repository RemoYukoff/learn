"""The same request in OpenAI format through OpenRouter.

Differences: tools are wrapped in {"type": "function", "function": {...}} with
"parameters" instead of "input_schema", calls come in message.tool_calls and the
arguments arrive as a JSON string.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from crm import TOOLS, to_openai

load_dotenv()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ.get("OPENROUTER_API_KEY"))

completion = client.chat.completions.create(
    model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-5.5"),
    max_tokens=4096,
    tools=to_openai(TOOLS),
    messages=[{"role": "user", "content": "Which tickets does Acme have open?"}],
)

choice = completion.choices[0]
print("finish_reason:", choice.finish_reason)
print("content:", choice.message.content)
for call in choice.message.tool_calls or []:
    print(f"tool_call: id={call.id} name={call.function.name} arguments={json.loads(call.function.arguments)}")
