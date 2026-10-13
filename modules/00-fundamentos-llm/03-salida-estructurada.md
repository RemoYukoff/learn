---
title: Salida estructurada
order: 3
type: implementacion
---

**Objetivo:** obtener del modelo objetos tipados y válidos (no "texto que parece JSON") para que el resto del sistema pueda confiar en ellos.

## Idea

Hay tres niveles, de peor a mejor:

| Nivel | Cómo | Garantía |
|---|---|---|
| Pedirlo en el prompt | "Respondé en JSON con estos campos" | Ninguna: puede agregar texto, olvidar campos o romper comillas |
| JSON mode | El proveedor fuerza JSON sintácticamente válido | JSON válido, pero sin garantía de esquema |
| **Structured outputs** | Le pasás un **JSON Schema** y el decoding se restringe a ese esquema | Cada respuesta valida contra el esquema |

Structured outputs funciona con *constrained decoding*: en cada paso solo se permiten los tokens que mantienen la salida dentro del esquema. Por eso es una garantía y no una sugerencia.

En Python el esquema se escribe como un modelo **Pydantic**; el SDK lo convierte a JSON Schema y valida la respuesta de vuelta al objeto. Es el mismo patrón que Zod en TypeScript.

### Diseño del esquema

- `Literal[...]` / enums para categorías: el modelo no puede inventar una nueva.
- `Field(description=...)`: las descripciones son parte del prompt.
- Campos opcionales solo si de verdad pueden faltar; si no, el modelo los omite para "ahorrar".
- Esquemas planos y chicos funcionan mejor que objetos muy anidados.
- Si necesitás "no sé", modelalo: `category: Literal[..., "unknown"]`.

> [!NOTE]
> La garantía es sintáctica y de esquema, no semántica. El JSON va a validar, pero el campo `priority` puede estar mal elegido. La calidad del contenido se mide con evals.

## Cómo se implementa

:::tabs
== Anthropic
`messages.parse()` recibe el modelo Pydantic en `output_format` y devuelve `parsed_output` ya validado.

```python
from typing import Literal
from pydantic import BaseModel, Field

class Ticket(BaseModel):
    category: Literal["billing", "bug", "feature_request", "other"]
    priority: Literal["low", "medium", "high"]
    summary: str = Field(description="One sentence, in English")
    customer_wants_refund: bool

response = client.messages.parse(
    model="claude-opus-5-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Extract the ticket fields:\n\n{text}"}],
    output_format=Ticket,
)
ticket: Ticket = response.parsed_output
```

Sin Pydantic, pasás el JSON Schema crudo en `messages.create(output_config={"format": {"type": "json_schema", "schema": {...}}})` y hacés `json.loads` del bloque de texto. El esquema necesita `additionalProperties: false` y `required`.

Ejemplo completo: `code/03_structured_anthropic.py`
== OpenAI
En el SDK de OpenAI, `chat.completions.parse()` recibe el modelo Pydantic en `response_format`. Funciona igual contra OpenAI o contra cualquier API compatible.

```python
completion = client.chat.completions.parse(
    model="gpt-5.6-luna",
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Extract the ticket fields:\n\n{text}"}],
    response_format=Ticket,
)
message = completion.choices[0].message
ticket = message.parsed           # None if the model refused
if message.refusal:
    ...
```

La Responses API (la más nueva de OpenAI) usa `client.responses.parse(..., text_format=Ticket)` y devuelve `response.output_parsed`.
== OpenRouter
OpenRouter es compatible con la API de OpenAI: mismo SDK, otro `base_url`. El mismo código sirve para Claude, GPT o Gemini cambiando el string del modelo.

```python
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])

completion = client.chat.completions.parse(
    model="anthropic/claude-opus-5.5",   # or "openai/gpt-5.6-luna", "google/gemini-3.8-flash"
    max_tokens=1024,
    messages=[{"role": "user", "content": f"Extract the ticket fields:\n\n{text}"}],
    response_format=Ticket,
)
```

Verificá en la página del modelo en OpenRouter que soporte `structured_outputs`. Si no, cae a JSON mode o falla.

Ejemplo completo: `code/03_structured_openrouter.py`
:::

## Errores comunes

- Pedir JSON en el prompt y parsear con regex. Usá structured outputs.
- Olvidar chequear `refusal` / `stop_reason`: una negativa o un corte por `max_tokens` no trae objeto válido.
- Esquemas con 40 campos opcionales: el modelo deja vacíos los que no entiende.
- Confiar en la semántica porque el esquema validó.

## En una entrevista

- **¿Cómo garantizás que el LLM devuelva JSON válido?** Structured outputs con JSON Schema (constrained decoding), validado con Pydantic. Pedirlo en el prompt no alcanza.
- **¿Diferencia entre JSON mode y structured outputs?** JSON mode garantiza sintaxis JSON; structured outputs garantiza el esquema.
- **¿Qué hacés si el modelo no soporta structured outputs?** Tool use con `strict: true` (módulo 01) o validar con Pydantic y reintentar pasando el error al modelo.
