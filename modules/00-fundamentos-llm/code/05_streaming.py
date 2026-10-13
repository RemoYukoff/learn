"""Streaming: print tokens as they arrive, then read the final message.

First with the Anthropic helper (text_stream + get_final_message), then through
OpenRouter with the OpenAI SDK (stream=True chunks).
"""

import os

import anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
PROMPT = [{"role": "user", "content": "List five things to monitor in an LLM app in production, one line each."}]

print("=== Anthropic ===")
client = anthropic.Anthropic()
with client.messages.stream(model="claude-opus-5-5", max_tokens=4096, messages=PROMPT) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    final = stream.get_final_message()
print(f"\n[stop_reason={final.stop_reason} output_tokens={final.usage.output_tokens}]")

if os.environ.get("OPENROUTER_API_KEY"):
    print("\n=== OpenRouter (OpenAI SDK) ===")
    router = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    stream = router.chat.completions.create(
        model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-5.5"),
        max_tokens=4096,
        messages=PROMPT,
        stream=True,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
        if chunk.usage:
            print(f"\n[output_tokens={chunk.usage.completion_tokens}]")
