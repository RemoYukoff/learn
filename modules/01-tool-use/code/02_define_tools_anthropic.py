"""One request with tools, no execution: see what a tool_use block looks like.

The model does not run anything. It answers with stop_reason == "tool_use" and
one or more tool_use blocks (name + input). Running the function is your job.
"""

import anthropic
from dotenv import load_dotenv

from crm import TOOLS

load_dotenv()
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-opus-5-5",
    max_tokens=4096,
    tools=[{**t, "strict": True} for t in TOOLS],  # strict: input always validates against the schema
    messages=[{"role": "user", "content": "Which tickets does Acme have open?"}],
)

print("stop_reason:", response.stop_reason)
for block in response.content:
    if block.type == "text":
        print("text:", block.text)
    elif block.type == "tool_use":
        print(f"tool_use: id={block.id} name={block.name} input={block.input}")
