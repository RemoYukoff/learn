---
title: Streaming
order: 5
type: implementacion
---

**Objetivo:** mostrar la respuesta mientras se genera y saber cuándo el streaming es obligatorio y no solo cosmético.

## Idea

Sin streaming, el cliente espera a que el modelo termine para recibir todo junto. Con streaming, el servidor manda **eventos** (Server-Sent Events) a medida que genera.

Por qué importa:

- **Latencia percibida**: el usuario ve texto en 1 segundo en vez de esperar 30.
- **Timeouts**: respuestas largas (decenas de miles de tokens) superan los timeouts HTTP sin streaming. Con `max_tokens` alto, el SDK de Anthropic te exige streaming.
- **Agentes**: mostrar progreso y tool calls mientras ocurren.

El flujo de eventos tiene la misma forma en todos los proveedores:

```text
message_start → content_block_start → content_block_delta × N → content_block_stop → message_delta (stop_reason, usage) → message_stop
```

Lo que tenés que resolver vos: acumular los deltas, saber cuándo terminó y con qué `stop_reason`, y manejar un corte de conexión a mitad de camino. Los SDKs traen helpers que acumulan por vos.

## Cómo se implementa

:::tabs
== Anthropic
`messages.stream()` es un context manager con `text_stream` (solo texto) y `get_final_message()` (el mensaje completo, igual que sin streaming).

```python
with client.messages.stream(
    model="claude-opus-5-5",
    max_tokens=64000,
    messages=[{"role": "user", "content": "Write a long report..."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    final = stream.get_final_message()

print(final.stop_reason, final.usage.output_tokens)
```

Para ver eventos de bajo nivel (thinking, tool use), iterá `for event in stream:` y mirá `event.type`.
== OpenRouter
Con el SDK de OpenAI pasás `stream=True` y recibís *chunks*. El texto viene en `choices[0].delta.content`; el uso, en el último chunk si pedís `include_usage`.

```python
stream = client.chat.completions.create(
    model="anthropic/claude-opus-5.5",
    max_tokens=4096,
    messages=[{"role": "user", "content": "Write a long report..."}],
    stream=True,
    stream_options={"include_usage": True},
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
    if chunk.usage:
        print("\noutput tokens:", chunk.usage.completion_tokens)
```
:::


> [!TIP]
> Para exponer streaming a un frontend, tu backend (FastAPI, Express) reenvía los eventos como SSE. Es lo que hace el Vercel AI SDK por debajo.

## Errores comunes

- Asumir que el stream terminó bien porque dejó de llegar texto: chequeá el `stop_reason` final.
- Concatenar deltas de tool input y parsear antes de que termine el bloque.
- No cerrar el stream (usá `with`), dejando conexiones abiertas.

## En una entrevista

- **¿Cuándo usás streaming?** Siempre que haya un humano esperando o salidas largas; para batch offline no hace falta.
- **¿Cómo exponés streaming de un LLM a un frontend?** Server-Sent Events desde el backend, reenviando deltas y un evento final con metadata.
