"""Structured output with the Anthropic SDK: messages.parse + a Pydantic model.

The API constrains generation to the JSON schema derived from the model, and the
SDK validates the result into a typed object.
"""

from typing import Literal

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
client = anthropic.Anthropic()


class Ticket(BaseModel):
    category: Literal["billing", "bug", "feature_request", "other"]
    priority: Literal["low", "medium", "high"]
    summary: str = Field(description="One sentence, in English")
    customer_wants_refund: bool


TEXT = "Hi, we were charged twice this month and our CFO is furious. Fix it ASAP and refund the extra charge."

response = client.messages.parse(
    model="claude-opus-5-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Extract the ticket fields from this email:\n\n{TEXT}"}],
    output_format=Ticket,
)

ticket = response.parsed_output
print(type(ticket).__name__, ticket.model_dump_json(indent=2))
print("priority is typed:", ticket.priority)
