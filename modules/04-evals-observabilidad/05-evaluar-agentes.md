---
title: Evaluar agentes
order: 5
type: implementacion
---

**Objetivo:** evaluar un agente por partes (cada decisión, el camino y el resultado) para poder diagnosticar qué falla.

## Idea

Un agente hace muchas cosas antes de responder. Evaluar solo la respuesta final te dice **que** falló, no **dónde**. Se evalúan tres capas:

| Capa | Pregunta | Cómo se mide |
|---|---|---|
| **Paso** (tool call) | ¿Eligió la tool correcta con los argumentos correctos? | Comparación determinista contra lo esperado; validez de argumentos |
| **Trayectoria** | ¿El camino fue razonable? ¿Sin pasos de más, sin loops? | Match contra una trayectoria de referencia (estricto, sin orden, subconjunto) o juez LLM |
| **Resultado** | ¿Completó la tarea? | Verificar el **estado final** del sistema, o juez LLM sobre la respuesta |

### Verificar el estado, no el texto

Para agentes que actúan sobre sistemas, la mejor verificación es mirar el mundo después de correr: ¿el ticket quedó cerrado?, ¿el reembolso existe y es de 49 USD?, ¿no se creó ningún reembolso duplicado? Es exactamente un test de integración: preparás un estado, corrés el agente contra un entorno de prueba (o tools simuladas) y hacés asserts sobre el estado final. Es determinista y no depende de cómo el agente lo explique.

### Trayectorias: cuánto exigir

| Modo | Pasa si | Cuándo |
|---|---|---|
| Estricto | Mismas tools, mismo orden | Flujos regulados donde el orden importa |
| Sin orden | Mismas tools, cualquier orden | Pasos independientes |
| Superset | Hizo al menos las esperadas (puede hacer más) | Verificar que no se saltee pasos obligatorios |
| Subset | No hizo nada fuera de lo esperado | Verificar que no se exceda (acciones no permitidas) |

Exigir trayectoria estricta en un agente abierto genera falsos negativos: hay varios caminos válidos. Combiná "superset de lo obligatorio" con "subset de lo permitido" y un tope de pasos.

### Métricas de agentes en producción

Tasa de tareas completadas, pasos promedio por tarea, tasa de errores por tool, tasa de escalamiento a humano, costo y latencia por tarea. Son las que aparecen en las búsquedas como "tasa de éxito de tool calls".

### Simulación de usuarios

Para agentes conversacionales, un segundo LLM hace de usuario con un objetivo y una personalidad, y conversa con el agente durante varios turnos. Después se evalúa la conversación completa. DeepEval y openevals traen simuladores; también se escribe en pocas líneas.

## Cómo se implementa

Caso común a todos los tabs: "Acme fue cobrado dos veces (49 USD): reembolsá y cerrá el ticket". La trayectoria esperada incluye `find_customer`, `issue_refund` y `update_ticket_status`.

:::tabs
== LangSmith
openevals (del equipo de LangChain) trae evaluadores de trayectoria que comparan mensajes en formato OpenAI, deterministas y sin llamar a ningún modelo. Se usan como evaluadores en `evaluate()` o en el plugin de pytest.

```python
from openevals.trajectory.match import create_trajectory_match_evaluator

must_do = create_trajectory_match_evaluator(
    trajectory_match_mode="superset",      # did at least these steps
    tool_args_match_mode="ignore",         # only compare tool names here
)
reference = [
    {"role": "user", "content": task},
    {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "find_customer", "arguments": "{}"}},
        {"function": {"name": "issue_refund", "arguments": "{}"}},
        {"function": {"name": "update_ticket_status", "arguments": "{}"}},
    ]},
]
result = must_do(outputs=agent_messages, reference_outputs=reference)
# {'key': 'trajectory_superset_match', 'score': True, ...}
```

`tool_args_match_overrides` permite reglas por tool (por ejemplo, comparar `amount_usd` exacto y el `reason` ignorando mayúsculas). openevals también tiene `create_trajectory_llm_as_judge`; ese usa `with_structured_output` de LangChain y necesita un juez que acepte `tool_choice` forzado (ver capítulo 3).
== DeepEval
`LLMTestCase` acepta `tools_called` y `expected_tools`. `ToolCorrectnessMetric` compara las tools (opcionalmente argumentos y orden); `TaskCompletionMetric` usa un juez para decidir si la tarea se completó.

```python
from deepeval import assert_test
from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase, ToolCall

case = LLMTestCase(
    input=task,
    actual_output=final_answer,
    tools_called=[ToolCall(name=c["name"], input_parameters=c["args"]) for c in calls],
    expected_tools=[ToolCall(name="find_customer"), ToolCall(name="issue_refund"),
                    ToolCall(name="update_ticket_status")],
)
judge = AnthropicModel(model="claude-opus-5-5")
assert_test(case, [
    ToolCorrectnessMetric(should_consider_ordering=False, threshold=1.0),
    TaskCompletionMetric(model=judge, threshold=0.8),
])
```
== ragas
ragas representa la conversación con sus propios tipos de mensaje. `ToolCallAccuracy` compara las tool calls contra una referencia; `AgentGoalAccuracyWithReference` usa un juez para decidir si se alcanzó el objetivo.

```python
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from ragas.metrics.collections import AgentGoalAccuracyWithReference, ToolCallAccuracy

conversation = [
    HumanMessage(content=task),
    AIMessage(content="", tool_calls=[ToolCall(name="find_customer", args={"name": "Acme"})]),
    ToolMessage(content='[{"id": "C-100"}]'),
    AIMessage(content="", tool_calls=[ToolCall(name="issue_refund",
              args={"customer_id": "C-100", "amount_usd": 49, "reason": "Duplicate charge T-1"})]),
    ToolMessage(content='{"id": "R-1"}'),
    AIMessage(content="Refunded 49 USD and closed T-1."),
]
tools = await ToolCallAccuracy(strict_order=False).ascore(
    user_input=conversation,
    reference_tool_calls=[ToolCall(name="find_customer", args={"name": "Acme"}),
                          ToolCall(name="issue_refund", args={"customer_id": "C-100", "amount_usd": 49,
                                                               "reason": "Duplicate charge T-1"})],
)
goal = await AgentGoalAccuracyWithReference(llm=llm).ascore(
    user_input=conversation, reference="The customer is refunded 49 USD and the ticket is closed.")
```

En este ejemplo el agente nunca llama a `update_ticket_status`: `ToolCallAccuracy` pasa (hizo lo que la referencia pide) pero el juez de objetivo debería fallar, porque el ticket no quedó cerrado. Es el tipo de diferencia que justifica medir las dos capas.
:::

## Errores comunes

- Evaluar solo el texto final de un agente que modifica sistemas: verificá el estado.
- Trayectoria estricta en un agente abierto: falla por caminos alternativos válidos.
- No medir pasos por tarea: un agente que acierta en 15 pasos cuesta 5 veces más que uno que acierta en 3.
- Correr evals de agentes contra sistemas reales con efectos: usá tools simuladas o un entorno de prueba.

## En una entrevista

- **¿Cómo evaluás un agente?** En tres capas: cada tool call (tool y argumentos), la trayectoria (pasos obligatorios, sin acciones no permitidas, tope de pasos) y el resultado (estado final del sistema o juez LLM).
- **¿Qué es trajectory evaluation?** Comparar la secuencia de pasos del agente con una referencia, en modo estricto, sin orden, subset o superset según cuánto importe el camino.
- **¿Cómo evitás efectos reales al evaluar un agente?** Tools mockeadas o un entorno sandbox con datos de prueba, y asserts sobre su estado final.
