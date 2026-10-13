"""Elasticsearch: full-text search engine with dense_vector fields and kNN search.

Start a single local node without security:
    docker run -d --rm --name learn-es -p 9200:9200 -e discovery.type=single-node \
      -e xpack.security.enabled=false -e ES_JAVA_OPTS="-Xms512m -Xmx512m" \
      docker.elastic.co/elasticsearch/elasticsearch:9.5.5
"""

import os

from elasticsearch import Elasticsearch, helpers

from rag_utils import EMBED_DIM, Embedder, all_chunks

es = Elasticsearch(os.environ.get("ES_URL", "http://localhost:9200"))
INDEX = "handbook"
chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

es.options(ignore_status=404).indices.delete(index=INDEX)
es.indices.create(
    index=INDEX,
    mappings={
        "properties": {
            "doc": {"type": "keyword"},
            "section": {"type": "text"},
            "content": {"type": "text"},  # analyzed for BM25 (used in chapter 5)
            "embedding": {"type": "dense_vector", "dims": EMBED_DIM, "index": True, "similarity": "cosine"},
        }
    },
)
helpers.bulk(
    es,
    ({"_index": INDEX, "_id": c.id, "doc": c.doc, "section": c.section, "content": c.text, "embedding": v.tolist()}
     for c, v in zip(chunks, vectors)),
    refresh=True,
)
print(f"Elasticsearch index '{INDEX}': {es.count(index=INDEX)['count']} docs")

res = es.search(
    index=INDEX,
    knn={"field": "embedding", "query_vector": embedder.query("Who approves a 3,500 USD refund?").tolist(), "k": 3, "num_candidates": 50},
    source=["section"],
)
print("\nTop 3:")
for hit in res["hits"]["hits"]:
    print(f"  score={hit['_score']:.3f}  {hit['_id']:<28} {hit['_source']['section']}")

res = es.search(
    index=INDEX,
    knn={
        "field": "embedding",
        "query_vector": embedder.query("How much does an extra seat cost?").tolist(),
        "k": 2,
        "num_candidates": 50,
        "filter": {"term": {"doc": "pricing.md"}},  # pre-filter: applied during the kNN search
    },
    source=False,
)
print("\nFiltered to doc == pricing.md:", [h["_id"] for h in res["hits"]["hits"]])
es.indices.delete(index=INDEX)
