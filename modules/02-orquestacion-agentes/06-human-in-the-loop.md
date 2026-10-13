---
title: Human-in-the-loop
order: 6
type: implementacion
---

**Objetivo:** pausar un agente antes de una acción sensible, pedir una decisión humana y retomar la ejecución, en los cuatro frameworks.

## La idea

Las búsquedas lo piden explícitamente: "human-in-the-loop para acciones críticas" y "políticas de confirmación antes de ejecutar acciones sensibles". El patrón tiene cuatro partes:

1. **Política**: qué acciones requieren aprobación. Lecturas no; escrituras con efectos (cerrar un ticket, emitir una nota de crédito, mandar un mail) sí. Puede depender de los argumentos (montos, clientes VIP).
2. **Pausa**: el sistema se detiene **antes** del efecto y guarda el estado.
3. **Decisión**: una persona aprueba, rechaza, edita los argumentos o responde en lugar de la tool. Puede tardar segundos o días, por otro canal (UI, Slack, mail).
4. **Reanudación**: el sistema sigue desde donde quedó con la decisión, sin repetir lo que ya hizo.

Lo que separa una demo de algo de producción es el paso 2: si la pausa vive en memoria del proceso (un `input()` dentro del loop), un deploy o un timeout la pierden. Por eso la pausa va de la mano del checkpointing.

Tipos de decisión que conviene soportar:

| Decisión | Qué hace el sistema |
|---|---|
| Aprobar | Ejecuta la tool con los argumentos propuestos |
| Rechazar | No ejecuta; le devuelve al modelo un resultado que explica el rechazo para que no reintente |
| Editar | Ejecuta con argumentos corregidos por la persona |
| Responder | No ejecuta; la respuesta humana se usa como resultado de la tool (tools tipo "preguntar al usuario") |

El ejemplo de los tabs: "cerrá todos los tickets abiertos de C-001", con `update_ticket_status` como acción que requiere aprobación.

## Implementación

:::tabs
== LangGraph
`interrupt(valor)` detiene el grafo dentro de un nodo (o dentro de una tool que ejecuta `ToolNode`), guarda el estado en el checkpointer y devuelve el control con el valor bajo la clave `__interrupt__`. Para seguir, invocás el mismo thread con `Command(resume=decisión)`: el nodo **se ejecuta de nuevo desde el principio** y esta vez `interrupt()` devuelve la decisión.

```python
from langgraph.types import Command, interrupt

@tool
def update_ticket_status(ticket_id: str, status: str) -> str:
    """Change a ticket status to open, pending or closed. Requires human approval."""
    decision = interrupt({"action": "update_ticket_status", "ticket_id": ticket_id, "status": status})
    if decision != "approve":
        return f"A human rejected changing {ticket_id} to {status}. Do not retry."
    return crm.update_ticket_status(ticket_id, status)

graph = builder.compile(checkpointer=InMemorySaver())     # required to interrupt
config = {"configurable": {"thread_id": "hitl-demo"}}

result = graph.invoke({"messages": [("user", "Close every open ticket of C-001.")]}, config)
while result.get("__interrupt__"):
    payload = result["__interrupt__"][0].value
    answer = ask_a_human(payload)                          # UI, Slack, input()...
    result = graph.invoke(Command(resume=answer), config)
```

- Entre la pausa y la reanudación pueden pasar días y cambiar de proceso: el estado vive en el checkpointer.
- Como el nodo se re-ejecuta, todo lo que esté **antes** de `interrupt()` tiene que ser idempotente.
- También podés pausar sin tocar los nodos con `compile(interrupt_before=["tools"])`, y editar el estado con `graph.update_state(...)` antes de seguir.
== LangChain
`HumanInTheLoopMiddleware` implementa la política sobre `create_agent`: para cada tool decís si interrumpe y qué decisiones se permiten. Cuando el modelo pide una tool protegida, el agente se detiene con un `HITLRequest` y se reanuda con una lista de decisiones (una por acción, en el mismo orden).

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command

agent = create_agent(
    model=ChatAnthropic(model="claude-opus-5-5", max_tokens=4096),
    tools=[list_open_tickets, update_ticket_status],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={
        "update_ticket_status": {"allowed_decisions": ["approve", "edit", "reject"]},
        "list_open_tickets": False,
    })],
    checkpointer=InMemorySaver(),
)

result = agent.invoke({"messages": [{"role": "user", "content": "Set T-101 to pending."}]}, config)
request = result["__interrupt__"][0].value          # {"action_requests": [...], "review_configs": [...]}

decisions = [{"type": "approve"}]
# {"type": "edit", "edited_action": {"name": "update_ticket_status", "args": {...}}}
# {"type": "reject", "message": "Waiting for the customer."}
# {"type": "respond", "message": "..."}   # only if listed in allowed_decisions
result = agent.invoke(Command(resume={"decisions": decisions}), config)
```

Es el mismo mecanismo de `interrupt` de LangGraph, empaquetado con un formato estándar que las UIs de LangChain (Agent Chat UI, LangSmith Studio) saben mostrar.
== CrewAI
En CrewAI la aprobación vive en los **Flows**. `@human_feedback` en un paso muestra su resultado a una persona, toma su respuesta en texto libre y, si declarás `emit`, usa un LLM para reducirla a uno de esos resultados. Cada resultado es un evento que escuchás con `@listen`.

```python
from crewai.flow import Flow, human_feedback, listen, start

class CloseTicketFlow(Flow):
    @start()
    @human_feedback(
        message="The agent wants to run this action. Approve or reject?",
        emit=["approved", "rejected"],
        llm=llm,
        default_outcome="rejected",
    )
    def propose(self):
        return {"action": "update_ticket_status", "ticket_id": "T-100", "status": "closed"}

    @listen("approved")
    def execute(self):
        proposal = self.human_feedback.output
        crm.update_ticket_status(proposal["ticket_id"], proposal["status"])

    @listen("rejected")
    def skip(self):
        print("Skipped:", self.human_feedback.feedback)

CloseTicketFlow().kickoff()
```

- Por defecto pregunta por consola. Para producción pasás un `provider` (`HumanFeedbackProvider`) que manda el pedido a Slack o a una UI y lanza `HumanFeedbackPending`: `kickoff()` devuelve ese objeto en vez de bloquear, el estado se guarda si el Flow tiene persistencia configurada (`@persist`) y se reanuda cuando llega la respuesta.
- Dentro de una Crew existe `Task(human_input=True)`: al terminar la tarea el agente le muestra el resultado a una persona por consola y lo corrige con su feedback. Sirve para revisar resultados, no para aprobar una tool antes de ejecutarla.

== MS Agent Framework
La política va en la tool: `@tool(approval_mode="always_require")`. Cuando el modelo la pide, el agente **no la ejecuta** y devuelve en `response.user_input_requests` un pedido de aprobación con la llamada propuesta. Respondés con un mensaje de usuario que contiene las respuestas de aprobación, en la misma sesión.

```python
from agent_framework import Agent, Message, tool

@tool(approval_mode="always_require")
def update_ticket_status(ticket_id: Annotated[str, "Ticket id"], status: Annotated[str, "open, pending or closed"]) -> str:
    """Change a ticket status."""
    return crm.update_ticket_status(ticket_id, status)

session = agent.create_session()
response = await agent.run("Close every open ticket of customer C-001.", session=session)

while response.user_input_requests:
    answers = []
    for request in response.user_input_requests:
        call = request.function_call                       # name + arguments propuestos
        approved = ask_a_human(call.name, call.arguments)
        answers.append(request.to_function_approval_response(approved))
    response = await agent.run(Message("user", answers), session=session)
```

- Si el modelo pide varias tools en la misma respuesta y alguna requiere aprobación, se pide aprobación para todas.
- En Workflows el mecanismo general es `ctx.request_info(...)`: el workflow emite un evento `request_info`, se puede checkpointear, y se reanuda con `workflow.run(responses={request_id: respuesta})`. Los builders de orquestación lo exponen con `.with_request_info()`.
:::

## Errores comunes

- Pedir aprobación **después** de ejecutar la acción. La pausa va antes del efecto.
- Pausas que viven en memoria del proceso. Sin checkpointer o sesión persistida, un reinicio pierde la aprobación pendiente.
- Rechazar sin explicarle al modelo por qué. Si el resultado de la tool no dice "rechazado por una persona, no reintentes", el modelo suele volver a pedirla.
- Efectos antes de `interrupt()` en LangGraph: el nodo se re-ejecuta al reanudar y los duplica.
- Aprobaciones sin auditoría. Guardá quién aprobó qué, con qué argumentos y cuándo.

## En una entrevista

- **¿Cómo implementás aprobación humana en LangGraph?** `interrupt()` dentro del nodo o tool sensible, checkpointer persistente, y reanudación con `Command(resume=...)` en el mismo `thread_id`.
- **¿Qué pasa con el código anterior al `interrupt()` al reanudar?** Se ejecuta de nuevo, así que tiene que ser idempotente.
- **¿Qué acciones deberían requerir aprobación?** Las que tienen efectos externos o son irreversibles: escrituras en sistemas del cliente, pagos, envíos de mensajes. Las lecturas no.
