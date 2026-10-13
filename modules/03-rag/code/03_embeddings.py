"""What embeddings capture and what they miss.

Local part (FastEmbed, no key): similarity between paraphrases, unrelated
sentences and exact identifiers. OpenRouter part (needs OPENROUTER_API_KEY):
the same sentences with Voyage 4, the embedding family Anthropic recommends.
"""

import os

import numpy as np
from dotenv import load_dotenv

from rag_utils import Embedder

load_dotenv()

SENTENCES = [
    "Refunds above 2,000 USD need approval from the finance director.",  # 0 reference
    "Big reimbursements must be signed off by the head of finance.",  # 1 paraphrase, few shared words
    "The finance director approves the annual budget in December.",  # 2 shares words, different meaning
    "Webhook deliveries carry an X-Northwind-Signature header.",  # 3 unrelated
    "X-Northwind-Signature",  # 4 bare identifier
]


def similarity_table(vectors: np.ndarray, label: str) -> None:
    v = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    sims = v @ v.T
    print(f"\n{label}: cosine similarity with sentence 0")
    for i in range(1, len(SENTENCES)):
        print(f"  [{i}] {sims[0, i]:.3f}  {SENTENCES[i]}")
    print(f"  identifier [4] vs sentence [3]: {sims[3, 4]:.3f}")


local = Embedder()
vectors = local.passages(SENTENCES)
print(f"FastEmbed {local.model.model_name}: {vectors.shape[0]} vectors of {vectors.shape[1]} floats")
similarity_table(vectors, "FastEmbed (local)")

# Query vs passage embedding: bge models add an instruction to queries.
q = local.query("who approves large refunds?")
p = local.passages([SENTENCES[0]])[0]
print(f"\nquery_embed vs passage_embed of the reference: {float(q @ p / np.linalg.norm(q) / np.linalg.norm(p)):.3f}")

if os.environ.get("OPENROUTER_API_KEY"):
    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    response = client.embeddings.create(model="voyageai/voyage-4-lite", input=SENTENCES)
    remote = np.array([d.embedding for d in response.data], dtype=np.float32)
    print(f"\nvoyage-4-lite via OpenRouter: dim={remote.shape[1]} tokens={response.usage.prompt_tokens}")
    similarity_table(remote, "Voyage 4 lite")
else:
    print("\nOPENROUTER_API_KEY not set: skipping the Voyage comparison.")
