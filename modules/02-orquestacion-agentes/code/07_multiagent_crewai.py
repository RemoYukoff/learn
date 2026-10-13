"""CrewAI multi-agent: a sequential crew, or a hierarchical one with a manager LLM.

Run (crewai venv):
  python 07_multiagent_crewai.py                 # Process.sequential
  python 07_multiagent_crewai.py --hierarchical  # Process.hierarchical (manager delegates)
Needs ANTHROPIC_API_KEY in .env.
"""

from __future__ import annotations

import sys

from crewai import LLM, Agent, Crew, Process, Task
from crewai.tools import tool
from dotenv import load_dotenv

import crm

load_dotenv()

llm = LLM(model="anthropic/claude-opus-5-5", max_tokens=4096)


@tool("get_customer")
def get_customer(customer_id: str) -> str:
    """Get a customer record by id."""
    return crm.get_customer(customer_id)


@tool("list_open_tickets")
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


analyst = Agent(
    role="CRM analyst",
    goal="Collect accurate facts about a customer from the CRM",
    backstory="You only report what the CRM tools return.",
    tools=[get_customer, list_open_tickets],
    llm=llm,
)
writer = Agent(
    role="Account manager",
    goal="Write short, actionable customer briefings",
    backstory="You turn raw facts into a briefing a busy manager can read in 20 seconds.",
    llm=llm,
)

collect = Task(
    description="Collect plan, country and open tickets for customer {customer_id}.",
    expected_output="A bullet list of facts.",
    agent=analyst,
)
brief = Task(
    description="Write a 3-line briefing for customer {customer_id} from the collected facts.",
    expected_output="Three lines of plain text.",
    agent=writer,
    context=[collect],  # explicit data dependency between tasks
)

if __name__ == "__main__":
    hierarchical = "--hierarchical" in sys.argv
    crew = Crew(
        agents=[analyst, writer],
        tasks=[collect, brief],
        process=Process.hierarchical if hierarchical else Process.sequential,
        # hierarchical: a manager agent plans, delegates tasks and validates results
        manager_llm=llm if hierarchical else None,
        verbose=True,
    )
    print(f"Process: {crew.process.value}\n")
    print("\nFinal:", crew.kickoff(inputs={"customer_id": "C-001"}).raw)
