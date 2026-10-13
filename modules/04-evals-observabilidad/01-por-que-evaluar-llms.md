---
title: Por qué evaluar LLMs es distinto a testear
order: 1
type: concepto
---

**Objetivo:** entender qué cambia cuando el sistema bajo prueba es no determinista y su salida es lenguaje, y qué se mantiene igual de lo que ya sabés de QA.

## Idea

En software clásico, un test compara la salida con un valor esperado: pasa o falla, siempre igual. Con un LLM eso se rompe en tres lugares:

| | Software clásico | Sistema con LLM |
|---|---|---|
| Determinismo | Misma entrada, misma salida | Misma entrada, salidas distintas (sampling, cambios del proveedor) |
| Oráculo | `assert output == expected` | Muchas respuestas correctas posibles, escritas distinto |
| Resultado | Pasa / falla | Una distribución: "acierta el 92% de las veces" |
| Regresión | Un cambio de código rompe un caso | Un cambio de prompt, de modelo o de datos mejora 10 casos y rompe 3 |

Por eso en el mundo LLM se habla de **evals** y no solo de tests: mediciones estadísticas de calidad sobre un dataset, que se comparan entre versiones.

### Lo que no cambia

Tu experiencia de QA aplica casi entera:

- **Pirámide**: muchas verificaciones baratas y deterministas, pocas caras.
- **Datos de prueba** curados, versionados, con casos borde.
- **Regresiones en CI** que bloquean un cambio.
- **Bugs reproducibles**: un caso que falló en producción se agrega al dataset.
- **Observabilidad** para entender fallas en producción.

### La pirámide de evals

<figure class="diagram">
<svg viewBox="0 0 700 300" role="img" aria-label="Pirámide de evals: checks deterministas en la base, LLM-as-judge en el medio, humanos arriba">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<line class="line dash" x1="242" y1="70" x2="392" y2="70"/>
<line class="line dash" x1="270" y1="140" x2="392" y2="140"/>
<line class="line dash" x1="327" y1="230" x2="392" y2="230"/>
<polygon class="human" points="190,20 242,100 138,100"/>
<polygon class="process" points="138,100 242,100 295,180 85,180"/>
<polygon class="store" points="85,180 295,180 360,280 20,280"/>
<text x="190" y="86" text-anchor="middle" class="title">Humanos</text>
<text x="190" y="146" text-anchor="middle" class="title">LLM-as-judge</text>
<text x="190" y="236" text-anchor="middle" class="title">Checks deterministas</text>
<text x="400" y="75" class="sub">revisión manual, A/B, feedback de usuarios</text>
<text x="400" y="145" class="sub">rúbricas, faithfulness, comparación pairwise</text>
<text x="400" y="228" class="sub">esquema, contiene, regex, tool correcta,</text>
<text x="400" y="246" class="sub">latencia, costo</text>
<line class="line" x1="672" y1="270" x2="672" y2="30" marker-end="url(#ah)"/>
<text x="660" y="150" class="sub" text-anchor="middle" transform="rotate(-90 660 150)">más caro y lento · menos casos</text>
</svg>
<figcaption>Todo lo que se puede verificar con código va abajo; el juez LLM para lo que necesita leer el texto; los humanos calibran al juez.</figcaption>
</figure>

Regla: todo lo que se pueda verificar con código, se verifica con código. El juez LLM es para lo que de verdad necesita leer el texto. Los humanos calibran al juez y revisan lo que importa.

### Qué se evalúa

| Nivel | Pregunta | Ejemplo |
|---|---|---|
| Componente | ¿Esta pieza hace bien su trabajo? | El retrieval trae el chunk correcto; el clasificador elige la categoría |
| Paso de agente | ¿Eligió la tool y los argumentos correctos? | `issue_refund(amount=49)` y no `amount=490` |
| Trayectoria | ¿El camino fue razonable? | No llamó 12 veces a la misma tool |
| Resultado final | ¿Resolvió la tarea? | El ticket quedó cerrado y el cliente reembolsado |
| Producción | ¿Funciona con usuarios reales? | Tasa de éxito, quejas, costo por tarea |

### Offline vs online

- **Offline**: antes de deployar, sobre un dataset fijo. Responde "¿esta versión es mejor que la anterior?".
- **Online**: en producción, sobre tráfico real (muestreado). Responde "¿sigue funcionando?, ¿qué tipo de pregunta falla?".

Los dos se alimentan: las fallas de producción se convierten en casos del dataset offline.

### Eval-driven development

El flujo que esperan las búsquedas ("construir evaluaciones de LLM para medir calidad"):

1. Definir qué es "bueno" para esta tarea, con ejemplos.
2. Armar el dataset y las métricas **antes** de iterar el prompt.
3. Medir la línea base.
4. Cambiar una cosa (prompt, modelo, retrieval, tool), medir, comparar.
5. Quedarse con el cambio solo si mejora sin romper otros casos.

## Errores comunes

- Probar un prompt con tres ejemplos a mano y declarar que "funciona".
- Correr cada caso una vez y tratar el resultado como determinista.
- Medir solo el resultado final de un agente: no sabés qué paso falló.
- Usar un juez LLM para algo que un `assert` resuelve.
- No guardar los casos de producción que fallaron.

## En una entrevista

- **¿En qué se diferencia evaluar un LLM de testear software?** La salida no es determinista y hay muchas respuestas válidas, así que se mide estadísticamente sobre un dataset y se compara entre versiones, combinando checks deterministas, jueces LLM y revisión humana.
- **¿Qué es una eval?** Un dataset de casos más una o varias métricas que producen un puntaje agregado para una versión del sistema.
- **¿Offline u online?** Ambos: offline para decidir si un cambio se deploya, online para detectar degradación y descubrir casos nuevos.
