"""CrewAI memory: one Memory object shared by the crew, recalled automatically between kickoffs.

Run (crewai venv): python 05_memory_crewai.py   (needs ANTHROPIC_API_KEY and OPENROUTER_API_KEY)

CrewAI memory needs an embedder (vector search) and an LLM that analyzes what to
store. Defaults are OpenAI; here the embedder goes through OpenRouter and the
analysis LLM is Claude.
"""

from __future__ import annotations

import os

from crewai import LLM, Agent, Crew, Task
from crewai.memory.unified_memory import Memory
from crewai.tools import tool
from dotenv import load_dotenv

import crm

load_dotenv()

llm = LLM(model="anthropic/claude-opus-5-5", max_tokens=4096)

memory = Memory(
    llm=llm,
    storage="./crew_memory.db",  # LanceDB folder (git-ignored by *.db); delete it to forget everything
    embedder={
        "provider": "openrouter",
        "config": {
            "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
            "model_name": "openai/text-embedding-3-small",
        },
    },
)


@tool("get_customer")
def get_customer(customer_id: str) -> str:
    """Get a customer record by id, e.g. C-001."""
    return crm.get_customer(customer_id)


@tool("list_open_tickets")
def list_open_tickets(customer_id: str) -> str:
    """List the open support tickets of a customer."""
    return crm.list_open_tickets(customer_id)


support = Agent(
    role="Support analyst",
    goal="Help the same user across several conversations",
    backstory="You remember what users told you before.",
    tools=[get_customer, list_open_tickets],
    llm=llm,
)


def run(question: str) -> None:
    task = Task(description=question, expected_output="A short answer.", agent=support)
    crew = Crew(agents=[support], tasks=[task], memory=memory)
    print(f"user: {question}\nbot:  {crew.kickoff().raw}\n")


if __name__ == "__main__":
    run("Remember that I always work with customer C-001 and I prefer answers in Spanish.")
    # A brand-new Crew and Task: only shared memory connects them.
    run("Which open tickets does my usual customer have?")

    print("Explicit recall:")
    for match in memory.recall("preferred language", limit=3):
        print(" -", match)
