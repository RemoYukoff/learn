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

Medido con el modelo local `bge-small-en-v1.5`:

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

Las dos familias que aparecen en la práctica: modelos por API (OpenAI es el más usado) y modelos abiertos de Hugging Face que corren en tu infraestructura.

> [!IMPORTANT]
> El modelo de embeddings es parte del índice. Si lo cambiás, tenés que reembeber **todo** el corpus: vectores de modelos distintos no son comparables. Guardá el nombre y versión del modelo junto al índice.

## Cómo se implementa

:::tabs
== OpenAI
Modelos por API: mandás textos y recibís vectores. `text-embedding-3-small` (1536 dimensiones) es el default razonable; `text-embedding-3-large` (3072) da algo más de calidad a más costo. Ambos permiten pedir menos dimensiones con `dimensions`.

```python
from openai import OpenAI

client = OpenAI()
response = client.embeddings.create(
    model="text-embedding-3-small",
    input=["Refunds above 2,000 USD need approval from the finance director.",
           "Big reimbursements must be signed off by the head of finance."],
)
vectors = [d.embedding for d in response.data]       # one list[float] per input, same order
print(len(vectors[0]), response.usage.prompt_tokens)
```

Se cobra por token de entrada y se embebe en lotes (decenas o cientos de textos por request).
== Hugging Face
Modelos abiertos con la librería `sentence-transformers`: corren en tu máquina o tu servidor, sin enviar datos afuera. `encode_query` y `encode_document` aplican el formato que cada modelo espera para preguntas y pasajes.

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")      # 384 dimensions
docs = model.encode_document([
    "Refunds above 2,000 USD need approval from the finance director.",
    "The finance director approves the annual budget in December.",
])
query = model.encode_query(["who approves large refunds?"])
print(model.similarity(query, docs))                        # cosine similarity matrix, shape (1, 2)
```
:::

## Errores comunes

- Embeber la pregunta como pasaje (o al revés) en modelos que distinguen.
- Mezclar vectores de dos modelos en el mismo índice.
- Chunks más largos que el máximo del modelo: se truncan sin aviso.
- Confiar en embeddings para buscar códigos, IDs o números exactos.
- Elegir el modelo por el primer puesto de un benchmark sin medir con tus datos.

## Preguntas de repaso

- **¿Qué es un embedding?** Una representación vectorial del significado de un texto, donde textos similares quedan cerca según una métrica como coseno.
- **¿Cómo elegís un modelo de embeddings?** Por calidad medida en mis datos e idioma, dimensiones, largo máximo, costo y si puede correr local. MTEB sirve para preseleccionar.
- **¿Qué pasa si cambiás el modelo de embeddings?** Hay que reindexar todo: los vectores de modelos distintos viven en espacios distintos.
- **¿Por qué no alcanza con embeddings?** Fallan con términos exactos, números y negaciones; se complementa con búsqueda léxica (BM25) y reranking.
