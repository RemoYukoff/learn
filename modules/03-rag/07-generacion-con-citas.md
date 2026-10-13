---
title: Generación con citas
order: 7
type: implementacion
---

**Objetivo:** que el modelo responda solo con lo recuperado, diga cuando no alcanza, y muestre de qué fragmento sale cada afirmación.

## Idea

La etapa de generación tiene tres trabajos:

1. **Usar el contexto y nada más** (o explicitar cuando usa conocimiento general).
2. **Decir que no sabe** cuando el contexto no alcanza, en vez de completar.
3. **Citar**: cada afirmación apunta a su fuente, para que un humano verifique y para detectar alucinaciones.

### Armar el prompt

- Separá fuentes y pregunta con estructura (tags o bloques), con un **id estable** por fuente.
- Instrucción explícita: "respondé solo con las fuentes; si no alcanzan, decí qué falta".
- Orden: las fuentes más relevantes primero (y en contextos muy largos, también cerca del final).
- No mandes 20 chunks "por las dudas": el ruido baja la calidad y sube el costo.

### Dos formas de citar

| | Citas nativas del proveedor | Citas pedidas en el prompt |
|---|---|---|
| Cómo | La API recibe fuentes como bloques especiales y devuelve qué pasaje exacto respalda cada parte del texto | Numerás fuentes y pedís salida estructurada con los ids por afirmación |
| Garantía | El texto citado es literal del documento | El modelo puede citar mal o inventar ids: hay que validar |
| Disponibilidad | Anthropic (`search_result` y `document` con citations) | Cualquier modelo |

### Validar las citas

Tratalas como cualquier salida de un LLM: verificá en código que los ids existan entre las fuentes enviadas, y en evals medí faithfulness. Una cita a un id que no mandaste es señal clara de alucinación.

## Cómo se implementa

:::tabs
== Anthropic
Cada chunk recuperado va como bloque `search_result` (fuente, título, texto) en el mensaje del usuario o en un `tool_result`. Con `citations` activado, la respuesta viene partida en bloques de texto y los citados traen el pasaje exacto.

```python
search_results = [{
    "type": "search_result",
    "source": f"handbook/{c.id}",
    "title": f"{c.doc} - {c.section}",
    "content": [{"type": "text", "text": c.text}],
    "citations": {"enabled": True},          # all results must agree: all on or all off
} for c in retrieved]

response = client.messages.create(
    model="claude-opus-5-5", max_tokens=2048,
    system="Answer only from the provided search results. If they are not enough, say what is missing.",
    messages=[{"role": "user", "content": [*search_results, {"type": "text", "text": question}]}],
)
for block in response.content:
    if block.type == "text":
        for cit in block.citations or []:        # search_result_location
            print(cit.source, cit.cited_text)
```

Cuando el retrieval es una tool de un agente, la tool devuelve los `search_result` dentro del `tool_result` y las citas funcionan igual. Las citas no se pueden combinar con salida estructurada (`output_config.format`).

== OpenRouter
Sin citas nativas: fuentes numeradas en el prompt y salida estructurada con los ids por afirmación. Funciona con cualquier modelo.

```python
class Claim(BaseModel):
    text: str
    source_ids: list[str]

class GroundedAnswer(BaseModel):
    claims: list[Claim]
    missing_information: str | None

context = "\n\n".join(f'<source id="{sid}">\n{text}\n</source>' for sid, text in sources.items())
answer = client.chat.completions.parse(
    model="anthropic/claude-opus-5.5",
    messages=[{"role": "system", "content": "Answer only from the sources. Every claim must cite source ids."},
              {"role": "user", "content": f"{context}\n\nQuestion: {question}"}],
    response_format=GroundedAnswer,
).choices[0].message.parsed

for claim in answer.claims:
    unknown = [s for s in claim.source_ids if s not in sources]   # validate in code
```

:::

## Errores comunes

- No darle al modelo una salida explícita para "no está en las fuentes".
- Citar documentos enteros en vez de fragmentos: el usuario no puede verificar.
- Confiar en ids citados sin validarlos.
- Mezclar instrucciones dentro del texto de las fuentes (prompt injection desde documentos): delimitá y tratá las fuentes como datos.

## En una entrevista

- **¿Cómo reducís alucinaciones en RAG?** Mejor retrieval, instrucción de responder solo con el contexto y decir cuando no alcanza, citas verificables, y medir faithfulness.
- **¿Cómo implementás citas?** Con citas nativas del proveedor si existen (pasaje literal); si no, fuentes con ids y salida estructurada, validando los ids en código.
- **¿Qué hacés si el documento recuperado contiene instrucciones maliciosas?** Delimitarlo como datos, no darle a la generación tools con efectos, y validar la salida; es prompt injection indirecta.
