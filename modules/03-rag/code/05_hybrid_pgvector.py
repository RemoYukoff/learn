"""Hybrid search in plain PostgreSQL: full-text (tsvector) + pgvector, fused with RRF in SQL.

Needs the pgvector container from 04_vector_pgvector.py.
"""

import os

import psycopg
from pgvector.psycopg import register_vector

from rag_utils import EMBED_DIM, Embedder, all_chunks

DSN = os.environ.get("PGVECTOR_DSN", "postgresql://postgres:postgres@localhost:5433/postgres")
chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])
QUESTION = "What second factor is required to reach production?"

HYBRID_SQL = """
WITH semantic AS (
    SELECT id, RANK() OVER (ORDER BY embedding <=> %(qvec)s) AS rank
    FROM chunks ORDER BY embedding <=> %(qvec)s LIMIT 10
),
keyword AS (
    SELECT id, RANK() OVER (ORDER BY ts_rank_cd(tsv, query) DESC) AS rank
    -- plainto_tsquery ANDs every term; swapping & for | gives BM25-like OR semantics
    FROM chunks, to_tsquery('english', replace(plainto_tsquery('english', %(qtext)s)::text, ' & ', ' | ')) AS query
    WHERE tsv @@ query ORDER BY ts_rank_cd(tsv, query) DESC LIMIT 10
)
SELECT COALESCE(s.id, k.id) AS id,
       COALESCE(1.0 / (60 + s.rank), 0) + COALESCE(1.0 / (60 + k.rank), 0) AS rrf
FROM semantic s FULL OUTER JOIN keyword k ON s.id = k.id
ORDER BY rrf DESC LIMIT 3
"""

with psycopg.connect(DSN, autocommit=True) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    conn.execute("DROP TABLE IF EXISTS chunks")
    conn.execute(f"""CREATE TABLE chunks (
        id text PRIMARY KEY, content text NOT NULL, embedding vector({EMBED_DIM}) NOT NULL,
        tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED)""")
    conn.execute("CREATE INDEX ON chunks USING gin (tsv)")
    conn.execute("CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops)")
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO chunks (id, content, embedding) VALUES (%s, %s, %s)",
                        [(c.id, c.text, v) for c, v in zip(chunks, vectors)])

    rows = conn.execute(HYBRID_SQL, {"qvec": embedder.query(QUESTION), "qtext": QUESTION}).fetchall()
    print(f"Question: {QUESTION}\nRRF (full-text + vector) top 3:")
    for id_, score in rows:
        print(f"  rrf={float(score):.4f}  {id_}")
    conn.execute("DROP TABLE chunks")
