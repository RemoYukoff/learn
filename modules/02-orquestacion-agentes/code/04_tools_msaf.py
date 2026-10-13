"""Same agent in Microsoft Agent Framework: Agent + @tool + AnthropicClient.

Run (msaf venv): python 04_tools_msaf.py   (needs ANTHROPIC_API_KEY in .env)
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework.anthropic import AnthropicClient
from dotenv import load_dotenv

import crm

load_dotenv()


@tool
def get_customer(customer_id: Annotated[str, "Customer id, e.g. C-001"]) -> str:
    """Get a customer record by id."""
    return crm.get_customer(customer_id)


@tool
def list_open_tickets(customer_id: Annotated[str, "Customer id"]) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


async def main() -> None:
    agent = Agent(
        client=AnthropicClient(model="claude-opus-5-5"),  # reads ANTHROPIC_API_KEY
        instructions="You are a support assistant. Use the CRM tools; never invent data.",
        tools=[get_customer, list_open_tickets],
        default_options={"max_tokens": 4096},  # the client default is 1024
    )
    question = "Which open tickets does customer C-001 have, and what plan are they on?"
    print(f"User: {question}\n")
    response = await agent.run(question)  # the framework runs the tool loop
    print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
