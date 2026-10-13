---
title: Cómo funciona un LLM (desde el lado de quien lo integra)
order: 1
type: concepto
---

**Objetivo:** entender tokens, ventana de contexto, sampling, razonamiento y stop reasons lo suficiente como para diagnosticar por qué una integración se comporta como se comporta.

## Idea

Un LLM es una función que recibe una secuencia de **tokens** y devuelve una distribución de probabilidad sobre el próximo token. Generar texto es repetir eso: elegir un token, agregarlo al final, volver a predecir. Todo lo demás (chat, tools, JSON, agentes) es protocolo construido encima de ese loop.

Lo que importa para integrarlo:

| Concepto | Qué es | Por qué te importa |
|---|---|---|
| Token | Fragmento de texto (≈ 3–4 caracteres en inglés, algo menos en español) | Se cobra y se limita por tokens, no por caracteres ni palabras |
| Ventana de contexto | Máximo de tokens (entrada + salida) que el modelo ve en una llamada | Los modelos actuales de Claude tienen 1M. Más contexto = más costo y más latencia, y la atención se diluye |
| `max_tokens` | Tope de tokens de salida que vos fijás | Si se alcanza, la respuesta se corta a mitad de frase |
| Stateless | La API no recuerda nada entre llamadas | En cada request mandás la conversación completa. "Memoria" es algo que construís vos |
| Roles | `system`, `user`, `assistant` (y en tools, resultados) | El system prompt fija comportamiento; el resto es el historial |

### Tokenización

Los tokenizers son distintos por proveedor y por generación de modelo. La misma frase puede costar un 30% más en un modelo nuevo. Nunca estimes con un tokenizer de otro proveedor (por ejemplo `tiktoken` para Claude): usá el endpoint de conteo del proveedor.

```text
"tokenización"  →  ["token", "ización"]        (ejemplo ilustrativo)
"   " (espacios) → también son tokens
JSON con mucha indentación → más tokens que el mismo JSON compacto
```

### Sampling: de distribución a texto

El modelo devuelve probabilidades; el **sampler** elige. Los parámetros clásicos:

- **temperature**: aplana (alto) o afila (bajo) la distribución. `0` ≈ elegir siempre el más probable.
- **top_p / top_k**: recortan la cola de tokens poco probables antes de elegir.

> [!WARNING]
> En los modelos más recientes de Claude (Opus 5.5, Sonnet 5.5, Fable) `temperature`, `top_p` y `top_k` **ya no se aceptan** y devuelven 400. El control de calidad/costo pasó a `effort`. En modelos de OpenAI y Gemini (vía OpenRouter) siguen existiendo. Si una búsqueda o entrevista pregunta por temperature, explicá qué hace y aclaralo.

Determinismo: aun con `temperature=0` la salida no es 100% reproducible (batching y punto flotante en GPU). Para tests, compará propiedades de la salida, no strings exactos.

### Razonamiento (thinking) y effort

Los modelos actuales "piensan" antes de responder: generan tokens de razonamiento que se cobran como salida pero normalmente no se muestran.

- En Claude Opus 5.5 el razonamiento es **adaptativo y siempre activo**: el modelo decide cuánto pensar.
- Lo controlás con `output_config={"effort": "low" | "medium" | "high" | "xhigh" | "max"}`. Más effort = mejor en problemas difíciles, más tokens y más latencia. El default en Opus 5.5 es `medium`.
- En OpenAI el equivalente es `reasoning_effort`; en OpenRouter, `reasoning`.

Regla práctica: clasificación, extracción y chat simple con `low`; agentes y código con `high` o `xhigh`. Medí antes de subirlo.

### Stop reasons

Cada respuesta dice **por qué** terminó. Ignorarlo es la fuente número uno de bugs silenciosos.

| `stop_reason` (Anthropic) | `finish_reason` (OpenAI) | Significa |
|---|---|---|
| `end_turn` | `stop` | Terminó normalmente |
| `max_tokens` | `length` | Se cortó por tu tope: la salida está incompleta |
| `tool_use` | `tool_calls` | Quiere ejecutar una tool (módulo 01) |
| `refusal` | `content_filter` | Se negó por políticas de seguridad |
| `pause_turn` | — | Tool de servidor larga en pausa, hay que reenviar |

### Contenido de la respuesta

La respuesta no es un string: es una **lista de bloques** (`text`, `thinking`, `tool_use`...). Siempre filtrá por tipo antes de leer `.text`.

## Cómo se ve en código

`code/01_tokens_and_context.py` cuenta tokens antes de enviar, hace una llamada, imprime `usage` y `stop_reason`, y repite con `max_tokens=20` para que veas una respuesta truncada.

```python
count = client.messages.count_tokens(model=MODEL, messages=messages)
response = client.messages.create(model=MODEL, max_tokens=1024, messages=messages)
print(response.stop_reason, response.usage.input_tokens, response.usage.output_tokens)
```

## Errores comunes

- Leer `response.content[0].text` sin chequear el tipo: con thinking o tools el primer bloque puede no ser texto.
- No mirar `stop_reason`: parsear un JSON que quedó cortado por `max_tokens`.
- `max_tokens` demasiado bajo con effort alto: el razonamiento se come el presupuesto y no queda para la respuesta.
- Asumir que el modelo "recuerda" la conversación anterior sin reenviarla.
- Estimar costos con palabras o con un tokenizer de otro proveedor.

## En una entrevista

- **¿Qué es la ventana de contexto y qué pasa si la superás?** El máximo de tokens que el modelo procesa por llamada. Si la superás, la API devuelve error; antes de eso, la calidad baja porque la información relevante se diluye. Se maneja con truncado, resumen o retrieval.
- **¿Para qué sirve temperature?** Controla la aleatoriedad del sampling. Bajo para tareas deterministas (extracción), alto para creatividad. En modelos nuevos de Claude se reemplazó por `effort`.
- **¿Cómo detectás una respuesta truncada?** `stop_reason == "max_tokens"` (o `finish_reason == "length"`).
- **¿Por qué una API de LLM es stateless y qué implica?** Escala mejor y no guarda datos; implica que el cliente arma y manda el historial, y que el costo crece con cada turno.
