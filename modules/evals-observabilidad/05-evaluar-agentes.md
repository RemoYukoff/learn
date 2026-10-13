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

### Por qué medir más de una capa

Las capas fallan de forma independiente. Un agente puede llamar exactamente a las tools que pedía la referencia (paso y trayectoria aprueban) y aun así no completar la tarea: por ejemplo, reembolsa pero nunca cierra el ticket porque la referencia no incluía ese paso. Al revés, puede llegar al resultado correcto por un camino de 15 pasos que cuesta cinco veces más. Medir solo una capa esconde la otra falla.

### Métricas de agentes en producción

Tasa de tareas completadas, pasos promedio por tarea, tasa de errores por tool, tasa de escalamiento a humano, costo y latencia por tarea.

### Simulación de usuarios

Para agentes conversacionales, un segundo LLM hace de usuario con un objetivo y una personalidad, y conversa con el agente durante varios turnos. Después se evalúa la conversación completa. DeepEval trae un simulador; también se escribe en pocas líneas.

## Cómo se implementa

Caso común a todos los tabs: "Acme fue cobrado dos veces (49 USD): reembolsá y cerrá el ticket". La trayectoria esperada incluye `find_customer`, `issue_refund` y `update_ticket_status`.

:::tabs
== LangSmith
En LangSmith un evaluador es una función común: recibe lo que devolvió el agente y la referencia del dataset, y devuelve un puntaje. Para trayectorias alcanza con comparar conjuntos de nombres de tools: lo obligatorio tiene que estar, lo prohibido no.

```python
from langsmith import evaluate

def target(inputs: dict) -> dict:
    result = run_agent(inputs["task"])          # your agent: final answer + tool calls made
    return {"answer": result.answer, "tools": [call.name for call in result.tool_calls]}

def required_tools(outputs: dict, reference_outputs: dict) -> dict:
    missing = set(reference_outputs["required_tools"]) - set(outputs["tools"])
    return {"key": "required_tools", "score": not missing, "comment": f"missing: {sorted(missing)}"}

def no_forbidden_tools(outputs: dict, reference_outputs: dict) -> bool:
    return not set(outputs["tools"]) & set(reference_outputs.get("forbidden_tools", []))

def step_budget(outputs: dict) -> bool:
    return len(outputs["tools"]) <= 6

evaluate(target, data="agent-refunds",
         evaluators=[required_tools, no_forbidden_tools, step_budget])
```

Cada ejemplo del dataset `agent-refunds` guarda en sus outputs de referencia `required_tools` (por ejemplo `find_customer`, `issue_refund`, `update_ticket_status`) y `forbidden_tools`. El resultado final se evalúa con otro evaluador: un juez como el del capítulo 3, o un chequeo del estado del sistema.
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
:::

## Errores comunes

- Evaluar solo el texto final de un agente que modifica sistemas: verificá el estado.
- Trayectoria estricta en un agente abierto: falla por caminos alternativos válidos.
- No medir pasos por tarea: un agente que acierta en 15 pasos cuesta 5 veces más que uno que acierta en 3.
- Correr evals de agentes contra sistemas reales con efectos: usá tools simuladas o un entorno de prueba.

## Preguntas de repaso

- **¿Cómo evaluás un agente?** En tres capas: cada tool call (tool y argumentos), la trayectoria (pasos obligatorios, sin acciones no permitidas, tope de pasos) y el resultado (estado final del sistema o juez LLM).
- **¿Qué es trajectory evaluation?** Comparar la secuencia de pasos del agente con una referencia, en modo estricto, sin orden, subset o superset según cuánto importe el camino.
- **¿Cómo evitás efectos reales al evaluar un agente?** Tools mockeadas o un entorno sandbox con datos de prueba, y asserts sobre su estado final.
