---
title: Chunking
order: 2
type: concepto
---

**Objetivo:** partir documentos en fragmentos que se recuperen bien y que, solos, tengan sentido.

## Idea

Un **chunk** es la unidad que se indexa, se recupera y se pega en el prompt. Se parte porque:

- Un embedding de un documento entero promedia muchos temas y no se parece a ninguna pregunta concreta.
- El contexto que mandás al modelo tiene que ser lo relevante, no 50 páginas.
- Las citas apuntan a un fragmento, no a un PDF.

El trade-off central:

| Chunks chicos | Chunks grandes |
|---|---|
| Embedding preciso, se parecen a preguntas puntuales | Más contexto alrededor de la respuesta |
| Pueden quedar sin contexto ("se aprueba en 5 días": ¿qué cosa?) | Embedding difuso, compiten mal en la búsqueda |
| Más chunks para indexar y recuperar | Más tokens por consulta |

### Estrategias

| Estrategia | Cómo parte | Cuándo |
|---|---|---|
| **Tamaño fijo con overlap** | Cada N caracteres o tokens, solapando M | Texto sin estructura. Corta frases por la mitad |
| **Recursiva** | Intenta por párrafos, si quedan grandes por líneas, luego frases, luego palabras | Default razonable para texto general |
| **Por estructura** | Por headings de Markdown/HTML, secciones de un PDF, funciones de código | Documentos con estructura. Casi siempre la mejor |
| **Semántica** | Corta donde cambia el tema (distancia entre embeddings de frases consecutivas) | Texto largo sin estructura; más cara |
| **Por documento** | Un chunk por documento chico (FAQ, ticket) | Unidades naturales cortas |

### Técnicas que mejoran cualquier estrategia

- **Encabezado contextual**: anteponer título del documento y sección a cada chunk. Un chunk "## Approval rules" solo no dice de qué; "Refund policy > Approval rules" sí. Los ejemplos lo hacen en `chunk_markdown`.
- **Contextual retrieval**: pedirle a un LLM barato una oración que ubique el chunk en el documento y anteponerla antes de embeber. Mejora mucho el recall, a costo de una llamada por chunk al indexar (con caching del documento es barato).
- **Parent-child / small-to-big**: indexar chunks chicos para buscar, pero mandar al modelo el chunk padre (la sección entera).
- **Metadata siempre**: documento, sección, fecha, idioma, permisos, versión. Sirve para filtrar, citar y borrar.

### Parsing: el paso que nadie mira

Antes de partir hay que **extraer bien el texto**. Tablas de PDF convertidas en sopa de números, headers y footers repetidos en cada página, columnas mezcladas: ningún chunking arregla un parsing malo. Para PDFs complejos se usan parsers de documentos especializados o directamente un modelo con visión.

## Cómo se ve en código

Los text splitters de LangChain (`langchain-text-splitters`) implementan las estrategias recursiva y por estructura:

```python
recursive = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
by_heading = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")])
```

Comparación medida sobre el corpus de prueba del módulo (10 documentos cortos de un handbook ficticio y 22 preguntas etiquetadas). hit@k = la pregunta encuentra, entre los k primeros chunks, el que contiene la evidencia:

| Estrategia | Chunks | hit@1 | hit@3 |
|---|---|---|---|
| Tamaño fijo (300, overlap 50) | 34 | 14/22 | 18/22 |
| Recursiva (300, overlap 50) | 35 | 18/22 | 19/22 |
| Por headings de Markdown | 36 | 18/22 | 19/22 |

El tamaño fijo pierde porque corta frases y separa la evidencia de su contexto. Con documentos más largos y menos prolijos la diferencia a favor de la estructura crece.

> [!TIP]
> No hay un tamaño "correcto". Elegí una estrategia, medí con tus preguntas (capítulo 6) y cambiá de a una variable. 200–800 tokens por chunk es el rango habitual.

## Errores comunes

- Elegir tamaño de chunk sin medir.
- Chunks sin el título del documento: el embedding no sabe de qué tema son.
- Ignorar tablas: partirlas por filas pierde los encabezados de columna.
- No versionar la estrategia: si la cambiás, hay que reindexar todo y las evaluaciones viejas no son comparables.

## En una entrevista

- **¿Cómo elegís el tamaño de chunk?** Según la estructura del contenido y midiendo recall con un set de preguntas. Empiezo por estructura (headings) y ajusto.
- **¿Para qué sirve el overlap?** Para que una idea cortada en el borde aparezca completa en al menos un chunk. Con chunking por estructura importa menos.
- **¿Qué es contextual retrieval?** Agregar a cada chunk un resumen corto de dónde está en el documento antes de embeberlo e indexarlo, para que sea entendible solo.
