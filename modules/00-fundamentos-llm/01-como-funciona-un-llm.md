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

Cada proveedor (y cada familia de modelos) parte el texto a su manera, así que la misma frase cuesta distinta cantidad de tokens según el modelo. Para contar, se usa el conteo del propio proveedor.

<figure class="diagram">
<svg viewBox="0 0 760 260" role="img" aria-label="Texto partido en tokens con sus ids, y el mismo JSON compacto e indentado con distinta cantidad de tokens">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<text x="20" y="28" class="title">Texto</text>
<text x="120" y="28" class="mono">"La tokenización no es obvia"</text>
<line class="line" x1="230" y1="40" x2="230" y2="62" marker-end="url(#ah)"/>
<text x="20" y="88" class="title">Tokens</text>
<rect class="input" x="120" y="68" width="31" height="30" rx="6"/>
<text x="136" y="88" text-anchor="middle" class="mono">La</text>
<text x="136" y="116" text-anchor="middle" class="sub">4723</text>
<rect class="process" x="157" y="68" width="62" height="30" rx="6"/>
<text x="188" y="88" text-anchor="middle" class="mono">␣token</text>
<text x="188" y="116" text-anchor="middle" class="sub">4037</text>
<rect class="input" x="225" y="68" width="69" height="30" rx="6"/>
<text x="259" y="88" text-anchor="middle" class="mono">ización</text>
<text x="259" y="116" text-anchor="middle" class="sub">22881</text>
<rect class="process" x="300" y="68" width="39" height="30" rx="6"/>
<text x="319" y="88" text-anchor="middle" class="mono">␣no</text>
<text x="319" y="116" text-anchor="middle" class="sub">912</text>
<rect class="input" x="345" y="68" width="39" height="30" rx="6"/>
<text x="364" y="88" text-anchor="middle" class="mono">␣es</text>
<text x="364" y="116" text-anchor="middle" class="sub">1560</text>
<rect class="process" x="390" y="68" width="39" height="30" rx="6"/>
<text x="409" y="88" text-anchor="middle" class="mono">␣ob</text>
<text x="409" y="116" text-anchor="middle" class="sub">3394</text>
<rect class="input" x="434" y="68" width="39" height="30" rx="6"/>
<text x="454" y="88" text-anchor="middle" class="mono">via</text>
<text x="454" y="116" text-anchor="middle" class="sub">6129</text>
<text x="487" y="88" class="sub" text-anchor="start">7 tokens</text>
<text x="20" y="116" class="sub">ids</text>
<text x="20" y="186" class="title">Compacto</text>
<rect class="store" x="120" y="166" width="31" height="30" rx="6"/>
<text x="136" y="186" text-anchor="middle" class="mono">{&quot;</text>
<rect class="store" x="157" y="166" width="26" height="30" rx="6"/>
<text x="170" y="186" text-anchor="middle" class="mono">a</text>
<rect class="store" x="189" y="166" width="31" height="30" rx="6"/>
<text x="205" y="186" text-anchor="middle" class="mono">&quot;:</text>
<rect class="store" x="226" y="166" width="26" height="30" rx="6"/>
<text x="239" y="186" text-anchor="middle" class="mono">1</text>
<rect class="store" x="258" y="166" width="26" height="30" rx="6"/>
<text x="271" y="186" text-anchor="middle" class="mono">}</text>
<text x="298" y="186" class="sub" text-anchor="start">5 tokens</text>
<text x="20" y="236" class="title">Indentado</text>
<rect class="risk" x="120" y="216" width="26" height="30" rx="6"/>
<text x="133" y="236" text-anchor="middle" class="mono">{</text>
<rect class="risk" x="152" y="216" width="31" height="30" rx="6"/>
<text x="168" y="236" text-anchor="middle" class="mono">\n</text>
<rect class="risk" x="189" y="216" width="31" height="30" rx="6"/>
<text x="205" y="236" text-anchor="middle" class="mono">␣␣</text>
<rect class="risk" x="226" y="216" width="39" height="30" rx="6"/>
<text x="246" y="236" text-anchor="middle" class="mono">&quot;a&quot;</text>
<rect class="risk" x="271" y="216" width="26" height="30" rx="6"/>
<text x="284" y="236" text-anchor="middle" class="mono">:</text>
<rect class="risk" x="303" y="216" width="31" height="30" rx="6"/>
<text x="319" y="236" text-anchor="middle" class="mono">␣1</text>
<rect class="risk" x="340" y="216" width="31" height="30" rx="6"/>
<text x="356" y="236" text-anchor="middle" class="mono">\n</text>
<rect class="risk" x="378" y="216" width="26" height="30" rx="6"/>
<text x="391" y="236" text-anchor="middle" class="mono">}</text>
<text x="418" y="236" class="sub" text-anchor="start">8 tokens: espacios y saltos también cuentan</text>
</svg>
<figcaption>Un tokenizer parte el texto en piezas frecuentes, no en palabras. ␣ marca un espacio. La partición y los ids son ilustrativos: cada modelo tiene su propio vocabulario.</figcaption>
</figure>

### Sampling: de distribución a texto

El modelo devuelve probabilidades; el **sampler** elige. Los parámetros clásicos:

- **temperature**: aplana (alto) o afila (bajo) la distribución. `0` ≈ elegir siempre el más probable.
- **top_p / top_k**: recortan la cola de tokens poco probables antes de elegir.

Determinismo: aun con `temperature=0` la salida no es 100% reproducible (batching y punto flotante en GPU). Para tests, compará propiedades de la salida, no strings exactos.

### Razonamiento (thinking) y effort

Los modelos actuales "piensan" antes de responder: generan tokens de razonamiento que se cobran como salida pero normalmente no se muestran.

- El razonamiento es **adaptativo**: el modelo decide cuánto pensar según la dificultad.
- Lo regulás con un nivel de **effort** (`low` a `max`): más effort = mejor en problemas difíciles, más tokens y más latencia. En Anthropic va en `output_config={"effort": ...}`; en OpenAI se llama `reasoning_effort`.

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

Contar tokens antes de enviar, llamar, y leer `usage` y `stop_reason` de la respuesta. Con `max_tokens=20` la misma pregunta vuelve cortada y con `stop_reason == "max_tokens"`.

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
- Estimar costos con palabras en vez de tokens.

## Preguntas de repaso

- **¿Qué es la ventana de contexto y qué pasa si la superás?** El máximo de tokens que el modelo procesa por llamada. Si la superás, la API devuelve error; antes de eso, la calidad baja porque la información relevante se diluye. Se maneja con truncado, resumen o retrieval.
- **¿Para qué sirve temperature?** Controla la aleatoriedad del sampling. Bajo para tareas deterministas (extracción), alto para creatividad.
- **¿Cómo detectás una respuesta truncada?** `stop_reason == "max_tokens"` (o `finish_reason == "length"`).
- **¿Por qué una API de LLM es stateless y qué implica?** Escala mejor y no guarda datos; implica que el cliente arma y manda el historial, y que el costo crece con cada turno.
