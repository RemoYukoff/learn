---
title: "LangGraph: streaming, subgrafos y time travel"
order: 8
---

**Objetivo:** mostrar progreso en tiempo real, componer grafos, paralelizar con `Send` y volver a un checkpoint anterior.

## Streaming

Un agente tarda: varias llamadas al modelo y a tools. Para una UI hace falta mostrar qué está pasando. `graph.stream(...)` emite eventos mientras el grafo se ejecuta, y `stream_mode` elige qué tipo:

| `stream_mode` | Qué emite | Uso típico |
|---|---|---|
| `"values"` | El estado completo después de cada paso | Debug, UIs que re-renderizan todo |
| `"updates"` | `{nodo: lo_que_devolvió}` por cada nodo | Mostrar pasos del agente ("buscando cliente...") |
| `"messages"` | Tuplas `(chunk_de_mensaje, metadata)` token por token desde cualquier llamada a un chat model | Escribir la respuesta en vivo |
| `"custom"` | Lo que escribas con `get_stream_writer()` desde un nodo o tool | Progreso propio ("procesando 3 de 10") |
| `"checkpoints"`, `"tasks"`, `"debug"` | Eventos internos del runtime | Herramientas y debugging profundo |

Se pueden combinar: con una lista, cada evento llega como `(modo, datos)`.

```python
from langgraph.config import get_stream_writer

def summarize(state):
    get_stream_writer()({"progress": f"summarizing {state['ticket_id']}"})
    ...

for mode, data in graph.stream(inputs, config, stream_mode=["updates", "custom"]):
    print(mode, data)

# Model tokens, with the node that produced them
for chunk, meta in agent.stream(inputs, stream_mode="messages"):
    if meta["langgraph_node"] == "model":
        print(chunk.text, end="", flush=True)
```

Todo existe también en async (`astream`).

## Subgrafos

Un grafo compilado se puede agregar como nodo de otro. Sirve para encapsular un agente o un proceso y reutilizarlo, y es la base del patrón jerárquico.

```python
ticket_graph = ticket_builder.compile()        # tiene su propio estado (TicketState)

builder = StateGraph(ReportState)
builder.add_node("ticket", ticket_graph)        # se usa como cualquier nodo
```

- Si el padre y el hijo **comparten claves** de estado, el subgrafo se agrega directo y esas claves se sincronizan (con sus reducers).
- Si los esquemas son distintos, lo invocás desde una función nodo que traduce: `def call(state): out = sub.invoke({...}); return {...}`.
- `stream(..., subgraphs=True)` incluye eventos de adentro de los subgrafos, con el **namespace** de cada uno (`('ticket:<id>',)`), así sabés de qué rama vienen.
- El checkpointer se propaga solo al subgrafo; no hace falta compilarlo con uno.

## Map-reduce con `Send`

Cuando la cantidad de ramas depende de los datos (un worker por documento, por ticket, por proveedor), una arista condicional devuelve una lista de `Send(nodo, input)`. Cada `Send` es una ejecución independiente del nodo, con su propio input, y todas corren en el mismo super-step. Un reducer en el estado junta los resultados.

```python
from langgraph.types import Send

class ReportState(TypedDict):
    ticket_ids: list[str]
    summaries: Annotated[list[str], operator.add]   # reduce

def fan_out(state: ReportState) -> list[Send]:
    return [Send("ticket", {"ticket_id": tid, "summaries": []}) for tid in state["ticket_ids"]]

builder.add_conditional_edges("load_tickets", fan_out, ["ticket"])
builder.add_edge("ticket", "write_report")          # espera a todas las ramas
```

## Durabilidad

Con checkpointer, `durability` controla cuándo se escribe cada checkpoint:

| Modo | Comportamiento | Trade-off |
|---|---|---|
| `"sync"` | Escribe antes de empezar el paso siguiente | Más seguro, más lento |
| `"async"` | Escribe en paralelo con el paso siguiente (default) | Buen balance; un crash puede perder el último paso |
| `"exit"` | Escribe solo al terminar o interrumpirse | Más rápido; no se puede retomar desde pasos intermedios |

Se pasa por ejecución: `graph.invoke(inputs, config, durability="sync")`.

## Time travel

Cada checkpoint de un thread queda guardado. Eso permite:

```python
history = list(graph.get_state_history(config))   # newest first
for snap in history:
    print(snap.next, snap.values)                   # what came next and the state at that point

# Re-run from an earlier point, unchanged (replay):
graph.invoke(None, history[2].config)

# Or branch: edit the state at that point and continue from there (fork)
forked_config = graph.update_state(history[2].config, {"ticket_ids": ["T-100"]})
graph.invoke(None, forked_config)
```

`update_state` crea un checkpoint **nuevo** como si el nodo de ese punto hubiera devuelto esos valores; los checkpoints anteriores no se tocan. Es la herramienta para reproducir el bug de un agente en producción: cargás el thread, volvés al paso previo al error, corregís el estado o el prompt y re-ejecutás.

## Todo junto

Un grafo que combina las piezas de este capítulo: carga los tickets de un cliente, lanza un subgrafo por ticket con `Send`, cada subgrafo escribe progreso con `get_stream_writer`, y al final se recorre el historial y se bifurca desde un checkpoint con un ticket menos. Así se ven los eventos y el historial (abreviado):

```text
=== stream_mode=["custom", "updates"] + subgraphs=True: namespaced events
(root) updates {'load_tickets': {'ticket_ids': ['T-100', 'T-101']}}
('ticket:14c3...',) custom {'progress': 'summarizing T-100'}
('ticket:14c3...',) updates {'summarize': {'summaries': ['T-100: Invoice shows wrong VAT (open)']}}
...
=== time travel: checkpoints of thread t, newest first
  next=()                     summaries=2
  next=('write_report',)      summaries=2
  next=('ticket', 'ticket')   summaries=0
  next=('load_tickets',)      summaries=0
```

## Errores comunes

- Usar `"values"` para una UI de chat: re-envía el historial entero en cada paso. Para texto en vivo, `"messages"`.
- Esperar tokens en `"messages"` desde un nodo que no llama a un chat model de LangChain (por ejemplo, el SDK de Anthropic directo). Ahí usá `"custom"`.
- Olvidar el reducer en la clave que juntan las ramas de `Send`: `InvalidUpdateError`.
- Creer que `update_state` reescribe la historia: crea una rama nueva desde ese punto.

## Preguntas de repaso

- **¿Cómo mostrás progreso de un agente en una UI?** `stream_mode=["updates", "messages", "custom"]`: pasos por nodo, tokens del modelo y eventos propios.
- **¿Para qué sirve `Send`?** Para fan-out dinámico: una ejecución del nodo por elemento, en paralelo, con un reducer que junta resultados.
- **¿Qué es time travel?** Volver a un checkpoint de un thread y re-ejecutar desde ahí, tal cual o con el estado editado. Útil para debug y para "deshacer".
