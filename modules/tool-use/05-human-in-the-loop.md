---
title: Human-in-the-loop
order: 5
type: concepto
---

**Objetivo:** poner una aprobación humana delante de las acciones sensibles sin romper el flujo del agente.

## Idea

Cuando un agente puede ejecutar acciones críticas, hace falta una política de confirmación. La idea es simple: algunas tools no se ejecutan hasta que una persona dice que sí.

### Qué requiere aprobación

Clasificá las tools por riesgo, no por intuición:

| Riesgo | Ejemplos | Política típica |
|---|---|---|
| Lectura | listar, buscar, consultar | Sin aprobación |
| Escritura reversible | cambiar estado de un ticket, crear borrador | Aprobación opcional o por umbral |
| Irreversible o con dinero | reembolsos, enviar emails a clientes, borrar | Siempre aprobación |

Umbrales: "reembolsos de más de 100 USD requieren aprobación" es más útil que "todos" o "ninguno".

### Dónde va el control

**En el ejecutor de tools, no en el prompt.** Pedirle al modelo "preguntá antes de reembolsar" no garantiza nada. El código intercepta la llamada y no la ejecuta sin aprobación.

### Qué pasa cuando el humano dice que no

La negativa vuelve al modelo como un `tool_result` normal: "El operador rechazó esta acción. Nota: …". El modelo puede explicar, pedir datos o tomar otro camino. No es un error ni corta el loop.

### Sincrónico vs asincrónico

- **Sincrónico**: el agente espera la respuesta (CLI, chat con el usuario presente). Es lo que hace el ejemplo.
- **Asincrónico**: la aprobación llega minutos u horas después (Slack, un panel). El agente tiene que **guardar su estado** y reanudar. Eso necesita persistencia, que es justamente lo que dan los frameworks del módulo de Orquestación de agentes (`interrupt` en LangGraph, approval requests en Agent Framework).

### Auditoría

Cada acción sensible deja registro: qué pidió el agente, quién aprobó, cuándo, qué se ejecutó y el resultado. En integraciones con ERPs y CRMs de clientes esto suele ser requisito contractual.

## Cómo se ve en código

Un agente al que se le pide reembolsar 49 USD y cerrar el ticket. Antes de ejecutar `issue_refund` y `update_ticket_status`, el ejecutor pide aprobación (por consola en una CLI, con un botón en Slack en producción). Si el operador rechaza con una nota, el modelo la recibe y responde en consecuencia.

```python
NEEDS_APPROVAL = {"issue_refund", "update_ticket_status"}

def run_tool(name, args):
    if name in NEEDS_APPROVAL:
        ok, note = approve(name, args)          # input() in a CLI, a Slack button in prod
        if not ok:
            return {"content": f"The human operator rejected this action. Their note: {note}"}
    return {"content": crm.FUNCTIONS[name](**args)}
```

> [!TIP]
> Mostrale al humano los argumentos exactos que se van a ejecutar, no el resumen del modelo. El resumen puede no coincidir con la llamada.

## Errores comunes

- Confiar en el prompt para pedir confirmación.
- Pedir aprobación para todo: el humano empieza a aprobar sin leer.
- Tratar el rechazo como excepción y cortar el agente.
- Aprobación asincrónica sin persistencia: si el proceso se reinicia, se pierde la tarea.

## Preguntas de repaso

- **¿Cómo implementás human-in-the-loop?** Interceptando la ejecución de tools sensibles en el código, pidiendo aprobación con los argumentos exactos y devolviendo la decisión al modelo como resultado. Para aprobaciones diferidas, persistir el estado del agente y reanudar.
- **¿Qué acciones deberían requerir aprobación?** Las irreversibles, las que mueven dinero o datos fuera, y las de alto impacto, con umbrales de negocio.
