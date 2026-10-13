---
title: LLM-as-judge
order: 3
type: implementacion
---

**Objetivo:** usar un modelo para calificar salidas de otro de forma confiable, y saber cuándo no confiar en él.

## Idea

Un **juez LLM** recibe el caso (entrada, salida a evaluar, referencia o contexto) y una **rúbrica**, y devuelve un veredicto estructurado. Es la forma escalable de evaluar texto libre.

### Formatos

| Formato | Qué devuelve | Cuándo |
|---|---|---|
| **Binario / categórico** | pass/fail, o yes/partial/no | El más confiable. Default |
| **Escala** | 1–5 | Útil con rúbrica por nivel; sin ella, los jueces se amontonan en 4 |
| **Pairwise** | Cuál de dos salidas es mejor | Comparar versiones (A/B offline). Más consistente que puntuar por separado |
| **Con referencia** | ¿Coincide con la respuesta esperada? | Correctness |
| **Sin referencia** | ¿Cumple el criterio? (tono, faithfulness al contexto, seguridad) | Producción, donde no hay referencia |

### Cómo escribir un buen juez

1. **Un criterio por juez.** "¿Es correcta?" y "¿es amable?" son dos jueces, no uno.
2. **Rúbrica explícita** con qué cuenta como pass y como fail, y ejemplos de cada uno.
3. **Razonamiento antes del veredicto** (campo `reason` primero, o thinking del modelo).
4. **Salida estructurada** para parsear el veredicto sin regex.
5. **Modelo fuerte como juez**, idealmente distinto del evaluado.

### Sesgos conocidos

| Sesgo | Efecto | Mitigación |
|---|---|---|
| Posición | En pairwise prefiere la primera (o segunda) opción | Evaluar en ambos órdenes |
| Verbosidad | Prefiere respuestas largas | Rúbrica que penalice relleno |
| Auto-preferencia | Prefiere salidas de su misma familia de modelos | Juez de otro proveedor o validar con humanos |
| Complacencia | Aprueba lo que "suena bien" | Pedir verificación contra el contexto, frase por frase |

### Calibrar al juez

El juez es un test que también hay que testear:

1. Etiquetá a mano 50–100 casos.
2. Evaluar los mismos casos con el juez.
3. Medí acuerdo (porcentaje de coincidencia, o Cohen's kappa) y mirá los desacuerdos.
4. Ajustá la rúbrica hasta que el acuerdo sea aceptable. Recién ahí usalo en CI.

## Cómo se implementa

Mismo juez en todos los tabs: ¿la respuesta de un bot de soporte es correcta comparada con la referencia?

:::tabs
== Anthropic
Sin librería: un prompt con rúbrica y salida estructurada.

```python
from typing import Literal
from pydantic import BaseModel

class Verdict(BaseModel):
    reason: str                         # reasoning first, verdict second
    verdict: Literal["pass", "fail"]

RUBRIC = """Grade the answer against the reference.
pass: states the same facts as the reference; extra correct detail is fine.
fail: contradicts the reference, misses a key fact, or adds an unsupported claim."""

def judge(question: str, answer: str, reference: str) -> Verdict:
    response = client.messages.parse(
        model="claude-opus-5-5",
        max_tokens=1024,
        system=RUBRIC,
        messages=[{"role": "user", "content":
            f"<question>{question}</question>\n<reference>{reference}</reference>\n<answer>{answer}</answer>"}],
        output_format=Verdict,
    )
    return response.parsed_output
```
== DeepEval
`GEval` arma el juez desde un criterio en lenguaje natural: genera pasos de evaluación y devuelve un score entre 0 y 1 con su razón. El modelo juez se elige con `model`.

```python
from deepeval.metrics import GEval
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

correctness = GEval(
    name="Correctness",
    criteria="The actual output states the same facts as the expected output, "
             "without contradicting it or adding unsupported claims.",
    evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
    model=AnthropicModel(model="claude-opus-5-5"),
    threshold=0.7,
)
case = LLMTestCase(input=question, actual_output=answer, expected_output=reference)
correctness.measure(case)
print(correctness.score, correctness.reason)
```
:::

## Errores comunes

- Un juez que evalúa cinco criterios a la vez y devuelve un número.
- Escalas 1–10 sin rúbrica por nivel.
- Usar el juez en CI sin haberlo comparado nunca contra etiquetas humanas.
- Pairwise en un solo orden.
- El mismo modelo como generador y juez sin validar el sesgo.

## Preguntas de repaso

- **¿Qué es LLM-as-judge y cuáles son sus riesgos?** Usar un LLM para calificar salidas con una rúbrica. Riesgos: sesgos de posición, verbosidad y auto-preferencia, y errores propios; se mitigan con rúbricas binarias, salida estructurada y calibración contra etiquetas humanas.
- **¿Cómo sabés si tu juez es confiable?** Midiendo acuerdo con etiquetas humanas sobre una muestra y revisando los desacuerdos antes de usarlo como gate.
- **¿Binario o escala?** Binario por defecto: es más consistente y más fácil de calibrar. Escala solo con rúbrica por nivel.
