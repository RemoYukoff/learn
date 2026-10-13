---
title: Tracing y observabilidad
order: 6
type: implementacion
---

**Objetivo:** registrar qué hizo un sistema LLM en cada request (cada llamada al modelo, cada tool, cada retrieval) para depurar, medir y alimentar las evals.

## Idea

Con un LLM, los logs de "request recibido / respuesta enviada" no alcanzan. Necesitás ver adentro: qué prompt exacto se mandó, qué devolvió el modelo, qué tools llamó con qué argumentos, cuánto tardó y costó cada paso. Eso es **tracing**, con el mismo modelo que OpenTelemetry usa para microservicios:

```text
trace  (un request de usuario)
└─ span: agent run                         2.8 s   $0.031
   ├─ span: llm call  (claude-opus-5-5)    1.1 s   in 2,340 / out 180 tokens
   ├─ span: tool find_customer             0.04 s  input {"name": "Acme"}
   ├─ span: retriever search_handbook      0.09 s  3 docs
   └─ span: llm call  (claude-opus-5-5)    1.5 s   in 3,910 / out 240 tokens
```

| Concepto | Qué es |
|---|---|
| **Trace** | Todo lo que pasó para atender un request |
| **Span** | Una operación dentro del trace, con inicio, fin, atributos y padre |
| **Atributos** | Modelo, tokens, costo, tool, argumentos, ids de usuario y sesión |
| **Session / thread** | Varios traces de la misma conversación |
| **Feedback / score** | Una evaluación pegada a un trace (thumbs up, juez online, etiqueta humana) |

### OpenTelemetry GenAI

OpenTelemetry tiene **convenciones semánticas para GenAI**: nombres estándar de atributos y métricas para llamadas a modelos. Usarlas hace que cualquier backend (Langfuse, LangSmith, Grafana, Datadog) entienda los datos.

| Atributo / métrica | Contenido |
|---|---|
| `gen_ai.operation.name` | `chat`, `embeddings`, `execute_tool`... |
| `gen_ai.provider.name` | `anthropic`, `openai`... |
| `gen_ai.request.model`, `gen_ai.response.model` | Modelo pedido y modelo que respondió |
| `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` | Tokens |
| `gen_ai.usage.cache_read.input_tokens` | Tokens leídos del cache |
| `gen_ai.response.finish_reasons` | Stop reasons |
| `gen_ai.tool.name`, `gen_ai.tool.call.id` | Tool ejecutada |
| `gen_ai.client.operation.duration` | Métrica: duración de llamadas |
| `gen_ai.client.token.usage` | Métrica: tokens usados |

### Qué no loguear

Los prompts y respuestas pueden tener datos personales o secretos. Las herramientas permiten **enmascarar** campos antes de enviar, desactivar la captura de contenido y muestrear. Definí la política antes de prender el tracing en producción.

### Para qué se usan los traces

- **Debug**: abrir el trace de una conversación que salió mal y ver en qué paso.
- **Datasets**: convertir traces reales (sobre todo los que fallaron) en casos de evaluación.
- **Evals online**: correr jueces sobre una muestra de traces y guardar el score en cada uno.
- **Métricas**: latencia, costo y errores por modelo, tool, feature o cliente (capítulo 7).

## Cómo se implementa

Mismo caso en todos los tabs: una función `answer(question)` que llama a Claude y a una tool de búsqueda, instrumentada para que cada llamada quede como span.

:::tabs
== LangSmith
`wrap_anthropic` envuelve el cliente para que cada llamada se registre como span de LLM; `@traceable` convierte cualquier función en span.

```python
import anthropic
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic

client = wrap_anthropic(anthropic.Anthropic())

@traceable(run_type="retriever")
def search_handbook(query: str) -> list[dict]:
    ...

@traceable(name="support-answer", metadata={"prompt_version": "v7"})
def answer(question: str) -> str:
    docs = search_handbook(question)
    response = client.messages.create(model="claude-opus-5-5", max_tokens=1024, messages=[...])
    return response.content[-1].text
```

Feedback sobre un trace ya registrado (por ejemplo, el thumbs down de un usuario):

```python
from langsmith import Client
Client().create_feedback(run_id=run_id, key="user_thumbs", score=0, comment="Wrong refund limit")
```
== Langfuse
Langfuse (open source, self-hostable) está construido sobre OpenTelemetry. `@observe` crea spans; las llamadas a Anthropic se capturan con la instrumentación OpenTelemetry para Anthropic y llegan a Langfuse como spans de tipo generación.

```python
from langfuse import get_client, observe
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor

AnthropicInstrumentor().instrument()   # every Anthropic call becomes a generation span
langfuse = get_client()

@observe(as_type="retriever")
def search_handbook(query: str) -> list[dict]:
    ...

@observe(name="support-answer")
def answer(question: str) -> str:
    docs = search_handbook(question)
    response = client.messages.create(model="claude-opus-5-5", max_tokens=1024, messages=[...])
    return response.content[-1].text
```

Scores (evals online, feedback) se guardan sobre el trace:

```python
langfuse.create_score(name="user_thumbs", value=0, trace_id=trace_id, data_type="BOOLEAN",
                      comment="Wrong refund limit")
```

`as_type` acepta `generation`, `agent`, `tool`, `retriever`, `evaluator`, `guardrail`: le dice a Langfuse qué tipo de paso es cada span.
== OpenTelemetry
Sin plataforma específica: el SDK de OpenTelemetry con la instrumentación de Anthropic emite spans con atributos `gen_ai.*` y los exporta por OTLP (el protocolo estándar de OpenTelemetry) a cualquier backend: Grafana, Datadog, Langfuse.

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.anthropic import AnthropicInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

provider = TracerProvider(resource=Resource.create({"service.name": "support-bot"}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))   # send spans to the backend
trace.set_tracer_provider(provider)
AnthropicInstrumentor().instrument()

tracer = trace.get_tracer("support-bot")

def answer(question: str) -> str:
    with tracer.start_as_current_span("support-answer") as span:
        span.set_attribute("app.prompt_version", "v7")
        with tracer.start_as_current_span("search_handbook"):
            docs = ...
        response = client.messages.create(model="claude-opus-5-5", max_tokens=1024, messages=[...])
        return response.content[-1].text
```

Ventaja: los traces del LLM quedan en el mismo sistema que los de tu API y tu base de datos, con el mismo trace id de punta a punta.
:::

## Errores comunes

- Loguear prompts completos con datos de clientes sin enmascarar.
- Instrumentar solo la llamada al modelo: sin los spans de tools y retrieval no se puede diagnosticar.
- No guardar la versión del prompt y del modelo como atributo: después no podés comparar.
- Traces que no se pueden convertir en casos de evaluación (falta input completo o contexto).
- Mezclar convenciones de atributos de versiones distintas de la instrumentación.

## En una entrevista

- **¿Qué observabilidad pondrías en un sistema con LLM?** Tracing por request con spans de cada llamada al modelo, tool y retrieval; atributos de modelo, tokens, costo, latencia y versión de prompt; feedback y evals online sobre los traces; métricas agregadas con alertas.
- **¿Qué son las convenciones GenAI de OpenTelemetry?** Nombres estándar (`gen_ai.*`) para atributos y métricas de llamadas a modelos, para que cualquier backend las interprete.
- **¿LangSmith, Langfuse u OpenTelemetry directo?** LangSmith si el stack es LangChain y querés evals y tracing integrados como SaaS; Langfuse si querés open source y self-host; OTel directo para integrarlo con la observabilidad existente de la empresa.
