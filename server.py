#!/usr/bin/env python3
"""Local server for the learn site: static files plus an edit endpoint.

    POST /api/edit  {slug, file, selection, context, tab, instruction}

Runs Claude Code headless (`claude -p`) with only the Read and Edit tools to
change one chapter .md, then re-runs validate.py. Standard library only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALIDATE = ROOT / ".claude/skills/add-module/scripts/validate.py"
EDIT_TIMEOUT = 600  # seconds; a headless edit usually takes 30 to 120
edit_lock = threading.Lock()

PROMPT = """Sos el editor de un sitio de estudio en español. El lector seleccionó un pasaje de un capítulo y pide un cambio.

Archivo a editar: {path}
Pasaje seleccionado (texto renderizado: puede faltar el markdown como **, `, enlaces o viñetas; buscalo en el archivo):
<<<
{selection}
>>>
Párrafo o bloque que lo contiene:
<<<
{context}
>>>
{tab_line}Pedido del lector:
<<<
{instruction}
>>>

Reglas:
- Editá solo {path}, con Read y Edit. No toques otros archivos.
- Cambiá lo necesario para cumplir el pedido, en la zona del pasaje. Si pide ampliar, agregá contenido ahí mismo o justo después.
- Español rioplatense, mismo tono y formato que el resto del capítulo.
- Primero la teoría de qué hace algo, después código de cómo se implementa. Código solo como snippets inline en Python; nada para ejecutar ni instalar (sin pip install, sin .env, sin "corré esto").
- Nada de detalles de librerías: bugs, versiones, alias deprecados, defaults, qué modelo acepta qué parámetro.
- Sin jerga sin explicar.
- No toques el frontmatter (title, order).
- Respetá los bloques :::tabs / == Etiqueta / ::: ; si el pasaje está dentro de una pestaña, el cambio va en esa pestaña.
- Diagramas: bloques ```mermaid con clases :::input, :::process, :::store, :::human, :::risk si hacen falta.

Al terminar respondé una sola línea en español diciendo qué cambiaste."""


def chapter_path(slug: str, file: str) -> Path | None:
    """Only chapters listed in manifest.json can be edited."""
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for mod in manifest["modules"]:
        if mod["slug"] == slug and any(c["file"] == file for c in mod["chapters"]):
            return ROOT / "modules" / slug / file
    return None


def changed_files() -> set[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return {line[3:] for line in out.splitlines()}


def run_edit(req: dict) -> dict:
    for key in ("slug", "file", "selection", "instruction"):
        if not isinstance(req.get(key), str) or not req[key].strip():
            return {"ok": False, "error": f"falta '{key}'"}
    path = chapter_path(req["slug"], req["file"])
    if path is None:
        return {"ok": False, "error": "capítulo desconocido"}
    rel = path.relative_to(ROOT).as_posix()

    tab = (req.get("tab") or "").strip()
    prompt = PROMPT.format(
        path=rel,
        selection=req["selection"].strip()[:4000],
        context=(req.get("context") or "").strip()[:4000] or "(sin contexto)",
        tab_line=f"Está dentro de la pestaña: {tab}\n" if tab else "",
        instruction=req["instruction"].strip()[:4000],
    )

    with edit_lock:
        original = path.read_text()
        before = changed_files()
        # Drop the parent session's variables so the server also works when
        # started from inside Claude Code.
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDECODE", "CLAUDE_CODE_"))}
        try:
            proc = subprocess.run(
                [
                    "claude", "-p", prompt,
                    "--tools", "Read,Edit",
                    "--allowedTools", "Read,Edit",
                    "--permission-mode", "acceptEdits",
                    "--strict-mcp-config",
                    "--no-session-persistence",
                    "--output-format", "json",
                ],
                cwd=ROOT, env=env, capture_output=True, text=True, timeout=EDIT_TIMEOUT,
            )
        except FileNotFoundError:
            return {"ok": False, "error": "no se encontró el comando claude"}
        except subprocess.TimeoutExpired:
            path.write_text(original)
            return {"ok": False, "error": "el agente tardó demasiado"}

        # Anything the agent touched besides the chapter is put back.
        for stray in changed_files() - before - {rel}:
            subprocess.run(["git", "checkout", "--", stray], cwd=ROOT, capture_output=True)

        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            result = {"is_error": True, "result": (proc.stderr or proc.stdout).strip()[-500:]}
        if proc.returncode != 0 or result.get("is_error"):
            path.write_text(original)
            return {"ok": False, "error": result.get("result") or "el agente falló"}

        if path.read_text() == original:
            return {"ok": False, "error": result.get("result") or "el agente no cambió nada"}

        check = subprocess.run([sys.executable, str(VALIDATE)], cwd=ROOT, capture_output=True, text=True)
        if check.returncode != 0:
            path.write_text(original)
            errors = [l for l in check.stdout.splitlines() if l.startswith("ERROR")]
            return {"ok": False, "error": "el cambio rompía el formato, se deshizo: " + "; ".join(errors)[:500]}

        return {"ok": True, "summary": (result.get("result") or "").strip()}


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/edit":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length))
            body = run_edit(req if isinstance(req, dict) else {})
        except (ValueError, json.JSONDecodeError):
            body = {"ok": False, "error": "pedido inválido"}
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(200 if body["ok"] else 400)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(os.environ.get("PORT", 8787))
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(ROOT)))
    print(f"learn en http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
