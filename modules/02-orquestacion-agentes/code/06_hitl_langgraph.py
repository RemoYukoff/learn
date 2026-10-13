"""Human-in-the-loop in LangGraph: interrupt() inside a sensitive tool, resume with Command.

Run: python 06_hitl_langgraph.py   (needs ANTHROPIC_API_KEY in .env, asks you y/n in the terminal)
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import Command, interrupt

import crm

load_dotenv()


@tool
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


@tool
def update_ticket_status(ticket_id: str, status: str) -> str:
    """Change a ticket status to open, pending or closed. Requires human approval."""
    # Execution stops here. The graph state is checkpointed and the run returns.
    decision = interrupt({"action": "update_ticket_status", "ticket_id": ticket_id, "status": status})
    # When resumed, the node runs again from the top and interrupt() returns the resume value.
    if decision != "approve":
        return f"A human rejected changing {ticket_id} to {status}. Do not retry."
    return crm.update_ticket_status(ticket_id, status)


TOOLS = [list_open_tickets, update_ticket_status]
model = ChatAnthropic(model="claude-opus-5-5", max_tokens=4096).bind_tools(TOOLS)


def agent(state: MessagesState) -> dict:
    return {"messages": [model.invoke(state["messages"])]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")
graph = builder.compile(checkpointer=InMemorySaver())  # interrupts need a checkpointer

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "hitl-demo"}}
    result = graph.invoke(
        {"messages": [("user", "Close every open ticket of customer C-001.")]}, config
    )
    # Each pending interrupt shows up under "__interrupt__" until it is resumed.
    while result.get("__interrupt__"):
        payload = result["__interrupt__"][0].value
        answer = input(f"Approve {payload}? [y/N] ").strip().lower()
        result = graph.invoke(Command(resume="approve" if answer == "y" else "reject"), config)

    print("\nAgent:", result["messages"][-1].text)
    print("Tickets now:", {t: v["status"] for t, v in crm.TICKETS.items()})
