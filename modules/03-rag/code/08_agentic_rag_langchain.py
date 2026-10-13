"""Agentic RAG with LangChain create_agent: retrieval is just a tool.

The model decides when to search, what query to use, and whether to search
again (for example once per sub-question). Needs ANTHROPIC_API_KEY.
"""

import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from rag_utils import HybridRetriever

load_dotenv()
retriever = HybridRetriever()


@tool
def search_handbook(query: str) -> str:
    """Search the company handbook (refunds, SLA, on-call, incidents, API limits, security,
    data retention, pricing, expenses, support hours). Returns the 3 most relevant sections
    with their ids. Use short, specific queries; call it again for each sub-question."""
    return "\n\n".join(f"[{c.id}]\n{c.text}" for c in retriever.search(query, top=3))


agent = create_agent(
    ChatAnthropic(model="claude-opus-5-5", max_tokens=4096),
    tools=[search_handbook],
    system_prompt="You answer questions about the company handbook. Always search before answering "
    "and cite the section ids you used in brackets.",
)

question = sys.argv[1] if len(sys.argv) > 1 else (
    "An Enterprise customer had 99.95% uptime last month and wants a refund of 3,000 USD. "
    "Do they get SLA credits, and who has to approve the refund?"
)
result = agent.invoke({"messages": [{"role": "user", "content": question}]})
for msg in result["messages"]:
    for call in getattr(msg, "tool_calls", None) or []:
        print(f"  search_handbook({call['args']['query']!r})")
print("\n" + result["messages"][-1].text)
