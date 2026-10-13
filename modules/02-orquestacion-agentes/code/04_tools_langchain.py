"""Same agent with LangChain's create_agent (a prebuilt LangGraph graph).

Run: python 04_tools_langchain.py   (needs ANTHROPIC_API_KEY in .env)
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

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


agent = create_agent(
    model=ChatAnthropic(model="claude-opus-5-5", max_tokens=4096),
    tools=[get_customer, list_open_tickets],
    system_prompt="You are a support assistant. Use the CRM tools; never invent data.",
)

if __name__ == "__main__":
    question = "Which open tickets does customer C-001 have, and what plan are they on?"
    print(f"User: {question}\n")
    result = agent.invoke({"messages": [{"role": "user", "content": question}]})
    for msg in result["messages"]:
        calls = getattr(msg, "tool_calls", None)
        label = f"tool calls {[c['name'] for c in calls]}" if calls else msg.text[:300]
        print(f"[{msg.type}] {label}")
