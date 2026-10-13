"""Tool-calling agent as an explicit LangGraph graph: agent node + ToolNode + tools_condition.

Run: python 04_tools_langgraph.py   (needs ANTHROPIC_API_KEY in .env)
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

import crm

load_dotenv()


@tool
def get_customer(customer_id: str) -> str:
    """Get a customer record by id, e.g. C-001."""
    return crm.get_customer(customer_id)


@tool
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


TOOLS = [get_customer, list_open_tickets]

# temperature/top_p are not sent: claude-opus-5-5 rejects them.
model = ChatAnthropic(model="claude-opus-5-5", max_tokens=4096).bind_tools(TOOLS)


def agent(state: MessagesState) -> dict:
    """One model call. If it asks for tools, tools_condition routes to the ToolNode."""
    return {"messages": [model.invoke(state["messages"])]}


builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(TOOLS))  # runs every tool_call in the last AI message
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
builder.add_edge("tools", "agent")  # loop back with the tool results
graph = builder.compile()

if __name__ == "__main__":
    question = "Which open tickets does customer C-001 have, and what plan are they on?"
    print(f"User: {question}\n")
    # stream_mode="updates" prints one line per node so you can watch the loop.
    for update in graph.stream({"messages": [("user", question)]}, stream_mode="updates"):
        for node, payload in update.items():
            last = payload["messages"][-1]
            calls = getattr(last, "tool_calls", None)
            if calls:
                print(f"[{node}] tool calls: {[(c['name'], c['args']) for c in calls]}")
            else:
                print(f"[{node}] {last.text[:300]}")
