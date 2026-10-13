---
name: add-module
description: Write a new learning module (or fill a pending one) for this AI Engineer study site - research current library versions, write Spanish reading chapters with technology tabs and inline code snippets, validate, regenerate manifest.json, check the render and commit. Use when the user says "/add-module <tech>", "agregá un módulo de X", "completá el módulo X", or asks to add a technology or concept to the site.
---

# add-module

Adds one module to `modules/` so the site at `index.html` shows it. One module per invocation.

Argument: a technology or concept (`rag`, `mcp`, `langsmith`, `pgvector`...). If it matches a module whose `module.json` has `"status": "pending"`, fill that module and keep its slug and order. Otherwise create a new one with the next free `NN`.

## Purpose of the site (shapes every decision)

- The reader is a senior QA / test-automation engineer with production Python, TypeScript, REST, SQL, Docker, CI/CD and one shipped tool-calling agent (Vercel AI SDK). Do not teach Python, HTTP, Docker or testing basics.
- Goal: learn skills and technologies that AI Engineer job descriptions require. **No projects, no "build X at the end", no exercises.** The site is flat study material: read-only chapters. Code appears only as snippets inside the chapter to illustrate the idea. Nothing in the repo is meant to be run, and nothing requires the reader's API keys, accounts, subscriptions or Docker. If the reader wants to try something, they write and set it up in their own project.
- Cover everything important about the technology, without padding. No time estimates.
- Prose in Spanish (rioplatense neutral, "vos" is fine). Code, identifiers and comments in code in English.

## Module structure

```
modules/NN-slug/
  module.json          # copy template/module.json
  01-chapter.md        # chapters, NN-kebab-case.md, frontmatter title/order/type
  02-chapter.md
```

No `code/` folder, no `requirements.txt`, no `.env.example`, no data files. The validator rejects them.

`module.json` fields: `slug`, `title`, `order` (int = folder prefix), `level` (basico | intermedio | avanzado), `status` (ready | pending), `summary`, `tags`, `prereqs` (module slugs), `versions` ({package: version} for the main libraries), optional `planned_chapters` (only for pending).

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

   - Use these exact labels so the reader's choice carries across pages: `Anthropic`, `OpenAI`, `OpenRouter`, `LangGraph`, `LangChain`, `CrewAI`, `MS Agent Framework`, `FastEmbed`, `pgvector`, `Chroma`, `Pinecone`, `Weaviate`, `FAISS`, `Milvus`, `Elasticsearch`, `LangSmith`, `ragas`, `promptfoo`, `OpenTelemetry`, `HubSpot`, `Salesforce`, `Odoo`, `Ollama`, `vLLM`, `FastAPI`. New label only for a technology not in this list.
   - Same example in every tab, so the reader compares the shape, not the problem.
   - First tab = the one job descriptions ask for most.
   - At least two tabs per block, no nested tabs.
4. Code lives only in fenced snippets inside the chapter. Do not reference script files, do not say "run this", "corré", "con tu API key", and do not include setup steps (venvs, `pip install`, `.env`, `docker run`). Mention setup facts only when they are knowledge worth having (e.g. "pgvector is a Postgres extension"), not as instructions.
5. Close with `## Errores comunes` and `## En una entrevista` (questions they ask and short answers).
6. Callouts: `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, `> [!IMPORTANT]`.
7. Tables over long lists when comparing technologies.

See `template/chapter.md` and the existing modules `00-fundamentos-llm`, `01-tool-use`, `02-orquestacion-agentes` for the expected depth and tone.

## Snippet rules

- Python. Snippets are short (usually under 25 lines), focused on one idea, and may elide setup with `...` (client creation, imports that are obvious).
- **Never write library calls from memory.** APIs in this space change monthly. Before writing a snippet, check the current API: install the latest PyPI version in a scratch venv outside the repo and introspect (`inspect.signature`, `dir`, reading the installed source), or read the official docs. For the Anthropic SDK, load the `claude-api` skill. This is a correctness check for the text, not runnable material for the repo.
- Default model in snippets: `claude-opus-5-5`. OpenAI-compatible snippets may use OpenRouter or OpenAI.
- Record the library versions the snippets were checked against in `module.json` `versions`.
- No unit or integration tests in this repo.

## Steps

1. Read `README.md`, `manifest.json` and one existing ready module to match tone and depth.
2. Research: official docs and current PyPI versions of every library the module covers. Check that libraries are still maintained (example: AutoGen and Semantic Kernel were merged into Microsoft Agent Framework; teach the current one and explain the mapping).
3. Write `module.json` and the chapters.
4. Check every snippet against the installed library (signatures, parameter names, return shapes) in a scratch venv outside the repo. Never call paid APIs or use the reader's keys.
5. `python3 .claude/skills/add-module/scripts/validate.py` until it prints `OK`. It rewrites `manifest.json`.
6. `uv run --with playwright==1.63.0 python .claude/skills/add-module/scripts/check_render.py --module <slug>` until 0 problems.
7. Commit on `main` and push: `git add modules/<slug> manifest.json && git commit -m "feat(module): <slug>" && git push`. One commit per finished module. End the commit message with the attribution line the session requires.
8. Report to the user: what the module covers and which APIs changed versus common knowledge.
