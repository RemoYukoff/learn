---
title: Definir tools
order: 2
type: implementacion
---

**Objetivo:** escribir definiciones de tools que el modelo use bien, y leer lo que el modelo devuelve en cada proveedor.

## Idea

Una tool tiene tres partes. Las tres son prompt:

| Parte | Buenas prácticas |
|---|---|
| `name` | Verbo + objeto, snake_case: `list_tickets`, `issue_refund` |
| `description` | Qué hace, cuándo usarla, cuándo no, qué devuelve, efectos secundarios ("irreversible") |
| Esquema de parámetros | JSON Schema con `description` en cada campo, `enum` para valores fijos, `required` y `additionalProperties: false` |

### Diseñar el set de tools

- **Pocas y específicas** mejor que muchas genéricas. `update_ticket_status(ticket_id, status)` en vez de `update_ticket(fields: object)`.
- **Alineadas a tareas**, no a endpoints: si siempre hacés buscar cliente → listar tickets, quizás conviene `get_customer_overview(name)`.
- **Resultados cortos y útiles**: devolvé los campos que el modelo necesita, no la respuesta cruda de la API. Incluí IDs para encadenar llamadas.
- **Errores accionables**: "Unknown customer_id 'X'. Use find_customer first." le dice al modelo cómo corregirse.
- Separá **lectura** de **escritura**: facilita aplicar confirmación humana solo a las que modifican.

### Strict mode

Con `strict: true` el proveedor garantiza que el `input` valida contra tu esquema (mismo mecanismo que salida estructurada). Requiere `additionalProperties: false` y todos los campos en `required`. Soporta un subconjunto de JSON Schema: si usás restricciones raras (`exclusiveMinimum`, `pattern` complejos) validalas en tu código.

Los fragmentos del módulo usan un CRM ficticio con cuatro tools: `find_customer(name)`, `list_tickets(customer_id, status)`, `update_ticket_status(ticket_id, status)` e `issue_refund(customer_id, amount_usd, reason)`. Detrás de cada una puede haber una lista en memoria o una llamada HTTP a HubSpot: para el agente es lo mismo.

## Cómo se implementa

:::tabs
== Anthropic
Las tools van en `tools` con `input_schema`. La respuesta trae bloques `tool_use` con `id`, `name` e `input` (ya parseado a dict) y `stop_reason == "tool_use"`.

```python
TOOLS = [{
    "name": "list_tickets",
    "description": "List support tickets of a customer filtered by status. Returns a JSON list.",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "Customer id like C-100"},
            "status": {"type": "string", "enum": ["open", "closed"]},
        },
        "required": ["customer_id", "status"],
        "additionalProperties": False,
    },
}]

response = client.messages.create(
    model="claude-opus-5-5",
    max_tokens=4096,
    tools=[{**t, "strict": True} for t in TOOLS],
    messages=[{"role": "user", "content": "Which tickets does Acme have open?"}],
)
for block in response.content:
    if block.type == "tool_use":
        print(block.id, block.name, block.input)   # input is a dict
```

== OpenAI
Cada tool va envuelta en `{"type": "function", "function": {...}}` y el esquema se llama `parameters`. Las llamadas vienen en `message.tool_calls` y los **argumentos son un string JSON** que tenés que parsear.

```python
tools = [{
    "type": "function",
    "function": {
        "name": "list_tickets",
        "description": "List support tickets of a customer filtered by status.",
        "parameters": {...same JSON Schema...},
        "strict": True,
    },
}]

completion = client.chat.completions.create(
    model="anthropic/claude-opus-5.5",      # via OpenRouter; "gpt-5.6-luna" on OpenAI
    max_tokens=4096,
    tools=tools,
    messages=[{"role": "user", "content": "Which tickets does Acme have open?"}],
)
message = completion.choices[0].message
for call in message.tool_calls or []:
    args = json.loads(call.function.arguments)  # string, not dict
    print(call.id, call.function.name, args)
```

Convertir del formato de Anthropic al de OpenAI es mecánico:

```python
def to_openai(tools: list[dict]) -> list[dict]:
    return [{"type": "function",
             "function": {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}}
            for t in tools]
```
:::

| | Anthropic | OpenAI / OpenRouter |
|---|---|---|
| Esquema | `input_schema` | `function.parameters` |
| Señal de tool | `stop_reason == "tool_use"` | `finish_reason == "tool_calls"` |
| Llamada | bloque `tool_use` en `content` | `message.tool_calls[]` |
| Argumentos | dict | string JSON |
| Resultado | bloque `tool_result` dentro de un mensaje `user` | mensaje `role: "tool"` por llamada |

## Errores comunes

- Parsear `arguments` de OpenAI como dict o hacer matching de strings sobre el JSON: siempre `json.loads`.
- Cambiar el orden o el texto de las tools entre llamadas: invalida el prompt cache (las tools son lo primero del prefijo).
- Descripciones que se contradicen con el system prompt.
- Una tool "god mode" con un parámetro `action` que hace cinco cosas distintas.

## En una entrevista

- **¿Qué hace que una tool sea fácil de usar para el modelo?** Nombre claro, descripción con cuándo usarla y qué devuelve, parámetros descritos y con enums, resultados cortos y errores que indican cómo corregirse.
- **¿Qué es strict mode?** Garantía de que los argumentos validan contra el esquema, por constrained decoding.
- **¿Diferencias entre el formato de Anthropic y OpenAI?** Mismo concepto; cambian los nombres, que OpenAI devuelve los argumentos como string, y cómo se devuelven los resultados.
