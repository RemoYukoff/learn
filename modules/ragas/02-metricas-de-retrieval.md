---
title: Métricas de retrieval
order: 2
---

**Objetivo:** medir si el retriever trae lo necesario y lo ordena bien, con y sin respuesta de referencia, y saber qué cambiar según qué métrica baja.

## Idea

El retrieval falla de dos maneras distintas, y cada una tiene su métrica:

- **Le falta información**: la respuesta correcta necesitaba un dato que ningún chunk trajo. Lo mide **context recall**.
- **Trae ruido o lo ordena mal**: los chunks útiles están, pero mezclados con otros irrelevantes o al fondo de la lista. Lo mide **context precision**.

El modelo no puede responder con lo que no recibió, y el ruido lo distrae. Por eso conviene mirar las dos.

### Context recall

¿El contexto recuperado alcanza para producir la respuesta de referencia?

1. El juez parte la `reference` en afirmaciones.
2. Para cada afirmación decide si se puede atribuir a alguno de los `retrieved_contexts`.
3. Puntaje = afirmaciones atribuibles / total de afirmaciones.

Si la referencia dice "lo aprueba el director de finanzas, con número de ticket" y el contexto solo menciona al director, recall = 0.5. Necesita `reference`: sin saber qué hacía falta, no se puede medir qué faltó.

### Context precision

¿Los chunks relevantes aparecen arriba en el ranking?

1. Para cada chunk, en el orden en que llegó, el juez decide si fue útil para llegar a la referencia (veredicto 1 o 0).
2. Se calcula la precisión en cada posición k (relevantes hasta k / k).
3. Puntaje = promedio de la precisión en las posiciones donde hay un chunk relevante.

Es la *average precision* de búsqueda clásica, con el juez haciendo de etiquetador. Premia tener los relevantes primero, no solo tenerlos.

<figure class="diagram">
<svg viewBox="0 0 700 230" role="img" aria-label="Dos rankings con los mismos chunks relevantes en distinto orden dan distinta context precision">
<text x="20" y="30" class="title">Ranking A</text>
<rect class="store" x="130" y="12" width="90" height="34" rx="6"/>
<text x="175" y="34" text-anchor="middle" class="mono">#1 útil</text>
<rect class="risk" x="235" y="12" width="90" height="34" rx="6"/>
<text x="280" y="34" text-anchor="middle" class="mono">#2 ruido</text>
<rect class="store" x="340" y="12" width="90" height="34" rx="6"/>
<text x="385" y="34" text-anchor="middle" class="mono">#3 útil</text>
<text x="455" y="27" class="sub">(1/1 + 2/3) / 2</text>
<text x="455" y="45" class="title">= 0.83</text>
<text x="20" y="120" class="title">Ranking B</text>
<rect class="risk" x="130" y="102" width="90" height="34" rx="6"/>
<text x="175" y="124" text-anchor="middle" class="mono">#1 ruido</text>
<rect class="store" x="235" y="102" width="90" height="34" rx="6"/>
<text x="280" y="124" text-anchor="middle" class="mono">#2 útil</text>
<rect class="store" x="340" y="102" width="90" height="34" rx="6"/>
<text x="385" y="124" text-anchor="middle" class="mono">#3 útil</text>
<text x="455" y="117" class="sub">(1/2 + 2/3) / 2</text>
<text x="455" y="135" class="title">= 0.58</text>
<text x="20" y="190" class="sub">Mismos chunks, mismo recall. Solo cambia el orden: B pone ruido primero y pierde precisión.</text>
</svg>
<figcaption>Context precision promedia la precisión en cada posición donde aparece un chunk útil.</figcaption>
</figure>

Hay una variante **sin referencia** que juzga la utilidad de cada chunk contra la `response` en lugar de la `reference`. Sirve en producción, pero mide otra cosa: qué chunks usó el modelo, no cuáles debería haber usado.

### Context relevance

¿Los chunks tienen que ver con la pregunta? No usa referencia ni respuesta: dos prompts de juez distintos califican la relevancia del contexto con 0, 1 o 2, y el puntaje es el promedio normalizado a 0–1. Es la métrica de retrieval más barata de obtener en producción, porque solo necesita pregunta y contexto.

### Context entity recall

Variante de recall basada en **entidades** (nombres, montos, fechas, productos): qué proporción de las entidades de la referencia aparece en el contexto. Útil en dominios donde la respuesta depende de datos puntuales, como soporte, legales o finanzas.

### Métricas con juez o con etiquetas

Si tu dataset tiene etiquetado **qué chunk** contiene la respuesta (por id o por una frase de evidencia, como en el módulo de RAG), podés calcular hit@k, MRR o nDCG sin juez: son exactas, gratis y deterministas. Las métricas de Ragas con juez sirven cuando no tenés esas etiquetas, cuando el chunking cambia seguido o cuando la respuesta se arma con varios chunks.

### Cómo leer los resultados

| Recall | Precision | Diagnóstico | Qué probar |
|---|---|---|---|
| Bajo | Alta | Lo que trae es bueno, pero falta | Subir k, búsqueda híbrida, revisar chunking y cobertura del corpus |
| Alto | Baja | Trae todo, con mucho ruido o mal ordenado | Reranker, bajar k, filtros por metadata |
| Bajo | Baja | El retriever no entiende la consulta | Modelo de embeddings, reescritura de la consulta, chunking |
| Alto | Alta | Retrieval sano | Si la respuesta igual falla, mirar generación (capítulo 3) |

## Cómo se implementa

El mismo caso en los dos tabs: una pregunta sobre reembolsos con tres chunks recuperados, el primero útil, el segundo ruido.

:::tabs
== Ragas
```python
from ragas.metrics.collections import ContextPrecision, ContextRecall, ContextRelevance

question = "Who approves a 3,500 USD refund?"
reference = "The finance director approves it, with the ticket number attached."
contexts = [
    "Refunds above 2,000 USD need approval from the finance director.",
    "Shipping is free for orders above 50 USD.",
    "Every refund request must include the support ticket number.",
]

precision = await ContextPrecision(llm=judge).ascore(
    user_input=question, reference=reference, retrieved_contexts=contexts)
recall = await ContextRecall(llm=judge).ascore(
    user_input=question, reference=reference, retrieved_contexts=contexts)
relevance = await ContextRelevance(llm=judge).ascore(
    user_input=question, retrieved_contexts=contexts)

print(precision.value, recall.value, relevance.value)
```
== DeepEval
Las mismas tres métricas, con nombres `Contextual*`. Cada una devuelve un score y una razón en texto.

```python
from deepeval.metrics import ContextualPrecisionMetric, ContextualRecallMetric, ContextualRelevancyMetric
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase

judge = AnthropicModel(model="claude-opus-5-5")
case = LLMTestCase(
    input=question,
    actual_output=answer,
    expected_output=reference,
    retrieval_context=contexts,
)

for metric in (ContextualPrecisionMetric(model=judge),
               ContextualRecallMetric(model=judge),
               ContextualRelevancyMetric(model=judge)):
    metric.measure(case)
    print(type(metric).__name__, metric.score, metric.reason)
```
:::

## Errores comunes

- Pasar los contextos en un orden distinto al que recibió el LLM: context precision depende del orden.
- Medir solo recall y subir k hasta 30: el recall sube y el modelo se ahoga en ruido.
- Usar la variante sin referencia como si midiera retrieval correcto: solo dice qué chunks aprovechó la respuesta.
- Calcular context recall con referencias escritas con datos que no están en el corpus: el recall nunca puede llegar a 1.
- Pagar un juez para algo que una etiqueta de evidencia resuelve exacto y gratis.

## Preguntas de repaso

- **¿Qué diferencia hay entre context recall y context precision?** Recall mide si el contexto contiene todo lo que pide la referencia; precision mide si los chunks útiles están arriba en el ranking.
- **¿Por qué context precision depende del orden?** Porque es average precision: promedia la precisión en cada posición donde hay un chunk relevante, y un relevante en la posición 3 vale menos que en la 1.
- **¿Qué métrica de retrieval podés calcular en producción?** Context relevance, que solo necesita pregunta y contexto.
- **Recall bajo y precision alta, ¿qué hacés?** Ampliar lo que trae el retriever: más k, búsqueda híbrida, mejor chunking o completar el corpus.
