"""Grounded answers with citations using Anthropic search_result blocks.

Each retrieved chunk goes in as a `search_result` content block (source, title,
text). With citations enabled, Claude's answer comes back split into text
blocks, and the cited ones carry the exact passage and its source.
Retrieval is local; generation needs ANTHROPIC_API_KEY.
"""

import os
import sys

import anthropic
from dotenv import load_dotenv

from rag_utils import Embedder, all_chunks, cosine_top_k

load_dotenv()
QUESTION = sys.argv[1] if len(sys.argv) > 1 else "Our CFO wants money back for a 3,500 USD charge. Who signs off, and could they get credits instead?"

chunks = all_chunks()
embedder = Embedder()
hits = cosine_top_k(embedder.query(QUESTION), embedder.passages([c.text for c in chunks]), k=4)
print(f"Retrieved: {[chunks[i].id for i, _ in hits]}")
if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("ANTHROPIC_API_KEY not set: skipping generation.")

search_results = [
    {
        "type": "search_result",
        "source": f"handbook/{chunks[i].id}",
        "title": f"{chunks[i].doc} - {chunks[i].section}",
        "content": [{"type": "text", "text": chunks[i].text}],
        "citations": {"enabled": True},  # all search results must agree: all enabled or none
    }
    for i, _ in hits
]

response = anthropic.Anthropic().messages.create(
    model="claude-opus-5-5",
    max_tokens=2048,
    output_config={"effort": "low"},
    system="Answer only from the provided search results. If they are not enough, say what is missing.",
    messages=[{"role": "user", "content": [*search_results, {"type": "text", "text": QUESTION}]}],
)

print(f"\nQuestion: {QUESTION}\n")
footnotes: list[str] = []
for block in response.content:
    if block.type != "text":
        continue
    marks = ""
    for cit in block.citations or []:
        footnotes.append(f"[{len(footnotes) + 1}] {cit.source}: \"{cit.cited_text.strip()[:90]}\"")
        marks += f"[{len(footnotes)}]"
    print(block.text + marks, end="")
print("\n\n" + "\n".join(footnotes))
