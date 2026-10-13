---
title: RAG agéntico
order: 8
---

**Objetivo:** pasar de "buscar una vez y responder" a sistemas donde el modelo decide qué buscar, evalúa lo que encontró y vuelve a buscar si hace falta.

## Idea

El RAG de los capítulos anteriores es un **pipeline fijo**: una búsqueda, top-k, respuesta. Funciona para preguntas directas. Falla cuando:

- La pregunta tiene **varias partes** que viven en documentos distintos ("¿le corresponden créditos de SLA y quién aprueba el reembolso?").
- La pregunta está mal formulada para buscar ("me despertaron tres noches").
- Lo recuperado **no alcanza** y habría que intentar otra búsqueda.

Dos patrones resuelven esto:

| Patrón | Quién decide | Cómo |
|---|---|---|
| **Retrieval como tool** | El modelo | El agente tiene una tool `search` y la llama cuantas veces quiera, con las queries que quiera. Es el loop del módulo de Tool use |
| **Grafo con control** (corrective / self-RAG) | Vos, con nodos LLM | Pasos fijos con decisiones: recuperar → evaluar relevancia → si no alcanza, reescribir la query y volver a buscar → generar |

El primero es más flexible; el segundo más predecible, barato y fácil de evaluar. En producción es común un grafo con pocas decisiones del LLM.

Otras técnicas que aparecen en este contexto:

- **Query rewriting / expansion**: reformular la pregunta, o generar varias queries y fusionar resultados.
- **Descomposición**: partir la pregunta en sub-preguntas, buscar cada una, combinar.
- **HyDE**: generar una respuesta hipotética y buscar con su embedding (se parece más a los documentos que la pregunta).
- **Routing**: elegir entre fuentes (handbook, base SQL, web) según la pregunta.

> [!WARNING]
> Cada decisión del LLM agrega latencia, costo y un punto de falla. Agregalas cuando las evals muestren que el pipeline fijo no alcanza, no por defecto.

En los dos tabs, `retriever.search(query, top=3)` es la búsqueda híbrida + rerank del capítulo 5 envuelta en un método que devuelve los mejores chunks (cada uno con `id` y `text`).

## Cómo se implementa

:::tabs
== LangGraph
Corrective RAG: el grafo recupera, un nodo LLM marca qué chunks sirven y si alcanzan, y una arista condicional decide entre generar o reescribir la query (máximo 2 reintentos).

```python
class Relevance(BaseModel):
    relevant_ids: list[int]
    enough: bool

llm = ChatAnthropic(model="claude-opus-5-5", max_tokens=2048)
grader = llm.with_structured_output(Relevance, method="json_schema")

def route(state: State) -> Literal["generate", "rewrite"]:
    if state["answer"] == "NEED_MORE" and state["rewrites"] < MAX_REWRITES:
        return "rewrite"
    return "generate"

builder = StateGraph(State)
builder.add_node("retrieve", retrieve)
builder.add_node("grade", grade)
builder.add_node("rewrite", rewrite)
builder.add_node("generate", generate)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "grade")
builder.add_conditional_edges("grade", route)
builder.add_edge("rewrite", "retrieve")
builder.add_edge("generate", END)
```


== LangChain
Retrieval como tool de un agente con `create_agent`. La descripción de la tool le dice al modelo qué cubre la base y que busque una vez por sub-pregunta.

```python
@tool
def search_handbook(query: str) -> str:
    """Search the company handbook (refunds, SLA, on-call, incidents, API limits, security,
    data retention, pricing, expenses, support hours). Returns the 3 most relevant sections
    with their ids. Use short, specific queries; call it again for each sub-question."""
    return "\n\n".join(f"[{c.id}]\n{c.text}" for c in retriever.search(query, top=3))

agent = create_agent(
    ChatAnthropic(model="claude-opus-5-5", max_tokens=4096),
    tools=[search_handbook],
    system_prompt="Always search before answering and cite the section ids you used in brackets.",
)
result = agent.invoke({"messages": [{"role": "user", "content": question}]})
```

Los `tool_calls` de los mensajes del resultado muestran qué buscó el agente. Con una pregunta de dos partes (por ejemplo, créditos de SLA y aprobación de un reembolso), lo esperable es una búsqueda por cada parte. Si hace una sola, el problema suele estar en la descripción de la tool.

:::

## Errores comunes

- Agente que busca siempre con la pregunta literal del usuario: la descripción de la tool tiene que invitar a reformular.
- Loops de reescritura sin límite.
- Evaluar solo la respuesta final de un RAG agéntico: logueá cada búsqueda para saber si el problema es la query, el retrieval o la síntesis.
- Usar un agente donde un pipeline fijo con híbrida y rerank ya resolvía.

## Preguntas de repaso

- **¿Qué es agentic RAG?** RAG donde un LLM decide cuándo y qué buscar (retrieval como tool) o evalúa lo recuperado y reintenta (corrective RAG), en vez de una sola búsqueda fija.
- **¿Qué es corrective RAG?** Agregar un paso que evalúa la relevancia de lo recuperado y, si no alcanza, reescribe la consulta o busca en otra fuente antes de generar.
- **¿Cuándo no usarías un agente para RAG?** Cuando las preguntas son directas y un pipeline fijo cumple las métricas: el agente agrega latencia, costo y variabilidad.
