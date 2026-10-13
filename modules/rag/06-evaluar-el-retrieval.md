---
title: Evaluar un RAG
order: 6
---

**Objetivo:** medir por separado si el sistema encuentra lo correcto y si responde bien con lo que encontró, para saber qué arreglar.

## Idea

Un RAG tiene dos etapas que fallan distinto, y se evalúan por separado:

| Etapa | Pregunta | Métricas |
|---|---|---|
| **Retrieval** | ¿El contexto tiene lo necesario? | hit@k / recall@k, MRR, nDCG, precision@k |
| **Generación** | ¿La respuesta es correcta y sale del contexto? | correctness, faithfulness (groundedness), answer relevance |

Si la respuesta está mal y el retrieval también, arreglá retrieval. Si el retrieval está bien y la respuesta mal, es prompt, modelo o contexto con ruido.

### El dataset de evaluación

Un set de preguntas con la respuesta esperada y **qué fragmento** la contiene. Es el activo más valioso del proyecto.

- **Fuentes**: preguntas reales de usuarios (logs), preguntas que escribe un experto, y sintéticas generadas por un LLM a partir de chunks (útiles para arrancar, sesgadas a ser fáciles).
- **Cobertura**: preguntas fáciles, con términos exactos, parafraseadas, que requieren dos documentos, y que **no tienen respuesta** en el corpus (el sistema tiene que decir "no sé").
- **Tamaño**: 30–100 preguntas bien elegidas dan señal. Mejor pocas y buenas que mil sintéticas.

Un truco útil para etiquetar: guardar con cada pregunta una frase de **evidencia** que solo está en el fragmento correcto. Un chunk es relevante si contiene esa frase. Así la etiqueta no depende de los ids de chunk, que cambian cada vez que cambia el chunking.

```json
{"question": "Our CFO wants money back for a 3,500 USD charge. Who signs off?",
 "evidence": "finance director",
 "answer": "The finance director, with a ticket reference."}
```

### Métricas de retrieval

| Métrica | Qué mide | Fórmula intuitiva |
|---|---|---|
| **hit@k** (recall@k con 1 relevante) | ¿Está la evidencia en el top k? | 1 si sí, 0 si no; promedio |
| **MRR** | Qué tan arriba aparece el primer relevante | promedio de 1/rank |
| **nDCG@k** | Calidad del orden, premiando relevantes arriba | ganancia con descuento log2 por posición, normalizada |
| **precision@k** | Cuánto del top k es relevante | relevantes / k. Importa porque el ruido confunde al modelo |

hit@k con k = lo que mandás al LLM es la métrica que más se relaciona con la calidad final: si la evidencia no llega, el modelo no puede responder bien.

### Métricas de generación

Se miden con **LLM-as-judge**: otro llamado al modelo con la pregunta, la respuesta de referencia, el contexto y la respuesta, que devuelve un veredicto estructurado.

- **Correctness**: ¿coincide con la referencia?
- **Faithfulness / groundedness**: ¿cada afirmación está respaldada por el contexto? Detecta alucinaciones aunque la respuesta "suene" bien.
- **Answer relevance**: ¿responde lo que se preguntó?

Herramientas que empaquetan esto: **LangSmith** y **DeepEval**, en el módulo de Evals y observabilidad. El patrón de fondo es el de este capítulo.

> [!IMPORTANT]
> Un juez LLM también se equivoca. Revisá a mano una muestra de sus veredictos al principio y cada vez que cambies el prompt del juez. Es tu experiencia de QA aplicada: el juez es un test que también hay que testear.

## Cómo se ve en código

Las métricas de retrieval son pocas líneas: para cada pregunta, la posición del primer chunk que contiene la evidencia.

```python
def metrics(ranking: list[str], evidence: str) -> dict[str, float]:
    rel = [evidence in text for text in ranking]          # ranking = retrieved chunk texts, best first
    first = next((n for n, r in enumerate(rel, 1) if r), None)
    return {
        "hit@1": float(first == 1),
        "hit@3": float(first is not None and first <= 3),
        "mrr": 1 / first if first else 0.0,
        "ndcg@10": sum(1 / math.log2(n + 1) for n, r in enumerate(rel, 1) if r),  # one relevant chunk: ideal DCG = 1
    }
```

Las cuatro estrategias del capítulo 5 medidas sobre el corpus de prueba del módulo (10 documentos cortos de un handbook ficticio y 22 preguntas etiquetadas), con latencia promedio por consulta en CPU:

```text
strategy        hit@1  hit@3  hit@10    MRR  nDCG@10  ms/query
dense            0.82   0.91    0.95   0.85     0.88       3.7
bm25             0.73   0.86    0.91   0.80     0.83       0.1
hybrid           0.73   0.91    1.00   0.83     0.87       4.0
hybrid+rerank    0.77   0.95    1.00   0.86     0.90      67.3
```

Para la generación, un juez LLM recibe pregunta, referencia, contexto y respuesta, y devuelve un veredicto con salida estructurada:

```python
class Grade(BaseModel):
    correct: Literal["yes", "partial", "no"]
    faithful: bool          # every claim is supported by the context
    reason: str

grade = client.messages.parse(model="claude-opus-5-5", ..., output_format=Grade).parsed_output
```

### Cómo se usa en la práctica

1. Armar el dataset y medir una línea base.
2. Cambiar **una** cosa (chunking, modelo de embeddings, k, híbrida, reranker, prompt).
3. Ejecutar las evals y comparar contra la línea base. El cambio se queda solo si mejora sin romper otras preguntas.
4. Ejecutar las evals en CI cada vez que cambie cualquier pieza del pipeline.

## Errores comunes

- Evaluar solo la respuesta final: no sabés qué etapa falla.
- Dataset solo sintético: preguntas parecidas al texto, todo da 100%.
- No incluir preguntas sin respuesta en el corpus.
- Comparar métricas entre runs con distinto chunking usando ids de chunk como etiqueta.
- Confiar ciegamente en el juez LLM.

## Preguntas de repaso

- **¿Cómo evaluás un sistema RAG?** Separando retrieval (recall@k, MRR, nDCG sobre preguntas etiquetadas) de generación (correctness y faithfulness con LLM-as-judge revisado por humanos), con un dataset fijo y corriendo en CI.
- **¿Qué es faithfulness?** Que todas las afirmaciones de la respuesta estén respaldadas por el contexto recuperado. Mide alucinación, no corrección.
- **¿Cómo armás el dataset si no tenés preguntas reales?** Sintéticas generadas desde los chunks para arrancar, revisadas por un experto, y reemplazadas progresivamente por preguntas reales de producción.
