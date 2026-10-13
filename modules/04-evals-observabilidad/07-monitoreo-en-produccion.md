---
title: Monitoreo en producción
order: 7
type: concepto
---

**Objetivo:** saber qué medir de un sistema LLM en producción, cómo detectar que se degradó, y cómo cerrar el ciclo con las evals.

## Idea

Un sistema LLM se degrada sin que nadie toque el código: cambia el tipo de preguntas, el proveedor actualiza el modelo, un documento del RAG queda viejo, una API externa empieza a devolver errores que el agente maneja mal. El monitoreo tiene que detectar eso antes que los usuarios.

### Qué medir

| Familia | Métricas | Para qué |
|---|---|---|
| **Operación** | Latencia p50/p95/p99, time to first token, tasa de errores HTTP, 429 y timeouts | Disponibilidad y experiencia |
| **Costo** | Tokens y USD por request, por tarea, por cliente y por feature; tasa de cache hits | Presupuesto y anomalías (un loop que gasta 100×) |
| **Agente** | Tasa de éxito de tool calls, errores por tool, pasos por tarea, tareas que tocan el límite de pasos | Confiabilidad del agente |
| **Calidad (online)** | Scores de jueces sobre una muestra, faithfulness, tasa de "no sé" | Degradación de calidad |
| **Usuario** | Thumbs up/down, reformulaciones, abandono, escalamiento a humano | La señal más real |
| **Seguridad** | Intentos de prompt injection detectados, rechazos, PII en salidas | Riesgo |

### Evals online

Correr jueces sobre todo el tráfico es caro. Se hace sobre una **muestra** (1–10%), más el 100% de los casos marcados por señales baratas: feedback negativo, respuestas muy largas, tool errors, stop reason `max_tokens` o `refusal`. El score queda guardado en el trace.

### Drift

- **Drift de entrada**: las preguntas cambian (nuevo producto, nuevo tipo de cliente). Se detecta agrupando preguntas por tema (embeddings + clustering) y mirando qué categorías crecen o aparecen.
- **Drift del modelo**: el proveedor actualiza o retira un modelo. Conviene fijar versiones de modelo cuando el proveedor lo permite y pasar la suite offline antes de migrar.
- **Drift de datos**: los documentos del RAG cambian o quedan viejos. Monitoreá recall en el dataset de evaluación cuando se reindexa.

### Alertas

Alertá sobre tendencias, no sobre casos sueltos (un juez que falla una vez es ruido):

- Tasa de éxito de tool calls cae X puntos respecto de la semana anterior.
- Costo por tarea sube más de 2× (loops, contexto que crece).
- p95 de latencia supera el SLO.
- Score medio del juez online cae bajo el umbral durante N horas.
- Aumento de feedback negativo en una categoría.

### Cerrar el ciclo

<figure class="diagram">
<svg viewBox="0 0 810 220" role="img" aria-label="Ciclo entre producción, dataset y evals">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<line class="line" x1="230" y1="48" x2="300" y2="48" marker-end="url(#ah)"/>
<line class="line" x1="510" y1="48" x2="580" y2="48" marker-end="url(#ah)"/>
<line class="line" x1="685.0" y1="76" x2="685.0" y2="150" marker-end="url(#ah)"/>
<line class="line" x1="580" y1="178" x2="510" y2="178" marker-end="url(#ah)"/>
<line class="line" x1="300" y1="178" x2="230" y2="178" marker-end="url(#ah)"/>
<line class="line" x1="125.0" y1="150" x2="125.0" y2="76" marker-end="url(#ah)"/>
<rect class="process" x="20" y="20" width="210" height="56" rx="8"/>
<text x="125.0" y="53.0" text-anchor="middle" class="title">Producción</text>
<rect class="node" x="300" y="20" width="210" height="56" rx="8"/>
<text x="405.0" y="45.0" text-anchor="middle" class="title">Traces y feedback</text>
<text x="405.0" y="62.0" text-anchor="middle" class="sub">evals online</text>
<rect class="risk" x="580" y="20" width="210" height="56" rx="8"/>
<text x="685.0" y="53.0" text-anchor="middle" class="title">Casos que fallan</text>
<rect class="store" x="580" y="150" width="210" height="56" rx="8"/>
<text x="685.0" y="175.0" text-anchor="middle" class="title">Dataset</text>
<text x="685.0" y="192.0" text-anchor="middle" class="sub">se etiquetan y se suman</text>
<rect class="node" x="300" y="150" width="210" height="56" rx="8"/>
<text x="405.0" y="175.0" text-anchor="middle" class="title">Evals offline en CI</text>
<text x="405.0" y="192.0" text-anchor="middle" class="sub">gate de cada cambio</text>
<rect class="process" x="20" y="150" width="210" height="56" rx="8"/>
<text x="125.0" y="183.0" text-anchor="middle" class="title">Deploy</text>
</svg>
<figcaption>Cada falla de producción que se entiende termina como caso del dataset.</figcaption>
</figure>

Cada falla de producción que se entiende se convierte en un caso del dataset. Con el tiempo el dataset refleja la realidad y la suite de CI atrapa las regresiones que importan.

### Guardrails en runtime

Parte del monitoreo actúa en línea, antes de responder: validar esquema de salida, bloquear PII, detectar injection en la entrada, limitar acciones por umbral (montos, cantidad de llamadas), y degradar a una respuesta segura o a un humano cuando algo no cumple. Se ve en detalle en el módulo 07.

## Cómo se ve en código

Lo mínimo por llamada: registrar uso, costo y resultado con atributos que permitan agregar después. Con OpenTelemetry, como métricas:

```python
from opentelemetry import metrics

meter = metrics.get_meter("support-bot")
tokens = meter.create_counter("gen_ai.client.token.usage", unit="{token}")
cost = meter.create_counter("app.llm.cost", unit="USD")
tool_calls = meter.create_counter("app.agent.tool_calls")

def record(response, feature: str, price_in: float, price_out: float) -> None:
    attrs = {"gen_ai.request.model": response.model, "app.feature": feature}
    tokens.add(response.usage.input_tokens, {**attrs, "gen_ai.token.type": "input"})
    tokens.add(response.usage.output_tokens, {**attrs, "gen_ai.token.type": "output"})
    cost.add((response.usage.input_tokens * price_in + response.usage.output_tokens * price_out) / 1e6, attrs)

def record_tool(name: str, ok: bool) -> None:
    tool_calls.add(1, {"gen_ai.tool.name": name, "app.outcome": "ok" if ok else "error"})
```

Con esas series, la tasa de éxito de tool calls es `ok / total` por tool, y el costo por feature es una suma agrupada. Langfuse y LangSmith calculan buena parte de esto solos a partir de los traces.

## Errores comunes

- Monitorear solo disponibilidad y latencia: el sistema "anda" y responde mal.
- Alertar por cada score bajo individual.
- No atribuir costo por cliente o feature: el aumento aparece en la factura sin explicación.
- Juntar feedback de usuarios y no convertirlo nunca en casos de evaluación.
- No fijar versión del modelo y descubrir un cambio de comportamiento por las quejas.

## En una entrevista

- **¿Qué monitorearías de un agente en producción?** Latencia y errores, costo por tarea y por cliente, tasa de éxito de tool calls y pasos por tarea, scores de evals online sobre una muestra, y feedback de usuarios, con alertas sobre tendencias.
- **¿Cómo detectás que la calidad bajó?** Evals online muestreadas comparadas contra una línea base, feedback negativo por categoría, y la suite offline corrida periódicamente contra el modelo en producción.
- **¿Cómo usás producción para mejorar el sistema?** Traces de fallas y feedback negativo se etiquetan y se agregan al dataset; el siguiente cambio se valida contra ese dataset en CI.
