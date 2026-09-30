"""The retrieval tool: split sources into passages, keep their locations, and rank
them with BM25 keyword scoring. It never calls the language model, so `wiki search`
works even when Gemma is not running.

The index lives in .wiki-state/ (outside the Obsidian vault) and is rebuilt
automatically whenever a file in vault/raw or vault/wiki changes.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import ROOT, Config
from .textutil import SUPPORTED_EXTS, read_source, tokenize

INDEX_VERSION = 2
K1, B = 1.5, 0.75


@dataclass
class Passage:
    id: str          # e.g. "vault/raw/lecture-3.md#L40-58"
    path: str        # path relative to project root
    kind: str        # "raw" (original evidence) or "wiki" (generated note)
    section: str     # nearest heading, if any
    start_line: int
    end_line: int
    text: str

    @property
    def location(self) -> str:
        where = f"{self.path}:{self.start_line}-{self.end_line}"
        return f"{where} ({self.section})" if self.section else where


@dataclass
class Hit:
    passage: Passage
    score: float


# ---- chunking -----------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*)")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_MANAGED = re.compile(r"<!-- wiki:(related|sources):start -->.*?<!-- wiki:\1:end -->", re.S)


def chunk_text(text: str, rel_path: str, kind: str, size: int, overlap: int) -> list[Passage]:
    """Split on headings first, then into ~`size`-character windows of whole lines
    with `overlap` characters carried over, so every passage keeps its section and line range."""
    if kind == "wiki":
        # Index the note body only; properties and link lists are navigation, not content.
        fm = _FRONTMATTER.match(text)
        if fm:
            text = "\n" * fm.group(0).count("\n") + text[fm.end():]
        text = _MANAGED.sub(lambda m: "\n" * m.group(0).count("\n"), text)

    lines = text.splitlines()
    sections: list[tuple[str, int, list[str]]] = []   # (heading, first line no, lines)
    heading, start, buf = "", 1, []
    for i, line in enumerate(lines, 1):
        m = _HEADING.match(line)
        if m and buf and any(l.strip() for l in buf):
            sections.append((heading, start, buf))
            heading, start, buf = m.group(2).strip(), i, [line]
        else:
            if m:
                heading = m.group(2).strip()
            buf.append(line)
    if buf:
        sections.append((heading, start, buf))

    passages = []
    for heading, first, sec_lines in sections:
        i = 0
        while i < len(sec_lines):
            j, length = i, 0
            while j < len(sec_lines) and (length < size or j == i):
                length += len(sec_lines[j]) + 1
                j += 1
            body = "\n".join(sec_lines[i:j]).strip()
            if len(tokenize(body)) >= 3:
                s, e = first + i, first + j - 1
                passages.append(Passage(f"{rel_path}#L{s}-{e}", rel_path, kind, heading, s, e, body))
            if j >= len(sec_lines):
                break
            # step back far enough to carry ~overlap characters into the next window
            back, k = 0, j
            while k > i + 1 and back < overlap:
                k -= 1
                back += len(sec_lines[k]) + 1
            i = k if k > i else j
    return passages


# ---- index --------------------------------------------------------------

def _corpus_files(cfg: Config) -> list[tuple[Path, str]]:
    files = []
    for kind, key in (("raw", "raw_dir"), ("wiki", "wiki_dir")):
        base = cfg.path(key)
        if base.exists():
            for p in sorted(base.rglob("*")):
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS and not p.name.startswith("."):
                    if kind == "wiki" and p.suffix.lower() != ".md":
                        continue
                    files.append((p, kind))
    return files


def _signature(files) -> list:
    return [[str(p.relative_to(ROOT)), p.stat().st_mtime_ns, p.stat().st_size] for p, _ in files]


class Index:
    def __init__(self, passages: list[Passage]):
        self.passages = passages
        self.tokens = [tokenize(p.section + " " + p.text) for p in passages]
        self.tf = [Counter(t) for t in self.tokens]
        self.avgdl = (sum(len(t) for t in self.tokens) / len(self.tokens)) if self.tokens else 0
        df = Counter()
        for t in self.tokens:
            df.update(set(t))
        n = len(passages)
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def search(self, query: str, k: int = 5, kinds=("raw", "wiki")) -> list[Hit]:
        q = tokenize(query)
        if not q:
            return []
        hits = []
        for p, tf, toks in zip(self.passages, self.tf, self.tokens):
            if p.kind not in kinds:
                continue
            dl = len(toks) or 1
            score = 0.0
            for w in set(q):
                f = tf.get(w)
                if f:
                    score += self.idf[w] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avgdl))
            if score > 0:
                hits.append(Hit(p, round(score, 3)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]


def build_index(cfg: Config, force: bool = False) -> tuple[Index, bool]:
    """Load the cached passage list, or rebuild it if any source/note changed.
    Returns (index, rebuilt?)."""
    state = cfg.path("state_dir")
    state.mkdir(parents=True, exist_ok=True)
    cache = state / "passages.json"
    files = _corpus_files(cfg)
    sig = _signature(files)

    if cache.exists() and not force:
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("version") == INDEX_VERSION and data.get("signature") == sig \
                and data.get("chunk_chars") == cfg.chunk_chars:
            return Index([Passage(**p) for p in data["passages"]]), False

    passages: list[Passage] = []
    for p, kind in files:
        rel = str(p.relative_to(ROOT))
        try:
            text = read_source(p)
        except RuntimeError as e:
            print(f"warning: skipped {rel}: {e}")
            continue
        passages.extend(chunk_text(text, rel, kind, cfg.chunk_chars, cfg.chunk_overlap))

    cache.write_text(json.dumps({
        "version": INDEX_VERSION, "signature": sig, "chunk_chars": cfg.chunk_chars,
        "passages": [asdict(p) for p in passages]}, indent=1), encoding="utf-8")
    return Index(passages), True
