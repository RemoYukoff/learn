---
title: Búsqueda híbrida y reranking
order: 5
type: implementacion
---

**Objetivo:** combinar búsqueda semántica y por palabras, y reordenar los candidatos con un reranker, sabiendo cuánto aporta cada paso.

## Idea

### Dos formas de buscar que fallan distinto

| | Densa (embeddings) | Léxica (BM25) |
|---|---|---|
| Encuentra | Paráfrasis, sinónimos, la idea | Términos exactos, códigos, nombres, números |
| Falla con | `X-Northwind-Signature`, SKUs, "SEV1" | "me despertaron tres noches" cuando el documento dice "page between 22:00 and 07:00" |

**BM25** es el algoritmo clásico de buscadores: puntúa un documento por cuántas veces aparecen los términos de la consulta, pesando más los términos raros en el corpus y normalizando por largo. No necesita modelo ni GPU.

En el corpus de prueba del módulo, cada una falla en preguntas distintas (rank de la evidencia, `-` = no está en el top 10):

| Pregunta | Densa | BM25 |
|---|---|---|
| "Uptime was 99.7% on Starter. How much credit…" | 1 | - |
| "Can I store an API key in our Git repository…" | 1 | - |
| "I got woken up by alerts three nights in a row…" | - | 1 |
| "What second factor is required to reach production?" | 9 | 1 |

### Búsqueda híbrida

Correr las dos y **fusionar** los rankings:

- **Reciprocal Rank Fusion (RRF)**: `score(d) = Σ 1 / (k + rank_i(d))`, con `k = 60` típico. Solo usa posiciones, así que no hay que normalizar scores que viven en escalas distintas. Es el default razonable.
- **Combinación lineal**: normalizar ambos scores y sumarlos con peso (`alpha`). Permite ajustar cuánto pesa cada lado, pero hay que calibrarlo.

### Reranking

Los embeddings comparan vectores calculados **por separado** (bi-encoder). Un **cross-encoder** lee pregunta y chunk **juntos** y devuelve un score de relevancia. Es mucho más preciso y mucho más lento, así que se usa en dos etapas:

```text
retrieval barato (híbrida, top 20–100)  ──▶  reranker caro (cross-encoder)  ──▶  top 3–5 al LLM
```

Opciones: cross-encoders abiertos de Hugging Face, APIs de reranking, o un LLM que ordena (caro, útil con pocos candidatos).

### Qué aporta cada paso (medido)

Medido sobre el corpus de prueba del módulo (10 documentos cortos de un handbook ficticio y 22 preguntas etiquetadas), con BM25, embeddings densos de un modelo abierto chico (bge-small-en-v1.5), RRF con k=60 y un cross-encoder chico (ms-marco-MiniLM-L-6-v2) sobre los 10 primeros candidatos:

| Estrategia | hit@1 | hit@3 | hit@10 | MRR |
|---|---|---|---|---|
| Densa | 0.82 | 0.91 | 0.95 | 0.85 |
| BM25 | 0.73 | 0.86 | 0.91 | 0.80 |
| Híbrida (RRF) | 0.73 | 0.91 | **1.00** | 0.83 |
| Híbrida + rerank | 0.77 | **0.95** | **1.00** | **0.86** |

Lectura honesta: la híbrida **sube el recall** (nada queda afuera del top 10) pero puede bajar la evidencia del primer puesto; el reranker recupera precisión arriba, a cambio de bastante más latencia por consulta.

### RRF y reranking en código

RRF no necesita ninguna librería: solo las posiciones de cada ranking.

```python
def rrf(*rankings: list[str], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, 1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)

candidates = rrf(dense_ids, keyword_ids)[:20]
```

El reranker es un cross-encoder de Hugging Face que puntúa cada par pregunta–chunk:

```python
from sentence_transformers import CrossEncoder

reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
texts = [chunk_text[i] for i in candidates]
ranked = reranker.rank(question, texts, top_k=3)        # [{"corpus_id": 4, "score": 8.1}, ...]
best = [candidates[r["corpus_id"]] for r in ranked]
```

## Cómo se implementa

Varias bases hacen la híbrida de forma nativa. Mismo ejemplo en todas: "What second factor is required to reach production?", que la búsqueda densa sola deja en el puesto 9. Con híbrida, el chunk de la política de seguridad que tiene la respuesta sale primero en Weaviate, pgvector y Elasticsearch (las tres medidas). `question` es el texto de la pregunta y `qvec` su embedding.

:::tabs
== Pinecone
En un document index, un campo `string` con `full_text_search` habilita BM25. Una cláusula vectorial va sola en `score_by`, así que hacés dos búsquedas y fusionás con RRF en el cliente.

```python
schema = {"fields": {
    "embedding": {"type": "dense_vector", "dimension": 384, "metric": "cosine"},
    "content": {"type": "string", "full_text_search": {"language": "en", "stemming": True, "stop_words": True}},
}}

keyword = index.documents.search(namespace="v1", top_k=10,
                                 score_by=[TextQuery(query=question, fields=["content"])])
semantic = index.documents.search(namespace="v1", top_k=10,
                                  score_by=[DenseVectorQuery(field="embedding", values=qvec)])
scores = {}
for result in (keyword, semantic):
    for rank, doc in enumerate(result.matches, 1):
        scores[doc.id] = scores.get(doc.id, 0) + 1 / (60 + rank)
```

== Weaviate
`query.hybrid` ejecuta BM25 y vector y los fusiona. `alpha` va de 0 (solo BM25) a 1 (solo vector).

```python
res = col.query.hybrid(
    query=question,                 # BM25 side
    vector=qvec,                    # vector side
    alpha=0.5,
    fusion_type=HybridFusion.RELATIVE_SCORE,   # or RANKED (RRF-like)
    limit=3,
)
```

Medido: `alpha=0` y `alpha=0.5` ponen el chunk correcto primero; `alpha=1` (solo vector) no lo trae en el top 3.

== pgvector
Full-text de Postgres (`tsvector` + índice GIN) y pgvector en la misma tabla, fusionados con RRF en una query.

```sql
ALTER TABLE chunks ADD COLUMN tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
CREATE INDEX ON chunks USING gin (tsv);

WITH semantic AS (
  SELECT id, RANK() OVER (ORDER BY embedding <=> :qvec) AS rank
  FROM chunks ORDER BY embedding <=> :qvec LIMIT 10
), keyword AS (
  SELECT id, RANK() OVER (ORDER BY ts_rank_cd(tsv, q) DESC) AS rank
  FROM chunks, to_tsquery('english', replace(plainto_tsquery('english', :qtext)::text, ' & ', ' | ')) q
  WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 10
)
SELECT COALESCE(s.id, k.id) AS id,
       COALESCE(1.0/(60+s.rank), 0) + COALESCE(1.0/(60+k.rank), 0) AS rrf
FROM semantic s FULL OUTER JOIN keyword k USING (id)
ORDER BY rrf DESC LIMIT 3;
```

El lado léxico busca con OR entre términos (como BM25), por eso el `replace(' & ', ' | ')` sobre la consulta de texto.

== Elasticsearch
Dos opciones en una sola request:

```python
# 1) query + knn: weighted sum of both scores
es.search(index=INDEX,
          query={"match": {"content": {"query": question, "boost": 0.3}}},
          knn={"field": "embedding", "query_vector": qvec, "k": 10, "num_candidates": 50, "boost": 0.7},
          size=3)

# 2) rrf retriever: rank fusion
es.search(index=INDEX, size=3, retriever={"rrf": {
    "retrievers": [
        {"standard": {"query": {"match": {"content": question}}}},
        {"knn": {"field": "embedding", "query_vector": qvec, "k": 10, "num_candidates": 50}},
    ],
    "rank_window_size": 10, "rank_constant": 60,
}})
```


:::

## Errores comunes

- Sumar scores de BM25 y coseno sin normalizar: viven en escalas distintas y uno domina.
- Rerankear solo el top 3: el reranker no puede subir lo que no está entre los candidatos. Dale 20–100.
- Agregar un reranker sin medir latencia: en CPU puede multiplicar el tiempo por consulta.
- Full-text en el idioma equivocado (stemming en inglés sobre texto en español).

## En una entrevista

- **¿Qué es búsqueda híbrida y por qué usarla?** Combinar búsqueda semántica y léxica. Los embeddings fallan con términos exactos y BM25 con paráfrasis; juntos suben el recall.
- **¿Qué es RRF?** Reciprocal Rank Fusion: suma `1/(k + rank)` de cada ranking. Fusiona sin normalizar scores.
- **¿Qué es un reranker y dónde va?** Un cross-encoder que puntúa pregunta y documento juntos. Va después del retrieval, sobre decenas de candidatos, para elegir los pocos que llegan al LLM.
- **¿Bi-encoder vs cross-encoder?** Bi-encoder embebe por separado y permite indexar (rápido, menos preciso). Cross-encoder procesa el par (preciso, no indexable, caro).
