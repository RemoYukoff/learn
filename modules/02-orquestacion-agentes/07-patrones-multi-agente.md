---
title: Patrones multi-agente
order: 7
type: implementacion
---

**Objetivo:** reconocer los patrones multi-agente, saber cuándo valen la pena y cómo se expresa cada uno en LangGraph, CrewAI y Microsoft Agent Framework.

## La idea

Un sistema multi-agente reparte el trabajo entre varios agentes, cada uno con su propio prompt, tools y contexto. Las razones legítimas para hacerlo:

- **Contexto acotado**: cada agente ve solo lo que necesita. Un agente con 40 tools y todo el historial elige peor que cuatro agentes con 10 tools cada uno.
- **Especialización**: prompts, modelos y permisos distintos por rol (un agente de lectura y otro con permisos de escritura).
- **Paralelismo**: subtareas independientes al mismo tiempo.
- **Organización del equipo**: cada agente lo mantiene un equipo distinto.

El costo: más llamadas al modelo, más latencia, errores que se propagan entre agentes y debugging más difícil. Un solo agente bien diseñado le gana a un multi-agente mal partido.

## Los patrones

| Patrón | Cómo funciona | Cuándo |
|---|---|---|
| **Pipeline secuencial** | A, después B, después C; cada uno recibe el resultado del anterior | Pasos conocidos: extraer, analizar, redactar |
| **Paralelo (fan-out / fan-in)** | La misma tarea o partes de ella van a varios agentes a la vez; un paso final combina | Revisiones desde varios ángulos, procesar N documentos |
| **Supervisor** | Un agente coordinador decide a qué especialista delegar, recibe los resultados y responde | Pedidos variados que mezclan dominios |
| **Jerárquico** | Supervisores de supervisores | Sistemas grandes con equipos de agentes |
| **Handoff** | Un agente le pasa el control de la conversación a otro, que sigue hablando con el usuario | Atención al cliente: triage, después ventas o soporte |
| **Group chat** | Varios agentes comparten una conversación; un orquestador elige quién habla en cada ronda | Debate, revisión cruzada, brainstorming |
| **Planner + ledger (Magentic)** | Un manager arma un plan, asigna pasos, lleva un registro de progreso y re-planifica si se traba | Tareas abiertas y largas |

Diferencia clave entre **supervisor** y **handoff**: en el supervisor los especialistas trabajan "por debajo" y devuelven un resultado al coordinador, que mantiene la conversación. En el handoff el control se transfiere y el nuevo agente pasa a hablar con el usuario.

El ejemplo de los tabs: armar un briefing del cliente C-001 (plan, país, tickets abiertos) con un agente de cuentas y uno de tickets, o con un pipeline analista y redactor.

## Implementación

:::tabs
== LangGraph
LangGraph no trae un único "multi-agente": lo armás con sus primitivas.

**Supervisor con agentes como tools.** Es el patrón que recomienda LangChain hoy. Cada especialista es un agente completo y el supervisor lo ve como una tool más. El contexto de cada especialista no ensucia el del supervisor.

```python
from langchain.agents import create_agent

accounts_agent = create_agent(model, tools=[get_customer], system_prompt="You answer about accounts.")
tickets_agent = create_agent(model, tools=[list_open_tickets], system_prompt="You answer about tickets.")

@tool
def ask_accounts(task: str) -> str:
    """Delegate a question about a customer's account or plan to the accounts specialist."""
    return accounts_agent.invoke({"messages": [{"role": "user", "content": task}]})["messages"][-1].text

@tool
def ask_tickets(task: str) -> str:
    """Delegate a question about support tickets to the tickets specialist."""
    return tickets_agent.invoke({"messages": [{"role": "user", "content": task}]})["messages"][-1].text

supervisor = create_agent(model, tools=[ask_accounts, ask_tickets],
                          system_prompt="Split the request, delegate, then write one combined answer.")
```

**Handoff con `Command`.** Cada agente es un nodo; para transferir el control devuelve `Command(goto="otro_agente", update={...})`. Si el agente es un subgrafo y quiere saltar a un nodo del grafo padre, usa `Command(goto=..., graph=Command.PARENT)`.

**Paralelo con `Send`.** Una arista condicional que devuelve `[Send("worker", {...}), ...]` lanza una ejecución del nodo por cada elemento, en paralelo, y un reducer junta los resultados. Lo ves funcionando en el capítulo siguiente.

**Pipeline y jerárquico.** Un pipeline son aristas fijas entre nodos-agente. Un jerárquico son subgrafos: un supervisor compilado se agrega como nodo de otro grafo.

> [!NOTE]
> Existen `langgraph-supervisor` y `langgraph-swarm` como paquetes prearmados. La documentación actual de LangChain recomienda el enfoque de agentes como tools para el supervisor, que da más control sobre qué contexto recibe cada especialista.

Ejemplo: `code/07_multiagent_langgraph.py`
== CrewAI
El multi-agente es el modelo nativo de CrewAI: varios `Agent`, varias `Task` y un `Process`.

```python
from crewai import Crew, Process, Task

collect = Task(description="Collect plan, country and open tickets for customer {customer_id}.",
               expected_output="A bullet list of facts.", agent=analyst)
brief = Task(description="Write a 3-line briefing for customer {customer_id}.",
             expected_output="Three lines.", agent=writer, context=[collect])

# Pipeline: las tareas corren en orden; context=[collect] pasa el resultado explícitamente.
crew = Crew(agents=[analyst, writer], tasks=[collect, brief], process=Process.sequential)

# Jerárquico: un manager planifica, delega cada tarea al agente que elija y valida el resultado.
crew = Crew(agents=[analyst, writer], tasks=[collect, brief],
            process=Process.hierarchical, manager_llm=llm)

crew.kickoff(inputs={"customer_id": "C-001"})
```

- `allow_delegation=True` en un agente le da tools para delegar trabajo o hacer preguntas a sus compañeros (supervisor informal).
- `async_execution=True` en una `Task` la corre en paralelo con las siguientes; una tarea posterior con `context=[...]` espera a que terminen (fan-out / fan-in).
- Para lógica condicional o handoffs usás un **Flow**: `@router` elige el próximo paso según el estado y cada paso puede lanzar una Crew distinta.

Ejemplo: `code/07_multiagent_crewai.py` (con `--hierarchical` para el modo jerárquico)
== MS Agent Framework
Los patrones vienen como builders en `agent_framework.orchestrations`. Cada uno arma un `Workflow` que se ejecuta con `await workflow.run(tarea)`.

```python
from agent_framework.orchestrations import (
    ConcurrentBuilder, GroupChatBuilder, HandoffBuilder, MagenticBuilder, SequentialBuilder,
)

# Pipeline: cada agente ve la conversación hasta ahí y agrega su turno.
workflow = SequentialBuilder(participants=[triager, responder]).build()

# Paralelo: misma entrada a todos, resultados agregados (.with_aggregator() para combinar a medida).
workflow = ConcurrentBuilder(participants=[security, support]).build()

# Handoff: el agente activo puede transferir la conversación a los que declares.
workflow = (HandoffBuilder(participants=[triage, billing, tech])
            .with_start_agent(triage)
            .add_handoff(triage, [billing, tech])
            .build())

# Group chat: un orquestador (agente o función) elige quién habla en cada ronda.
workflow = GroupChatBuilder(participants=[writer, reviewer], orchestrator_agent=moderator,
                            max_rounds=6).build()

# Magentic: manager con plan, ledger de progreso y re-planificación (Magentic-One de AutoGen).
workflow = MagenticBuilder(participants=[researcher, coder], manager_agent=manager).build()

result = await workflow.run("Customer C-001 reports that SSO login fails for new users.")
for output in result.get_outputs():
    ...
```

- Para un supervisor simple: `especialista.as_tool()` convierte un agente en tool de otro, igual que en LangGraph.
- Para grafos a medida, `WorkflowBuilder` con executors y aristas (`add_edge`, `add_fan_out_edges`, `add_fan_in_edges`, `add_switch_case_edge_group`).

Ejemplo: `code/07_multiagent_msaf.py` (sequential y concurrent)
:::

## Cómo elegir el patrón

1. ¿Los pasos son siempre los mismos? Pipeline.
2. ¿Las subtareas son independientes? Paralelo.
3. ¿Los pedidos mezclan dominios y hace falta una respuesta unificada? Supervisor.
4. ¿El usuario tiene que seguir hablando con el especialista? Handoff.
5. ¿La tarea es abierta y larga? Planner con ledger, con límites de rondas y presupuesto.

## Errores comunes

- Partir en agentes algo que un solo agente resuelve. Medí primero con uno.
- Delegar con instrucciones vagas. El especialista no ve la conversación del supervisor: la tarea delegada tiene que ser autocontenida.
- Pasar historiales completos entre agentes. Se multiplica el costo y el ruido; pasá resultados resumidos.
- Group chats sin límite de rondas ni condición de terminación.
- No poder rastrear qué agente hizo qué. Nombrá los agentes (`name=`) y usá tracing.

## En una entrevista

- **¿Supervisor o handoff?** Supervisor si el coordinador debe integrar resultados y mantener la conversación; handoff si el especialista toma el control y sigue con el usuario.
- **¿Cómo paralelizás en LangGraph?** Con `Send` desde una arista condicional (map) y un reducer en el estado para juntar resultados (reduce).
- **¿Process.hierarchical en CrewAI?** Agrega un manager que planifica, asigna tareas a los agentes y valida resultados; requiere `manager_llm` o `manager_agent`.
- **¿Cuándo no usarías multi-agente?** Cuando un agente con buenas tools alcanza: menos latencia, menos costo y más fácil de evaluar.
