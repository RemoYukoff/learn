"""Human-in-the-loop with LangChain's HumanInTheLoopMiddleware on create_agent.

Run: python 06_hitl_langchain.py   (needs ANTHROPIC_API_KEY in .env, asks you in the terminal)
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

import crm

load_dotenv()


@tool
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


@tool
def update_ticket_status(ticket_id: str, status: str) -> str:
    """Change a ticket status to open, pending or closed."""
    return crm.update_ticket_status(ticket_id, status)


agent = create_agent(
    model=ChatAnthropic(model="claude-opus-5-5", max_tokens=4096),
    tools=[list_open_tickets, update_ticket_status],
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "update_ticket_status": {"allowed_decisions": ["approve", "edit", "reject"]},
                "list_open_tickets": False,  # read-only: never ask
            }
        )
    ],
    checkpointer=InMemorySaver(),
)

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "hitl-lc"}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Set ticket T-101 to pending."}]}, config
    )
    while result.get("__interrupt__"):
        request = result["__interrupt__"][0].value  # HITLRequest
        decisions = []
        for action in request["action_requests"]:
            answer = input(f"{action['name']}({action['args']})  [a]pprove / [r]eject / [e]dit to closed: ").strip().lower()
            if answer == "a":
                decisions.append({"type": "approve"})
            elif answer == "e":
                edited = {"name": action["name"], "args": {**action["args"], "status": "closed"}}
                decisions.append({"type": "edit", "edited_action": edited})
            else:
                decisions.append({"type": "reject", "message": "Not now, waiting for the customer."})
        # One decision per action, in the same order.
        result = agent.invoke(Command(resume={"decisions": decisions}), config)

    print("\nAgent:", result["messages"][-1].text)
    print("Tickets now:", {t: v["status"] for t, v in crm.TICKETS.items()})
