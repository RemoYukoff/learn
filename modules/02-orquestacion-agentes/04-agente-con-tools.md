---
title: Agente con tools
order: 4
type: implementacion
---

**Objetivo:** construir el mismo agente con tools en los cuatro frameworks y reconocer qué parte del loop resuelve cada uno.

## La idea, sin framework

Un agente con tools es el loop del módulo anterior:

<figure class="diagram">
<svg viewBox="0 0 700 225" role="img" aria-label="Loop de agente con tools">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<line class="line" x1="140" y1="94" x2="190" y2="94" marker-end="url(#ah)"/>
<line class="line" x1="310" y1="94" x2="360" y2="94" marker-end="url(#ah)"/>
<line class="line" x1="480" y1="94" x2="540" y2="94" marker-end="url(#ah)"/>
<text x="510" y="86" text-anchor="middle" class="sub">no</text>
<line class="line" x1="420" y1="129" x2="420" y2="165" marker-end="url(#ah)"/>
<text x="432" y="152" text-anchor="start" class="sub">sí</text>
<path class="line" d="M360,185 H250 V118" marker-end="url(#ah)"/>
<rect class="input" x="20" y="70" width="120" height="48" rx="8"/>
<text x="80.0" y="99.0" text-anchor="middle" class="title">Mensajes</text>
<rect class="process" x="190" y="70" width="120" height="48" rx="8"/>
<text x="250.0" y="99.0" text-anchor="middle" class="title">Modelo</text>
<polygon class="risk" points="420,59 480,94 420,129 360,94"/>
<text x="420" y="92" text-anchor="middle" class="title">¿pidió</text>
<text x="420" y="108" text-anchor="middle" class="title">tools?</text>
<rect class="store" x="540" y="70" width="140" height="48" rx="8"/>
<text x="610.0" y="99.0" text-anchor="middle" class="title">Respuesta final</text>
<rect class="node" x="360" y="165" width="120" height="42" rx="8"/>
<text x="420.0" y="191.0" text-anchor="middle" class="title">Ejecutar tools</text>
<text x="305" y="178" text-anchor="middle" class="sub">agregar resultados</text>
</svg>
</figure>

Cualquier framework necesita resolver lo mismo:

1. **Declarar tools**: nombre, descripción y esquema de argumentos, casi siempre derivados de una función tipada y su docstring.
2. **Llamar al modelo** con esas tools.
3. **Ejecutar** las tool calls de la respuesta (en paralelo si son varias) y devolver resultados, incluidos errores.
4. **Repetir** hasta que el modelo responda sin tools o se llegue a un límite.

Lo que cambia es cuánto de eso queda a la vista. El ejemplo de todos los tabs es el mismo: un asistente de soporte que responde "¿qué tickets abiertos tiene el cliente C-001 y en qué plan está?" usando dos tools del CRM falso del módulo (`get_customer` y `list_open_tickets`, funciones Python que devuelven JSON; ver el capítulo 2).


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
    client=AnthropicClient(model="claude-opus-5-5"),
    instructions="You are a support assistant. Use the CRM tools; never invent data.",
    tools=[get_customer, list_open_tickets],
)
response = await agent.run(question)
print(response.text)
```

El mismo `Agent` funciona con `OpenAIChatClient`, Azure, Bedrock u Ollama cambiando solo el cliente. Con `agent.as_tool()` un agente se vuelve tool de otro.
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
- Tools con efectos (cambiar estado de un ticket) sin aprobación humana. Lo resolvemos en el capítulo de human-in-the-loop.

## En una entrevista

- **¿Qué hace `ToolNode`?** Ejecuta en paralelo todas las tool calls del último `AIMessage` y devuelve un `ToolMessage` por cada una. Con `handle_tool_errors` los errores de las tools vuelven al modelo como mensaje en vez de cortar el grafo.
- **¿Qué diferencia hay entre `create_agent` y armar el grafo?** `create_agent` es ese mismo grafo prearmado con puntos de extensión (middleware). Armo el grafo cuando necesito nodos o routing propios.
- **¿Cómo describe CrewAI un agente?** Con `role`, `goal` y `backstory`, que forman su system prompt, y tareas con `description` y `expected_output`.
