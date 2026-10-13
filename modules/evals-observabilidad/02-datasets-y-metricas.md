---
title: Datasets y métricas
order: 2
---

**Objetivo:** armar un dataset de evaluación útil, elegir métricas por tipo de tarea, y leer los resultados con criterio estadístico.

## Idea

### El dataset (golden set)

Cada caso tiene, como mínimo, la **entrada** y algo contra qué comparar. Según la tarea:

| Campo | Para qué |
|---|---|
| `input` | Lo que recibe el sistema (pregunta, conversación, documento) |
| `reference_output` | La respuesta esperada o los hechos que tiene que contener |
| `expected_tools` | Las tools y argumentos que debería usar un agente |
| `context` | Para RAG: qué fragmento tiene la respuesta |
| `metadata` | Categoría, dificultad, idioma, origen (producción, sintético, experto) |

Fuentes, de mejor a peor señal:

1. **Producción**: preguntas reales, especialmente las que fallaron o generaron quejas.
2. **Expertos del dominio**: casos que saben que son difíciles.
3. **Sintéticos**: un LLM genera variaciones a partir de documentos o de casos semilla. Sirven para arrancar y para cobertura; tienden a ser más fáciles que la realidad.

Cobertura que no puede faltar: casos felices, casos borde, entradas adversarias (prompt injection, pedidos fuera de alcance), y casos donde la respuesta correcta es **"no puedo / no sé"**.

> [!TIP]
> Un dataset de 50 casos bien elegidos y etiquetados con cuidado vale más que 2.000 sintéticos. Empezá chico, crecé con lo que falla en producción.

Versioná el dataset como código: un cambio de casos cambia los números, y hay que poder saber contra qué versión se midió.

### Métricas por tipo de tarea

| Tarea | Métricas típicas | Tipo |
|---|---|---|
| Clasificación, extracción | Exact match, accuracy, precision/recall por clase, validez de esquema | Determinista |
| Salida estructurada | Valida contra el esquema, campos correctos | Determinista |
| Respuesta libre | Correctness vs referencia, relevancia, tono, completitud | LLM-as-judge |
| RAG | Recall@k, MRR (retrieval); faithfulness, correctness (generación) | Mixta |
| Agentes | Tool correcta, argumentos correctos, trayectoria, tarea completada | Mixta |
| Seguridad | Tasa de rechazo correcto, fuga de PII, resistencia a injection | Mixta |
| Operación | Latencia p50/p95, costo por tarea, tokens, tasa de error | Determinista |

Métricas de texto clásicas (BLEU, ROUGE, similitud de embeddings) correlacionan mal con calidad percibida en respuestas abiertas. Sirven como señal barata, no como veredicto.

### No determinismo: cómo leer números

- **Repeticiones**: cada caso importante se evalúa varias veces (3–5) y se reporta la tasa de éxito, no un único resultado.
- **pass@k vs pass^k**: `pass@k` = al menos una de k corridas acierta (útil cuando un humano elige). `pass^k` = las k aciertan (lo que importa para un agente autónomo que tiene que funcionar siempre).
- **Tamaño de muestra**: con 50 casos, la diferencia entre 84% y 88% es de dos casos y probablemente ruido. Mirá intervalos de confianza o al menos qué casos cambiaron.
- **Comparación por caso**: más útil que el promedio. ¿Qué casos pasaron de bien a mal? Eso es la regresión.
- **Slicing**: el promedio esconde. Cortá por categoría, idioma, largo de la entrada.

```python
import math

def pass_rate_ci(passes: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Pass rate with a Wilson 95% confidence interval."""
    p = passes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return p, center - half, center + half

pass_rate_ci(44, 50)   # (0.88, ~0.76, ~0.94): a 0.84 baseline is inside the interval
```

### Umbrales y gates

En CI no se exige 100%. Se fija un umbral por métrica (por ejemplo, correctness ≥ 0.85 y ninguna regresión en casos marcados como críticos) y el pipeline falla si no se cumple.

## Errores comunes

- Dataset armado una vez y nunca actualizado con casos de producción.
- Solo casos felices: el sistema "pasa" y falla con el primer usuario real.
- Comparar promedios de dos corridas con 30 casos y sacar conclusiones.
- Métricas de similitud de texto como juez de calidad.
- No versionar el dataset.

## Preguntas de repaso

- **¿Cómo armás un dataset de evaluación?** Casos reales de producción y de expertos, completados con sintéticos para cobertura, incluyendo casos borde, adversarios y "no sé"; etiquetados y versionados.
- **¿Qué métricas usarías para un chatbot de soporte?** Deterministas para formato y tools, LLM-as-judge para correctness y faithfulness, tasa de resolución y escalamiento en producción, más latencia y costo.
- **¿Cómo manejás la variabilidad de los resultados?** Repeticiones por caso, tasas en vez de resultados únicos, intervalos de confianza, y comparación caso por caso entre versiones.
