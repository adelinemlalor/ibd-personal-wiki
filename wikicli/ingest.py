"""`wiki ingest`: read original sources, have local Gemma extract a summary and
concepts, and write readable, linked notes into vault/wiki.

Pipeline per source (unchanged sources are skipped):
  1. split the source at headings/pages, then group into parts of <= ingest_section_chars
  2. MAP:    Gemma extracts summary / key points (tagged by section) / candidate concepts
  3. REDUCE: Gemma names the source note, picks a folder, writes a description, then
             keeps only distinct concepts (the harness first drops the source's own subject)
  4. write one source note + one note per concept (merged with existing notes)
Then, for every note touched: pick meaningful "Related notes" with a stated reason,
and rewrite index.md, the Source Catalog, and the retrieval index.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import time
from pathlib import Path

from .config import ROOT, Config
from .llm import LocalGemma
from .notes import Note, get_block, load_notes, set_block, wikilinks, write_note
from .retrieval import Index, Passage, build_index, chunk_text
from .textutil import (SUPPORTED_EXTS, _stem, clean_title, file_sha256, normalize_key,
                       read_source, source_id_for, tokenize)

SECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "concepts": {"type": "array", "items": {
            "type": "object",
            "properties": {"name": {"type": "string"},
                           "description": {"type": "string"},
                           "details": {"type": "array", "items": {"type": "string"}}},
            "required": ["name", "description", "details"]}},
    },
    "required": ["summary", "key_points", "concepts"],
}


def _source_folders(cfg) -> list[str]:
    # Concepts/ holds concept notes only; a whole source goes in a topic folder.
    return [f for f in cfg.wiki_folders if f != "Concepts"] or cfg.wiki_folders


def _source_schema(folders):
    return {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "folder": {"type": "string", "enum": folders},
            "description": {"type": "string"},
            "summary": {"type": "string"},
        },
        "required": ["title", "folder", "description", "summary"],
    }


def _related_schema(candidates):
    # Reason first, score second: a small model rates more sensibly after explaining.
    return {
        "type": "object",
        "properties": {"judgments": {"type": "array", "items": {
            "type": "object",
            "properties": {"title": {"type": "string", "enum": candidates},
                           "shared_subject": {"type": "string"},
                           "strength": {"type": "integer", "minimum": 0, "maximum": 3}},
            "required": ["title", "shared_subject", "strength"]}}},
        "required": ["judgments"],
    }

MIN_LINK_STRENGTH = 2


# ---- links back to the original evidence ------------------------------------

def _vault_rel(cfg: Config, path: Path) -> str:
    return str(path.relative_to(cfg.path("vault_dir")))


def source_link(cfg: Config, raw_path: Path, heading: str = "") -> str:
    """Obsidian link to the original file, down to the heading when it is Markdown."""
    rel = _vault_rel(cfg, raw_path)
    if raw_path.suffix.lower() == ".md":
        target = rel[:-3]
        h = re.sub(r"[#\[\]|^]", " ", heading).strip()
        if h:
            return f"[[{target}#{h}|{raw_path.name} § {h}]]"
        return f"[[{target}|{raw_path.name}]]"
    m = re.match(r"Page (\d+)$", heading or "")
    if raw_path.suffix.lower() == ".pdf" and m:              # Obsidian opens PDFs at a page
        return f"[[{rel}#page={m.group(1)}|{raw_path.name} p.{m.group(1)}]]"
    return f"[[{rel}|{raw_path.name}]]"


# ---- model calls -------------------------------------------------------------

GENERIC_WORDS = {"program", "programme", "session", "general", "information", "info", "overview",
                 "introduction", "intro", "document", "notes", "note", "plan", "template", "tool",
                 "course", "class", "structure", "sample", "question", "questionnaire", "slide"}


def _is_source_subject(name: str, title: str, file_name: str) -> bool:
    """True if a proposed concept is just the source's own subject: its words are all in
    the source title/file name (plus generic words), or it spells out an acronym there
    ("International Business Development Program" for "IBD")."""
    words = set(tokenize(name))
    base = set(tokenize(title + " " + file_name)) | {_stem(w) for w in GENERIC_WORDS}
    if words and words <= base:
        return True
    acronyms = {w for w in re.findall(r"\b[A-Z]{2,}\b", title + " " + file_name)}
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", name)).upper()
    return any(initials.startswith(a) for a in acronyms)


def _windows(sections, limit):
    """Group consecutive heading-sections (e.g. slide pages) into windows of <= limit
    characters, so Gemma sees enough context per call and makes fewer calls."""
    groups, cur, size = [], [], 0
    for sec in sections:
        if cur and size + len(sec.text) > limit:
            groups.append(cur)
            cur, size = [], 0
        cur.append(sec)
        size += len(sec.text) + 2
    if cur:
        groups.append(cur)
    return groups


def _window_schema(headings):
    kp = {"type": "object", "properties": {"point": {"type": "string"}}, "required": ["point"]}
    if headings:
        kp["properties"]["section"] = {"type": "string", "enum": headings}
        kp["required"].append("section")
    schema = json.loads(json.dumps(SECTION_SCHEMA))
    schema["properties"]["key_points"] = {"type": "array", "items": kp}
    return schema


def _extract(cfg: Config, llm: LocalGemma, src: Path, text: str, log) -> dict:
    rules = cfg.prompt("ingest-instructions.md")
    rel = str(src.relative_to(ROOT))
    sections = chunk_text(text, rel, "raw", cfg.ingest_section_chars, 0)
    windows = _windows(sections, cfg.ingest_section_chars)
    log(f"  {len(text)} chars -> {len(sections)} section(s) -> {len(windows)} Gemma call(s) "
        f"of <= {cfg.ingest_section_chars} chars")

    # MAP: summary, key points (tagged with their section/page) and candidate concepts.
    mapped, key_points = [], []
    for i, win in enumerate(windows, 1):
        t0 = time.time()
        headings = list(dict.fromkeys(s.section for s in win if s.section))
        body = "\n\n".join(s.text for s in win)
        data = llm.chat_json([
            {"role": "system", "content": rules},
            {"role": "user", "content":
                f"SOURCE FILE: {src.name}\nPART {i}/{len(windows)} "
                f"(lines {win[0].start_line}-{win[-1].end_line})\n\n<<<\n{body}\n>>>\n\n"
                f"Extract a 2-3 sentence summary of this part, 3-6 key points (each one a complete "
                f"sentence stating a specific fact, number, date, or instruction from the text, tagged "
                f"with the section heading it comes from), and at most {cfg.max_concepts_per_source} important "
                f"concepts. Use only this text."},
        ], _window_schema(headings))
        by_heading = {s.section: s for s in win}
        for kp in data.get("key_points", []):
            point = kp.get("point", "").strip() if isinstance(kp, dict) else str(kp).strip()
            sec = by_heading.get(kp.get("section") if isinstance(kp, dict) else None, win[0])
            if point:
                key_points.append((point, sec))
        mapped.append(data)
        log(f"  part {i}: {len(data.get('concepts', []))} concept(s) in {time.time() - t0:.1f}s")

    # REDUCE 1: name the whole source.
    digest = "\n".join(f"- {m['summary']}" for m in mapped)
    meta = llm.chat_json([
        {"role": "system", "content": rules},
        {"role": "user", "content":
            f"SOURCE FILE: {src.name}\nSummaries of its parts:\n{digest}\n\n"
            f"Name this source's wiki note (2-5 words, subject name, no file name, no dates), "
            f"choose a folder from {_source_folders(cfg)}, write a one-sentence description, and a "
            f"3-5 sentence summary of the whole source. Use only the summaries above."},
    ], _source_schema(_source_folders(cfg)))
    # "Pacman Project Notes" -> "Pacman Project": the folder already says what kind of note it is.
    meta["title"] = re.sub(r"\s+(notes?|summary|overview|information|structure)$", "",
                           meta["title"].strip(), flags=re.I)

    # Merge candidate concepts by normalized name; drop ones that are the source itself.
    concepts: dict[str, dict] = {}
    for m in mapped:
        for c in m.get("concepts", []):
            name = clean_title(c.get("name", ""), max_words=5)
            key = normalize_key(name)
            if not key or _is_source_subject(name, meta["title"], src.stem):
                continue
            entry = concepts.setdefault(key, {"name": name, "description": c.get("description", "").strip(),
                                              "details": [], "hits": 0})
            entry["hits"] += 1
            for d in c.get("details", []):
                if d.strip() and d.strip() not in entry["details"]:
                    entry["details"].append(d.strip())

    # REDUCE 2: let Gemma keep only distinct subtopics (merging near-synonyms).
    chosen = []
    if len(concepts) > 1:
        cands = sorted(concepts.values(), key=lambda c: -c["hits"])[:12]
        listing = "\n".join(f"- {c['name']}: {c['description']}" for c in cands)
        try:
            pick = llm.chat_json([
                {"role": "system", "content": rules},
                {"role": "user", "content":
                    f"SOURCE NOTE: {meta['title']} — {meta['description']}\n\nCANDIDATE CONCEPTS:\n{listing}\n\n"
                    f"Choose at most {cfg.max_concepts_per_source} candidates that are distinct, important "
                    f"subtopics of this source and deserve their own note. Skip candidates that are the "
                    f"source's own subject, near-duplicates of another candidate, or trivial details."},
            ], {"type": "object", "properties": {"keep": {"type": "array", "items": {
                "type": "string", "enum": [c["name"] for c in cands]}}}, "required": ["keep"]})
            chosen = [concepts[normalize_key(n)] for n in dict.fromkeys(pick.get("keep", []))]
        except ValueError as e:
            log(f"  warning: concept selection failed ({e}); using most frequent")
    if not chosen:
        chosen = sorted(concepts.values(), key=lambda c: -c["hits"])
    meta["concepts"] = chosen[: cfg.max_concepts_per_source]
    meta["key_points"] = key_points
    log(f"  concepts kept: {', '.join(c['name'] for c in meta['concepts']) or '(none)'}")
    return meta


# ---- note writing ------------------------------------------------------------

def _unique_path(cfg: Config, folder: str, title: str, notes: list[Note], own_sid: str) -> tuple[str, Path]:
    """Readable filename; if another subject already has it, add a short qualifier."""
    wiki = cfg.path("wiki_dir")
    taken = {n.key: n for n in notes}
    t = title
    clash = taken.get(normalize_key(t))
    if clash and clash.props.get("source_id") not in (None, own_sid):
        t = f"{title} - {folder}"
    return t, wiki / folder / f"{t}.md"


def _write_source_note(cfg, src, sid, sha, meta, model, existing: Note | None, notes) -> Note:
    if existing:                                   # keep the established name and place
        title, path = existing.title, existing.path
    else:
        title = clean_title(meta["title"], max_words=6)
        title, path = _unique_path(cfg, meta["folder"], title, notes, sid)

    key_points = "\n".join(f"- {kp.strip()} — {source_link(cfg, src, sec.section)}"
                           for kp, sec in meta["key_points"]) or "- (none extracted)"
    concept_lines = "\n".join(f"- [[{c['name']}]] — {c['description']}" for c in meta["concepts"]) \
        or "- (no separate concept notes)"
    related = (get_block(existing.body, "related") if existing else None) or "- (not linked yet)"
    body = (
        f"# {title}\n\n{meta['description'].strip()}\n\n"
        f"## Summary\n\n{meta['summary'].strip()}\n\n"
        f"## Key points\n\n<!-- wiki:keypoints:start -->\n{key_points}\n<!-- wiki:keypoints:end -->\n\n"
        f"## Concepts in this source\n\n<!-- wiki:concepts:start -->\n{concept_lines}\n<!-- wiki:concepts:end -->\n\n"
        f"## Related notes\n\n<!-- wiki:related:start -->\n{related}\n<!-- wiki:related:end -->\n\n"
        f"## Source\n\n<!-- wiki:sources:start -->\n"
        f"- Original: {source_link(cfg, src)} (`{sid}`, sha256 `{sha[:12]}`)\n"
        f"- Listed in the [[Source Catalog]]\n<!-- wiki:sources:end -->\n"
    )
    props = {
        "type": "source-note",
        "description": meta["description"].strip(),
        "source_id": sid,
        "source_path": _vault_rel(cfg, src),
        "source_sha256": sha,
        "generated_by": model,
        "ingested": dt.date.today().isoformat(),
        "reviewed": existing.props.get("reviewed", False) if existing else False,
        "tags": ["source-note"],
    }
    note = Note(path, title, props, body)
    write_note(note)
    return note


def _write_concept(cfg, concept, src, sid, source_title, model, notes: list[Note]) -> tuple[Note, bool]:
    """Create a concept note, or merge this source's details into an existing note
    about the same subject (matched by normalized title or alias)."""
    key = normalize_key(concept["name"])
    match = None
    for n in notes:
        aliases = [normalize_key(a) for a in n.props.get("aliases", [])]
        if n.key == key or key in aliases:
            match = n
            break
    if match is None:
        # Gemma may rename a concept between runs ("IBD Project Travel" -> "IBD Project Travel
        # Costs"). If one name contains the other and the note already has this source, reuse it.
        words = set(key.split())
        for n in notes:
            if sid not in (n.props.get("source_ids") or []):
                continue
            for other in [n.key] + [normalize_key(a) for a in n.props.get("aliases", [])]:
                ow = set(other.split())
                if len(ow) >= 2 and len(words) >= 2 and (ow <= words or words <= ow):
                    match = n
                    break
            if match:
                break

    details = "\n".join(f"- {d}" for d in concept["details"][:5]) or f"- {concept['description']}"
    block = f"### From [[{source_title}]]\n{details}\n\nOriginal: {source_link(cfg, src)}"

    if match is None:
        title = concept["name"]
        path = cfg.path("wiki_dir") / "Concepts" / f"{title}.md"
        body = (f"# {title}\n\n{concept['description'].strip()}\n\n## Details by source\n\n"
                f"<!-- wiki:from:{sid}:start -->\n{block}\n<!-- wiki:from:{sid}:end -->\n\n"
                f"## Related notes\n\n<!-- wiki:related:start -->\n- (not linked yet)\n<!-- wiki:related:end -->\n")
        props = {"type": "concept", "description": concept["description"].strip(),
                 "source_ids": [sid], "generated_by": model,
                 "ingested": dt.date.today().isoformat(), "reviewed": False, "tags": ["concept"]}
        note = Note(path, title, props, body)
        created = True
    else:
        note, created = match, False
        name = f"from:{sid}"
        if get_block(note.body, name) is not None:
            note.body = set_block(note.body, name, block)
        else:                                        # insert before Related notes
            new = f"<!-- wiki:{name}:start -->\n{block}\n<!-- wiki:{name}:end -->\n\n"
            if "## Related notes" in note.body:
                note.body = note.body.replace("## Related notes", new + "## Related notes", 1)
            else:
                note.body = note.body.rstrip() + "\n\n" + new
        ids = note.props.get("source_ids") or ([note.props["source_id"]] if note.props.get("source_id") else [])
        if sid not in ids:
            ids.append(sid)
        if note.props.get("type") == "concept":
            note.props["source_ids"] = ids

    # Sources list at the bottom is always rebuilt from the per-source blocks.
    srcs = re.findall(r"<!-- wiki:from:(src-[^:]+):start -->.*?Original: (.*?)\n", note.body + "\n", re.S)
    lines = "\n".join(f"- {link} (`{s}`)" for s, link in srcs)
    if note.props.get("type") == "concept":
        note.body = set_block(note.body, "sources", lines + "\n- Listed in the [[Source Catalog]]", "Sources")
    write_note(note)
    return note, created


def _tidy_reason(text: str) -> str:
    text = re.sub(r"\b[Tt]his candidate\b", "It", text.strip())
    return re.sub(r"\s*(the )?'?([^']+)'? candidate", r" \2", text)


def _relink(cfg: Config, llm: LocalGemma, scope: list[Note], all_notes: list[Note], log):
    """For each note, show Gemma the 5 most similar notes (BM25 over title, description,
    body) and let it keep only the genuinely related ones, each with a reason."""
    passages = [Passage(n.title, str(n.path), "wiki", n.title, 0, 0,
                        f"{n.title} {n.description} {n.body[:3000]}") for n in all_notes]
    idx = Index(passages)
    by_title = {n.title: n for n in all_notes}
    for note in scope:
        if note.props.get("reviewed"):
            continue                     # human-curated links are kept as they are
        # Notes already linked in the body (e.g. source <-> its concepts) are not repeated.
        body_wo = re.sub(r"<!-- wiki:related:start -->.*?<!-- wiki:related:end -->", "", note.body, flags=re.S)
        already = set(wikilinks(body_wo))
        hits = idx.search(f"{note.title} {note.description} {note.body[:1500]}", k=12)
        hits = [h for h in hits if h.passage.id != note.title and h.passage.id not in already]
        # Only candidates that share real vocabulary with this note (>= 40% of the best match).
        top = hits[0].score if hits else 0
        cands = [h.passage.id for h in hits if h.score >= max(0.4 * top, 1.0)][:5]
        if not cands:
            lines = "- (no closely related notes yet)"
        else:
            listing = "\n".join(f"- {t}: {by_title[t].description}" for t in cands)
            try:
                data = llm.chat_json([
                    {"role": "system", "content": "You connect notes in a personal wiki."},
                    {"role": "user", "content":
                        f"NOTE: {note.title} — {note.description}\n\nCANDIDATES:\n{listing}\n\n"
                        "For each candidate, first write the concrete subject it shares with the note "
                        "in one sentence (or 'nothing'), then rate the connection strength: 0 = different "
                        "topics, 1 = loosely related, 2 = clearly related, 3 = one directly builds on or "
                        "is part of the other. Write the shared subject as a plain statement about the two "
                        "notes (never call them 'candidate')."},
                ], _related_schema(cands))
                chosen = sorted((j for j in data.get("judgments", [])
                                 if j.get("title") in by_title and j.get("strength", 0) >= MIN_LINK_STRENGTH),
                                key=lambda j: -j["strength"])[:3]
            except ValueError as e:
                log(f"  warning: relink failed for {note.title}: {e}")
                chosen = []
            lines = "\n".join(f"- [[{r['title']}]] — {_tidy_reason(r['shared_subject'])}" for r in chosen) \
                or "- (no closely related notes yet)"
        note.body = set_block(note.body, "related", lines, "Related notes")
        write_note(note)
        log(f"  related for {note.title}: {lines.count('[[')} link(s)")


def write_index(cfg: Config, notes: list[Note]):
    groups: dict[str, list[Note]] = {}
    wiki = cfg.path("wiki_dir")
    for n in notes:
        folder = n.path.parent.relative_to(wiki).as_posix() or "Other"
        groups.setdefault(folder, []).append(n)
    parts = ["# Personal Wiki Index", "",
             "Start here. Notes are grouped by topic folder; each source note links to its concepts, "
             "related notes, and the original file in `raw/`. See the [[Source Catalog]] for every "
             "original source and the notes generated from it.", ""]
    for folder in [f for f in cfg.wiki_folders if f in groups] + sorted(set(groups) - set(cfg.wiki_folders)):
        parts.append(f"## {folder}\n")
        for n in sorted(groups[folder], key=lambda n: n.title.lower()):
            parts.append(f"- [[{n.title}]] — {n.description}")
        parts.append("")
    cfg.path("index_file").write_text("\n".join(parts), encoding="utf-8")


def write_catalog(cfg: Config, notes: list[Note]):
    raw = cfg.path("raw_dir")
    rows = ["# Source Catalog", "",
            "Original files are kept unchanged in `raw/`. The `source_id` is the machine ID stored "
            "in each note's properties; note filenames are readable subject names.", "",
            "| Original file | source_id | sha256 | Source note | Concept notes |",
            "|---|---|---|---|---|"]
    for src in sorted(p for p in raw.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS):
        sid = source_id_for(src)
        owner = next((n for n in notes if n.props.get("source_id") == sid), None)
        concepts = [n for n in notes if sid in (n.props.get("source_ids") or [])]
        # "|" inside a wikilink alias must be escaped in a Markdown table cell
        rows.append(f"| {source_link(cfg, src).replace('|', chr(92) + '|')} | `{sid}` | `{file_sha256(src)[:12]}` | "
                    f"{f'[[{owner.title}]]' if owner else '(not ingested)'} | "
                    f"{', '.join(f'[[{c.title}]]' for c in concepts) or '—'} |")
    cfg.path("catalog_file").write_text("\n".join(rows) + "\n", encoding="utf-8")


# ---- entry point -------------------------------------------------------------

def run_ingest(cfg: Config, target: Path, *, force=False, overwrite_reviewed=False,
               relink_all=False, log=print) -> dict:
    raw_dir = cfg.path("raw_dir").resolve()
    target = target.resolve()
    if not target.exists():
        raise FileNotFoundError(f"No such file or folder: {target}")

    if target.is_dir():
        files = sorted(p for p in target.rglob("*") if p.is_file()
                       and p.suffix.lower() in SUPPORTED_EXTS and not p.name.startswith("."))
    else:
        files = [target]
    if not files:
        raise FileNotFoundError(f"No .md, .txt or .pdf sources found in {target}")

    # Originals must live, unchanged, in vault/raw. Copy anything given from elsewhere.
    staged = []
    for f in files:
        if raw_dir not in f.parents:
            dest = raw_dir / f.name
            if dest.exists() and file_sha256(dest) != file_sha256(f):
                raise FileExistsError(f"{dest} already exists with different content; rename one of them")
            if not dest.exists():
                shutil.copy2(f, dest)
                log(f"copied original {f.name} -> {dest.relative_to(ROOT)}")
            f = dest
        staged.append(f)

    llm = LocalGemma(cfg)
    notes = load_notes(cfg.path("wiki_dir"))
    touched: dict[str, Note] = {}
    report = {"model": cfg.model, "started": dt.datetime.now().isoformat(timespec="seconds"), "sources": []}
    t_all = time.time()

    for src in staged:
        sid, sha = source_id_for(src), file_sha256(src)
        existing = next((n for n in notes if n.props.get("source_id") == sid
                         and n.props.get("type") == "source-note"), None)
        rel = str(src.relative_to(ROOT))
        if existing and existing.props.get("source_sha256") == sha and not force:
            log(f"= {rel}: unchanged, keeping [[{existing.title}]]")
            report["sources"].append({"source": rel, "status": "unchanged", "note": existing.title})
            continue
        if existing and existing.props.get("reviewed") and not overwrite_reviewed:
            log(f"! {rel}: note [[{existing.title}]] is marked reviewed; use --overwrite-reviewed to regenerate")
            report["sources"].append({"source": rel, "status": "skipped-reviewed", "note": existing.title})
            continue

        log(f"+ {rel} ({'update' if existing else 'new'})")
        t0 = time.time()
        text = read_source(src)
        meta = _extract(cfg, llm, src, text, log)
        note = _write_source_note(cfg, src, sid, sha, meta, cfg.model, existing, notes)
        if not existing:
            notes.append(note)
        touched[note.title] = note
        concept_titles = []
        for c in meta["concepts"]:
            cnote, created = _write_concept(cfg, c, src, sid, note.title, cfg.model, notes)
            if created:
                notes.append(cnote)
            touched[cnote.title] = cnote
            concept_titles.append(cnote.title)
        # A re-ingested source may no longer mention a concept: drop its stale block there.
        for other in notes:
            if other.title in concept_titles or get_block(other.body, f"from:{sid}") is None:
                continue
            other.body = re.sub(rf"<!-- wiki:from:{re.escape(sid)}:start -->.*?"
                                rf"<!-- wiki:from:{re.escape(sid)}:end -->\n*", "", other.body, flags=re.S)
            other.props["source_ids"] = [s for s in other.props.get("source_ids", []) if s != sid]
            write_note(other)
            if not other.props["source_ids"]:
                log(f"  note [[{other.title}]] no longer has any source; review or delete it")
        # Keep the source note's concept list pointing at the real (possibly merged) titles.
        note.body = set_block(note.body, "concepts", "\n".join(
            f"- [[{t}]] — {c['description']}" for t, c in zip(concept_titles, meta["concepts"])) or
            "- (no separate concept notes)")
        write_note(note)
        secs = round(time.time() - t0, 1)
        log(f"  wrote [[{note.title}]] + {len(concept_titles)} concept note(s) in {secs}s")
        report["sources"].append({"source": rel, "status": "ingested", "note": note.title,
                                  "concepts": concept_titles, "seconds": secs})

    notes = load_notes(cfg.path("wiki_dir"))              # re-read what is on disk now
    scope = notes if relink_all else [n for n in notes if n.title in touched]
    if scope:
        log(f"linking related notes for {len(scope)} note(s)")
        _relink(cfg, llm, scope, notes, log)
        notes = load_notes(cfg.path("wiki_dir"))
    write_index(cfg, notes)
    write_catalog(cfg, notes)
    index, _ = build_index(cfg, force=True)
    report.update({"seconds": round(time.time() - t_all, 1), "notes_total": len(notes),
                   "passages_indexed": len(index.passages)})
    log(f"index.md, Source Catalog and retrieval index updated "
        f"({len(notes)} notes, {len(index.passages)} passages) in {report['seconds']}s")
    return report
