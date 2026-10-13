---
title: Panorama de frameworks
order: 2
type: concepto
---

**Objetivo:** ubicar cada framework que nombran las búsquedas, saber qué modelo mental usa cada uno y poder responder por AutoGen y Semantic Kernel aunque hoy se usen con otro nombre.

## Qué piden las búsquedas

| Framework | Búsquedas que lo nombran | Cómo lo piden |
|---|---|---|
| LangGraph | 4 de 4 | Requisito en todas |
| LangChain | 4 de 4 | Casi siempre junto a LangGraph |
| CrewAI | 2 de 4 | Alternativa válida (AYI), deseable (Baires HR) |
| AutoGen | 2 de 4 | Alternativa válida (AYI), deseable (Baires HR) |
| Semantic Kernel | 1 de 4 | Alternativa válida (AYI) |

Conclusión práctica: **LangGraph a fondo**, y el resto a nivel de poder leer código, comparar y explicar cuándo elegiría cada uno. Este módulo sigue esa proporción.

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

Desde la versión 1.0 LangChain se reorganizó alrededor de `create_agent`: una función que devuelve **un grafo de LangGraph ya compilado** con el loop modelo-tools. Se personaliza con **middleware** (aprobación humana, resumen de historial, reintentos, límites de llamadas) en vez de cadenas. Sigue aportando la capa de integraciones: modelos (`ChatAnthropic`, `init_chat_model`), tools, loaders, vector stores. Si en una entrevista te preguntan por "chains" o LCEL, es la API vieja: hoy se usa para pipelines simples y el código nuevo de agentes va por `create_agent` o LangGraph.

### CrewAI

Framework independiente de LangChain, orientado a roles. Dos piezas:

- **Crew:** agentes con `role`, `goal` y `backstory`, tareas con `description` y `expected_output`, y un `Process` (secuencial o jerárquico con un manager). Rápido para prototipos tipo "equipo de especialistas".
- **Flow:** orquestación por eventos con `@start`, `@listen`, `@router` y estado tipado. Es lo que se usa en producción para tener control del orden, persistencia y pasos humanos, y dentro de un paso podés lanzar una Crew.

### Microsoft Agent Framework (ex AutoGen + Semantic Kernel)

Microsoft unificó sus dos frameworks en uno: **Microsoft Agent Framework** (paquete `agent-framework`). AutoGen quedó en mantenimiento (la última versión de `autogen-agentchat` es la 0.7.5, de septiembre de 2025) y Semantic Kernel recibe soporte pero el desarrollo nuevo de agentes va al framework unificado. Tiene dos capas:

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

> [!NOTE]
> Si en la entrevista preguntan por AutoGen, explicá el modelo conversacional (agentes que se mandan mensajes en un equipo con condición de terminación) y aclará que hoy lo escribirías con Microsoft Agent Framework. Muestra que seguís el ecosistema.

### Otros que conviene reconocer

- **OpenAI Agents SDK** (`openai-agents`): agentes, handoffs, guardrails, sesiones y tracing con foco en modelos de OpenAI. Minimalista.
- **Claude Agent SDK** (`claude-agent-sdk`): el harness de Claude Code como librería, con tools de archivos, bash, búsqueda web, subagentes y MCP ya incluidos. Para agentes que trabajan sobre un filesystem o un repo.
- **LlamaIndex**: fuerte en RAG; también tiene workflows y agentes. Aparece en búsquedas centradas en RAG.

## Cómo elegir

1. ¿Alcanza con el SDK del proveedor y un loop? Usalo.
2. ¿Necesitás grafo explícito, pausas humanas y durabilidad? LangGraph.
3. ¿Un agente estándar con algún agregado (aprobación, resumen de historial)? LangChain `create_agent`, que te deja bajar a LangGraph si crece.
4. ¿El equipo piensa en roles y querés un prototipo rápido de varios agentes? CrewAI; pasá a Flows para producción.
5. ¿Stack Microsoft (.NET, Azure AI Foundry) o una base de código AutoGen/SK? Microsoft Agent Framework.

## Cómo correr los ejemplos de este módulo

Los frameworks fijan versiones incompatibles entre sí (CrewAI exige `pydantic<2.13`, por ejemplo), así que hay tres entornos:

```sh
cd modules/02-orquestacion-agentes/code
cp .env.example .env    # ANTHROPIC_API_KEY (y OPENROUTER_API_KEY para la memoria de CrewAI)

# LangGraph + LangChain: 03_*, 04_tools_langgraph/langchain, 05/06/07 *_langgraph|langchain, 08_*
uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements.txt

# CrewAI: *_crewai.py
uv venv -p 3.12 .venv-crewai && uv pip install -p .venv-crewai -r requirements-crewai.txt

# Microsoft Agent Framework: *_msaf.py
uv venv -p 3.12 .venv-msaf && uv pip install -p .venv-msaf -r requirements-msaf.txt

.venv/bin/python 03_graph_basics.py
.venv-crewai/bin/python 04_tools_crewai.py
```

Todos los ejemplos usan el mismo CRM falso de `code/crm.py`, así el problema es idéntico en cada tab y solo cambia el framework.

## Errores comunes

- Elegir framework por popularidad en vez de por el tipo de control que necesitás.
- Mezclar dos frameworks de orquestación en el mismo servicio. Elegí uno; integraciones sueltas (un vector store de LangChain dentro de un Flow de CrewAI) sí están bien.
- Aprender tutoriales viejos: `AgentExecutor`, `initialize_agent`, `ConversationBufferMemory` y los planners de Semantic Kernel son APIs reemplazadas.

## En una entrevista

- **¿LangChain o LangGraph?** LangGraph es el runtime de grafos con estado y persistencia; `create_agent` de LangChain es un agente prearmado que corre sobre LangGraph. Empiezo con `create_agent` y bajo a un grafo propio cuando necesito controlar el flujo.
- **¿Qué ventaja tiene CrewAI?** Modelar rápido un equipo de agentes por rol y tarea. Para producción uso Flows por el control del orden y del estado.
- **¿Qué pasó con AutoGen?** Microsoft lo unificó con Semantic Kernel en Microsoft Agent Framework; los group chats, handoffs y Magentic-One existen ahí como orquestaciones.
