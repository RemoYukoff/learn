---
title: Errores, reintentos y validación
order: 4
type: concepto
---

**Objetivo:** hacer que un agente sea confiable en producción: que se recupere de errores, que no ejecute entradas inválidas y que no se quede en loop.

## Idea

En un agente hay tres capas que fallan de forma distinta:

| Capa | Qué falla | Qué hacer |
|---|---|---|
| Llamada al modelo | 429, 5xx, timeouts, red | Reintentos con backoff (el SDK lo hace) y límite de concurrencia |
| Decisión del modelo | Tool equivocada, argumentos inválidos, loop | Validar, devolver error accionable, limitar vueltas y llamadas |
| Ejecución de la tool | La API externa falla, timeout, datos inexistentes | Capturar, traducir a mensaje útil, reintentar solo si es idempotente |

### Validar antes de ejecutar

El JSON Schema (y `strict`) garantiza tipos. Las **reglas de negocio** las validás vos: montos máximos, formatos de ID, permisos del usuario sobre ese recurso. Pydantic es la herramienta natural en Python.

Si la validación falla, **no ejecutes**: devolvé un `tool_result` con `is_error: true` y el detalle. El modelo casi siempre corrige en la siguiente vuelta o le explica al usuario.

### Errores como feedback

Un buen mensaje de error dice qué pasó y qué hacer:

```text
Mal:  Error 404
Bien: Unknown customer_id 'C-999'. Use find_customer to get a valid id.
```

### Límites que todo agente necesita

- **Vueltas máximas** del loop.
- **Llamadas por tool**: evita reintentar lo mismo indefinidamente.
- **Presupuesto de tokens o costo** por tarea.
- **Timeout por tool** (las APIs de clientes se cuelgan).

### Idempotencia y efectos secundarios

Los reintentos son seguros en lecturas. En escrituras (`issue_refund`), un reintento después de un timeout puede duplicar la operación. Usá **idempotency keys** si la API las soporta, o verificá el estado antes de reintentar. Esto es igual que en cualquier integración, pero el agente lo hace más probable porque reintenta solo.

### Observabilidad mínima

Por cada tool call registrá: tool, input, resultado o error, latencia, y el id de la conversación. Es lo que piden las búsquedas como "tasa de éxito de tool calls" y lo que vas a usar en evals (módulo 04).

## Cómo se ve en código

Un pedido de reembolso de 900 USD cuando la regla de negocio permite hasta 500: la validación con Pydantic rechaza la llamada antes de ejecutarla, el modelo recibe el error como `tool_result` y reacciona (explica el límite o propone otra acción). El ejecutor además corta después de 3 llamadas a la misma tool.

```python
class RefundInput(BaseModel):
    customer_id: str = Field(pattern=r"^C-\d+$")
    amount_usd: float = Field(gt=0, le=500)   # business rule
    reason: str = Field(min_length=5)

def run_tool(name, args, calls):
    calls[name] += 1
    if calls[name] > MAX_CALLS_PER_TOOL:
        return {"content": f"Tool {name} called too many times. Stop and report.", "is_error": True}
    if name in VALIDATORS:
        try:
            args = VALIDATORS[name](**args).model_dump()
        except ValidationError as e:
            return {"content": f"Invalid input: {e.errors(include_url=False)}", "is_error": True}
    ...
```

> [!NOTE]
> Tu experiencia en QA aplica directo: las tools son una API pública cuyo cliente es impredecible. Casos borde, entradas inválidas y estados inconsistentes son el día a día.

## Errores comunes

- Confiar en que el modelo respeta reglas escritas en el prompt ("nunca reembolses más de 500"). El prompt guía; el código hace cumplir.
- Errores genéricos que no le dicen al modelo cómo seguir.
- Reintentar escrituras sin idempotencia.
- No distinguir error de la tool (se lo contás al modelo) de error del sistema (alertás a un humano).

## En una entrevista

- **¿Cómo evitás que un agente ejecute una acción inválida?** Validación en código antes de ejecutar (esquema, reglas de negocio, permisos), y confirmación humana para lo irreversible.
- **¿Cómo evitás loops infinitos?** Límite de vueltas, de llamadas por tool y de presupuesto; detectar llamadas repetidas con los mismos argumentos.
- **¿Qué métricas mirás de un agente en producción?** Tasa de éxito de tool calls, errores por tool, vueltas por tarea, latencia, costo por tarea y tasa de tareas completadas.
