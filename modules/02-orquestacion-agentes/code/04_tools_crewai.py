"""Same agent in CrewAI: Agent (role/goal/backstory) + Task + Crew.

Run (crewai venv): python 04_tools_crewai.py   (needs ANTHROPIC_API_KEY in .env)
"""

from __future__ import annotations

from crewai import LLM, Agent, Crew, Task
from crewai.tools import tool
from dotenv import load_dotenv

import crm

load_dotenv()


@tool("get_customer")
def get_customer(customer_id: str) -> str:
    """Get a customer record by id, e.g. C-001."""
    return crm.get_customer(customer_id)


@tool("list_open_tickets")
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


# Native Anthropic provider (crewai[anthropic]). Keep two or more tools per agent:
# with exactly one tool CrewAI forces tool_choice, which claude-opus-5-5 rejects.
llm = LLM(model="anthropic/claude-opus-5-5", max_tokens=4096)

support = Agent(
    role="Support analyst",
    goal="Answer questions about customers using only CRM data",
    backstory="You work in a B2B support team and never guess customer data.",
    tools=[get_customer, list_open_tickets],
    llm=llm,
    verbose=True,
)

task = Task(
    description="{question}",
    expected_output="A short answer that lists ticket ids and the customer's plan.",
    agent=support,
)

crew = Crew(agents=[support], tasks=[task])

if __name__ == "__main__":
    question = "Which open tickets does customer C-001 have, and what plan are they on?"
    print(f"User: {question}\n")
    result = crew.kickoff(inputs={"question": question})
    print("\nFinal:", result.raw)
