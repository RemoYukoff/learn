---
title: Embeddings
order: 3
type: implementacion
---

**Objetivo:** saber qué captura un embedding, qué no, y cómo elegir y usar un modelo de embeddings.

## Idea

Un **embedding** es un vector de números (cientos o miles) que representa el significado de un texto. Textos con significado parecido quedan cerca en ese espacio. Buscar = embeber la pregunta y encontrar los vectores más cercanos.

### Similitud

| Métrica | Qué mide | Nota |
|---|---|---|
| Coseno | Ángulo entre vectores | La más usada. Ignora la longitud |
| Producto interno | Ángulo × longitudes | Con vectores normalizados es igual al coseno, y más rápido |
| Euclídea (L2) | Distancia en línea recta | Con vectores normalizados ordena igual que coseno |

Usá la métrica con la que se entrenó el modelo (casi siempre coseno) y configurá la base vectorial con la misma.

### Qué captura y qué no

Captura **significado**: "big reimbursements must be signed off by the head of finance" queda cerca de "refunds above 2,000 USD need approval from the finance director" aunque compartan pocas palabras.

Le cuesta:

- **Identificadores y códigos exactos** (`X-Northwind-Signature`, números de factura, SKUs).
- **Números y negaciones** ("más de 200" vs "menos de 200" quedan casi iguales).
- **Palabras compartidas con distinto sentido**: una frase con las mismas palabras pero otro tema puede quedar casi tan cerca como una paráfrasis real.

Lo medido en `code/03_embeddings.py` con `bge-small-en-v1.5`:

| Frase comparada con "Refunds above 2,000 USD need approval from the finance director" | Coseno |
|---|---|
| Paráfrasis: "Big reimbursements must be signed off by the head of finance" | 0.743 |
| Mismas palabras, otro tema: "The finance director approves the annual budget in December" | 0.718 |
| Sin relación: "Webhook deliveries carry an X-Northwind-Signature header" | 0.465 |

La paráfrasis gana, pero por poco. Por eso se combina con búsqueda por palabras (capítulo 5) y se rerankea.

### Elegir un modelo

| Criterio | Qué mirar |
|---|---|
| Calidad en tu dominio e idioma | Benchmarks (MTEB) como filtro inicial, después medir con tus preguntas |
| Dimensiones | Más dimensiones = más memoria y almacenamiento. Muchos modelos permiten truncar (Matryoshka) |
| Largo máximo de entrada | Chunks más largos que el límite se truncan en silencio |
| Local vs API | Local: sin costo por token, sin enviar datos afuera, necesitás CPU/GPU. API: mejor calidad, latencia de red |
| Query vs documento | Muchos modelos embeben distinto la pregunta y el pasaje (prefijos o `input_type`). Usarlo mal baja el recall |

Anthropic no tiene modelo de embeddings propio y recomienda **Voyage AI**. OpenRouter expone Voyage y otros modelos con la API de embeddings compatible con OpenAI.

> [!IMPORTANT]
> El modelo de embeddings es parte del índice. Si lo cambiás, tenés que reembeber **todo** el corpus: vectores de modelos distintos no son comparables. Guardá el nombre y versión del modelo junto al índice.

## Cómo se implementa

:::tabs
== FastEmbed
Modelos ONNX que corren en CPU, sin API key. Bueno para desarrollo, datos sensibles y volumen alto.

```python
from fastembed import TextEmbedding

model = TextEmbedding("BAAI/bge-small-en-v1.5")          # 384 dims, ~70 MB
passages = list(model.passage_embed(["Refunds above 2,000 USD need..."]))
query = next(iter(model.query_embed("who approves large refunds?")))  # adds the query instruction
```

`passage_embed` y `query_embed` existen porque los modelos BGE esperan un prefijo distinto para preguntas. Los ejemplos lo encapsulan en `rag_utils.Embedder`.
== OpenRouter
La API de embeddings compatible con OpenAI, con modelos de Voyage, Google, NVIDIA y otros. Necesita `OPENROUTER_API_KEY`.

```python
from openai import OpenAI

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
response = client.embeddings.create(model="voyageai/voyage-4-lite", input=sentences)
vectors = [d.embedding for d in response.data]
print(len(vectors[0]), response.usage.prompt_tokens)
```

Se cobra por token de entrada, como un LLM pero mucho más barato. Embebé en lotes (decenas o cientos de textos por request).
:::

Ejemplo con ambos: `code/03_embeddings.py`

## Errores comunes

- Embeber la pregunta como pasaje (o al revés) en modelos que distinguen.
- Mezclar vectores de dos modelos en el mismo índice.
- Chunks más largos que el máximo del modelo: se truncan sin aviso.
- Confiar en embeddings para buscar códigos, IDs o números exactos.
- Elegir el modelo por el primer puesto de un benchmark sin medir con tus datos.

## En una entrevista

- **¿Qué es un embedding?** Una representación vectorial del significado de un texto, donde textos similares quedan cerca según una métrica como coseno.
- **¿Cómo elegís un modelo de embeddings?** Por calidad medida en mis datos e idioma, dimensiones, largo máximo, costo y si puede correr local. MTEB sirve para preseleccionar.
- **¿Qué pasa si cambiás el modelo de embeddings?** Hay que reindexar todo: los vectores de modelos distintos viven en espacios distintos.
- **¿Por qué no alcanza con embeddings?** Fallan con términos exactos, números y negaciones; se complementa con búsqueda léxica (BM25) y reranking.
