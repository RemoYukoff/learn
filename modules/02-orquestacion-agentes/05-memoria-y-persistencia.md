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

Más vocabulario que aparece en entrevistas:

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

    snapshot = graph.get_state(config)      # estado actual del thread
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

Ejemplo: `code/05_memory_langgraph.py` (corré el script dos veces: la segunda vez el thread sigue desde `memory.sqlite`).
== CrewAI
CrewAI tiene una **memoria unificada**: un objeto `Memory` que guarda recuerdos en una base vectorial local (LanceDB), usa un LLM para decidir qué guardar y cómo categorizarlo, y los recupera combinando similitud, recencia e importancia. Con `Crew(memory=True)` se crea una con defaults; para controlar modelos y storage pasás una instancia.

```python
from crewai import LLM, Crew
from crewai.memory.unified_memory import Memory

llm = LLM(model="anthropic/claude-opus-5-5", max_tokens=4096)

memory = Memory(
    llm=llm,                                   # analiza qué guardar (default: un modelo de OpenAI)
    storage="./crew_memory.db",                # carpeta de LanceDB
    embedder={                                 # default: OpenAI embeddings
        "provider": "openrouter",
        "config": {"api_key": os.environ["OPENROUTER_API_KEY"],
                   "model_name": "openai/text-embedding-3-small"},
    },
)

crew = Crew(agents=[support], tasks=[task], memory=memory)
crew.kickoff()

memory.remember("User prefers Spanish", scope="/users/alice")   # escritura explícita
memory.recall("preferred language", limit=3)                    # búsqueda explícita
```

- Las crews guardan automáticamente lo que producen y recuperan recuerdos relevantes antes de cada tarea.
- `scope` organiza los recuerdos como rutas (`/users/alice`), y `memory.scope("/users/alice")` devuelve una vista limitada a esa rama: así separás usuarios.
- Corto plazo: dentro de un `kickoff` las tareas comparten contexto por `context=[...]`; entre ejecuciones, la memoria es la que conecta.

> [!NOTE]
> Anthropic no ofrece embeddings. Para no depender de una key de OpenAI, el ejemplo usa embeddings a través de OpenRouter. También hay proveedores locales (`ollama`, `sentence_transformer`).

Ejemplo: `code/05_memory_crewai.py`
== MS Agent Framework
**Corto plazo = `AgentSession`.** Una sesión agrupa los mensajes de una conversación. El proveedor de historial por defecto (`InMemoryHistoryProvider`) guarda los mensajes dentro de `session.state`, así que persisten mientras conserves la sesión, y se serializan con `to_dict()` / `from_dict()`.

```python
from agent_framework import Agent, AgentSession, InMemoryHistoryProvider

agent = Agent(client=client, instructions="...", context_providers=[InMemoryHistoryProvider()])

session = agent.create_session(session_id="ticket-1")
await agent.run("My customer id is C-001.", session=session)
await agent.run("What is my id?", session=session)        # recuerda

saved = session.to_dict()                                  # guardalo en tu DB
restored = AgentSession.from_dict(saved)
```

Para guardar el historial del lado del servidor hay proveedores para Redis (`agent-framework-redis`) y Cosmos DB, o el historial del propio servicio cuando el cliente lo soporta (Responses API, Foundry).

**Largo plazo = context providers.** Un `ContextProvider` se ejecuta antes y después de cada `run`: antes inyecta contexto (instrucciones, mensajes, tools) y después puede extraer y guardar información. Hay proveedores listos: `MemoryContextProvider` y `FileMemoryProvider`, Mem0 (`agent-framework-mem0`), Redis, y búsqueda vectorial (`VectorCollectionContextProvider`). Para compactar el historial, `Agent(compaction_strategy=...)` acepta estrategias como `SlidingWindowStrategy` o `SummarizationStrategy`.

Ejemplo: `code/05_memory_msaf.py`
:::

## Errores comunes

- Usar el mismo `thread_id` para usuarios distintos: el segundo ve la conversación del primero.
- Guardar en memoria de largo plazo sin namespace por usuario. Es una fuga de datos entre clientes.
- `InMemorySaver` o `InMemoryStore` en producción: se pierde todo al reiniciar y no escala a varias réplicas.
- Dejar crecer el historial sin recorte ni resumen. Sube el costo de cada request y en algún momento rompe el límite de contexto.
- Meter en el estado objetos no serializables (clientes HTTP, conexiones). El checkpointer tiene que poder serializarlo.

## En una entrevista

- **¿Corto vs largo plazo?** Corto plazo es el historial de un thread, persistido con un checkpointer; largo plazo son hechos curados en un store con namespaces, que se recuperan en cualquier thread.
- **¿Cómo manejás conversaciones largas?** Recorte por tokens, resumen de mensajes viejos o limpieza de resultados de tools, más memoria de largo plazo para lo importante.
- **¿Qué guardarías en memoria de largo plazo para un agente de soporte?** Preferencias del cliente, contexto de su cuenta y resoluciones previas, separados por cliente y con fecha para poder expirarlos.
