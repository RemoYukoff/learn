"""Hybrid search in Pinecone (SDK 10 document index): two searches fused client-side.

A dense_vector clause must stand alone in score_by, so you run a BM25 text
search and a vector search over the same index and merge them with RRF.
Needs PINECONE_API_KEY.
"""

import os
import time

from dotenv import load_dotenv
from pinecone import DenseVectorQuery, Pinecone, TextQuery

from rag_utils import EMBED_DIM, Embedder, all_chunks

load_dotenv()
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
NAME, NS = "handbook-hybrid", "v1"
QUESTION = "What second factor is required to reach production?"

chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

if pc.indexes.exists(NAME):
    pc.indexes.delete(NAME)
pc.indexes.create(
    name=NAME,
    schema={"fields": {
        "embedding": {"type": "dense_vector", "dimension": EMBED_DIM, "metric": "cosine"},
        "content": {"type": "string", "full_text_search": {"language": "en", "stemming": True, "stop_words": True}},
    }},
    deployment={"deployment_type": "managed", "cloud": "aws", "region": "us-east-1"},
)
index = pc.index(NAME)
index.documents.upsert(namespace=NS, documents=[
    {"_id": c.id, "embedding": v.tolist(), "content": c.text} for c, v in zip(chunks, vectors)
])
time.sleep(5)

keyword = index.documents.search(namespace=NS, top_k=10, score_by=[TextQuery(query=QUESTION, fields=["content"])])
semantic = index.documents.search(
    namespace=NS, top_k=10, score_by=[DenseVectorQuery(field="embedding", values=embedder.query(QUESTION).tolist())]
)

scores: dict[str, float] = {}
for result in (keyword, semantic):
    for rank, doc in enumerate(result.matches, 1):
        scores[doc.id] = scores.get(doc.id, 0.0) + 1 / (60 + rank)
print(f"Question: {QUESTION}\nRRF top 3: {sorted(scores, key=scores.get, reverse=True)[:3]}")
pc.indexes.delete(NAME)
