"""FAISS: a vector index library, not a database.

It stores vectors and returns positions. Ids, text and metadata live in your
own structures, and so does filtering. Shows an exact index and an HNSW index.
"""

import faiss
import numpy as np

from rag_utils import EMBED_DIM, Embedder, all_chunks

chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])
faiss.normalize_L2(vectors)  # with unit vectors, inner product == cosine similarity

exact = faiss.IndexFlatIP(EMBED_DIM)  # brute force, 100% recall
exact.add(vectors)
hnsw = faiss.IndexHNSWFlat(EMBED_DIM, 32, faiss.METRIC_INNER_PRODUCT)  # approximate, graph based
hnsw.hnsw.efSearch = 64
hnsw.add(vectors)
print(f"FAISS: {exact.ntotal} vectors in IndexFlatIP and IndexHNSWFlat")


def search(index: faiss.Index, question: str, k: int = 3, params=None) -> list[tuple[str, float]]:
    q = embedder.query(question).reshape(1, -1)
    faiss.normalize_L2(q)
    scores, ids = index.search(q, k, params=params)
    return [(chunks[i].id, float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]


for name, index in (("exact", exact), ("hnsw", hnsw)):
    print(f"\n{name} top 3:")
    for cid, score in search(index, "Who approves a 3,500 USD refund?"):
        print(f"  score={score:.3f}  {cid}")

# Metadata filter: FAISS only knows positions, so you pass the allowed ids.
allowed = np.array([i for i, c in enumerate(chunks) if c.doc == "pricing.md"], dtype=np.int64)
params = faiss.SearchParameters(sel=faiss.IDSelectorArray(allowed))
print("\nFiltered to doc == pricing.md:", [cid for cid, _ in search(exact, "How much does an extra seat cost?", 2, params)])

faiss.write_index(hnsw, "handbook.faiss")  # persisting is a file you manage
print("Saved index to handbook.faiss (remember to save your id -> chunk mapping too)")
