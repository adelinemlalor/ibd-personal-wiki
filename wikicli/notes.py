"""Reading and writing wiki notes: properties (frontmatter) and harness-managed blocks.

The notes themselves are the source of truth. Every run rescans vault/wiki, so a
note you rename or edit in Obsidian is still found by its `source_id` / `note_key`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .textutil import normalize_key

FM_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)


@dataclass
class Note:
    path: Path
    title: str
    props: dict = field(default_factory=dict)
    body: str = ""

    @property
    def key(self) -> str:
        return normalize_key(self.title)

    @property
    def description(self) -> str:
        return self.props.get("description", "")


def parse_props(text: str) -> tuple[dict, str]:
    m = FM_RE.match(text)
    if not m:
        return {}, text
    props = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        try:
            props[k.strip()] = json.loads(v)          # we always write JSON-compatible YAML
        except json.JSONDecodeError:
            props[k.strip()] = v.strip("'\"")
    return props, text[m.end():]


def render_props(props: dict) -> str:
    lines = [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in props.items()]
    return "---\n" + "\n".join(lines) + "\n---\n"


def load_notes(wiki_dir: Path) -> list[Note]:
    notes = []
    for p in sorted(wiki_dir.rglob("*.md")):
        props, body = parse_props(p.read_text(encoding="utf-8"))
        notes.append(Note(p, p.stem, props, body))
    return notes


def write_note(note: Note):
    note.path.parent.mkdir(parents=True, exist_ok=True)
    note.path.write_text(render_props(note.props) + note.body.rstrip() + "\n", encoding="utf-8")


def set_block(body: str, name: str, content: str, heading: str | None = None) -> str:
    """Replace (or append) a block the harness owns, delimited by HTML comments,
    so re-ingestion updates it in place instead of duplicating it."""
    start, end = f"<!-- wiki:{name}:start -->", f"<!-- wiki:{name}:end -->"
    block = f"{start}\n{content.strip()}\n{end}"
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if pat.search(body):
        return pat.sub(lambda _: block, body)
    prefix = f"\n\n## {heading}\n" if heading else "\n\n"
    return body.rstrip() + prefix + block + "\n"


def get_block(body: str, name: str) -> str | None:
    m = re.search(rf"<!-- wiki:{re.escape(name)}:start -->\n?(.*?)\n?<!-- wiki:{re.escape(name)}:end -->",
                  body, re.S)
    return m.group(1) if m else None


WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK.finditer(text)]
