---
title: Qué es RAG y cuándo conviene
order: 1
type: concepto
---

**Objetivo:** entender las piezas de un sistema RAG, por qué existe y cuándo conviene otra cosa.

## Idea

Un LLM sabe lo que vio en su entrenamiento. No sabe nada de tu empresa, de lo que pasó ayer ni de los documentos de un cliente. **Retrieval-Augmented Generation** resuelve eso en dos tiempos:

1. **Retrieval**: buscar los fragmentos de tus documentos relevantes para la pregunta.
2. **Generation**: pasarle esos fragmentos al modelo junto con la pregunta y pedirle que responda usándolos.

El modelo no aprende nada. Le das, en cada llamada, el material para que responda. Es un open-book exam.

### Las piezas

```text
 INDEXADO (offline, cuando cambian los documentos)
 documentos ─▶ parsear ─▶ chunking ─▶ embeddings ─▶ vector store (+ índice de texto)

 CONSULTA (online, por pregunta)
 pregunta ─▶ (reescribir) ─▶ buscar top-k ─▶ (rerankear) ─▶ prompt con contexto ─▶ LLM ─▶ respuesta con citas
```

| Pieza | Qué decide | Capítulo |
|---|---|---|
| Chunking | En qué unidades se parte cada documento | 2 |
| Embeddings | Cómo se convierte texto en vectores comparables | 3 |
| Vector store | Dónde se guardan y cómo se buscan rápido | 4 |
| Híbrida y reranking | Cómo combinar significado y palabras exactas, y ordenar mejor | 5 |
| Evaluación | Cómo saber si encuentra lo correcto | 6 |
| Generación con citas | Cómo responder solo con lo recuperado y mostrar de dónde sale | 7 |
| RAG agéntico | Cuándo el modelo decide qué y cuántas veces buscar | 8 |

### Por qué RAG y no otra cosa

| Alternativa | Cuándo gana | Cuándo pierde |
|---|---|---|
| **Pegar todo en el prompt** | Pocos documentos que entran holgados en el contexto (los modelos actuales tienen 1M tokens). Con prompt caching es barato | Corpus grande o que cambia; costo y latencia por consulta; la calidad baja con mucho ruido |
| **RAG** | Corpus grande, cambiante, con permisos por usuario, y cuando necesitás citar fuentes | Preguntas que requieren leer todo el corpus ("¿qué tienen en común todos los contratos?") |
| **Fine-tuning** | Enseñar formato, estilo o una tarea | Enseñar hechos: los aprende mal, no se actualizan y no se pueden citar |
| **Tools / SQL** | Datos estructurados (pedidos, métricas) | Texto libre |

Regla práctica: si los documentos entran en el contexto con margen, probá primero **sin RAG** y con caching. Si no entran, cambian seguido, o necesitás filtrar por permisos, RAG.

### Dónde falla un RAG

Casi todos los problemas son de **retrieval**, no del modelo:

- El fragmento correcto **no se recupera** (chunking malo, embeddings que no capturan códigos o números, falta de búsqueda por palabras).
- Se recupera pero **muy abajo** y queda fuera del top-k.
- Se recuperan fragmentos **parecidos pero equivocados** (el "crédito" de la política de reembolsos vs el "crédito" del SLA) y el modelo mezcla.
- El modelo **ignora el contexto** y responde de memoria, o completa lo que falta inventando.

Por eso el módulo pone tanto peso en medir el retrieval (capítulo 6) antes de tocar el prompt.

### El corpus de los ejemplos

Todos los scripts usan el handbook ficticio de "Northwind Cloud" en `code/data/`: diez documentos cortos (reembolsos, SLA, on-call, precios, seguridad...) y 22 preguntas etiquetadas con la frase que contiene la respuesta. Hay preguntas fáciles, preguntas con códigos exactos (`X-Northwind-Signature`) y preguntas parafraseadas ("me despertaron tres noches") para que las diferencias entre técnicas se vean de verdad.

## Cómo se ve en código

`code/01_minimal_rag.py` es un RAG completo en 40 líneas: chunking por secciones, embeddings locales con FastEmbed, similitud coseno con numpy, y respuesta con Claude. La parte de retrieval corre sin API key.

```python
chunks = all_chunks()                                    # 1. chunking
matrix = embedder.passages([c.text for c in chunks])    # 2. embeddings (indexado)
hits = cosine_top_k(embedder.query(QUESTION), matrix, k=3)   # 3. retrieval
context = "\n\n".join(f'<source id="{chunks[i].id}">\n{chunks[i].text}\n</source>' for i, _ in hits)
response = client.messages.create(model="claude-opus-5-5", ..., messages=[{"role": "user", "content": f"{context}\n\nQuestion: {QUESTION}"}])
```

> [!NOTE]
> Para unos miles de chunks, numpy con fuerza bruta alcanza y sobra. Las bases vectoriales importan por escala, filtros, actualizaciones y operación, no porque el cálculo sea difícil.

## Errores comunes

- Empezar por elegir la base vectorial. Lo que más impacta es chunking, búsqueda híbrida y evaluar.
- Ajustar el prompt cuando el problema es que el fragmento correcto no llegó al contexto.
- No guardar metadata (documento, sección, fecha, permisos) junto a cada chunk: después no podés filtrar ni citar.
- Usar fine-tuning para que el modelo "sepa" los documentos.

## En una entrevista

- **¿Qué es RAG?** Recuperar fragmentos relevantes de una base de conocimiento y pasárselos al LLM en el prompt para que responda con esa información, idealmente citando las fuentes.
- **¿RAG o fine-tuning?** RAG para conocimiento (hechos actualizables y citables); fine-tuning para comportamiento (formato, estilo, tareas). Se pueden combinar.
- **¿RAG o contexto largo?** Si el corpus entra holgado y es estable, contexto largo con caching es más simple. RAG cuando es grande, cambia, o hay permisos por usuario.
- **¿Dónde falla un RAG típicamente?** En el retrieval: el fragmento correcto no se recupera o queda fuera del top-k. Se diagnostica midiendo retrieval por separado de la generación.
