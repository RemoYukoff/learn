"""Pinecone: managed, serverless vector database (needs PINECONE_API_KEY, free tier available).

Uses the Pinecone SDK 10 "document index" API: the index declares a schema of
fields (a dense vector, optionally full-text fields), and every record is a
JSON document. The older dimension=/index.upsert()/index.query() style still
works but is deprecated.
"""

import os
import time

from dotenv import load_dotenv
from pinecone import DenseVectorQuery, Pinecone

from rag_utils import EMBED_DIM, Embedder, all_chunks

load_dotenv()
pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
NAME, NS = "handbook", "v1"  # namespaces split one index per tenant or per version

chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

if pc.indexes.exists(NAME):
    pc.indexes.delete(NAME)
pc.indexes.create(  # blocks until the index is ready
    name=NAME,
    schema={
        "fields": {
            "embedding": {"type": "dense_vector", "dimension": EMBED_DIM, "metric": "cosine"},
            "content": {"type": "string", "full_text_search": {}},  # enables BM25-style text search (chapter 5)
        }
    },
    deployment={"deployment_type": "managed", "cloud": "aws", "region": "us-east-1"},
)
index = pc.index(NAME)

# Fields not declared in the schema (doc, section) are stored as filterable metadata.
index.documents.upsert(
    namespace=NS,
    documents=[
        {"_id": c.id, "embedding": v.tolist(), "content": c.text, "doc": c.doc, "section": c.section}
        for c, v in zip(chunks, vectors)
    ],
)
time.sleep(5)  # upserts apply asynchronously
print(f"Pinecone index '{NAME}': {len(chunks)} documents upserted")

res = index.documents.search(
    namespace=NS,
    top_k=3,
    score_by=[DenseVectorQuery(field="embedding", values=embedder.query("Who approves a 3,500 USD refund?").tolist())],
    include_fields=["section"],
)
print("\nTop 3:")
for doc in res.matches:
    print(f"  score={doc.score:.3f}  {doc.id:<28} {doc.get('section')}")

res = index.documents.search(
    namespace=NS,
    top_k=2,
    score_by=[DenseVectorQuery(field="embedding", values=embedder.query("How much does an extra seat cost?").tolist())],
    filter={"doc": {"$eq": "pricing.md"}},  # MongoDB-style operators: $eq, $in, $gt, $and...
)
print("\nFiltered to doc == pricing.md:", [d.id for d in res.matches])
pc.indexes.delete(NAME)
