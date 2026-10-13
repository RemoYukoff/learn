---
title: Por qué orquestar
order: 1
type: concepto
---

**Objetivo:** saber qué problemas resuelve un framework de orquestación, qué vocabulario usa y cuándo no hace falta ninguno.

## Del loop al sistema

En el módulo de tool use armaste el loop de agente a mano: llamar al modelo, ejecutar las tools que pide, devolver resultados, repetir hasta `end_turn`. Ese loop alcanza para muchos casos reales. Los frameworks de orquestación aparecen cuando el sistema necesita cosas que el loop no da gratis:

| Necesidad | Qué pasa con un loop a mano |
|---|---|
| Pasos fijos combinados con pasos decididos por el modelo | Terminás con `if` anidados alrededor del loop |
| Pausar para que una persona apruebe y seguir horas después | Tenés que serializar todo el estado y reconstruirlo |
| Recuperarte de un crash a mitad de una tarea larga | Arrancás de cero y repetís llamadas y efectos |
| Varios agentes especializados que colaboran | Cada uno es un loop distinto y la coordinación queda implícita |
| Ver qué hizo el agente paso a paso | Logs ad hoc |
| Streaming de progreso a una UI | Callbacks propios en cada lugar |

Un framework de orquestación es, en esencia, **un runtime que ejecuta pasos sobre un estado compartido y guarda ese estado entre pasos**. Todo lo demás se apoya en eso.

## Workflow vs agente

La distinción más útil para diseñar:

- **Workflow:** el código decide el camino. El LLM ejecuta pasos concretos (clasificar, extraer, redactar) dentro de un flujo que vos definiste. Predecible, barato, fácil de testear.
- **Agente:** el modelo decide el camino. Elige qué tool usar y cuándo terminar. Flexible, más caro, menos predecible.

En producción casi todo es una mezcla: un workflow con algunos nodos donde un agente tiene autonomía acotada. Los frameworks modernos modelan las dos cosas con la misma primitiva (un grafo o un flujo de pasos), y un agente es simplemente un ciclo `modelo -> tools -> modelo` dentro de ese grafo.

> [!TIP]
> Empezá siempre por la opción más simple que funcione: una llamada, después un workflow, y solo después un agente. Es la recomendación de Anthropic en "Building effective agents".

## Las piezas

**Estado.** Un objeto tipado (dict, dataclass, modelo Pydantic) que viaja por el sistema: mensajes, datos extraídos, contadores, resultados parciales. Cada paso lee el estado y devuelve una actualización.

**Reducers.** Reglas para combinar actualizaciones. Por defecto un campo se reemplaza; con un reducer se acumula (append a una lista de mensajes, suma de contadores). Son clave cuando varios pasos corren en paralelo y escriben el mismo campo.

**Nodos y aristas.** Un nodo es una función (o un agente entero). Una arista dice qué viene después. Las **aristas condicionales** eligen el siguiente nodo según el estado, y permiten **ciclos**: la diferencia práctica entre un grafo y una cadena.

**Checkpoints.** Después de cada paso el runtime guarda una foto del estado. Con eso salen tres capacidades:

1. **Durabilidad:** si el proceso muere, se retoma desde el último checkpoint.
2. **Human-in-the-loop:** el grafo se pausa, se guarda, y sigue cuando llega la decisión humana, aunque sea en otro proceso y otro día.
3. **Time travel:** volver a un checkpoint anterior, editar el estado y re-ejecutar desde ahí. Muy útil para debuggear agentes.

**Threads o sesiones.** Un identificador que agrupa los checkpoints de una conversación. Es la memoria de corto plazo.

**Store.** Memoria de largo plazo que sobrevive entre threads: preferencias del usuario, hechos aprendidos.

**Multi-agente.** Varios agentes con prompts y tools distintos, coordinados por un patrón (supervisor, pipeline, handoff, grupo). Se ve en el capítulo de patrones.

## Cuándo no usar un framework

- El caso es una sola llamada o un loop de tools sin pausas ni persistencia. El loop de 40 líneas del módulo de Tool use es más fácil de leer, testear y debuggear.
- Necesitás control fino sobre cada request (caching, thinking, formatos nuevos de la API) y el framework todavía no expone esa opción. Los SDKs de los proveedores cambian más rápido que las capas encima.
- El equipo no conoce el framework y el sistema es chico. Cada capa extra es una abstracción más para entender cuando algo falla.

Señales de que sí conviene: pausas humanas, tareas largas que tienen que sobrevivir a reinicios, varios agentes, necesidad de trazas y replays, o un equipo que ya estandarizó en uno.

## Errores comunes

- Hacer un "agente" para algo que es un workflow fijo. Si sabés el orden de los pasos, escribilo como workflow.
- Meter todo en el estado (respuestas HTTP crudas, documentos enteros). El estado se serializa en cada checkpoint: guardá referencias o resúmenes.
- Olvidar que reanudar un nodo lo ejecuta de nuevo desde el principio. Los efectos externos dentro de un nodo tienen que ser idempotentes o ir después de la pausa.
- Mezclar memoria de conversación con memoria de usuario en el mismo lugar.

## Preguntas de repaso

- **¿Diferencia entre workflow y agente?** En el workflow el código define el camino; en el agente el modelo elige las acciones y cuándo terminar. Uso workflows por defecto y agentes donde la variabilidad lo justifica.
- **¿Para qué sirve un checkpointer?** Persistir el estado tras cada paso: retomar después de fallas, pausar para aprobación humana y reproducir o bifurcar ejecuciones.
- **¿Cuándo no usarías LangGraph?** Para un loop simple de tools sin persistencia ni pausas: el SDK del proveedor alcanza y es más transparente.
