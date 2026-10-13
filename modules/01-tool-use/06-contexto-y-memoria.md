---
title: Contexto y memoria del agente
order: 6
type: concepto
---

**Objetivo:** controlar cuánto contexto consume un agente a medida que trabaja y distinguir los tipos de memoria que se mencionan en las búsquedas.

## Idea

### El contexto crece en cada vuelta

Cada vuelta del loop reenvía todo: system prompt, tools, pedido, cada llamada y cada resultado. Con resultados de tools grandes, el contexto se llena rápido, y eso trae tres problemas:

- **Costo**: pagás esos tokens en cada vuelta.
- **Latencia**: más entrada, más tiempo hasta el primer token.
- **Calidad**: con mucho ruido, el modelo pierde lo relevante (*context rot*).

Medí `usage.input_tokens` por vuelta: es la primera métrica de salud de un agente.

### Estrategias, de simple a compleja

| Estrategia | Qué hace | Cuándo |
|---|---|---|
| Resultados chicos | La tool devuelve solo lo necesario | Siempre, es lo más barato |
| Recortar resultados viejos | Reemplazar `tool_result` antiguos por un placeholder | Agentes con muchas lecturas grandes |
| Context editing (servidor) | El proveedor borra resultados viejos según reglas | Igual, sin código propio |
| Resumen / compaction | Resumir el historial viejo en un bloque corto | Conversaciones largas |
| Sub-agentes | Un agente lee mucho y devuelve solo la conclusión | Tareas de investigación o fan-out |

### Tipos de memoria

"Memoria" en las búsquedas suele mezclar dos cosas:

| | Memoria de corto plazo | Memoria de largo plazo |
|---|---|---|
| Qué es | El historial de esta conversación o tarea | Hechos que sobreviven entre conversaciones |
| Dónde vive | `messages` (o el checkpoint del framework) | Base de datos, vector store, archivos |
| Ejemplo | "el cliente que buscaste recién es C-100" | "este usuario prefiere respuestas en inglés" |
| Cómo se lee | Va entera en cada llamada | Se busca lo relevante y se inyecta, o el agente la consulta con una tool |

La de largo plazo se implementa de dos maneras: **retrieval automático** (antes de cada llamada buscás recuerdos relevantes y los agregás al prompt, como RAG en el módulo 03) o **memoria como tool** (el agente decide cuándo leer y escribir, por ejemplo la memory tool de Anthropic que expone un directorio de archivos).

Los frameworks del módulo 02 le dan nombre a esto: *checkpointer* (corto plazo, por thread) y *store* (largo plazo) en LangGraph; *sessions* y *context providers* en Agent Framework; *memory* en CrewAI.

## Cómo se ve en código

Recorte en el cliente: antes de cada llamada, los `tool_result` viejos se reemplazan por un placeholder y solo el último queda completo.

```python
def trim_old_tool_results(messages: list[dict], keep_last: int = 1) -> None:
    seen = 0
    for msg in reversed(messages):
        if msg["role"] != "user" or not isinstance(msg["content"], list):
            continue
        for part in msg["content"]:
            if part.get("type") == "tool_result":
                seen += 1
                if seen > keep_last:
                    part["content"] = "[old tool result removed to save context]"
```

Lo mismo del lado del servidor con context editing de Anthropic (beta): un disparador decide cuándo borrar y cuántos resultados conservar.

```python
CONTEXT_EDITS = {"edits": [{
    "type": "clear_tool_uses_20250919",
    "trigger": {"type": "tool_uses", "value": 2},
    "keep": {"type": "tool_uses", "value": 1},
}]}
client.beta.messages.create(..., betas=["context-management-2025-06-27"], context_management=CONTEXT_EDITS)
```

> [!WARNING]
> Recortar contexto cambia el prefijo y puede invalidar el prompt cache. Recortá por bloques grandes y poco frecuentes, no un poquito en cada vuelta.

## Errores comunes

- Devolver la respuesta completa de una API (cientos de campos) como resultado de tool.
- Meter toda la "memoria de largo plazo" en el system prompt en cada llamada.
- Borrar resultados que el modelo todavía necesita (por ejemplo IDs) sin dejar un resumen.

## En una entrevista

- **¿Cómo manejás el contexto en un agente de larga duración?** Resultados de tools compactos, recorte o context editing de resultados viejos, resumen del historial, y sub-agentes para trabajo de lectura intensiva.
- **¿Diferencia entre memoria de corto y largo plazo?** Corto plazo es el historial de la tarea actual; largo plazo persiste entre sesiones en un store y se recupera por relevancia o vía tool.
