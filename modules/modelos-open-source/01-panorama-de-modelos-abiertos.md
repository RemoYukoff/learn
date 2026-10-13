---
title: Panorama de modelos abiertos
order: 1
---

**Objetivo:** saber qué es un modelo de pesos abiertos, qué familias existen, qué permite cada licencia y cuánta memoria hace falta para correrlo.

## Idea

Un modelo **de pesos abiertos** (open weights) publica los parámetros entrenados: los descargás y lo corrés donde quieras. Es distinto de **open source** en sentido estricto, que además publicaría datos de entrenamiento y código. Casi todos los modelos "abiertos" populares son open weights.

### Por qué usar uno en vez de una API

| Motivo | Detalle |
|---|---|
| Datos | Los datos no salen de tu infraestructura (salud, banca, gobierno) |
| Costo a volumen | Con tráfico alto y constante, una GPU propia puede salir más barata que pagar por token |
| Control | Versión fija, sin cambios del proveedor, latencia predecible |
| Personalización | Se puede fine-tunear a fondo |
| Offline / edge | Corre en una laptop, en un servidor aislado o en un dispositivo |

A cambio: operás vos (GPUs, escalado, actualizaciones) y los mejores modelos cerrados suelen seguir siendo más capaces en tareas difíciles.

### Familias principales

| Familia | Quién | Tamaños típicos | Licencia de pesos |
|---|---|---|---|
| **Llama** | Meta | 1B a 400B+ | Licencia propia (uso comercial con condiciones) |
| **Qwen** | Alibaba | 0.6B a 200B+ | Apache 2.0 en la mayoría |
| **Gemma** | Google | 1B a 30B | Licencia propia de Gemma |
| **Mistral** | Mistral AI | 7B a 120B+ | Apache 2.0 en los chicos, otras en los grandes |
| **DeepSeek** | DeepSeek | Modelos MoE grandes y destilados chicos | MIT en la mayoría |
| **gpt-oss** | OpenAI | 20B y 120B | Apache 2.0 |

Dentro de cada familia suele haber variantes **base** (solo predicen texto) e **instruct / chat** (entrenadas para seguir instrucciones y conversar). Para aplicaciones se usa la instruct.

### Licencias

- **Permisivas** (Apache 2.0, MIT): uso comercial, modificación y redistribución con atribución.
- **Propias** (Llama, Gemma): permiten uso comercial pero con condiciones (límites de usuarios, políticas de uso aceptable, obligación de mencionar el modelo).
- **Gated**: el repositorio exige aceptar la licencia antes de descargar.

Antes de usar un modelo en un producto, la licencia la revisa alguien que sepa leerla.

### Tamaño y memoria

La regla base: **memoria ≈ parámetros × bytes por parámetro**, más espacio para el KV cache (el contexto de las conversaciones en curso) y el runtime.

<figure class="diagram">
<svg viewBox="0 0 640 190" role="img" aria-label="Memoria de pesos de un modelo de 8B: 16 GB en BF16, 8 GB en INT8, unos 4,5 GB en 4 bits">
<text x="155" y="52" text-anchor="end" class="title">FP16 / BF16</text>
<rect class="process" x="170" y="30" width="384" height="32" rx="6"/>
<text x="564" y="52" class="sub">16 GB</text>
<text x="155" y="104" text-anchor="end" class="title">INT8</text>
<rect class="input" x="170" y="82" width="192" height="32" rx="6"/>
<text x="372" y="104" class="sub">8 GB</text>
<text x="155" y="156" text-anchor="end" class="title">4 bits</text>
<rect class="store" x="170" y="134" width="108" height="32" rx="6"/>
<text x="288" y="156" class="sub">~4.5 GB</text>
</svg>
<figcaption>Memoria solo de pesos para un modelo de 8B parámetros. El KV cache va aparte.</figcaption>
</figure>

| Precisión | Bytes por parámetro | 8B | 70B |
|---|---|---|---|
| FP16 / BF16 | 2 | ~16 GB | ~140 GB |
| INT8 | 1 | ~8 GB | ~70 GB |
| 4 bits | ~0.5 | ~4.5 GB | ~40 GB |

### Cuantización

**Cuantizar** es guardar los pesos con menos bits. Baja memoria y sube velocidad a cambio de algo de calidad; a 4 bits la pérdida suele ser chica en modelos de 7B para arriba, y crece en modelos muy chicos o tareas que exigen precisión (matemática, código).

| Formato | Para qué |
|---|---|
| **GGUF** | Archivo único con el modelo cuantizado para llama.cpp y Ollama. CPU, Apple Silicon y GPUs de consumo |
| **AWQ / GPTQ** | Cuantización a 4 bits pensada para servir en GPU con vLLM y similares |
| **FP8** | 8 bits en GPUs modernas, casi sin pérdida, usado en servidores |
| **bitsandbytes (NF4)** | Cuantización al cargar el modelo con transformers; base de QLoRA |

### Mixture of Experts (MoE)

Muchos modelos grandes son **MoE**: tienen muchos "expertos" y en cada token se activan solo algunos. Un modelo de 120B parámetros totales puede usar ~5B activos por token: computa como uno chico pero **ocupa la memoria de uno grande**, porque todos los expertos tienen que estar cargados.

## Errores comunes

- Confundir "abierto" con "sin restricciones": la licencia puede limitar el uso comercial.
- Usar la variante base cuando se necesitaba la instruct.
- Calcular memoria solo por los pesos y quedarse sin lugar para el KV cache con contextos largos o muchas requests.
- Elegir el modelo más grande que entra en la GPU sin medir si uno más chico alcanza para la tarea.

## Preguntas de repaso

- **¿Qué es un modelo open weights?** Un modelo cuyos parámetros entrenados están publicados para descargar y correr localmente; no implica que los datos o el código de entrenamiento sean abiertos.
- **¿Cuánta memoria necesita un modelo de 8B en BF16?** Unos 16 GB solo de pesos, más el KV cache.
- **¿Qué es cuantizar y qué se pierde?** Representar los pesos con menos bits; se gana memoria y velocidad, se pierde algo de calidad, más notorio en modelos chicos.
- **¿Qué es un modelo MoE?** Uno con muchos expertos donde cada token activa solo algunos: cómputo de modelo chico, memoria de modelo grande.
