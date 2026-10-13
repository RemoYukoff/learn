"""Milvus: open-source vector database built for very large scale.

Milvus Lite runs embedded from a local file (no server), same client API as a
Milvus cluster or Zilliz Cloud: change the URI and nothing else.
"""

import os

from pymilvus import MilvusClient

from rag_utils import EMBED_DIM, Embedder, all_chunks

URI = os.environ.get("MILVUS_URI", "./milvus_handbook.db")  # or http://localhost:19530
chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

client = MilvusClient(URI)
if client.has_collection("handbook"):
    client.drop_collection("handbook")
# Quick-setup collection: int primary key "id", vector field "vector", dynamic fields for the rest.
client.create_collection("handbook", dimension=EMBED_DIM, metric_type="COSINE")
client.insert(
    "handbook",
    [
        {"id": i, "vector": v.tolist(), "chunk_id": c.id, "doc": c.doc, "section": c.section, "text": c.text}
        for i, (c, v) in enumerate(zip(chunks, vectors))
    ],
)
print(f"Milvus collection 'handbook': {client.get_collection_stats('handbook')['row_count']} rows")

res = client.search(
    "handbook",
    data=[embedder.query("Who approves a 3,500 USD refund?").tolist()],
    limit=3,
    output_fields=["chunk_id", "section"],
)
print("\nTop 3:")
for hit in res[0]:
    print(f"  score={hit['distance']:.3f}  {hit['entity']['chunk_id']:<28} {hit['entity']['section']}")

res = client.search(
    "handbook",
    data=[embedder.query("How much does an extra seat cost?").tolist()],
    limit=2,
    filter='doc == "pricing.md"',  # boolean expression language
    output_fields=["chunk_id"],
)
print("\nFiltered to doc == pricing.md:", [h["entity"]["chunk_id"] for h in res[0]])
client.drop_collection("handbook")
client.close()
