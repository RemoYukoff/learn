"""Native hybrid search in Weaviate: BM25 + vector with a single `alpha` knob.

alpha=0 is pure BM25, alpha=1 is pure vector. Needs the Weaviate container from 04_vector_weaviate.py.
"""

import weaviate
from weaviate.classes.config import Configure, DataType, Property
from weaviate.classes.data import DataObject
from weaviate.classes.query import HybridFusion

from rag_utils import Embedder, all_chunks

chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])
QUESTION = "What second factor is required to reach production?"

with weaviate.connect_to_local() as client:
    client.collections.delete("HandbookHybrid")
    col = client.collections.create(
        "HandbookHybrid",
        properties=[Property(name="chunk_id", data_type=DataType.TEXT), Property(name="content", data_type=DataType.TEXT)],
        vector_config=Configure.Vectors.self_provided(),
    )
    col.data.insert_many([DataObject(properties={"chunk_id": c.id, "content": c.text}, vector=v.tolist()) for c, v in zip(chunks, vectors)])

    print(f"Question: {QUESTION}")
    for alpha in (0.0, 0.5, 1.0):
        res = col.query.hybrid(
            query=QUESTION,  # used for BM25
            vector=embedder.query(QUESTION).tolist(),  # used for the vector side
            alpha=alpha,
            fusion_type=HybridFusion.RELATIVE_SCORE,  # normalizes both score sets, then weights them
            limit=3,
        )
        print(f"  alpha={alpha}: {[o.properties['chunk_id'] for o in res.objects]}")
    client.collections.delete("HandbookHybrid")
