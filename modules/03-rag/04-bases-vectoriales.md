---
title: Bases vectoriales
order: 4
type: implementacion
---

**Objetivo:** entender qué hace una base vectorial por dentro, cómo elegir una, y usar las siete que aparecen en las búsquedas con el mismo ejemplo.

## Idea

Una base vectorial guarda vectores con su metadata y responde "dame los k más cercanos a este vector", rápido, con filtros, y soportando altas, bajas y cambios.

### Búsqueda exacta vs aproximada (ANN)

Comparar la pregunta contra cada vector (**fuerza bruta**) da el resultado exacto y alcanza hasta cientos de miles de vectores. Más allá se usan índices **ANN** (approximate nearest neighbors) que sacrifican un poco de recall por velocidad.

| Índice | Cómo funciona | Trade-off |
|---|---|---|
| **HNSW** | Grafo por capas: se navega de nodos lejanos a cercanos | El default en casi todas. Rápido y con recall alto; usa mucha memoria. Parámetros: `M` (conexiones), `ef_construction`, `ef_search` |
| **IVF** | Agrupa vectores en clusters y busca solo en los más cercanos | Menos memoria; recall depende de cuántos clusters revisás (`nprobe`) |
| **Cuantización (PQ, SQ, binaria)** | Comprime los vectores | Mucha menos memoria, algo de recall. Se combina con las anteriores |
| **DiskANN** | Grafo en disco | Escalas de miles de millones con poca RAM |

### Filtros sobre metadata

Casi siempre buscás "lo más parecido **dentro de** este cliente / idioma / fecha / permiso". Hay dos estrategias:

- **Post-filtering**: buscar top-k y después filtrar. Si el filtro es restrictivo, te quedás con 0 resultados.
- **Pre-filtering / filtered search**: el filtro se aplica durante la búsqueda. Es lo que hacen bien las bases modernas.

Multi-tenancy (un índice para muchos clientes) es un filtro más, o namespaces / particiones separadas. Es requisito habitual en productos B2B.

### Comparación

| | Tipo | Hosting | Fuerte en | Cuándo |
|---|---|---|---|---|
| **Pinecone** | Base vectorial | Solo managed (serverless) | Cero operación, escala, namespaces | Querés no operar nada |
| **Chroma** | Base vectorial | Embebida, server o cloud | Simplicidad, prototipos | Desarrollo, apps chicas |
| **Weaviate** | Base vectorial | Self-hosted o cloud | Híbrida nativa, módulos de embeddings, multi-tenancy | Producto con búsqueda rica |
| **pgvector** | Extensión de Postgres | Donde tengas Postgres | SQL, joins, transacciones, un sistema menos | Ya usás Postgres (muy común) |
| **FAISS** | Librería de índices | En tu proceso | Velocidad, control fino de índices | Batch, investigación, construir tu propio servicio |
| **Milvus** | Base vectorial distribuida | Lite embebido, cluster o Zilliz Cloud | Escala enorme, GPU | Miles de millones de vectores |
| **Elasticsearch** | Motor de búsqueda con vectores | Self-hosted o Elastic Cloud | Full-text maduro + vectores + filtros | Ya tenés ES, o la búsqueda léxica pesa mucho |

> [!TIP]
> En una entrevista, "¿qué base vectorial usarías?" casi nunca tiene respuesta única. Una buena respuesta: "pgvector si ya hay Postgres y el volumen es moderado; Pinecone o Weaviate si quiero managed o híbrida nativa; FAISS para batch". Y mencionar que el retrieval se mide igual en todas.

## Cómo se implementa

Todos los scripts hacen lo mismo: crear la colección para 384 dimensiones con coseno, cargar los 37 chunks con metadata (`doc`, `section`), buscar "Who approves a 3,500 USD refund?" y repetir otra búsqueda filtrando `doc == "pricing.md"`. Los seis que corren localmente (todos menos Pinecone, que necesita cuenta) devuelven el mismo top 3, con `refunds.md#1` (Approval rules) primero.

:::tabs
== Pinecone
Pinecone SDK 10 usa **document indexes**: declarás un schema de campos y cada registro es un documento JSON. Los campos no declarados quedan como metadata filtrable. (El estilo anterior `dimension=` + `index.upsert`/`index.query` sigue funcionando pero está deprecado.)

```python
from pinecone import DenseVectorQuery, Pinecone

pc = Pinecone()   # PINECONE_API_KEY
pc.indexes.create(
    name="handbook",
    schema={"fields": {"embedding": {"type": "dense_vector", "dimension": 384, "metric": "cosine"}}},
    deployment={"deployment_type": "managed", "cloud": "aws", "region": "us-east-1"},
)
index = pc.index("handbook")
index.documents.upsert(namespace="v1", documents=[
    {"_id": c.id, "embedding": v.tolist(), "doc": c.doc, "section": c.section} for c, v in zip(chunks, vectors)
])
res = index.documents.search(
    namespace="v1", top_k=3,
    score_by=[DenseVectorQuery(field="embedding", values=query_vector)],
    filter={"doc": {"$eq": "pricing.md"}},
    include_fields=["section"],
)
for doc in res.matches:
    print(doc.id, doc.score, doc.get("section"))
```

Los upserts son asincrónicos: un documento puede tardar unos segundos en aparecer. Los **namespaces** separan tenants o versiones dentro de un índice.

Ejemplo: `code/04_vector_pinecone.py` (necesita cuenta; hay free tier)
== Chroma
Embebida en tu proceso y persistida en una carpeta. Cero infraestructura.

```python
import chromadb

client = chromadb.PersistentClient(path="./chroma_data")
col = client.get_or_create_collection("handbook", configuration={"hnsw": {"space": "cosine"}})
col.upsert(
    ids=[c.id for c in chunks],
    embeddings=vectors.tolist(),
    documents=[c.text for c in chunks],
    metadatas=[{"doc": c.doc, "section": c.section} for c in chunks],
)
res = col.query(query_embeddings=[query_vector], n_results=3, where={"doc": "pricing.md"})
print(res["ids"][0], res["distances"][0])
```

Chroma también puede embeber por vos si le pasás `documents` sin `embeddings` (usa un modelo por defecto). Es cómodo, pero fijá el modelo explícitamente en producción.

Ejemplo: `code/04_vector_chroma.py`
== Weaviate
Schema con propiedades tipadas. Podés traer tus vectores (`self_provided`) o configurar un vectorizador para que Weaviate embeba solo.

```python
import weaviate
from weaviate.classes.config import Configure, DataType, Property, VectorDistances
from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter

with weaviate.connect_to_local() as client:
    col = client.collections.create(
        "Handbook",
        properties=[Property(name="doc", data_type=DataType.TEXT), Property(name="content", data_type=DataType.TEXT)],
        vector_config=Configure.Vectors.self_provided(
            vector_index_config=Configure.VectorIndex.hnsw(distance_metric=VectorDistances.COSINE)),
    )
    col.data.insert_many([DataObject(properties={"doc": c.doc, "content": c.text}, vector=v.tolist())
                          for c, v in zip(chunks, vectors)])
    res = col.query.near_vector(near_vector=query_vector, limit=3,
                                filters=Filter.by_property("doc").equal("pricing.md"))
```

```sh
docker run -d --rm --name learn-weaviate -p 8080:8080 -p 50051:50051 \
  -e DEFAULT_VECTORIZER_MODULE=none -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  cr.weaviate.io/semitechnologies/weaviate:1.40.1
```

Ejemplo: `code/04_vector_weaviate.py`
== pgvector
Un tipo de columna `vector(n)` en Postgres. La búsqueda es SQL con el operador `<=>` (distancia coseno), y los filtros son `WHERE` comunes.

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE handbook_chunks (
  id text PRIMARY KEY, doc text, section text, content text,
  embedding vector(384) NOT NULL
);
CREATE INDEX ON handbook_chunks USING hnsw (embedding vector_cosine_ops);

SELECT id, embedding <=> $1 AS distance
FROM handbook_chunks
WHERE doc = 'pricing.md'
ORDER BY embedding <=> $1
LIMIT 3;
```

```python
import psycopg
from pgvector.psycopg import register_vector

with psycopg.connect(DSN, autocommit=True) as conn:
    register_vector(conn)            # numpy arrays <-> vector
    rows = conn.execute("SELECT id FROM handbook_chunks ORDER BY embedding <=> %s LIMIT 3", (query_vector,)).fetchall()
```

Operadores: `<->` L2, `<#>` producto interno negativo, `<=>` coseno. El índice tiene que usar el mismo (`vector_cosine_ops` para `<=>`). Ventaja enorme: joins con tus tablas, transacciones y permisos en el mismo lugar.

```sh
docker run -d --rm --name learn-pgvector -e POSTGRES_PASSWORD=postgres -p 5433:5432 pgvector/pgvector:0.8.7-pg18-trixie
```

Ejemplo: `code/04_vector_pgvector.py`
== FAISS
Una librería de índices (Meta), no una base: guarda vectores y devuelve **posiciones**. Ids, texto, metadata y persistencia son tuyos.

```python
import faiss

faiss.normalize_L2(vectors)                       # unit vectors: inner product == cosine
index = faiss.IndexHNSWFlat(384, 32, faiss.METRIC_INNER_PRODUCT)
index.add(vectors)

q = query_vector.reshape(1, -1); faiss.normalize_L2(q)
scores, positions = index.search(q, 3)            # positions into your own chunks list

# filter: pass the allowed positions
allowed = np.array([i for i, c in enumerate(chunks) if c.doc == "pricing.md"])
params = faiss.SearchParameters(sel=faiss.IDSelectorArray(allowed))
scores, positions = index.search(q, 3, params=params)
faiss.write_index(index, "handbook.faiss")
```

Ejemplo: `code/04_vector_faiss.py`
== Milvus
Base distribuida para escala muy grande. **Milvus Lite** corre embebido desde un archivo con el mismo cliente: cambiás la URI y pasás a un cluster o a Zilliz Cloud.

```python
from pymilvus import MilvusClient

client = MilvusClient("./milvus_handbook.db")   # or "http://localhost:19530"
client.create_collection("handbook", dimension=384, metric_type="COSINE")
client.insert("handbook", [
    {"id": i, "vector": v.tolist(), "chunk_id": c.id, "doc": c.doc} for i, (c, v) in enumerate(zip(chunks, vectors))
])
res = client.search("handbook", data=[query_vector], limit=3,
                    filter='doc == "pricing.md"', output_fields=["chunk_id"])
for hit in res[0]:
    print(hit["entity"]["chunk_id"], hit["distance"])
```

Ejemplo: `code/04_vector_milvus.py`
== Elasticsearch
Un motor de búsqueda full-text con campos `dense_vector` y búsqueda kNN. Si la empresa ya lo usa, suele ser la opción natural.

```python
from elasticsearch import Elasticsearch, helpers

es = Elasticsearch("http://localhost:9200")
es.indices.create(index="handbook", mappings={"properties": {
    "doc": {"type": "keyword"},
    "content": {"type": "text"},
    "embedding": {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"},
}})
helpers.bulk(es, ({"_index": "handbook", "_id": c.id, "doc": c.doc, "content": c.text, "embedding": v.tolist()}
                  for c, v in zip(chunks, vectors)), refresh=True)
res = es.search(index="handbook", knn={
    "field": "embedding", "query_vector": query_vector, "k": 3, "num_candidates": 50,
    "filter": {"term": {"doc": "pricing.md"}},
})
```

`num_candidates` es cuántos vecinos explora el HNSW por shard: más = mejor recall, más lento.

```sh
docker run -d --rm --name learn-es -p 9200:9200 -e discovery.type=single-node \
  -e xpack.security.enabled=false -e ES_JAVA_OPTS="-Xms512m -Xmx512m" \
  docker.elastic.co/elasticsearch/elasticsearch:9.5.5
```

Ejemplo: `code/04_vector_elasticsearch.py`
:::

## Errores comunes

- Configurar la colección con una métrica y el modelo con otra (L2 vs coseno sin normalizar).
- Post-filtering con filtros restrictivos: la búsqueda devuelve 3 resultados y el filtro los elimina a todos.
- No guardar el texto ni la metadata junto al vector (en FAISS, perder el mapeo posición → chunk).
- Reindexar sin versionar: mezclar chunks de dos estrategias o dos modelos.
- Elegir un sistema distribuido para 50.000 vectores.

## En una entrevista

- **¿Cómo funciona HNSW?** Un grafo jerárquico de vecinos: se entra por capas con pocos nodos y se baja refinando hacia los más cercanos. Da búsqueda aproximada con recall alto y latencia baja a cambio de memoria.
- **¿Qué es ANN y por qué no búsqueda exacta?** Búsqueda aproximada de vecinos: con millones de vectores la exacta es demasiado lenta; ANN pierde un poco de recall a cambio de órdenes de magnitud de velocidad.
- **¿pgvector o una base vectorial dedicada?** pgvector si ya hay Postgres y el volumen es moderado: un sistema menos, SQL, joins y transacciones. Dedicada para escala muy grande, híbrida avanzada o cero operación.
- **¿Cómo manejás multi-tenancy?** Filtro por tenant en cada búsqueda (pre-filtering) o namespaces/particiones por tenant, más control de acceso en la capa de aplicación.
