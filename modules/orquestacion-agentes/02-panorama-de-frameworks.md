---
title: Panorama de frameworks
order: 2
type: concepto
---

**Objetivo:** ubicar los frameworks de orquestación más usados, saber qué modelo mental usa cada uno y entender AutoGen y Semantic Kernel aunque hoy se usen con otro nombre.

## Los modelos mentales

| | LangGraph | LangChain | CrewAI | Microsoft Agent Framework |
|---|---|---|---|---|
| Primitiva | Grafo de nodos sobre un estado tipado | Agente prearmado (`create_agent`) + middleware | Crew (agentes con rol + tareas) y Flow (pasos con eventos) | Agent + Workflows (grafo de executors) + orquestaciones prearmadas |
| Nivel | Bajo: vos dibujás el grafo | Alto: un agente en una línea | Alto: describís roles y tareas | Medio: agentes simples o grafos explícitos |
| Persistencia | Checkpointers (memoria, SQLite, Postgres) | La de LangGraph | Memory unificada, checkpoints de Flow | Sesiones serializables, checkpoint storage en workflows |
| Human-in-the-loop | `interrupt()` + `Command(resume=...)` | `HumanInTheLoopMiddleware` | `@human_feedback` en Flows, `human_input` en Tasks | `approval_mode` en tools, request/response en workflows |
| Multi-agente | Lo armás: supervisor, Send, subgrafos | Agentes como tools | `Process.sequential` / `hierarchical` | Sequential, Concurrent, Handoff, GroupChat, Magentic |
| Lenguajes | Python, JS/TS | Python, JS/TS | Python | Python, .NET |

### LangGraph

Runtime de bajo nivel de LangChain Inc. Un `StateGraph` con nodos (funciones) y aristas (fijas o condicionales), compilado a un objeto que se puede `invoke`, `stream` y persistir. No impone cómo es un agente: el agente es un ciclo que vos dibujás o uno prearmado. Es la opción cuando necesitás control explícito del flujo, durabilidad y pausas humanas. Se integra con LangSmith para trazas.

### LangChain

LangChain se organiza alrededor de `create_agent`: una función que devuelve **un grafo de LangGraph ya compilado** con el loop modelo-tools. Se personaliza con **middleware** (aprobación humana, resumen de historial, reintentos, límites de llamadas) en vez de cadenas. Sigue aportando la capa de integraciones: modelos (`ChatAnthropic`, `init_chat_model`), tools, loaders, vector stores.

### CrewAI

Framework independiente de LangChain, orientado a roles. Dos piezas:

- **Crew:** agentes con `role`, `goal` y `backstory`, tareas con `description` y `expected_output`, y un `Process` (secuencial o jerárquico con un manager). Rápido para prototipos tipo "equipo de especialistas".
- **Flow:** orquestación por eventos con `@start`, `@listen`, `@router` y estado tipado. Es lo que se usa en producción para tener control del orden, persistencia y pasos humanos, y dentro de un paso podés lanzar una Crew.

### Microsoft Agent Framework (ex AutoGen + Semantic Kernel)

Microsoft unificó sus dos frameworks en uno: **Microsoft Agent Framework** (paquete `agent-framework`). El desarrollo nuevo de agentes de Microsoft va a este framework; AutoGen y Semantic Kernel quedaron como antecesores. Tiene dos capas:

- **Agent:** un cliente de chat (Anthropic, OpenAI, Azure, Bedrock, Ollama...), instrucciones, tools y middleware. Hace el loop de tools solo.
- **Workflows:** grafo tipado de executors con aristas, fan-out/fan-in, checkpoints y pedidos de input humano, más orquestaciones prearmadas (`SequentialBuilder`, `ConcurrentBuilder`, `HandoffBuilder`, `GroupChatBuilder`, `MagenticBuilder`).

Cómo traducir lo que pide una búsqueda que dice AutoGen o Semantic Kernel:

| Concepto viejo | Dónde vive ahora |
|---|---|
| AutoGen `AssistantAgent` | `Agent` |
| AutoGen `FunctionTool` / SK `KernelFunction` y plugins | `@tool` (funciones Python con tipos) |
| AutoGen `RoundRobinGroupChat`, `SelectorGroupChat` | `GroupChatBuilder` (orquestador elige quién habla) |
| AutoGen `Swarm` (handoffs) | `HandoffBuilder` |
| AutoGen `MagenticOneGroupChat` | `MagenticBuilder` (manager con task ledger y progress ledger) |
| AutoGen teams y termination conditions | Workflows y `termination_condition` de los builders |
| SK `Kernel` + `ChatCompletionAgent` | `Agent` con un chat client |
| SK planners | Function calling nativo del modelo (los planners se deprecaron) |
| SK Process Framework | Workflows |


### Otros que conviene reconocer

- **OpenAI Agents SDK** (`openai-agents`): agentes, handoffs, guardrails, sesiones y tracing con foco en modelos de OpenAI. Minimalista.
- **Claude Agent SDK** (`claude-agent-sdk`): el harness de Claude Code como librería, con tools de archivos, bash, búsqueda web, subagentes y MCP ya incluidos. Para agentes que trabajan sobre un filesystem o un repo.
- **LlamaIndex**: fuerte en RAG; también tiene workflows y agentes.

## Cómo elegir

1. ¿Alcanza con el SDK del proveedor y un loop? Usalo.
2. ¿Necesitás grafo explícito, pausas humanas y durabilidad? LangGraph.
3. ¿Un agente estándar con algún agregado (aprobación, resumen de historial)? LangChain `create_agent`, que te deja bajar a LangGraph si crece.
4. ¿El equipo piensa en roles y querés un prototipo rápido de varios agentes? CrewAI; pasá a Flows para producción.
5. ¿Stack Microsoft (.NET, Azure AI Foundry) o una base de código AutoGen/SK? Microsoft Agent Framework.

## El ejemplo común del módulo

Todos los capítulos usan el mismo CRM falso para que el problema sea idéntico en cada tab y solo cambie el framework. Son tres funciones Python comunes; cada framework las envuelve con su propio decorador de tool:

```python
CUSTOMERS = {"C-001": {"id": "C-001", "name": "Acme SA", "plan": "enterprise", "country": "AR"}, ...}
TICKETS = {"T-100": {"id": "T-100", "customer_id": "C-001", "subject": "Invoice shows wrong VAT", "status": "open"}, ...}

def get_customer(customer_id: str) -> str: ...           # customer record as JSON, or an error message
def list_open_tickets(customer_id: str) -> str: ...      # open tickets of a customer as JSON
def update_ticket_status(ticket_id: str, status: str) -> str: ...   # the sensitive action in the HITL chapter
```


## Errores comunes

- Elegir framework por popularidad en vez de por el tipo de control que necesitás.
- Mezclar dos frameworks de orquestación en el mismo servicio. Elegí uno; integraciones sueltas (un vector store de LangChain dentro de un Flow de CrewAI) sí están bien.

## Preguntas de repaso

- **¿LangChain o LangGraph?** LangGraph es el runtime de grafos con estado y persistencia; `create_agent` de LangChain es un agente prearmado construido sobre LangGraph. Empiezo con `create_agent` y bajo a un grafo propio cuando necesito controlar el flujo.
- **¿Qué ventaja tiene CrewAI?** Modelar rápido un equipo de agentes por rol y tarea. Para producción uso Flows por el control del orden y del estado.
- **¿Qué pasó con AutoGen?** Microsoft lo unificó con Semantic Kernel en Microsoft Agent Framework; los group chats, handoffs y Magentic-One existen ahí como orquestaciones.
