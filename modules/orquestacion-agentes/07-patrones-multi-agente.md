---
title: Patrones multi-agente
order: 7
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

<figure class="diagram">
<svg viewBox="0 0 780 360" role="img" aria-label="Patrones multi-agente">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<rect class="zone" x="6" y="6" width="248" height="168" rx="10"/>
<text x="130.0" y="30" text-anchor="middle" class="title">Pipeline secuencial</text>
<rect class="process" x="24" y="80" width="56" height="28" rx="8"/>
<text x="52.0" y="99.0" text-anchor="middle" class="title">A</text>
<rect class="process" x="100" y="80" width="56" height="28" rx="8"/>
<text x="128.0" y="99.0" text-anchor="middle" class="title">B</text>
<rect class="process" x="176" y="80" width="56" height="28" rx="8"/>
<text x="204.0" y="99.0" text-anchor="middle" class="title">C</text>
<line class="line" x1="80" y1="94" x2="100" y2="94" marker-end="url(#ah)"/>
<line class="line" x1="156" y1="94" x2="176" y2="94" marker-end="url(#ah)"/>
<rect class="zone" x="266" y="6" width="248" height="168" rx="10"/>
<text x="390.0" y="30" text-anchor="middle" class="title">Paralelo (fan-out / fan-in)</text>
<rect class="input" x="278" y="94" width="44" height="28" rx="8"/>
<text x="300.0" y="113.0" text-anchor="middle" class="title">In</text>
<rect class="process" x="362" y="48" width="56" height="28" rx="8"/>
<text x="390.0" y="67.0" text-anchor="middle" class="title">A</text>
<line class="line" x1="322" y1="108" x2="362" y2="62" marker-end="url(#ah)"/>
<line class="line" x1="418" y1="62" x2="450" y2="108" marker-end="url(#ah)"/>
<rect class="process" x="362" y="88" width="56" height="28" rx="8"/>
<text x="390.0" y="107.0" text-anchor="middle" class="title">B</text>
<line class="line" x1="322" y1="108" x2="362" y2="102" marker-end="url(#ah)"/>
<line class="line" x1="418" y1="102" x2="450" y2="108" marker-end="url(#ah)"/>
<rect class="process" x="362" y="128" width="56" height="28" rx="8"/>
<text x="390.0" y="147.0" text-anchor="middle" class="title">C</text>
<line class="line" x1="322" y1="108" x2="362" y2="142" marker-end="url(#ah)"/>
<line class="line" x1="418" y1="142" x2="450" y2="108" marker-end="url(#ah)"/>
<rect class="store" x="450" y="94" width="50" height="28" rx="8"/>
<text x="475.0" y="113.0" text-anchor="middle" class="title">Σ</text>
<rect class="zone" x="526" y="6" width="248" height="168" rx="10"/>
<text x="650.0" y="30" text-anchor="middle" class="title">Supervisor</text>
<rect class="risk" x="622" y="48" width="56" height="28" rx="8"/>
<text x="650.0" y="67.0" text-anchor="middle" class="title">S</text>
<rect class="process" x="546" y="124" width="56" height="28" rx="8"/>
<text x="574.0" y="143.0" text-anchor="middle" class="title">A</text>
<line class="line" x1="636" y1="76" x2="574" y2="124" marker-start="url(#ah)" marker-end="url(#ah)"/>
<rect class="process" x="622" y="124" width="56" height="28" rx="8"/>
<text x="650.0" y="143.0" text-anchor="middle" class="title">B</text>
<line class="line" x1="650" y1="76" x2="650" y2="124" marker-start="url(#ah)" marker-end="url(#ah)"/>
<rect class="process" x="698" y="124" width="56" height="28" rx="8"/>
<text x="726.0" y="143.0" text-anchor="middle" class="title">C</text>
<line class="line" x1="664" y1="76" x2="726" y2="124" marker-start="url(#ah)" marker-end="url(#ah)"/>
<rect class="zone" x="6" y="186" width="248" height="168" rx="10"/>
<text x="130.0" y="210" text-anchor="middle" class="title">Jerárquico</text>
<rect class="risk" x="102" y="222" width="56" height="28" rx="8"/>
<text x="130.0" y="241.0" text-anchor="middle" class="title">S</text>
<rect class="risk" x="40" y="268" width="56" height="28" rx="8"/>
<text x="68.0" y="287.0" text-anchor="middle" class="title">S1</text>
<line class="line" x1="130" y1="250" x2="68" y2="268" marker-end="url(#ah)"/>
<rect class="process" x="18" y="316" width="44" height="24" rx="8"/>
<line class="line" x1="68" y1="296" x2="40" y2="316" marker-end="url(#ah)"/>
<rect class="process" x="68" y="316" width="44" height="24" rx="8"/>
<line class="line" x1="68" y1="296" x2="90" y2="316" marker-end="url(#ah)"/>
<rect class="risk" x="164" y="268" width="56" height="28" rx="8"/>
<text x="192.0" y="287.0" text-anchor="middle" class="title">S2</text>
<line class="line" x1="130" y1="250" x2="192" y2="268" marker-end="url(#ah)"/>
<rect class="process" x="142" y="316" width="44" height="24" rx="8"/>
<line class="line" x1="192" y1="296" x2="164" y2="316" marker-end="url(#ah)"/>
<rect class="process" x="192" y="316" width="44" height="24" rx="8"/>
<line class="line" x1="192" y1="296" x2="214" y2="316" marker-end="url(#ah)"/>
<rect class="zone" x="266" y="186" width="248" height="168" rx="10"/>
<text x="390.0" y="210" text-anchor="middle" class="title">Handoff</text>
<rect class="human" x="278" y="276" width="70" height="28" rx="8"/>
<text x="313.0" y="295.0" text-anchor="middle" class="title">Usuario</text>
<rect class="process" x="420" y="236" width="56" height="28" rx="8"/>
<text x="448.0" y="255.0" text-anchor="middle" class="title">A</text>
<rect class="process" x="420" y="312" width="56" height="28" rx="8"/>
<text x="448.0" y="331.0" text-anchor="middle" class="title">B</text>
<line class="line" x1="348" y1="284" x2="420" y2="252" marker-start="url(#ah)" marker-end="url(#ah)"/>
<line class="line" x1="448" y1="264" x2="448" y2="312" marker-end="url(#ah)"/>
<text x="490" y="292" text-anchor="middle" class="sub">transfiere</text>
<line class="line dash" x1="348" y1="296" x2="420" y2="324" marker-start="url(#ah)" marker-end="url(#ah)"/>
<rect class="zone" x="526" y="186" width="248" height="168" rx="10"/>
<text x="650.0" y="210" text-anchor="middle" class="title">Group chat</text>
<line class="line" x1="590" y1="236" x2="602" y2="264"/>
<line class="line" x1="712" y1="236" x2="700" y2="264"/>
<line class="line" x1="590" y1="316" x2="602" y2="294"/>
<line class="line" x1="712" y1="316" x2="700" y2="294"/>
<rect class="store" x="600" y="262" width="100" height="34" rx="8"/>
<text x="650.0" y="284.0" text-anchor="middle" class="title">chat</text>
<rect class="process" x="534" y="222" width="56" height="28" rx="8"/>
<text x="562.0" y="241.0" text-anchor="middle" class="title">A</text>
<rect class="process" x="712" y="222" width="56" height="28" rx="8"/>
<text x="740.0" y="241.0" text-anchor="middle" class="title">B</text>
<rect class="process" x="534" y="302" width="56" height="28" rx="8"/>
<text x="562.0" y="321.0" text-anchor="middle" class="title">C</text>
<rect class="process" x="712" y="302" width="56" height="28" rx="8"/>
<text x="740.0" y="321.0" text-anchor="middle" class="title">D</text>
<text x="650.0" y="346" text-anchor="middle" class="sub">un orquestador elige quién habla</text>
</svg>
<figcaption>Supervisor: los especialistas devuelven resultados al coordinador. Handoff: el control pasa a otro agente.</figcaption>
</figure>

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

**Paralelo con `Send`.** Una arista condicional que devuelve `[Send("worker", {...}), ...]` lanza una ejecución del nodo por cada elemento, en paralelo, y un reducer junta los resultados. El capítulo siguiente lo muestra en detalle.

**Pipeline y jerárquico.** Un pipeline son aristas fijas entre nodos-agente. Un jerárquico son subgrafos: un supervisor compilado se agrega como nodo de otro grafo.

== CrewAI
El multi-agente es el modelo nativo de CrewAI: varios `Agent`, varias `Task` y un `Process`.

```python
from crewai import Crew, Process, Task

collect = Task(description="Collect plan, country and open tickets for customer {customer_id}.",
               expected_output="A bullet list of facts.", agent=analyst)
brief = Task(description="Write a 3-line briefing for customer {customer_id}.",
             expected_output="Three lines.", agent=writer, context=[collect])

# Pipeline: tasks run in order; context=[collect] passes the result explicitly.
crew = Crew(agents=[analyst, writer], tasks=[collect, brief], process=Process.sequential)

# Hierarchical: a manager plans, delegates each task to the agent it picks, and validates.
crew = Crew(agents=[analyst, writer], tasks=[collect, brief],
            process=Process.hierarchical, manager_llm=llm)

crew.kickoff(inputs={"customer_id": "C-001"})
```

- `allow_delegation=True` en un agente le da tools para delegar trabajo o hacer preguntas a sus compañeros (supervisor informal).
- `async_execution=True` en una `Task` la ejecuta en paralelo con las siguientes; una tarea posterior con `context=[...]` espera a que terminen (fan-out / fan-in).
- Para lógica condicional o handoffs usás un **Flow**: `@router` elige el próximo paso según el estado y cada paso puede lanzar una Crew distinta.
== MS Agent Framework
Los patrones vienen como builders en `agent_framework.orchestrations`. Cada uno arma un `Workflow` que se ejecuta con `await workflow.run(tarea)`.

```python
from agent_framework.orchestrations import (
    ConcurrentBuilder, GroupChatBuilder, HandoffBuilder, MagenticBuilder, SequentialBuilder,
)

# Pipeline: each agent sees the conversation so far and adds its turn.
workflow = SequentialBuilder(participants=[triager, responder]).build()

# Concurrent: same input to every agent, results aggregated (.with_aggregator() for custom merging).
workflow = ConcurrentBuilder(participants=[security, support]).build()

# Handoff: the active agent can transfer the conversation to the agents you declare.
workflow = (HandoffBuilder(participants=[triage, billing, tech])
            .with_start_agent(triage)
            .add_handoff(triage, [billing, tech])
            .build())

# Group chat: an orchestrator (agent or function) picks who speaks each round.
workflow = GroupChatBuilder(participants=[writer, reviewer], orchestrator_agent=moderator,
                            max_rounds=6).build()

# Magentic: manager with a plan, progress ledger and re-planning (AutoGen's Magentic-One).
workflow = MagenticBuilder(participants=[researcher, coder], manager_agent=manager).build()

result = await workflow.run("Customer C-001 reports that SSO login fails for new users.")
for output in result.get_outputs():
    ...
```

- Para un supervisor simple: `especialista.as_tool()` convierte un agente en tool de otro, igual que en LangGraph.
- Para grafos a medida, `WorkflowBuilder` con executors y aristas (`add_edge`, `add_fan_out_edges`, `add_fan_in_edges`, `add_switch_case_edge_group`).
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

## Preguntas de repaso

- **¿Supervisor o handoff?** Supervisor si el coordinador debe integrar resultados y mantener la conversación; handoff si el especialista toma el control y sigue con el usuario.
- **¿Cómo paralelizás en LangGraph?** Con `Send` desde una arista condicional (map) y un reducer en el estado para juntar resultados (reduce).
- **¿Process.hierarchical en CrewAI?** Agrega un manager que planifica, asigna tareas a los agentes y valida resultados; requiere `manager_llm` o `manager_agent`.
- **¿Cuándo no usarías multi-agente?** Cuando un agente con buenas tools alcanza: menos latencia, menos costo y más fácil de evaluar.
