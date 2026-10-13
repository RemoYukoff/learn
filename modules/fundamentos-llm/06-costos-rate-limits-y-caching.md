---
title: Costos, rate limits y caching
order: 6
---

**Objetivo:** estimar y bajar el costo de una integración sin perder calidad, y no caerse por rate limits.

## Idea

### Cómo se cobra

Se paga por millón de tokens, con precios distintos para entrada y salida. La salida suele costar varias veces más que la entrada, y los tokens de razonamiento cuentan como salida. Los modelos grandes cuestan bastante más por token que los chicos de la misma familia.

Costo de un agente = suma de **todas** las llamadas del loop, y cada llamada reenvía el historial completo. Un agente de 10 pasos con 20k tokens de contexto paga esos 20k diez veces (salvo caching).

### Palancas, de gratis a costosas

1. **Prompt caching** (gratis en calidad). El proveedor guarda el procesamiento de un prefijo idéntico. Leer del cache cuesta una fracción del precio normal de entrada; escribirlo la primera vez cuesta un poco más. El cache vive unos minutos y se renueva con cada uso.
   - Es **match de prefijo**: cualquier byte distinto invalida todo lo que viene después.
   - Orden: tools → system → mensajes. Lo estable primero, lo variable al final.
   - Asesinos silenciosos del cache: timestamps en el system prompt, JSON sin ordenar, lista de tools que cambia de orden.
   - Verificalo con `usage.cache_read_input_tokens`; si es 0 en llamadas repetidas, algo cambia el prefijo.
2. **Contexto más chico**: mandar solo lo necesario, resumir historial, retrieval en vez de pegar documentos enteros.
3. **Batch API**: 50% de descuento para trabajos que pueden esperar hasta 24 h.
4. **Effort**: bajar de `high` a `low` en tareas simples reduce tokens de razonamiento.
5. **Modelo más chico**: el último recurso. Medí con evals antes: un modelo barato que necesita más reintentos no es más barato.

### Rate limits

Los proveedores limitan **requests por minuto**, **tokens de entrada por minuto** y **tokens de salida por minuto**, por organización y modelo. Al superarlos: 429 con header `retry-after`.

- Los SDKs reintentan 429 con backoff; configurá `max_retries`.
- En sistemas con concurrencia, poné una cola o semáforo antes de la API, no confíes solo en reintentos.
- Los tokens cacheados normalmente no cuentan para el límite de entrada.

### Controles de gasto

Lo que se espera ver en producción: presupuesto por cliente o feature, alertas diarias, límites por API key (OpenRouter los tiene nativos), y registrar `usage` de cada llamada para atribuir costos.

## Cómo se ve en código

Un prefijo largo y estable (políticas, documentación, ejemplos) marcado con `cache_control`. La primera llamada escribe el cache (`cache_creation_input_tokens`); las siguientes con el mismo prefijo lo leen (`cache_read_input_tokens`) a ~10% del precio.

```python
system = [{"type": "text", "text": POLICY, "cache_control": {"type": "ephemeral"}}]
r = client.messages.create(model=MODEL, max_tokens=512, system=system, messages=[...])
print(r.usage.cache_creation_input_tokens, r.usage.cache_read_input_tokens)
```


## Errores comunes

- Poner la fecha y hora en el system prompt: invalida el cache en cada llamada.
- Medir costo por request en vez de por tarea completada.
- Elegir el modelo más barato sin evals.
- No registrar `usage` y descubrir el gasto a fin de mes.

## Preguntas de repaso

- **¿Cómo bajarías el costo de un sistema LLM?** Medir primero (usage por feature), después caching, contexto más chico, batch para lo asíncrono, effort por ruta, y recién al final un modelo más chico validado con evals.
- **¿Cómo funciona el prompt caching?** El proveedor reutiliza el cómputo de un prefijo idéntico durante un TTL; se cobra mucho menos la lectura. Requiere prefijo estable byte a byte.
- **¿Cómo manejás rate limits?** Backoff con `retry-after`, control de concurrencia propio, colas, y caching para bajar tokens por minuto.
