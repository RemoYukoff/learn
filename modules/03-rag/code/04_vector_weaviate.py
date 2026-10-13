"""Weaviate: open-source vector database with its own schema, filters and hybrid search.

Start it:
    docker run -d --rm --name learn-weaviate -p 8080:8080 -p 50051:50051 \
      -e DEFAULT_VECTORIZER_MODULE=none -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
      cr.weaviate.io/semitechnologies/weaviate:1.40.1
"""

import weaviate
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter, MetadataQuery

from rag_utils import Embedder, all_chunks

chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

with weaviate.connect_to_local() as client:
    client.collections.delete("Handbook")
    handbook = client.collections.create(
        "Handbook",
        properties=[
            Property(name="chunk_id", data_type=DataType.TEXT),
            Property(name="doc", data_type=DataType.TEXT),
            Property(name="section", data_type=DataType.TEXT),
            Property(name="content", data_type=DataType.TEXT),
        ],
        # We bring our own vectors. Weaviate can also embed for you with a vectorizer module.
        vector_config=Configure.Vectors.self_provided(
            vector_index_config=Configure.VectorIndex.hnsw(distance_metric=VectorDistances.COSINE)
        ),
    )
    handbook.data.insert_many([
        DataObject(properties={"chunk_id": c.id, "doc": c.doc, "section": c.section, "content": c.text}, vector=v.tolist())
        for c, v in zip(chunks, vectors)
    ])
    print(f"Weaviate collection 'Handbook': {len(handbook)} objects")

    res = handbook.query.near_vector(
        near_vector=embedder.query("Who approves a 3,500 USD refund?").tolist(),
        limit=3,
        return_metadata=MetadataQuery(distance=True),
    )
    print("\nTop 3:")
    for o in res.objects:
        print(f"  distance={o.metadata.distance:.3f}  {o.properties['chunk_id']:<28} {o.properties['section']}")

    res = handbook.query.near_vector(
        near_vector=embedder.query("How much does an extra seat cost?").tolist(),
        limit=2,
        filters=Filter.by_property("doc").equal("pricing.md"),
    )
    print("\nFiltered to doc == pricing.md:", [o.properties["chunk_id"] for o in res.objects])
    client.collections.delete("Handbook")
