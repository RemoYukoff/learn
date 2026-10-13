"""Native hybrid search in Elasticsearch: BM25 + kNN in one request.

Two ways to fuse:
  - query + knn in the same search: scores are added (weighted with boost). Free (basic license).
  - the `rrf` retriever: rank-based fusion. Needs an Enterprise license or a trial;
    to try it locally add -e xpack.license.self_generated.type=trial to docker run.
Needs the Elasticsearch container from 04_vector_elasticsearch.py.
"""

import os

from elasticsearch import AuthorizationException, Elasticsearch, helpers

from rag_utils import EMBED_DIM, Embedder, all_chunks

es = Elasticsearch(os.environ.get("ES_URL", "http://localhost:9200"))
INDEX = "handbook_hybrid"
chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

es.options(ignore_status=404).indices.delete(index=INDEX)
es.indices.create(index=INDEX, mappings={"properties": {
    "content": {"type": "text", "analyzer": "english"},
    "embedding": {"type": "dense_vector", "dims": EMBED_DIM, "similarity": "cosine"},
}})
helpers.bulk(es, ({"_index": INDEX, "_id": c.id, "content": c.text, "embedding": v.tolist()} for c, v in zip(chunks, vectors)), refresh=True)

QUESTION = "What second factor is required to reach production?"  # dense alone ranks the answer 9th
qvec = embedder.query(QUESTION).tolist()

# 1. Linear combination: final score = 0.3 * BM25 score + 0.7 * kNN similarity
res = es.search(
    index=INDEX,
    query={"match": {"content": {"query": QUESTION, "boost": 0.3}}},
    knn={"field": "embedding", "query_vector": qvec, "k": 10, "num_candidates": 50, "boost": 0.7},
    size=3,
    source=False,
)
print(f"Question: {QUESTION}\nquery + knn (weighted sum) top 3:")
for hit in res["hits"]["hits"]:
    print(f"  score={hit['_score']:.3f}  {hit['_id']}")

# 2. Reciprocal Rank Fusion with retrievers (licensed feature)
try:
    res = es.search(
        index=INDEX,
        retriever={"rrf": {
            "retrievers": [
                {"standard": {"query": {"match": {"content": QUESTION}}}},
                {"knn": {"field": "embedding", "query_vector": qvec, "k": 10, "num_candidates": 50}},
            ],
            "rank_window_size": 10,
            "rank_constant": 60,
        }},
        size=3,
        source=False,
    )
    print("RRF retriever top 3:", [h["_id"] for h in res["hits"]["hits"]])
except AuthorizationException as e:
    print(f"RRF retriever not available on this license: {e.message}")
es.indices.delete(index=INDEX)
