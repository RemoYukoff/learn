---
name: add-module
description: Write a new standalone learning module for this study site - research current library versions, write Spanish reading chapters with technology tabs and inline code snippets, validate, regenerate manifest.json, check the render and commit. Use when the user says "/add-module <tech>", "agregá un módulo de X", or asks to add a technology or concept to the site.
---

# add-module

Adds one module to `modules/` so the site at `index.html` shows it. One module per invocation.

Argument: a technology or concept (`rag`, `mcp`, `langsmith`, `pgvector`...). Create `modules/<slug>/` (kebab-case, no number prefix). If a module on that topic already exists, extend or rewrite it instead of creating a duplicate.

## Purpose of the site (shapes every decision)

- Each module stands on its own: RAG teaches RAG, MCP teaches MCP. Do not frame a module as part of a career path, course or role (no "AI Engineer", no "lo que piden las búsquedas"). Modules have no order, level or prerequisites: React, RAG or Kubernetes are just modules to search and study. Mention another module only by name and only if it exists ("ver el módulo de RAG"), never by number.
- The reader is a senior engineer with production Python, TypeScript, REST, SQL, Docker, CI/CD and testing experience. Do not teach those basics.
- **No projects, no "build X at the end", no exercises.** The site is flat study material: read-only chapters. Code appears only as snippets inside the chapter to illustrate the idea. Nothing in the repo is meant to be run, and nothing requires the reader's API keys, accounts, subscriptions or Docker. If the reader wants to try something, they write and set it up in their own project.
- Cover everything important about the technology, without padding. No time estimates.
- **Theory, then code.** Each chapter explains what the thing does and how it works, then shows in code how it is implemented. Nothing else. No implementation gotchas: no notes about which model accepts which parameter, library bugs, version quirks, deprecated aliases, default values, env var names, licenses or install problems. If a library needs a workaround, just write the working code without commenting on it.
- **Only mainstream, maintained libraries.** Cover the libraries most used in industry for the topic, and only maintained ones (a release in the last ~6 months). No name-dropping of niche or alternative libraries.
- Prose in Spanish (rioplatense neutral, "vos" is fine). Code, identifiers and comments in code in English.

## Module structure

```
modules/<slug>/
  module.json          # copy template/module.json
  01-chapter.md        # chapters, NN-kebab-case.md, frontmatter title/order/type
  02-chapter.md
```

No `code/` folder, no `requirements.txt`, no `.env.example`, no data files. The validator rejects them.

`module.json` fields: `slug` (= folder name), `title`, `summary` (one sentence, shown on the module card), `tags` (used by search), `versions` ({package: version} the snippets were checked against; not shown on the site).

## Chapter rules

1. Start with frontmatter (`title`, `order`, `type: concepto | implementacion`) then `**Objetivo:**` in one line. Do not repeat the title as `#` heading: the viewer renders it.
2. **Concept first, agnostic.** Explain what the thing does and how it works without tying it to a library: vocabulary, moving parts, trade-offs, failure modes.
3. **Then the implementations in a tab block** when more than one technology does the same job:

   ```
   :::tabs
   == LangGraph
   markdown + code
   == CrewAI
   markdown + code
   :::
   ```

   - Use these exact labels so the reader's choice carries across pages: `Anthropic`, `OpenAI`, `OpenRouter`, `LangGraph`, `LangChain`, `CrewAI`, `MS Agent Framework`, `Hugging Face`, `pgvector`, `Chroma`, `Pinecone`, `Weaviate`, `FAISS`, `Milvus`, `Elasticsearch`, `LangSmith`, `DeepEval`, `Langfuse`, `OpenTelemetry`, `HubSpot`, `Salesforce`, `Odoo`, `Ollama`, `vLLM`, `FastAPI`. New label only for a technology not in this list.
   - Same example in every tab, so the reader compares the shape, not the problem.
   - First tab = the most widely used one.
   - At least two tabs per block, no nested tabs.
4. Code lives only in fenced snippets inside the chapter. Do not reference script files, do not say "run this", "corré", "con tu API key", and do not include setup steps (venvs, `pip install`, `.env`, `docker run`). Mention setup facts only when they are knowledge worth having (e.g. "pgvector is a Postgres extension"), not as instructions.
5. Close with `## Errores comunes` and `## Preguntas de repaso` (key questions about the topic with short answers).
6. Callouts: `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!IMPORTANT]`.
7. Tables over long lists when comparing technologies.
8. **Diagrams, never ASCII art.** Studying is easier with pictures: add a diagram whenever a structure, flow, sequence, hierarchy, state machine or comparison is easier to see than to read. Two options:
   - **Mermaid (default).** A fenced ```` ```mermaid ```` block; the viewer renders it with the site palette and re-renders on theme change. Use it for `flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `timeline`, `mindmap`, `classDiagram`. Color nodes with the site classes `:::input`, `:::process`, `:::store`, `:::human`, `:::risk` (flowcharts and state diagrams). Never set colors or themes inside the diagram.

     ```mermaid
     flowchart LR
         Q[Pregunta]:::input --> R[Retriever]:::process --> L[LLM]:::process --> A[Respuesta]:::store
     ```
   - **Inline SVG** for custom visuals Mermaid cannot draw well (pyramids, token chips, timelines with bars). Raw HTML in the Markdown, no blank lines inside:

     ```html
     <figure class="diagram">
     <svg viewBox="0 0 W H" role="img" aria-label="what it shows">
     <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="arrowhead" d="M0,0 L10,5 L0,10 z"/></marker></defs>
     ...connectors first (class="line" or "line dash", marker-end="url(#ah)"), then boxes and text...
     </svg>
     <figcaption>One sentence.</figcaption>
     </figure>
     ```

     Only site classes, no hard-coded colors or fonts: boxes `node`, `input`, `process`, `store`, `human`, `risk`, group borders `zone`, text `title`, `sub`, `mono`. viewBox width 500–860.

   Keep 5–9 main elements and short labels. Check every diagram with a screenshot in light and dark.

See `template/chapter.md` and the existing modules `00-fundamentos-llm`, `01-tool-use`, `02-orquestacion-agentes` for the expected depth and tone.

## Snippet rules

- Python. Snippets are short (usually under 25 lines), focused on one idea, and may elide setup with `...` (client creation, imports that are obvious).
- **Never write library calls from memory.** APIs in this space change monthly. Before writing a snippet, check the current API: install the latest PyPI version in a scratch venv outside the repo and introspect (`inspect.signature`, `dir`, reading the installed source), or read the official docs. For the Anthropic SDK, load the `claude-api` skill. This is a correctness check for the text, not runnable material for the repo.
- Default model in snippets: `claude-opus-5-5`. OpenAI-compatible snippets may use OpenRouter or OpenAI.
- Record the library versions the snippets were checked against in `module.json` `versions`.
- No unit or integration tests in this repo.

## Steps

1. Read `README.md`, `manifest.json` and one existing ready module to match tone and depth.
2. Research: which libraries are most used for the topic, their official docs and current PyPI versions. Drop libraries without a release in ~6 months. If a library was superseded (AutoGen and Semantic Kernel became Microsoft Agent Framework), teach the current one and explain the conceptual mapping.
3. Write `module.json` and the chapters.
4. Check every snippet against the installed library (signatures, parameter names, return shapes) in a scratch venv outside the repo. Never call paid APIs or use the reader's keys.
5. `python3 .claude/skills/add-module/scripts/validate.py` until it prints `OK`. It rewrites `manifest.json`.
6. `uv run --with playwright==1.63.0 python .claude/skills/add-module/scripts/check_render.py --module <slug>` until 0 problems.
7. Commit on `main` and push: `git add modules/<slug> manifest.json && git commit -m "feat(module): <slug>" && git push`. One commit per finished module. End the commit message with the attribution line the session requires.
8. Report to the user in plain words: what the module covers. No library trivia in the report either.
