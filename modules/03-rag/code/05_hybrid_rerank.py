"""Hybrid search and reranking, built by hand so every step is visible.

1. Dense retrieval (embeddings) and sparse retrieval (BM25) over the same chunks
2. Reciprocal Rank Fusion (RRF) merges both rankings without comparing scores
3. A cross-encoder reranks the fused top candidates
For each labeled question prints the rank of the chunk that holds the evidence.
Runs offline (downloads two small models on first run).
"""

import bm25s
from fastembed.rerank.cross_encoder import TextCrossEncoder

from rag_utils import Embedder, all_chunks, cosine_top_k, load_questions

K = 10  # candidates per retriever
chunks = all_chunks()
texts = [c.text for c in chunks]

embedder = Embedder()
matrix = embedder.passages(texts)

bm25 = bm25s.BM25()
bm25.index(bm25s.tokenize(texts, stopwords="en", show_progress=False), show_progress=False)

reranker = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")


def dense(q: str) -> list[int]:
    return [i for i, _ in cosine_top_k(embedder.query(q), matrix, K)]


def sparse(q: str) -> list[int]:
    ids, _ = bm25.retrieve(bm25s.tokenize([q], stopwords="en", show_progress=False), k=K, show_progress=False)
    return [int(i) for i in ids[0]]


def rrf(*rankings: list[int], k: int = 60) -> list[int]:
    """score(d) = sum over rankings of 1 / (k + rank). Only ranks matter, not raw scores."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, i in enumerate(ranking, 1):
            scores[i] = scores.get(i, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)


def rerank(q: str, candidates: list[int]) -> list[int]:
    """A cross-encoder reads question and chunk together: slower, much more precise."""
    scores = list(reranker.rerank(q, [texts[i] for i in candidates]))
    return [i for _, i in sorted(zip(scores, candidates), reverse=True)]


def rank_of(evidence: str, ranking: list[int]) -> str:
    return next((str(n) for n, i in enumerate(ranking, 1) if evidence in texts[i]), "-")


print(f"{'dense':>5} {'bm25':>5} {'rrf':>5} {'rerank':>6}  question")
for q in load_questions():
    d, s = dense(q["question"]), sparse(q["question"])
    fused = rrf(d, s)
    reranked = rerank(q["question"], fused[:K])
    ranks = [rank_of(q["evidence"], r) for r in (d, s, fused, reranked)]
    print(f"{ranks[0]:>5} {ranks[1]:>5} {ranks[2]:>5} {ranks[3]:>6}  {q['question'][:58]}")
print("\nrank = position of the chunk containing the evidence ('-' = not in the top 10)")
