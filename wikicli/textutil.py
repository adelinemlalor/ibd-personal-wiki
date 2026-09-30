"""Reading sources, tokenizing, and cleaning up note names."""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

TEXT_EXTS = {".md", ".markdown", ".txt"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS | DOCX_EXTS

STOPWORDS = set("""
a an the and or but if then else of to in on at by for with from as is are was were be been being
it its this that these those there here what which who whom whose when where why how do does did
done have has had i me my we our you your he she they them their his her not no yes so than too
very can could should would will shall may might must about into over under again also just only
any all some each other such own same more most few both between during before after above below
up down out off once further while because until against through s t don now use used using
""".split())


def read_source(path: Path) -> str:
    """Return the plain text of a source file, as Markdown-ish text with headings so
    passages keep a location: PDFs get one "## Page N" heading per page (via the local
    `pdftotext` tool); Word files keep their heading styles and bullets."""
    ext = path.suffix.lower()
    if ext in TEXT_EXTS:
        return path.read_text(encoding="utf-8", errors="replace")
    if ext in PDF_EXTS:
        exe = shutil.which("pdftotext")
        if not exe:
            raise RuntimeError(f"{path.name}: PDF support needs `pdftotext` (brew install poppler)")
        out = subprocess.run([exe, "-layout", str(path), "-"], capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(f"{path.name}: pdftotext failed: {out.stderr.strip()}")
        pages = []
        for n, page in enumerate(out.stdout.split("\f"), 1):
            lines = [re.sub(r"\s{2,}", "  ", l).strip() for l in page.splitlines()]
            body = "\n".join(l for l in lines if l)
            if body:
                pages.append(f"## Page {n}\n{body}")
        return "\n\n".join(pages)
    if ext in DOCX_EXTS:
        return _read_docx(path)
    raise RuntimeError(f"{path.name}: unsupported file type {ext}")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _read_docx(path: Path) -> str:
    """Extract paragraphs from word/document.xml with the standard library only."""
    try:
        with zipfile.ZipFile(path) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError) as e:
        raise RuntimeError(f"{path.name}: not a readable .docx ({e})")
    out = []
    for p in root.iter(f"{_W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{_W}t")).strip()
        if not text:
            continue
        style = p.find(f"{_W}pPr/{_W}pStyle")
        style = style.get(f"{_W}val", "") if style is not None else ""
        m = re.match(r"(?i)heading\s*(\d)", style)
        if m:
            out.append("#" * min(int(m.group(1)) + 1, 6) + " " + text)
        elif style.lower() == "title":
            out.append("# " + text)
        elif p.find(f"{_W}pPr/{_W}numPr") is not None:
            out.append("- " + text)
        elif _looks_like_heading(text):
            out.append("## " + text)
        else:
            out.append(text)
    return "\n".join(out)


def _looks_like_heading(text: str) -> bool:
    """Templates often fake headings with plain paragraphs: "(1) Central Strategic
    Challenge" or "TEAM CLIMATE". Treat those as section headings."""
    words = text.split()
    if re.match(r"^\(\d+\)\s+\S", text) and len(words) <= 8:
        return True
    letters = re.sub(r"[^A-Za-z]", "", text)
    return 1 <= len(words) <= 8 and len(letters) >= 4 and letters.isupper()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_id_for(path: Path) -> str:
    """Stable machine ID for a raw source: slug of the original filename.
    It lives in note properties and the catalog, never in a note's filename."""
    slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return f"src-{slug}"


def _stem(word: str) -> str:
    # Tiny suffix stripper so "embeddings"/"embedding"/"embedded" meet in the index.
    for suf in ("ations", "ation", "ings", "ing", "ies", "ied", "edly", "ed", "es", "s"):
        if len(word) > len(suf) + 3 and word.endswith(suf):
            if suf in ("ies", "ied"):
                return word[: -len(suf)] + "y"
            return word[: -len(suf)]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


_BAD_NAME_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]]')


def clean_title(raw: str, max_words: int = 6) -> str:
    """Turn a model-proposed title into a short, readable filename-safe note name."""
    t = _BAD_NAME_CHARS.sub(" ", raw or "")
    t = re.sub(r"\.(md|txt|pdf)$", "", t.strip(), flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" .-_")
    words = t.split(" ")[:max_words]
    small = {"a", "an", "and", "of", "the", "in", "on", "for", "to", "vs", "with"}
    out = []
    for i, w in enumerate(words):
        if w.isupper() and len(w) > 1:          # keep acronyms like RAG, GPU
            out.append(w)
        elif i > 0 and w.lower() in small:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out) or "Untitled Note"


def normalize_key(title: str) -> str:
    """Key used to detect that two titles name the same subject."""
    return " ".join(_stem(w) for w in re.findall(r"[a-z0-9]+", title.lower()))
