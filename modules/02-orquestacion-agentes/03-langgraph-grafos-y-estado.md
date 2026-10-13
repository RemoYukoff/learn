---
title: "LangGraph: grafos y estado"
order: 3
type: implementacion
---

**Objetivo:** escribir un grafo de LangGraph desde cero y entender exactamente qué hace con el estado en cada paso.

## El modelo de ejecución

LangGraph ejecuta el grafo en **super-steps** (modelo Pregel):

1. Arranca en `START` con el input como estado inicial.
2. En cada paso ejecuta todos los nodos activos (en paralelo si hay varios).
3. Cada nodo recibe el estado completo y **devuelve solo las claves que cambia**.
4. Las actualizaciones se combinan en el estado con los **reducers**.
5. Las aristas deciden qué nodos se activan en el siguiente paso.
6. Termina cuando no queda ningún nodo activo (se llegó a `END`).

Si hay un checkpointer, se guarda una foto del estado al final de cada super-step.

## Estado y reducers

El estado se declara con un `TypedDict` (también sirven dataclasses o Pydantic). Cada clave tiene un reducer: por defecto **reemplazar**. Con `Annotated[tipo, función]` definís otro:

```python
import operator
from typing import Annotated, TypedDict

class TriageState(TypedDict):
    ticket: str                                  # reemplazo
    attempts: int                                # reemplazo
    log: Annotated[list[str], operator.add]      # concatenar listas
```

Si un nodo devuelve `{"log": ["paso 2"]}`, LangGraph hace `estado["log"] + ["paso 2"]`. Esto importa sobre todo cuando dos nodos en paralelo escriben la misma clave: sin reducer, LangGraph lanza `InvalidUpdateError` porque no sabe cuál gana.

Para conversaciones existe un reducer específico, `add_messages`, y un estado prearmado:

```python
from langgraph.graph import MessagesState          # {"messages": Annotated[list, add_messages]}
from langgraph.graph.message import add_messages

class AgentState(MessagesState):
    customer_id: str                               # your own fields
```

`add_messages` agrega mensajes nuevos, **reemplaza** los que vienen con un `id` ya existente (para editar) y acepta tuplas como `("user", "hola")` o dicts, que convierte a objetos de mensaje.

## Nodos, aristas y routing

```python
from langgraph.graph import END, START, StateGraph

def classify(state: TriageState) -> dict:
    category = "billing" if "invoice" in state["ticket"].lower() else "technical"
    return {"category": category, "log": [f"classify -> {category}"]}

def route_by_category(state: TriageState) -> str:
    return state["category"]            # name of the next node

builder = StateGraph(TriageState)
builder.add_node("classify", classify)
builder.add_node("billing", billing)
builder.add_node("technical", technical)
builder.add_node("review", review)

builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", route_by_category)  # elige billing o technical
builder.add_edge("billing", "review")
builder.add_edge("technical", "review")
builder.add_conditional_edges("review", route_after_review)   # vuelve a technical o END

graph = builder.compile()
final = graph.invoke({"ticket": "SSO login fails", "attempts": 0, "log": []})
```

- **`add_edge(a, b)`**: siempre después de `a` va `b`. Si un nodo tiene varias aristas salientes, los destinos corren en paralelo en el mismo super-step.
- **`add_conditional_edges(a, fn, path_map=None)`**: `fn(state)` devuelve el nombre del nodo siguiente (o una lista, o `END`). Tipar el retorno con `Literal[...]` o pasar `path_map` le permite a LangGraph dibujar el grafo.
- **Ciclos**: una arista condicional puede volver a un nodo anterior. Así se arma un loop de reintento o el loop de agente. Para que no sea infinito, guardá un contador en el estado; además LangGraph corta con `GraphRecursionError` al pasar `recursion_limit`. En LangGraph 1.2 el default es 10007 pasos (las versiones 0.x usaban 25), así que para un agente conviene fijarlo vos: `graph.invoke(inputs, {"recursion_limit": 30})`.
- **`compile()`** valida el grafo (que haya entrada desde `START`, que no haya nodos inalcanzables) y devuelve un `CompiledStateGraph` con `invoke`, `stream`, `get_state` y compañía. Acá también se pasa el `checkpointer` y el `store`.

### Routing desde el nodo con `Command`

En lugar de una función de routing separada, un nodo puede actualizar el estado y decidir el destino en un solo retorno:

```python
from typing import Literal
from langgraph.types import Command

def classify(state: TriageState) -> Command[Literal["billing", "technical"]]:
    category = "billing" if "invoice" in state["ticket"].lower() else "technical"
    return Command(update={"category": category}, goto=category)
```

Es el estilo habitual en sistemas multi-agente, donde un agente "le pasa la posta" a otro.

### Robustez por nodo

`add_node` acepta `retry_policy=RetryPolicy(max_attempts=3)` para reintentar ante excepciones (llamadas a APIs inestables), `timeout` y `cache_policy`. Preferí estas opciones a envolver cada nodo con `try/except` a mano.

## Un ejemplo completo

Un triage de tickets sin LLM: un clasificador por palabras clave, dos ramas y un loop de revisión que obliga a reintentar una vez. El campo `log` usa el reducer `operator.add`; `draft` y `attempts` se reemplazan.

```python
import operator
from typing import Annotated, Literal, TypedDict
from langgraph.graph import END, START, StateGraph

class Triage(TypedDict):
    ticket: str
    category: str
    draft: str
    attempts: int
    log: Annotated[list[str], operator.add]

def classify(state: Triage) -> dict:
    category = "technical" if "login" in state["ticket"].lower() else "billing"
    return {"category": category, "log": [f"classify -> {category}"]}

def technical(state: Triage) -> dict:
    n = state["attempts"] + 1
    draft = "Looking into it" if n == 1 else "Tech team: we reset your SSO metadata, please retry login."
    return {"draft": draft, "attempts": n, "log": [f"technical attempt {n}"]}

def billing(state: Triage) -> dict:
    return {"draft": "Billing will fix the invoice today.", "log": ["billing"]}

def review(state: Triage) -> Literal["retry", "done"]:
    return "retry" if len(state["draft"]) < 20 else "done"

builder = StateGraph(Triage)
builder.add_node("classify", classify)
builder.add_node("technical", technical)
builder.add_node("billing", billing)
builder.add_edge(START, "classify")
builder.add_conditional_edges("classify", lambda s: s["category"])        # returns the node name
builder.add_conditional_edges("technical", review, {"retry": "technical", "done": END})
builder.add_edge("billing", END)
graph = builder.compile()

result = graph.invoke({"ticket": "SSO login fails for new users", "attempts": 0, "log": []})
```

Para el ticket de SSO, `result["log"]` queda así:

```text
classify -> technical
technical attempt 1
technical attempt 2
```

El reducer conserva el historial de pasos a través del ciclo, mientras que `draft` y `attempts` muestran solo el último valor. `graph.get_graph().draw_mermaid()` devuelve el diagrama del grafo en Mermaid, útil para documentarlo.

## Errores comunes

- Devolver el estado entero desde un nodo. Funciona con claves de reemplazo, pero con reducers duplica datos (por ejemplo, la lista de mensajes entera vuelve a agregarse). Devolvé solo lo que cambia.
- Mutar el `state` recibido (`state["log"].append(...)`). El cambio no pasa por el reducer ni queda en el checkpoint de forma confiable.
- Dos nodos paralelos escribiendo una clave sin reducer: `InvalidUpdateError`.
- Ciclos sin condición de salida en el estado, confiando solo en `recursion_limit`. Con el default actual un agente trabado puede hacer miles de llamadas al modelo antes de cortar.
- Olvidar `add_edge(START, ...)`: `compile()` falla con "Graph must have an entrypoint".

## En una entrevista

- **¿Qué es un reducer en LangGraph?** La función que combina la actualización de un nodo con el valor actual de una clave. Por defecto reemplaza; `add_messages` agrega o reemplaza por id; `operator.add` concatena.
- **¿Cómo se hace un loop?** Con una arista condicional que vuelve a un nodo anterior, más una condición de salida en el estado.
- **¿Qué devuelve un nodo?** Un dict parcial con las claves que cambia, o un `Command` con `update` y `goto`.
