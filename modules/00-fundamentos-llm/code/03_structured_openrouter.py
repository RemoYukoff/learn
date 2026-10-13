"""Structured output through OpenRouter with the OpenAI SDK.

OpenRouter exposes an OpenAI-compatible API, so the same code works with Claude,
GPT or Gemini by changing OPENROUTER_MODEL.
"""

import os
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

load_dotenv()
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ.get("OPENROUTER_API_KEY"))
MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-5.5")


class Ticket(BaseModel):
    category: Literal["billing", "bug", "feature_request", "other"]
    priority: Literal["low", "medium", "high"]
    summary: str = Field(description="One sentence, in English")
    customer_wants_refund: bool


TEXT = "Hi, we were charged twice this month and our CFO is furious. Fix it ASAP and refund the extra charge."

completion = client.chat.completions.parse(
    model=MODEL,
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Extract the ticket fields from this email:\n\n{TEXT}"}],
    response_format=Ticket,
)

message = completion.choices[0].message
if message.refusal:
    print("Refused:", message.refusal)
else:
    print(f"[{MODEL}]", message.parsed.model_dump_json(indent=2))
