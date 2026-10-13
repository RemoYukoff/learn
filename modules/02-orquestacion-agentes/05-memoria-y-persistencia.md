---
title: Memoria y persistencia
order: 5
type: implementacion
---

**Objetivo:** distinguir memoria de corto y de largo plazo, y saber dónde vive cada una en LangGraph, CrewAI y Microsoft Agent Framework.

## La idea

La API de un LLM no tiene memoria: cada request manda todo el contexto. "Memoria" en un agente es la decisión de **qué guardar, dónde y qué volver a meter en el prompt**. Hay dos niveles:

| | Corto plazo | Largo plazo |
|---|---|---|
| Qué guarda | Los mensajes y el estado de **una** conversación o tarea | Hechos que valen **entre** conversaciones: preferencias, datos del usuario, aprendizajes |
| Clave | thread / sesión | usuario, organización, agente (un namespace) |
| Cómo vuelve al prompt | Se reenvía el historial (recortado o resumido) | Se busca lo relevante y se inyecta en el system prompt o como tool |
| Riesgo típico | El historial crece hasta llenar el contexto | Guardar basura o datos de otro usuario |

Más vocabulario:

- **Persistencia del estado** (checkpointing) no es lo mismo que memoria de largo plazo: guarda todo el estado del grafo para retomar o auditar, no hechos curados.
- **Gestión del contexto**: recortar mensajes viejos, resumirlos, o borrar resultados de tools largos. Es la otra cara de la memoria de corto plazo.
- **Memoria semántica**: largo plazo indexado por embeddings para recuperar por significado (es RAG sobre la memoria del agente).
- **Escritura en caliente vs en segundo plano**: el agente guarda recuerdos con una tool mientras conversa, o un proceso posterior extrae hechos de la conversación terminada.

El ejemplo de todos los tabs: la misma persona abre dos tickets. En el primero dice su id de cliente y su idioma preferido. En el segundo, el agente no tiene el historial del primero pero sí debería saber la preferencia.

## Implementación

:::tabs
== LangGraph
**Corto plazo = checkpointer + `thread_id`.** Al compilar con un checkpointer, cada invocación con el mismo `thread_id` continúa el estado anterior. Solo mandás el mensaje nuevo; `add_messages` lo agrega al historial guardado.

```python
from langgraph.checkpoint.sqlite import SqliteSaver

with SqliteSaver.from_conn_string("memory.sqlite") as checkpointer:
    graph = builder.compile(checkpointer=checkpointer, store=store)
    config = {"configurable": {"thread_id": "ticket-1"}}
    graph.invoke({"messages": [("user", "My customer id is C-001.")]}, config)
    graph.invoke({"messages": [("user", "What is my id?")]}, config)   # recuerda

    snapshot = graph.get_state(config)      # current state of the thread
    snapshot.values["messages"]             # historial completo
```

Checkpointers: `InMemorySaver` (pruebas), `SqliteSaver` (`langgraph-checkpoint-sqlite`, local), `PostgresSaver` (`langgraph-checkpoint-postgres`, producción).

**Largo plazo = store con namespaces.** El store es un key-value por namespace (tupla), compartido entre threads. Un nodo lo recibe por el `Runtime`, junto con un contexto por ejecución que no se guarda en el checkpoint (ideal para `user_id`):

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

@dataclass
class Context:
    user_id: str

def chat(state: MessagesState, runtime: Runtime[Context]) -> dict:
    namespace = ("users", runtime.context.user_id)
    prefs = [item.value["text"] for item in runtime.store.search(namespace)]
    runtime.store.put(namespace, "language", {"text": "answers in Spanish"})
    ...

builder = StateGraph(MessagesState, context_schema=Context)
graph = builder.compile(checkpointer=checkpointer, store=InMemoryStore())
graph.invoke(inputs, config, context=Context(user_id="alice"))
```

`InMemoryStore(index={"embed": ..., "dims": ...})` y `PostgresStore` agregan búsqueda semántica con `store.search(namespace, query="...")`.

**Contexto que crece:** con `create_agent` de LangChain agregás `SummarizationMiddleware(model, trigger=("tokens", 100_000), keep=("messages", 20))`, que resume el historial viejo. `create_agent` acepta los mismos `checkpointer` y `store`.

Con un checkpointer persistente como `SqliteSaver`, el thread sobrevive al reinicio del proceso: una nueva invocación con el mismo `thread_id` sigue desde el último checkpoint guardado.
== CrewAI
CrewAI tiene una **memoria unificada**: un objeto `Memory` que guarda recuerdos en una base vectorial local, usa un LLM para decidir qué guardar y cómo categorizarlo, y los recupera combinando similitud, recencia e importancia. Con `Crew(memory=True)` se activa con la configuración por defecto, o pasás una instancia propia.

```python
from crewai import LLM, Crew
from crewai.memory.unified_memory import Memory

memory = Memory(
    llm=LLM(model="anthropic/claude-opus-5-5"),   # decides what to store and how to categorize it
    storage="./crew_memory.db",                   # local vector store folder
)

crew = Crew(agents=[support], tasks=[task], memory=memory)
crew.kickoff()

memory.remember("User prefers Spanish", scope="/users/alice")   # explicit write
memory.recall("preferred language", limit=3)                    # explicit search
```

- Las crews guardan automáticamente lo que producen y recuperan recuerdos relevantes antes de cada tarea.
- `scope` organiza los recuerdos como rutas (`/users/alice`), y `memory.scope("/users/alice")` devuelve una vista limitada a esa rama: así separás usuarios.
- Corto plazo: dentro de un `kickoff` las tareas comparten contexto por `context=[...]`; entre ejecuciones, la memoria es la que conecta.

== MS Agent Framework
**Corto plazo = `AgentSession`.** Una sesión agrupa los mensajes de una conversación. Un history provider guarda los mensajes de la sesión; la sesión se serializa con `to_dict()` / `from_dict()` para guardarla y retomarla.

```python
from agent_framework import Agent, AgentSession, InMemoryHistoryProvider

agent = Agent(client=client, instructions="...", context_providers=[InMemoryHistoryProvider()])

session = agent.create_session(session_id="ticket-1")
await agent.run("My customer id is C-001.", session=session)
await agent.run("What is my id?", session=session)        # recuerda

saved = session.to_dict()                                  # guardalo en tu DB
restored = AgentSession.from_dict(saved)
```

Para persistir el historial fuera del proceso se usa un history provider respaldado por una base de datos.

**Largo plazo = context providers.** Un `ContextProvider` se ejecuta antes y después de cada `run`: antes inyecta contexto (instrucciones, mensajes, tools) y después puede extraer y guardar información. Hay proveedores listos para memoria y para búsqueda vectorial. Para compactar el historial, `Agent(compaction_strategy=...)` acepta estrategias como `SlidingWindowStrategy` o `SummarizationStrategy`.
:::

## Errores comunes

- Usar el mismo `thread_id` para usuarios distintos: el segundo ve la conversación del primero.
- Guardar en memoria de largo plazo sin namespace por usuario. Es una fuga de datos entre clientes.
- `InMemorySaver` o `InMemoryStore` en producción: se pierde todo al reiniciar y no escala a varias réplicas.
- Dejar crecer el historial sin recorte ni resumen. Sube el costo de cada request y en algún momento rompe el límite de contexto.
- Meter en el estado objetos no serializables (clientes HTTP, conexiones). El checkpointer tiene que poder serializarlo.

## Preguntas de repaso

- **¿Corto vs largo plazo?** Corto plazo es el historial de un thread, persistido con un checkpointer; largo plazo son hechos curados en un store con namespaces, que se recuperan en cualquier thread.
- **¿Cómo manejás conversaciones largas?** Recorte por tokens, resumen de mensajes viejos o limpieza de resultados de tools, más memoria de largo plazo para lo importante.
- **¿Qué guardarías en memoria de largo plazo para un agente de soporte?** Preferencias del cliente, contexto de su cuenta y resoluciones previas, separados por cliente y con fecha para poder expirarlos.
