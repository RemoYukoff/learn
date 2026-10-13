#!/usr/bin/env python3
"""Render every page of the site in headless Chromium and report problems.

Serves the repo on a free localhost port, visits home, each module page and each
chapter listed in manifest.json, and fails on:
  - console errors or uncaught page errors
  - missing <h1> or the viewer's error view
  - :::tabs blocks that do not switch, or a tab choice that does not persist

Run (no project venv needed):

    uv run --with playwright==1.63.0 python .claude/skills/add-module/scripts/check_render.py
    uv run --with playwright==1.63.0 python .claude/skills/add-module/scripts/check_render.py --module 01-tool-use
    ... --screenshots /tmp/shots     # also save a PNG per page

If Chromium is missing: uv run --with playwright==1.63.0 playwright install chromium
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # silence request logs
        pass


def serve() -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", help="only check this module slug")
    parser.add_argument("--screenshots", type=Path, help="directory to save a PNG per page")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "manifest.json").read_text())
    routes = [] if args.module else ["#/"]
    for mod in manifest["modules"]:
        if args.module and mod["slug"] != args.module:
            continue
        routes.append(f"#/{mod['slug']}")
        routes += [f"#/{mod['slug']}/{c['file']}" for c in mod["chapters"]]
    if not routes:
        print(f"No routes for module {args.module!r}")
        return 1

    server, port = serve()
    base = f"http://127.0.0.1:{port}/"
    failures: list[str] = []
    tab_checked = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(base)
        page.wait_for_selector("#content h1")

        for route in routes:
            errors.clear()
            page.goto(base + route)
            try:
                page.wait_for_selector("#content article h1", timeout=8000)
                page.wait_for_load_state("networkidle")
            except Exception:
                failures.append(f"{route}: no <h1> rendered")
                continue
            h1 = page.inner_text("#content article h1")
            if h1.strip() in {"Error", "No encontrado"}:
                body = page.inner_text("#content article")
                failures.append(f"{route}: viewer error view: {body[:200]!r}")
            if page.locator(".diagram-error").count():
                failures.append(f"{route}: mermaid diagram failed to render")
            for err in errors:
                failures.append(f"{route}: console: {err}")
            if page.locator(".tabs").count() and "Error" not in h1:
                # every tab block must have exactly one visible panel
                bad = page.evaluate(
                    """() => [...document.querySelectorAll('.tabs')].filter(
                        b => [...b.querySelectorAll(':scope > .tab-panel')].filter(p => !p.hidden).length !== 1
                    ).length"""
                )
                if bad:
                    failures.append(f"{route}: {bad} tab block(s) without exactly one visible panel")
                if not tab_checked:
                    tab_checked = True
                    first = page.locator(".tabs").first
                    buttons = first.locator(":scope > .tab-bar > .tab-btn")
                    label = buttons.nth(1).inner_text()
                    buttons.nth(1).click()
                    if first.locator(":scope > .tab-panel:not([hidden])").get_attribute("data-label") != label:
                        failures.append(f"{route}: clicking tab {label!r} did not switch the panel")
                    page.reload()
                    page.wait_for_selector(".tabs")
                    active = page.locator(".tabs").first.locator(".tab-btn.active").inner_text()
                    if active != label:
                        failures.append(f"{route}: tab {label!r} not persisted after reload (got {active!r})")
                    page.evaluate("localStorage.removeItem('learn-tab-pref')")
            if args.screenshots:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                name = route.strip("#/").replace("/", "__") or "home"
                page.screenshot(path=str(args.screenshots / f"{name}.png"), full_page=True)
            print(f"ok  {route}" if not any(f.startswith(route + ":") for f in failures) else f"BAD {route}")

        browser.close()
    server.shutdown()

    for f in failures:
        print("FAIL", f)
    print(f"\n{len(routes)} pages checked, {len(failures)} problem(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
