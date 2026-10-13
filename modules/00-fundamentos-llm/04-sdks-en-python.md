---
title: SDKs en Python y multi-proveedor
order: 4
type: implementacion
---

**Objetivo:** manejar con soltura los SDKs oficiales: cliente, mensajes, conversación de varios turnos, errores, reintentos y cómo cambiar de proveedor.

## Idea

Todos los proveedores exponen el mismo concepto: mandás una lista de mensajes con roles y recibís una respuesta. Las diferencias están en los nombres y en dónde va cada cosa.

| Concepto | Anthropic Messages API | OpenAI Chat Completions | OpenAI Responses API |
|---|---|---|---|
| Endpoint | `messages.create` | `chat.completions.create` | `responses.create` |
| System prompt | parámetro `system` | mensaje con `role: "system"` | parámetro `instructions` |
| Respuesta | `content`: lista de bloques | `choices[0].message` | `output`: lista de items |
| Tope de salida | `max_tokens` (obligatorio) | `max_tokens` / `max_completion_tokens` | `max_output_tokens` |
| Por qué terminó | `stop_reason` | `finish_reason` | `status` + items |
| Estado en servidor | no | no | opcional (`previous_response_id`) |

**Chat Completions** es el formato que todo el ecosistema copió: OpenRouter, Ollama, vLLM, Groq y la mayoría de los gateways lo hablan. Saberlo te deja usar casi cualquier modelo con un solo SDK.

### Multi-proveedor: por qué y cómo

En producción es común usar más de un proveedor y elegir según costo, latencia y calidad. Opciones:

1. **SDK nativo por proveedor**: acceso a todas las features (caching, thinking, citations), más código.
2. **Gateway compatible con OpenAI** (OpenRouter, LiteLLM): un SDK, cambiás el modelo con un string; perdés algunas features específicas o llegan tarde.
3. **Abstracción de framework** (LangChain `init_chat_model`, Agent Framework clients): útil si ya usás el framework.

Patrón común en producción: SDK nativo para el camino principal, gateway para fallback y experimentos.

### Errores y reintentos

Los errores se dividen en dos grupos: los transitorios, que se reintentan con backoff (los SDKs ya lo hacen solos), y los del request, que no se arreglan reintentando.

| Error | Significa | Reintentar |
|---|---|---|
| 400 | El request está mal armado | No |
| 401 / 403 | Credenciales o permisos | No |
| 404 | Modelo o recurso inexistente | No |
| 429 | Rate limit | Sí, esperando lo que indica `retry-after` |
| 5xx | Falla del proveedor | Sí |
| Red / timeout | Conexión | Sí |

Registrá el id de cada request para poder rastrear una falla con el proveedor.

## Cómo se implementa

:::tabs
== Anthropic
```python
import anthropic

client = anthropic.Anthropic(max_retries=3, timeout=60.0)
history = []

def send(text: str) -> str:
    history.append({"role": "user", "content": text})
    response = client.messages.create(
        model="claude-opus-5-5",
        max_tokens=1024,
        system="You are a concise assistant.",
        messages=history,
    )
    # keep the full content blocks, not only the text
    history.append({"role": "assistant", "content": response.content})
    return next(b.text for b in response.content if b.type == "text")
```

```python
try:
    client.messages.create(...)
except anthropic.RateLimitError as e:
    wait = e.response.headers.get("retry-after")
except anthropic.APIStatusError as e:
    print(e.status_code, e.message)
except anthropic.APIConnectionError:
    ...
```

== OpenAI
Chat Completions: el system prompt es un mensaje más y la respuesta está en `choices`.

```python
from openai import OpenAI

client = OpenAI(max_retries=3)
messages = [
    {"role": "system", "content": "You are a concise assistant."},
    {"role": "user", "content": "What is a token?"},
]
completion = client.chat.completions.create(model="gpt-5.6-luna", max_tokens=512, messages=messages)
choice = completion.choices[0]
print(choice.finish_reason, choice.message.content)
messages.append({"role": "assistant", "content": choice.message.content})
```

Responses API: más nueva, con estado opcional en el servidor.

```python
first = client.responses.create(model="gpt-5.6-luna", instructions="Be concise.", input="What is a token?")
print(first.output_text)
follow = client.responses.create(model="gpt-5.6-luna", input="And a context window?", previous_response_id=first.id)
```
== OpenRouter
El SDK de OpenAI con `base_url` de OpenRouter. El modelo se elige con `proveedor/modelo`.

```python
import os
from openai import OpenAI

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])

for model in ["anthropic/claude-opus-5.5", "google/gemini-3.8-flash"]:
    completion = client.chat.completions.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": "What is a token in an LLM?"}],
    )
    print(model, completion.usage.prompt_tokens, completion.choices[0].message.content)
```

:::

## Errores comunes

- Guardar en el historial solo el texto del assistant cuando hubo thinking o tools: los bloques se tienen que devolver tal cual.
- Capturar `Exception` y reintentar todo, incluidos los 400.
- Hardcodear la API key en el código.
- Mezclar formatos: mandar `role: "system"` en `messages` de Anthropic esperando que sea el system prompt principal.

## Preguntas de repaso

- **¿Cómo integrarías varios proveedores de LLM?** Interfaz propia delgada o gateway compatible con OpenAI; elección por costo, latencia y calidad medida con evals; fallback ante 429/5xx.
- **¿Qué errores reintentás?** 429, 5xx, timeouts y errores de red, con backoff exponencial y respetando `retry-after`. Nunca 400/401/404.
- **¿Chat Completions o Responses?** Chat Completions es el estándar de facto y lo habla todo el ecosistema; Responses agrega estado en servidor y tools nativas de OpenAI.
