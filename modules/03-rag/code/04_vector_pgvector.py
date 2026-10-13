"""pgvector: vectors as a column type in PostgreSQL.

Start Postgres with the extension (port 5433 to avoid clashing with a local Postgres):
    docker run -d --rm --name learn-pgvector -e POSTGRES_PASSWORD=postgres -p 5433:5432 pgvector/pgvector:0.8.7-pg18-trixie
"""

import os

import psycopg
from pgvector.psycopg import register_vector

from rag_utils import EMBED_DIM, Embedder, all_chunks

DSN = os.environ.get("PGVECTOR_DSN", "postgresql://postgres:postgres@localhost:5433/postgres")
chunks = all_chunks()
embedder = Embedder()
vectors = embedder.passages([c.text for c in chunks])

with psycopg.connect(DSN, autocommit=True) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)  # lets psycopg send/receive numpy arrays as vector
    conn.execute("DROP TABLE IF EXISTS handbook_chunks")
    conn.execute(f"""
        CREATE TABLE handbook_chunks (
            id text PRIMARY KEY,
            doc text NOT NULL,
            section text NOT NULL,
            content text NOT NULL,
            embedding vector({EMBED_DIM}) NOT NULL
        )""")
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO handbook_chunks (id, doc, section, content, embedding) VALUES (%s, %s, %s, %s, %s)",
            [(c.id, c.doc, c.section, c.text, v) for c, v in zip(chunks, vectors)],
        )
    # HNSW index for cosine distance; without it Postgres scans every row (exact search).
    conn.execute("CREATE INDEX ON handbook_chunks USING hnsw (embedding vector_cosine_ops)")
    print(f"pgvector table handbook_chunks: {len(chunks)} rows + HNSW index")

    q = embedder.query("Who approves a 3,500 USD refund?")
    rows = conn.execute(
        "SELECT id, section, embedding <=> %s AS distance FROM handbook_chunks ORDER BY distance LIMIT 3", (q,)
    ).fetchall()
    print("\nTop 3 (<=> is cosine distance):")
    for id_, section, dist in rows:
        print(f"  distance={dist:.3f}  {id_:<28} {section}")

    # Filters are plain SQL: combine with joins, tenants, permissions, dates...
    q = embedder.query("How much does an extra seat cost?")
    rows = conn.execute(
        "SELECT id FROM handbook_chunks WHERE doc = %s ORDER BY embedding <=> %s LIMIT 2", ("pricing.md", q)
    ).fetchall()
    print("\nFiltered to doc == pricing.md:", [r[0] for r in rows])
    conn.execute("DROP TABLE handbook_chunks")
