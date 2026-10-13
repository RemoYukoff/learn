"""Supervisor pattern in LangGraph/LangChain: specialist agents exposed to a supervisor as tools.

Run: python 07_multiagent_langgraph.py   (needs ANTHROPIC_API_KEY in .env)

Each specialist is a full agent (its own prompt, tools and loop). The supervisor
only sees two tools, decides who works, and writes the final answer. The
specialists' intermediate messages never reach the supervisor's context.
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

import crm

load_dotenv()

model = ChatAnthropic(model="claude-opus-5-5", max_tokens=4096)


@tool
def get_customer(customer_id: str) -> str:
    """Get a customer record by id."""
    return crm.get_customer(customer_id)


@tool
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


accounts_agent = create_agent(
    model, tools=[get_customer], system_prompt="You answer questions about customer accounts and plans.",
    name="accounts",
)
tickets_agent = create_agent(
    model, tools=[list_open_tickets], system_prompt="You answer questions about support tickets.",
    name="tickets",
)


@tool
def ask_accounts(task: str) -> str:
    """Delegate a question about a customer's account or plan to the accounts specialist."""
    result = accounts_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return result["messages"][-1].text


@tool
def ask_tickets(task: str) -> str:
    """Delegate a question about support tickets to the tickets specialist."""
    result = tickets_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return result["messages"][-1].text


supervisor = create_agent(
    model,
    tools=[ask_accounts, ask_tickets],
    system_prompt=(
        "You coordinate specialists. Split the request, delegate each part with a "
        "self-contained task, then write one combined answer."
    ),
    name="supervisor",
)

if __name__ == "__main__":
    question = "Prepare a short briefing on customer C-001: plan, country and open tickets."
    print(f"User: {question}\n")
    for update in supervisor.stream({"messages": [{"role": "user", "content": question}]}, stream_mode="updates"):
        for node, payload in update.items():
            if not payload or "messages" not in payload:
                continue
            last = payload["messages"][-1]
            calls = getattr(last, "tool_calls", None)
            print(f"[{node}] " + (f"delegates {[(c['name'], c['args']['task']) for c in calls]}" if calls else last.text[:400]))
