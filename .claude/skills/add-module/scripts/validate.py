#!/usr/bin/env python3
"""Validate every module under modules/ and regenerate manifest.json.

Standard library only. Run from anywhere:

    python3 .claude/skills/add-module/scripts/validate.py          # validate + write manifest
    python3 .claude/skills/add-module/scripts/validate.py --check  # validate only

Exit code 1 when any error is found; the manifest is not written in that case.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MODULES = ROOT / "modules"
MANIFEST = ROOT / "manifest.json"

SLUG_RE = re.compile(r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")
CHAPTER_RE = re.compile(r"^\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)
LEVELS = {"basico", "intermedio", "avanzado"}
CHAPTER_TYPES = {"concepto", "implementacion"}
REQUIRED_MODULE_KEYS = {"title", "order", "level", "summary", "tags", "prereqs", "versions"}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: str, msg: str) -> None:
        self.errors.append(f"ERROR   {where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"WARNING {where}: {msg}")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if kv:
            value = re.sub(r"\s+#.*$", "", kv.group(2)).strip().strip("\"'")
            meta[kv.group(1)] = value
    return meta


def check_tabs(text: str, where: str, report: Report) -> None:
    """:::tabs blocks must close and contain at least two '== Label' tabs."""
    fence: str | None = None
    in_tabs = False
    labels: list[str] = []
    start_line = 0
    for n, line in enumerate(text.splitlines(), 1):
        fm = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fm:
            if fence is None:
                fence = fm.group(1)
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence:
            continue
        stripped = line.strip()
        if stripped == ":::tabs":
            if in_tabs:
                report.error(where, f"line {n}: nested :::tabs (block opened at line {start_line})")
            in_tabs, labels, start_line = True, [], n
        elif stripped == ":::" and in_tabs:
            if len(labels) < 2:
                report.error(where, f"line {start_line}: :::tabs block needs at least 2 tabs, found {len(labels)}")
            if len(set(labels)) != len(labels):
                report.error(where, f"line {start_line}: duplicate tab labels {labels}")
            in_tabs = False
        elif in_tabs and (m := re.match(r"^==\s+(.+?)\s*$", line)):
            labels.append(m.group(1))
    if in_tabs:
        report.error(where, f"line {start_line}: :::tabs block never closed with :::")
    if fence:
        report.error(where, "unclosed code fence")


RUN_PHRASES = re.compile(
    r"`code/|\bcorré\b|\bcorrelo\b|ejecut[áa]lo|python \d\d_|pip install|uv pip|\.env\.example|tu API key|tus claves",
    re.I,
)


def validate_module(path: Path, report: Report) -> dict | None:
    slug = path.name
    where = f"modules/{slug}"
    if not SLUG_RE.match(slug):
        report.error(where, "folder must be NN-kebab-case, e.g. 03-rag")
    meta_file = path / "module.json"
    if not meta_file.exists():
        report.error(where, "missing module.json")
        return None
    try:
        meta = json.loads(meta_file.read_text())
    except json.JSONDecodeError as exc:
        report.error(f"{where}/module.json", f"invalid JSON: {exc}")
        return None

    missing = REQUIRED_MODULE_KEYS - meta.keys()
    if missing:
        report.error(f"{where}/module.json", f"missing keys: {sorted(missing)}")
        return None
    if meta.get("slug", slug) != slug:
        report.error(f"{where}/module.json", f"slug '{meta['slug']}' does not match folder")
    if not isinstance(meta["order"], int) or meta["order"] != int(slug[:2]):
        report.error(f"{where}/module.json", "order must be an int equal to the folder prefix")
    if meta["level"] not in LEVELS:
        report.error(f"{where}/module.json", f"level must be one of {sorted(LEVELS)}")
    for key in ("status", "planned_chapters"):
        if key in meta:
            report.error(f"{where}/module.json", f"'{key}' is not used: a module exists only when its chapters exist")
    for key in ("tags", "prereqs"):
        if not isinstance(meta[key], list):
            report.error(f"{where}/module.json", f"{key} must be a list")
    if not isinstance(meta["versions"], dict):
        report.error(f"{where}/module.json", "versions must be an object {package: version}")

    chapters = []
    md_files = sorted(p for p in path.glob("*.md"))
    for md in md_files:
        cwhere = f"{where}/{md.name}"
        if not CHAPTER_RE.match(md.name):
            report.error(cwhere, "chapter file must be NN-kebab-case.md")
            continue
        text = md.read_text()
        fm = parse_frontmatter(text)
        if fm is None:
            report.error(cwhere, "missing frontmatter block (--- title/order/type ---)")
            continue
        for key in ("title", "order", "type"):
            if not fm.get(key):
                report.error(cwhere, f"frontmatter missing '{key}'")
        if fm.get("type") and fm["type"] not in CHAPTER_TYPES:
            report.error(cwhere, f"type must be one of {sorted(CHAPTER_TYPES)}")
        try:
            order = int(fm.get("order", ""))
        except ValueError:
            report.error(cwhere, "order must be an integer")
            continue
        if order != int(md.name[:2]):
            report.error(cwhere, f"order {order} does not match file prefix {md.name[:2]}")
        check_tabs(text, cwhere, report)
        for n, line in enumerate(text.splitlines(), 1):
            if m := RUN_PHRASES.search(line):
                report.error(cwhere, f"line {n}: '{m.group(0)}' - chapters are read-only, no runnable files or setup steps")
        chapters.append({"file": md.name, "title": fm.get("title", md.stem), "order": order, "type": fm.get("type", "concepto")})

    chapters.sort(key=lambda c: c["order"])
    orders = [c["order"] for c in chapters]
    if len(set(orders)) != len(orders):
        report.error(where, f"duplicate chapter orders {orders}")

    extra = sorted(p.name for p in path.iterdir() if p.name != "module.json" and p.suffix != ".md")
    if extra:
        report.error(where, f"only module.json and chapter .md files are allowed, found {extra}")

    if not chapters:
        report.error(where, "module has no chapters")

    entry = {
        "slug": slug,
        "title": meta["title"],
        "order": meta["order"],
        "level": meta["level"],
        "summary": meta["summary"],
        "tags": meta["tags"],
        "prereqs": meta["prereqs"],
        "versions": meta["versions"],
        "chapters": chapters,
    }
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate only, do not write manifest.json")
    args = parser.parse_args()

    report = Report()
    entries = []
    for path in sorted(p for p in MODULES.iterdir() if p.is_dir()):
        entry = validate_module(path, report)
        if entry:
            entries.append(entry)

    slugs = {e["slug"] for e in entries}
    orders = [e["order"] for e in entries]
    if len(set(orders)) != len(orders):
        report.error("modules", f"duplicate module orders {sorted(orders)}")
    for e in entries:
        for pre in e["prereqs"]:
            if pre not in slugs:
                report.error(f"modules/{e['slug']}/module.json", f"prereq '{pre}' is not a module slug")

    if not (ROOT / "home.md").exists():
        report.error("home.md", "missing")

    for line in report.warnings + report.errors:
        print(line)

    if report.errors:
        print(f"\n{len(report.errors)} error(s). manifest.json not written.")
        return 1

    entries.sort(key=lambda e: e["order"])
    if not args.check:
        MANIFEST.write_text(json.dumps({"modules": entries}, ensure_ascii=False, indent=2) + "\n")
    chapters = sum(len(e["chapters"]) for e in entries)
    action = "checked" if args.check else "manifest.json written"
    print(f"OK: {len(entries)} modules, {chapters} chapters. {action}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
