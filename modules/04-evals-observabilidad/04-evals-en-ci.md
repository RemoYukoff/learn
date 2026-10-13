---
title: Evals en CI
order: 4
type: implementacion
---

**Objetivo:** convertir las evals en un gate automático que corre en cada cambio de prompt, modelo o código, y conocer cómo lo resuelve cada herramienta.

## Idea

Una suite de evals en CI tiene las mismas piezas que una suite de tests, con dos diferencias: el resultado es un puntaje contra un umbral, y cuesta plata (llamadas al modelo).

```text
dataset versionado
   │
   ▼
correr el sistema (target) en cada caso
   │
   ▼
evaluadores ──▶ puntajes ──▶ comparar con umbral y versión anterior
                                   │
                                   ▼
                     pasa / falla el pipeline + reporte
```

### Decisiones de diseño

| Decisión | Opciones |
|---|---|
| Cuándo corre | En cada PR que toca prompts, modelos o código del agente; suite completa nightly |
| Cuánto corre | Subset rápido y barato en PR; dataset completo antes de release |
| Qué bloquea | Umbral por métrica y "ningún caso crítico pasa de bien a mal" |
| Dónde quedan los resultados | Archivo en el CI, o una plataforma que guarda experimentos y permite comparar |
| Costo | Cachear llamadas idénticas, modelos baratos para jueces simples, presupuesto por corrida |

### Panorama de herramientas

| Herramienta | Forma | Fuerte en | Detalle |
|---|---|---|---|
| **LangSmith** | Plataforma (SaaS / self-host) + SDK | Datasets, experimentos comparables, tracing integrado, plugin de pytest | Integra natural con LangChain/LangGraph pero sirve sin ellos |
| **DeepEval** | Librería Python, estilo pytest | 50+ métricas listas, `assert_test`, agentes, RAG | Open source |
| **Langfuse** | Plataforma open source | Datasets y experimentos sobre tracing | Self-hostable; ver capítulo 6 |

## Cómo se implementa

Mismo caso en todos los tabs: un bot de soporte (`support_bot(question) -> str`) y un dataset de preguntas con respuesta de referencia. El gate exige que la respuesta mencione el dato correcto y que un juez la apruebe.

:::tabs
== LangSmith
Dos estilos. **`evaluate()`** corre un target sobre un dataset guardado en LangSmith y registra un experimento comparable con los anteriores. Los evaluadores son funciones que reciben `inputs`, `outputs` y `reference_outputs`.

```python
from langsmith import Client, evaluate

client = Client()
client.create_dataset("support-golden")
client.create_examples(dataset_name="support-golden", examples=[
    {"inputs": {"question": "How much can an agent refund alone?"}, "outputs": {"answer": "200 USD"}},
])

def target(inputs: dict) -> dict:
    return {"answer": support_bot(inputs["question"])}

def mentions_reference(outputs: dict, reference_outputs: dict) -> bool:
    return reference_outputs["answer"].lower() in outputs["answer"].lower()

results = evaluate(target, data="support-golden", evaluators=[mentions_reference],
                   experiment_prefix="prompt-v7", num_repetitions=3)
```

**Plugin de pytest**: tests normales marcados con `@pytest.mark.langsmith`; cada corrida se registra como experimento.

```python
import pytest
from langsmith import testing as t

@pytest.mark.langsmith
def test_refund_limit():
    question = "How much can an agent refund alone?"
    t.log_inputs({"question": question})
    answer = support_bot(question)
    t.log_outputs({"answer": answer})
    t.log_feedback(key="mentions_limit", score="200" in answer)
    assert "200" in answer
```
== DeepEval
Estilo pytest: cada caso es un `LLMTestCase` y `assert_test` falla si alguna métrica queda bajo su umbral.

```python
import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import GEval
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

dataset = EvaluationDataset(goldens=[
    Golden(input="How much can an agent refund alone?", expected_output="Up to 200 USD."),
])
correctness = GEval(
    name="Correctness",
    criteria="The actual output states the same facts as the expected output.",
    evaluation_params=[SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
    model=AnthropicModel(model="claude-opus-5-5"),
    threshold=0.7,
)

@pytest.mark.parametrize("golden", dataset.goldens)
def test_support_bot(golden: Golden):
    case = LLMTestCase(input=golden.input, actual_output=support_bot(golden.input),
                       expected_output=golden.expected_output)
    assert_test(case, [correctness])
```
:::

## Errores comunes

- Correr la suite completa con jueces caros en cada commit: lento y caro. Subset en PR, completo nightly.
- Umbrales tan altos que el pipeline falla por ruido; tan bajos que nada bloquea.
- No cachear: cada corrida paga de nuevo las mismas llamadas.
- Resultados que solo quedan en el log del CI y no se pueden comparar con la versión anterior.
- Cambiar dataset y prompt en el mismo PR: no sabés qué movió los números.

## En una entrevista

- **¿Cómo integrás evals en CI/CD?** Dataset versionado, target que ejecuta el sistema, evaluadores deterministas y LLM, umbrales por métrica y por casos críticos; subset en PR y suite completa nightly; resultados guardados como experimentos para comparar.
- **¿LangSmith o DeepEval?** LangSmith si querés una plataforma con datasets, experimentos comparables y tracing juntos; DeepEval si el equipo vive en pytest y querés métricas listas para usar.
- **¿Cómo controlás el costo de las evals?** Cache, subsets, jueces más baratos donde alcanza, y checks deterministas primero.
