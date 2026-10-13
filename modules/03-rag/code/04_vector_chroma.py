"""Chroma: embedded vector DB (in-process, persisted to a folder). No server needed.

Same flow in every 04_vector_*.py: create a collection, load the chunks with
their vectors and metadata, search, search with a metadata filter, clean up.
"""

import shutil

import chromadb

from rag_utils import Embedder, all_chunks

PATH = "./chroma_data"
chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

client = chromadb.PersistentClient(path=PATH)
collection = client.get_or_create_collection("handbook", configuration={"hnsw": {"space": "cosine"}})
collection.upsert(
    ids=[c.id for c in chunks],
    embeddings=vectors.tolist(),
    documents=[c.text for c in chunks],
    metadatas=[{"doc": c.doc, "section": c.section} for c in chunks],
)
print(f"Chroma collection 'handbook': {collection.count()} vectors")

q = embedder.query("Who approves a 3,500 USD refund?").tolist()
res = collection.query(query_embeddings=[q], n_results=3, include=["metadatas", "distances"])
print("\nTop 3:")
for id_, meta, dist in zip(res["ids"][0], res["metadatas"][0], res["distances"][0]):
    print(f"  distance={dist:.3f}  {id_:<28} {meta['section']}")

q = embedder.query("How much does an extra seat cost?").tolist()
res = collection.query(query_embeddings=[q], n_results=2, where={"doc": "pricing.md"})
print("\nFiltered to doc == pricing.md:", res["ids"][0])

client.delete_collection("handbook")
shutil.rmtree(PATH, ignore_errors=True)
