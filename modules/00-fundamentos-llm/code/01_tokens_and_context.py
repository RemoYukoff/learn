"""Tokens, context and stop reasons.

Counts tokens before sending, makes one call, and shows usage and stop_reason.
Then repeats with a tiny max_tokens to see a truncated answer (stop_reason == "max_tokens").
"""

import anthropic
from dotenv import load_dotenv

load_dotenv()
client = anthropic.Anthropic()
MODEL = "claude-opus-5-5"

messages = [{"role": "user", "content": "Explain in three sentences what a context window is."}]

count = client.messages.count_tokens(model=MODEL, messages=messages)
print(f"Input tokens before sending: {count.input_tokens}")

response = client.messages.create(model=MODEL, max_tokens=1024, messages=messages)
print("\n--- full answer ---")
print(next(b.text for b in response.content if b.type == "text"))
print(f"\nstop_reason={response.stop_reason}")
print(f"usage: input={response.usage.input_tokens} output={response.usage.output_tokens}")

truncated = client.messages.create(model=MODEL, max_tokens=20, messages=messages)
print("\n--- max_tokens=20 ---")
print(next((b.text for b in truncated.content if b.type == "text"), "(no text: the budget went to thinking)"))
print(f"stop_reason={truncated.stop_reason}  <- always check this before trusting the output")
