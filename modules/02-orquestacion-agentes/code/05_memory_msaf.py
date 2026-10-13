"""Microsoft Agent Framework memory: AgentSession for the thread, a context provider for long-term facts.

Run (msaf venv): python 05_memory_msaf.py   (needs ANTHROPIC_API_KEY in .env)
"""

from __future__ import annotations

import asyncio

from agent_framework import Agent, InMemoryHistoryProvider
from agent_framework.anthropic import AnthropicClient
from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    agent = Agent(
        client=AnthropicClient(model="claude-opus-5-5"),
        instructions="You are a support assistant. Be brief.",
        # Default provider (added automatically when none is set): keeps the messages
        # in session.state, so they survive as long as you keep or serialize the session.
        # Swap for a Redis or Cosmos history provider to persist server-side.
        context_providers=[InMemoryHistoryProvider()],
        default_options={"max_tokens": 2048},
    )

    session = agent.create_session(session_id="ticket-1")
    for text in ("My customer id is C-001.", "What is my customer id?"):
        response = await agent.run(text, session=session)
        print(f"[ticket-1] user: {text}\n[ticket-1] bot:  {response.text}\n")

    other = agent.create_session(session_id="ticket-2")
    response = await agent.run("What is my customer id?", session=other)
    print(f"[ticket-2] bot: {response.text}  <- new session, no history\n")

    # The history lives inside the session: serialize it to save it between requests.
    saved = session.to_dict()
    print("serialized session keys:", list(saved))


if __name__ == "__main__":
    asyncio.run(main())
