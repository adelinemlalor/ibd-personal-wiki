"""`wiki lint`: check the vault the way a reader in Obsidian would.

- every [[link]] resolves to a note, a raw file, a heading in a Markdown file, or a real PDF page
- every note's first heading matches its filename; names are short and human-readable
- no two notes share a normalized subject name (duplicates)
- every wiki note has a source reference back to vault/raw
"""
from __future__ import annotations

import re
import subprocess
import shutil
from pathlib import Path

from .config import Config
from .notes import WIKILINK, load_notes, parse_props
from .textutil import normalize_key

MACHINE_NAME = re.compile(r"(\d{6,}|[0-9a-f]{8,}|--|_task|chunk[-_ ]?\d+|^src-)", re.I)


def _pdf_pages(path: Path) -> int | None:
    exe = shutil.which("pdfinfo")
    if not exe:
        return None
    out = subprocess.run([exe, str(path)], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", out)
    return int(m.group(1)) if m else None


def run_lint(cfg: Config, out=print) -> int:
    vault = cfg.path("vault_dir")
    notes = load_notes(cfg.path("wiki_dir"))
    by_name = {n.title.lower(): n for n in notes}
    for extra in (cfg.path("index_file"), cfg.path("catalog_file")):
        by_name[extra.stem.lower()] = None
    problems, links_checked = [], 0

    files = [p for p in vault.rglob("*.md") if ".obsidian" not in p.parts]
    for f in files:
        _, body = parse_props(f.read_text(encoding="utf-8"))
        for m in WIKILINK.finditer(body.replace("\\|", "|")):
            links_checked += 1
            full = m.group(0)[2:-2].split("|")[0]
            target, _, anchor = full.partition("#")
            target = target.strip()
            where = f"{f.relative_to(vault)}: [[{full}]]"
            if target.lower() in by_name:
                continue
            path = vault / target
            if not path.exists() and (vault / (target + ".md")).exists():
                path = vault / (target + ".md")
            if not path.exists():
                problems.append(f"broken link  {where}")
                continue
            if anchor.startswith("page="):
                pages = _pdf_pages(path)
                if pages and not (1 <= int(anchor[5:]) <= pages):
                    problems.append(f"bad page     {where} (PDF has {pages} pages)")
            elif anchor and path.suffix == ".md":
                heads = [h.strip() for h in re.findall(r"^#+\s+(.*)$", path.read_text(encoding="utf-8"), re.M)]
                if anchor.strip() not in heads:
                    problems.append(f"bad heading  {where}")

    seen = {}
    for n in notes:
        rel = n.path.relative_to(vault)
        h1 = re.search(r"^# (.+)$", n.body, re.M)
        if not h1 or h1.group(1).strip() != n.title:
            problems.append(f"heading      {rel}: first heading does not match filename")
        if len(n.title.split()) > 6 or MACHINE_NAME.search(n.title):
            problems.append(f"name         {rel}: not a short readable subject name")
        k = normalize_key(n.title)
        if k in seen:
            problems.append(f"duplicate    {rel} and {seen[k]}")
        seen[k] = rel
        if "[[raw/" not in n.body:
            problems.append(f"no source    {rel}: no link to an original in raw/")

    out(f"checked {len(notes)} notes, {len(files)} Markdown files, {links_checked} links")
    for p in problems:
        out("  " + p)
    out("OK: no problems found" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0
