---
title: Qué es function calling
order: 1
type: concepto
---

**Objetivo:** entender el protocolo que convierte un modelo de texto en algo que consulta y modifica sistemas reales, y quién hace qué en cada paso.

## Idea

Un LLM solo produce texto. **Function calling** (Anthropic lo llama *tool use*) es un acuerdo de formato:

1. Vos le describís al modelo un conjunto de **tools**: nombre, descripción y un JSON Schema de los parámetros.
2. El modelo, en vez de contestar, puede devolver un pedido estructurado: "llamá a `list_tickets` con `{"customer_id": "C-100"}`".
3. **Tu código** ejecuta la función, con tus credenciales y tus reglas.
4. Le devolvés el resultado al modelo, que sigue razonando: responde o pide otra tool.

```text
 tu app                         modelo
   │  mensajes + tools  ───────▶  │
   │                              │ decide: necesito datos
   │  ◀─────── tool_use(name,input)
   │ ejecuta list_tickets()        │
   │  tool_result  ─────────────▶  │
   │                              │ decide: ya puedo responder
   │  ◀─────────────── texto final │
```

El modelo **nunca ejecuta nada**. Elige qué tool usar y con qué argumentos. Eso tiene dos consecuencias que las entrevistas preguntan:

- **Seguridad**: los permisos son los de tu código, no los del modelo. Validás y autorizás cada llamada vos.
- **Confiabilidad**: el modelo puede elegir mal la tool o pasar argumentos inválidos. Tu ejecutor tiene que tolerarlo y devolver errores útiles.

### Qué decide el modelo y cómo

El modelo ve las tools como parte del prompt. Elige según:

- **La descripción**: es la parte más importante. Qué hace, cuándo usarla, cuándo no, qué devuelve.
- **El nombre y los parámetros**: nombres claros (`issue_refund`, no `op3`), descripciones en cada parámetro, enums cuando hay valores fijos.
- **El contexto de la conversación**.

`tool_choice` controla si puede elegir (`auto`, el default), si no puede usar tools (`none`), o si está obligado a usar alguna.

### Llamadas en paralelo

En un mismo turno el modelo puede pedir **varias tools a la vez** (por ejemplo, buscar dos clientes). Las ejecutás (en paralelo si son independientes) y devolvés **todos** los resultados juntos en el siguiente mensaje.

### Tools del cliente vs tools del servidor

| Tipo | Quién la ejecuta | Ejemplos |
|---|---|---|
| Client tools | Tu código | Tu CRM, tu base de datos, tu API |
| Server tools | El proveedor | Web search, code execution de Anthropic u OpenAI |
| Tools vía MCP | Un servidor MCP | Módulo 05 |

Este módulo trata las client tools, que son el 90% del trabajo en las búsquedas ("conectar agentes a ERPs, CRMs y APIs de clientes").

### De tool use a agente

Una llamada con tools es un paso. Un **agente** es un loop: llamar al modelo, ejecutar las tools que pide, devolver resultados, repetir hasta que responda sin pedir tools. Ese loop es el capítulo 3, y los frameworks del módulo 02 lo empaquetan.

## Errores comunes

- Pensar que el modelo "llama a la API": no, la llama tu código.
- Descripciones de una línea ("gets tickets"). La calidad de la elección depende de la descripción.
- Exponer tools demasiado poderosas (`run_sql(query)`) cuando alcanzaba con tools específicas.
- Devolver resultados enormes (todo el JSON de la API) que llenan el contexto.

## En una entrevista

- **¿Cómo funciona function calling?** Definís tools con JSON Schema, el modelo devuelve un pedido estructurado con nombre y argumentos, tu código ejecuta y le devuelve el resultado. El modelo nunca ejecuta.
- **¿Cómo hace el modelo para elegir la tool correcta?** Por la descripción, el nombre, el esquema y el contexto. Por eso las descripciones se escriben como prompts y se evalúan.
- **¿Qué riesgos tiene darle tools a un LLM?** Acciones no deseadas por error o por prompt injection. Se mitiga con permisos mínimos, validación, confirmación humana para acciones sensibles y auditoría.
