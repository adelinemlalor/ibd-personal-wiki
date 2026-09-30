"""Saved outputs: every ask/search/chat/ingest run is written to runs/ as JSON
(machine-readable) and Markdown (human-readable). runs/ is outside the vault,
so saved answers are never retrieved as evidence."""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .config import Config


def _slug(text: str, n: int = 6) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:n]
    return "-".join(words) or "run"


def save_run(cfg: Config, kind: str, title: str, record: dict, markdown: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = cfg.path("runs_dir") / kind
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / f"{stamp}-{_slug(title)}"
    base.with_suffix(".json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    base.with_suffix(".md").write_text(markdown, encoding="utf-8")
    return base.with_suffix(".md")


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")
