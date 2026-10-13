"""OpenAI SDK against OpenRouter: Chat Completions, multi-turn and switching providers."""

import os

import openai
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    max_retries=3,
)
MODELS = [os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-5.5"), "google/gemini-3.8-flash"]

for model in MODELS:
    messages = [
        {"role": "system", "content": "Answer in one sentence."},
        {"role": "user", "content": "What is a token in an LLM?"},
    ]
    try:
        completion = client.chat.completions.create(model=model, max_tokens=512, messages=messages)
    except openai.APIStatusError as e:
        print(f"[{model}] error {e.status_code}: {e.message}")
        continue
    choice = completion.choices[0]
    usage = completion.usage
    print(f"[{model}] finish_reason={choice.finish_reason} tokens in/out={usage.prompt_tokens}/{usage.completion_tokens}")
    print("   ", choice.message.content)
