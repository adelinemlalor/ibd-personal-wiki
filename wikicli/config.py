"""Load config.json and resolve every path relative to the project root."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PATH_KEYS = ("vault_dir", "raw_dir", "wiki_dir", "index_file", "catalog_file",
             "state_dir", "runs_dir", "prompts_dir")


@dataclass
class Config:
    values: dict = field(default_factory=dict)

    def __getattr__(self, name):
        try:
            return self.values[name]
        except KeyError:
            raise AttributeError(name)

    def path(self, key: str) -> Path:
        return ROOT / self.values[key]

    def prompt(self, name: str) -> str:
        """Read an instruction file from prompts/. The model never reads files itself."""
        p = self.path("prompts_dir") / name
        if not p.exists():
            raise FileNotFoundError(f"Missing instruction file: {p}")
        return p.read_text(encoding="utf-8").strip()


def load_config(path: str | None = None, overrides: dict | None = None) -> Config:
    cfg_path = Path(path) if path else ROOT / "config.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    values = json.loads(cfg_path.read_text(encoding="utf-8"))
    # Environment variables win over the file, CLI flags win over both.
    if os.environ.get("WIKI_MODEL"):
        values["model"] = os.environ["WIKI_MODEL"]
    if os.environ.get("OLLAMA_URL"):
        values["ollama_url"] = os.environ["OLLAMA_URL"]
    for k, v in (overrides or {}).items():
        if v is not None:
            values[k] = v
    return Config(values)
