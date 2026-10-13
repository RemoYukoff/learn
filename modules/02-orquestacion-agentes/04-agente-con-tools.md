---
title: Agente con tools
order: 4
type: implementacion
---

**Objetivo:** construir el mismo agente con tools en los cuatro frameworks y reconocer qué parte del loop resuelve cada uno.

## La idea, sin framework

Un agente con tools es el loop del módulo anterior:

```text
mensajes ──> modelo ──¿pidió tools?── no ──> respuesta final
               ▲            │ sí
               │            ▼
               └──── ejecutar tools, agregar resultados
```

Cualquier framework necesita resolver lo mismo:

1. **Declarar tools**: nombre, descripción y esquema de argumentos, casi siempre derivados de una función tipada y su docstring.
2. **Llamar al modelo** con esas tools.
3. **Ejecutar** las tool calls de la respuesta (en paralelo si son varias) y devolver resultados, incluidos errores.
4. **Repetir** hasta que el modelo responda sin tools o se llegue a un límite.

Lo que cambia es cuánto de eso queda a la vista. El ejemplo de todos los tabs es el mismo: un asistente de soporte que responde "¿qué tickets abiertos tiene el cliente C-001 y en qué plan está?" usando dos tools de `code/crm.py`.

> [!IMPORTANT]
> `claude-opus-5-5` rechaza `temperature`, `top_p` y `tool_choice` forzado (`any` o una tool concreta). Ningún ejemplo los manda. Si un framework fuerza `tool_choice` por su cuenta, vas a ver un error 400; el tab de CrewAI explica el caso.

## Implementación

:::tabs
== LangGraph
Armás el grafo del loop a mano con dos piezas prearmadas: `ToolNode` ejecuta todas las tool calls del último mensaje y `tools_condition` enruta a `"tools"` si hay tool calls o a `END` si no.

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

@tool
def get_customer(customer_id: str) -> str:
    """Get a customer record by id, e.g. C-001."""
    return crm.get_customer(customer_id)

TOOLS = [get_customer, list_open_tickets]
model = ChatAnthropic(model="claude-opus-5-5", max_tokens=4096).bind_tools(TOOLS)

def agent(state: MessagesState) -> dict:
    return {"messages": [model.invoke(state["messages"])]}

builder = StateGraph(MessagesState)
builder.add_node("agent", agent)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)   # "tools" o END
builder.add_edge("tools", "agent")
graph = builder.compile()

for update in graph.stream({"messages": [("user", question)]}, stream_mode="updates"):
    print(update)
```

Cuándo conviene: cuando querés meter nodos propios en el medio (validar, resumir, pedir aprobación, cortar por presupuesto). El grafo es tuyo.

Ejemplo: `code/04_tools_langgraph.py`
== LangChain
`create_agent` devuelve el mismo grafo ya armado. Recibe el modelo, las tools y un system prompt, y se extiende con middleware.

```python
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic

agent = create_agent(
    model=ChatAnthropic(model="claude-opus-5-5", max_tokens=4096),
    tools=[get_customer, list_open_tickets],
    system_prompt="You are a support assistant. Use the CRM tools; never invent data.",
)
result = agent.invoke({"messages": [{"role": "user", "content": question}]})
print(result["messages"][-1].text)
```

`model` también acepta un string como `"anthropic:claude-opus-5-5"` (usa `init_chat_model`). Otros parámetros útiles: `response_format` para salida estructurada, `checkpointer` y `store` para memoria, `middleware` para HITL, resúmenes de historial o límites de llamadas.

Ejemplo: `code/04_tools_langchain.py`
== CrewAI
CrewAI describe al agente por rol, objetivo e historia, y el trabajo como una `Task` con resultado esperado. La `Crew` ejecuta las tareas y el agente hace el loop de tools internamente.

```python
from crewai import LLM, Agent, Crew, Task
from crewai.tools import tool

@tool("get_customer")
def get_customer(customer_id: str) -> str:
    """Get a customer record by id, e.g. C-001."""
    return crm.get_customer(customer_id)

llm = LLM(model="anthropic/claude-opus-5-5", max_tokens=4096)

support = Agent(
    role="Support analyst",
    goal="Answer questions about customers using only CRM data",
    backstory="You work in a B2B support team and never guess customer data.",
    tools=[get_customer, list_open_tickets],
    llm=llm,
)
task = Task(description="{question}", expected_output="Ticket ids and the plan.", agent=support)
result = Crew(agents=[support], tasks=[task]).kickoff(inputs={"question": question})
print(result.raw)
```

- `anthropic/...` usa el proveedor nativo de Anthropic, que viene con el extra `crewai[anthropic]`. Sin ese extra CrewAI necesita LiteLLM.
- Los `{placeholders}` de `description` se completan con `kickoff(inputs=...)`.

> [!WARNING]
> Si un agente de CrewAI tiene **exactamente una tool**, CrewAI fuerza `tool_choice` a esa tool, y lo mismo hace con `output_pydantic`/`response_model`. `claude-opus-5-5` responde 400 a eso. Dale al menos dos tools o ninguna, y pedí JSON en el prompt en vez de forzar el esquema.

Ejemplo: `code/04_tools_crewai.py`
== MS Agent Framework
Un `Agent` combina un chat client, instrucciones y tools. Las funciones con `@tool` (o funciones planas) se convierten en tools a partir de sus tipos, y `Annotated` agrega la descripción de cada argumento. Todo es `async`.

```python
from typing import Annotated
from agent_framework import Agent, tool
from agent_framework.anthropic import AnthropicClient

@tool
def get_customer(customer_id: Annotated[str, "Customer id, e.g. C-001"]) -> str:
    """Get a customer record by id."""
    return crm.get_customer(customer_id)

agent = Agent(
    client=AnthropicClient(model="claude-opus-5-5"),      # lee ANTHROPIC_API_KEY
    instructions="You are a support assistant. Use the CRM tools; never invent data.",
    tools=[get_customer, list_open_tickets],
    default_options={"max_tokens": 4096},                 # el default del cliente es 1024
)
response = await agent.run(question)
print(response.text)
```

El mismo `Agent` funciona con `OpenAIChatClient`, Azure, Bedrock u Ollama cambiando solo el cliente. Con `agent.as_tool()` un agente se vuelve tool de otro.

Ejemplo: `code/04_tools_msaf.py`
:::

## Comparación rápida

| | Dónde está el loop | Cómo se define una tool | Cómo ves los pasos |
|---|---|---|---|
| LangGraph | Grafo propio (`agent` + `ToolNode`) | `@tool` de LangChain o función | `stream(stream_mode="updates")` |
| LangChain | Grafo prearmado de `create_agent` | `@tool` | `result["messages"]`, stream igual que LangGraph |
| CrewAI | Dentro del `Agent` | `@tool("name")` de CrewAI | `verbose=True`, eventos |
| MS Agent Framework | Dentro del `Agent` (function invocation) | `@tool` o función tipada | `run(stream=True)`, middleware, OpenTelemetry |

## Errores comunes

- Docstrings vagos. La descripción de la tool es parte del prompt: "Get a customer record by id, e.g. C-001" funciona mejor que "customer tool".
- Lanzar excepciones desde una tool cuando el problema es de datos. Devolvé un texto de error que el modelo pueda usar ("customer not found, known ids: ..."); `crm.py` lo hace así.
- `max_tokens` bajo con modelos que piensan: el razonamiento consume tokens del mismo presupuesto y la respuesta sale cortada.
- Tools con efectos (cambiar estado de un ticket) sin aprobación humana. Lo resolvemos en el capítulo de human-in-the-loop.

## En una entrevista

- **¿Qué hace `ToolNode`?** Ejecuta en paralelo todas las tool calls del último `AIMessage` y devuelve un `ToolMessage` por cada una. Por defecto convierte en mensaje solo los errores de argumentos inválidos y relanza las demás excepciones; con `handle_tool_errors=True` (o un string o una función) también devuelve esos errores al modelo.
- **¿Qué diferencia hay entre `create_agent` y armar el grafo?** `create_agent` es ese mismo grafo prearmado con puntos de extensión (middleware). Armo el grafo cuando necesito nodos o routing propios.
- **¿Cómo describe CrewAI un agente?** Con `role`, `goal` y `backstory`, que forman su system prompt, y tareas con `description` y `expected_output`.
