"""The smallest useful RAG: chunk, embed, retrieve top-k, answer with Claude.

Retrieval runs locally (no key needed). Generation needs ANTHROPIC_API_KEY;
without it the script stops after printing the retrieved context.
"""

import os
import sys

import anthropic
from dotenv import load_dotenv

from rag_utils import Embedder, all_chunks, cosine_top_k

load_dotenv()
QUESTION = sys.argv[1] if len(sys.argv) > 1 else "A customer was charged twice. Who has to approve the refund?"

# 1. Index (offline step): chunk the documents and embed every chunk once.
chunks = all_chunks()
embedder = Embedder()
matrix = embedder.passages([c.text for c in chunks])
print(f"Indexed {len(chunks)} chunks from {len({c.doc for c in chunks})} documents, dim={matrix.shape[1]}")

# 2. Retrieve (per question): embed the question, take the k most similar chunks.
hits = cosine_top_k(embedder.query(QUESTION), matrix, k=3)
print(f"\nQuestion: {QUESTION}\n")
for i, score in hits:
    print(f"  {score:.3f}  {chunks[i].id:<28} {chunks[i].section}")

if not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit("\nANTHROPIC_API_KEY not set: skipping generation.")

# 3. Generate: the retrieved text goes into the prompt, clearly separated from the question.
context = "\n\n".join(f'<source id="{chunks[i].id}">\n{chunks[i].text}\n</source>' for i, _ in hits)
response = anthropic.Anthropic().messages.create(
    model="claude-opus-5-5",
    max_tokens=1024,
    output_config={"effort": "low"},
    system="Answer using only the sources. If they do not contain the answer, say you don't know. "
    "Mention the source id you used.",
    messages=[{"role": "user", "content": f"{context}\n\nQuestion: {QUESTION}"}],
)
print("\n" + next(b.text for b in response.content if b.type == "text"))
