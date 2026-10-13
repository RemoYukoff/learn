"""Human-in-the-loop in Microsoft Agent Framework: approval_mode="always_require" on a tool.

Run (msaf venv): python 06_hitl_msaf.py   (needs ANTHROPIC_API_KEY, asks you in the terminal)

The run returns approval requests instead of executing the tool. You answer with
approval responses in a new user message on the same session.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

from agent_framework import Agent, Message, tool
from agent_framework.anthropic import AnthropicClient
from dotenv import load_dotenv

import crm

load_dotenv()


@tool
def list_open_tickets(customer_id: Annotated[str, "Customer id"]) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


@tool(approval_mode="always_require")
def update_ticket_status(
    ticket_id: Annotated[str, "Ticket id, e.g. T-100"],
    status: Annotated[str, "open, pending or closed"],
) -> str:
    """Change a ticket status."""
    return crm.update_ticket_status(ticket_id, status)


async def main() -> None:
    agent = Agent(
        client=AnthropicClient(model="claude-opus-5-5"),
        instructions="You are a support assistant.",
        tools=[list_open_tickets, update_ticket_status],
        default_options={"max_tokens": 4096},
    )
    session = agent.create_session()
    response = await agent.run("Close every open ticket of customer C-001.", session=session)

    while response.user_input_requests:
        answers = []
        for request in response.user_input_requests:
            call = request.function_call
            ok = input(f"Approve {call.name}({call.arguments})? [y/N] ").strip().lower() == "y"
            answers.append(request.to_function_approval_response(ok))
        response = await agent.run(Message("user", answers), session=session)

    print("\nAgent:", response.text)
    print("Tickets now:", {t: v["status"] for t, v in crm.TICKETS.items()})


if __name__ == "__main__":
    asyncio.run(main())
