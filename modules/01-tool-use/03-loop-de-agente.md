---
title: Loop de agente desde cero
order: 3
type: implementacion
---

**Objetivo:** escribir el loop de agente a mano, entender cada línea, y saber qué te ahorra un tool runner o un framework.

## Idea

Un agente es este loop:

```text
messages = [pedido del usuario]
repetir hasta N veces:
    respuesta = modelo(messages, tools)
    agregar respuesta a messages            ← completa, con los bloques tool_use
    si no pidió tools: devolver el texto    ← terminó
    para cada tool pedida:
        resultado = ejecutar(tool, input)   ← errores como resultado, no excepción
    agregar TODOS los resultados a messages ← en un solo mensaje
```

Cinco reglas que, si no se cumplen, rompen el loop:

1. **El historial se reenvía completo** en cada vuelta (la API es stateless).
2. **La respuesta del assistant se guarda entera**, incluidos los bloques `tool_use` y `thinking`. Si guardás solo el texto, la API rechaza los `tool_result` porque no encuentra el `tool_use` que responden.
3. **Cada `tool_result` referencia el `id`** del `tool_use` que responde.
4. **Todos los resultados de un turno van juntos.** Partirlos en varios mensajes enseña al modelo a dejar de pedir tools en paralelo.
5. **Siempre hay un límite de vueltas.** Un agente sin tope puede quedar en loop gastando plata.

### Condición de salida

Se termina cuando `stop_reason` deja de ser `tool_use`. Revisá cuál fue: `end_turn` es éxito; `max_tokens` es una respuesta cortada; `refusal` es una negativa. No las trates igual.

### Tool runner: el loop empaquetado

Los SDKs y frameworks traen el loop hecho. El de Anthropic (`client.beta.messages.tool_runner`) genera el esquema desde la firma y el docstring de una función decorada, ejecuta las tools y vuelve a llamar hasta terminar. Te deja engancharte en cada vuelta para loguear, aprobar o modificar resultados.

Cuándo escribir el loop a mano: control total del flujo, formatos no estándar, o cuando querés entender qué pasa (como acá). En producción, tool runner o framework (módulo 02), salvo que tengas una razón.

## Cómo se implementa

:::tabs
== Anthropic
```python
def agent(task: str) -> str:
    messages = [{"role": "user", "content": task}]
    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model="claude-opus-5-5", max_tokens=8192, system=SYSTEM, tools=TOOLS, messages=messages
        )
        messages.append({"role": "assistant", "content": response.content})   # full content
        if response.stop_reason != "tool_use":
            return next((b.text for b in response.content if b.type == "text"), "")

        results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": FUNCTIONS[block.name](**block.input)})
                except Exception as e:
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": f"{type(e).__name__}: {e}", "is_error": True})
        messages.append({"role": "user", "content": results})               # one message
    return "[gave up]"
```

Con el tool runner, lo mismo sin loop:

```python
from anthropic import beta_tool

@beta_tool
def list_tickets(customer_id: str, status: str = "open") -> str:
    """List support tickets of a customer filtered by status.

    Args:
        customer_id: Customer id like C-100.
        status: "open" or "closed".
    """
    return crm.list_tickets(customer_id, status)

runner = client.beta.messages.tool_runner(
    model="claude-opus-5-5", max_tokens=8192, max_iterations=10,
    tools=[find_customer, list_tickets, update_ticket_status],
    messages=[{"role": "user", "content": "..."}],
)
for message in runner:          # one iteration per model response
    ...
```

Ejemplos: `code/03_agent_loop.py` y `code/03_tool_runner.py`
== OpenAI
Mismo loop. Cambia que los resultados van como **un mensaje `role: "tool"` por llamada** y que el mensaje del assistant se guarda con sus `tool_calls`.

```python
def agent(task: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    for _ in range(MAX_TURNS):
        completion = client.chat.completions.create(
            model=MODEL, max_tokens=8192, tools=to_openai(TOOLS), messages=messages
        )
        message = completion.choices[0].message
        messages.append(message.model_dump(exclude_none=True))   # keeps tool_calls
        if not message.tool_calls:
            return message.content
        for call in message.tool_calls:
            try:
                result = FUNCTIONS[call.function.name](**json.loads(call.function.arguments))
            except Exception as e:
                result = f"ERROR {type(e).__name__}: {e}"
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    return "[gave up]"
```

Ejemplo: `code/03_agent_loop_openrouter.py`
:::

> [!TIP]
> Corré `code/03_agent_loop.py` y mirá el orden de las llamadas impresas: busca el cliente, lista tickets, cierra el de CSV y vuelve a listar. Nadie le programó ese plan: lo deduce de las descripciones de las tools.

## Errores comunes

- Guardar solo el texto del assistant: la siguiente llamada falla con un error de `tool_use_id` sin pareja.
- Mandar cada `tool_result` en su propio mensaje.
- Lanzar la excepción de una tool hacia arriba: el agente muere en vez de corregirse.
- Loop sin límite de vueltas.
- Confundir `max_tokens` con fin normal.

## En una entrevista

- **Describí el loop de un agente.** Llamar al modelo con tools, si pide tools ejecutarlas y devolver resultados, repetir hasta que responda sin tools o se alcance un límite.
- **¿Qué pasa si una tool falla?** Se devuelve el error como `tool_result` con `is_error`, con un mensaje que le permita corregirse; el loop sigue.
- **¿Por qué usarías un framework en vez del loop a mano?** Persistencia, streaming, human-in-the-loop, reintentos y observabilidad ya resueltos. A cambio, más abstracción y dependencia.
