---
title: Streaming
order: 5
---

**Objetivo:** mostrar la respuesta mientras se genera y saber cuándo el streaming es obligatorio y no solo cosmético.

## Idea

Sin streaming, el cliente espera a que el modelo termine para recibir todo junto. Con streaming, el servidor manda **eventos** (Server-Sent Events) a medida que genera.

Por qué importa:

- **Latencia percibida**: el usuario ve texto en 1 segundo en vez de esperar 30.
- **Timeouts**: respuestas largas (decenas de miles de tokens) superan los timeouts HTTP sin streaming.
- **Agentes**: mostrar progreso y tool calls mientras ocurren.

El flujo de eventos tiene la misma forma en todos los proveedores:

<figure class="diagram">
<svg viewBox="0 0 730 180" role="img" aria-label="Secuencia de eventos de streaming">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<line class="line" x1="210" y1="45.0" x2="250" y2="45.0" marker-end="url(#ah)"/>
<line class="line" x1="210" y1="135.0" x2="250" y2="135.0" marker-end="url(#ah)"/>
<line class="line" x1="450" y1="45.0" x2="490" y2="45.0" marker-end="url(#ah)"/>
<line class="line" x1="450" y1="135.0" x2="490" y2="135.0" marker-end="url(#ah)"/>
<path class="line" d="M590.0,70 V90.0 H110.0 V110" marker-end="url(#ah)"/>
<rect class="node" x="10" y="20" width="200" height="50" rx="8"/>
<text x="110.0" y="50.0" text-anchor="middle" class="mono">message_start</text>
<rect class="node" x="250" y="20" width="200" height="50" rx="8"/>
<text x="350.0" y="50.0" text-anchor="middle" class="mono">content_block_start</text>
<rect class="input" x="490" y="20" width="200" height="50" rx="8"/>
<text x="590.0" y="42.0" text-anchor="middle" class="mono">content_block_delta × N</text>
<text x="590.0" y="59.0" text-anchor="middle" class="sub">texto que va llegando</text>
<rect class="node" x="10" y="110" width="200" height="50" rx="8"/>
<text x="110.0" y="140.0" text-anchor="middle" class="mono">content_block_stop</text>
<rect class="store" x="250" y="110" width="200" height="50" rx="8"/>
<text x="350.0" y="132.0" text-anchor="middle" class="mono">message_delta</text>
<text x="350.0" y="149.0" text-anchor="middle" class="sub">stop_reason, usage</text>
<rect class="node" x="490" y="110" width="200" height="50" rx="8"/>
<text x="590.0" y="140.0" text-anchor="middle" class="mono">message_stop</text>
</svg>
</figure>

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

## Preguntas de repaso

- **¿Cuándo usás streaming?** Siempre que haya un humano esperando o salidas largas; para batch offline no hace falta.
- **¿Cómo exponés streaming de un LLM a un frontend?** Server-Sent Events desde el backend, reenviando deltas y un evento final con metadata.
