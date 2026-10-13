"""Shared helpers for the RAG examples.

- load_docs():      the fictional company handbook in data/*.md
- chunk_markdown(): heading-aware chunks with metadata (doc, section)
- Embedder:         local embeddings with FastEmbed (no API key, runs on CPU)
- load_questions(): labeled questions used to evaluate retrieval

The first run downloads the embedding model (~70 MB) to the FastEmbed cache.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # 384 dimensions, good quality/size trade-off for English
EMBED_DIM = 384


@dataclass
class Chunk:
    id: str
    doc: str
    section: str
    text: str
    meta: dict = field(default_factory=dict)


def load_docs() -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted(DATA.glob("*.md"))}


def chunk_markdown(doc: str, text: str) -> list[Chunk]:
    """One chunk per `##` section. The document title is prepended to every chunk
    so a chunk still makes sense on its own (contextual header)."""
    title = re.search(r"^# (.+)$", text, re.M).group(1)
    parts = re.split(r"^## ", text, flags=re.M)
    chunks = [Chunk(f"{doc}#0", doc, title, parts[0].strip())]
    for i, part in enumerate(parts[1:], 1):
        heading, _, body = part.partition("\n")
        chunks.append(Chunk(f"{doc}#{i}", doc, heading.strip(), f"# {title}\n## {heading.strip()}\n{body.strip()}"))
    return [c for c in chunks if len(c.text) > 20]


def all_chunks() -> list[Chunk]:
    return [c for doc, text in load_docs().items() for c in chunk_markdown(doc, text)]


def load_questions() -> list[dict]:
    return json.loads((DATA / "questions.json").read_text())


class Embedder:
    """Thin wrapper over FastEmbed. Passages and queries are embedded differently:
    bge models expect an instruction prefix on queries, which query_embed adds."""

    def __init__(self, model: str = EMBED_MODEL) -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model)

    def passages(self, texts: list[str]) -> np.ndarray:
        return np.array(list(self.model.passage_embed(texts)), dtype=np.float32)

    def query(self, text: str) -> np.ndarray:
        return np.array(next(iter(self.model.query_embed(text))), dtype=np.float32)


def cosine_top_k(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    """Brute-force cosine similarity. Fine up to ~100k vectors; beyond that use an index."""
    q = query / np.linalg.norm(query)
    m = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    scores = m @ q
    top = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in top]


class HybridRetriever:
    """Dense + BM25 fused with RRF, then reranked with a cross-encoder (see chapter 5).
    Used by the agentic examples so they focus on orchestration, not retrieval."""

    def __init__(self, k: int = 10) -> None:
        import bm25s
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self.k = k
        self.chunks = all_chunks()
        self.texts = [c.text for c in self.chunks]
        self.embedder = Embedder()
        self.matrix = self.embedder.passages(self.texts)
        self._bm25s = bm25s
        self.bm25 = bm25s.BM25()
        self.bm25.index(bm25s.tokenize(self.texts, stopwords="en", show_progress=False), show_progress=False)
        self.reranker = TextCrossEncoder("Xenova/ms-marco-MiniLM-L-6-v2")

    def search(self, query: str, top: int = 3) -> list[Chunk]:
        dense = [i for i, _ in cosine_top_k(self.embedder.query(query), self.matrix, self.k)]
        ids, _ = self.bm25.retrieve(self._bm25s.tokenize([query], stopwords="en", show_progress=False), k=self.k, show_progress=False)
        scores: dict[int, float] = {}
        for ranking in (dense, [int(i) for i in ids[0]]):
            for rank, i in enumerate(ranking, 1):
                scores[i] = scores.get(i, 0.0) + 1 / (60 + rank)
        candidates = sorted(scores, key=scores.get, reverse=True)[: self.k]
        rerank = list(self.reranker.rerank(query, [self.texts[i] for i in candidates]))
        best = [i for _, i in sorted(zip(rerank, candidates), reverse=True)[:top]]
        return [self.chunks[i] for i in best]
