"""Microsoft Agent Framework orchestrations: sequential pipeline and concurrent fan-out.

Run (msaf venv): python 07_multiagent_msaf.py   (needs ANTHROPIC_API_KEY in .env)

Other builders in agent_framework.orchestrations: HandoffBuilder (agents pass
control to each other), GroupChatBuilder (orchestrator picks the next speaker)
and MagenticBuilder (manager with a task ledger; the AutoGen Magentic-One design).
"""

from __future__ import annotations

import asyncio

from agent_framework import Agent
from agent_framework.anthropic import AnthropicClient
from agent_framework.orchestrations import ConcurrentBuilder, SequentialBuilder
from dotenv import load_dotenv

load_dotenv()


def make_agent(name: str, instructions: str) -> Agent:
    return Agent(
        client=AnthropicClient(model="claude-opus-5-5"),
        name=name,
        instructions=instructions,
        default_options={"max_tokens": 2048},
    )


def print_outputs(title: str, outputs: list) -> None:
    print(f"\n=== {title}")
    for output in outputs:
        messages = output if isinstance(output, list) else [output]
        for msg in messages:
            author = getattr(msg, "author_name", None) or getattr(msg, "role", "")
            print(f"[{author}] {getattr(msg, 'text', msg)}")


async def main() -> None:
    task = "Customer C-001 (enterprise plan) reports that SSO login fails for new users."

    # Sequential: each agent sees the conversation so far and adds its turn.
    triager = make_agent("triager", "Classify the issue: area, severity (low/medium/high), one line.")
    responder = make_agent("responder", "Write a 3-line reply to the customer based on the triage.")
    sequential = SequentialBuilder(participants=[triager, responder]).build()
    print_outputs("sequential", (await sequential.run(task)).get_outputs())

    # Concurrent: same input to every agent in parallel, results aggregated.
    security = make_agent("security", "Assess security impact in two lines.")
    support = make_agent("support", "Suggest a workaround in two lines.")
    concurrent = ConcurrentBuilder(participants=[security, support]).build()
    print_outputs("concurrent", (await concurrent.run(task)).get_outputs())


if __name__ == "__main__":
    asyncio.run(main())
