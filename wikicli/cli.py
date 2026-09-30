"""Command-line entry point. Parses the command, loads config + instructions,
and hands off to the matching mode. Run `./wiki --help`."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ROOT, load_config
from .llm import LocalGemma, ModelUnavailable

DESCRIPTION = """Personal wiki CLI: local Gemma (via Ollama) + your own notes.

commands:
  ingest [PATH]        read originals in vault/raw (or PATH), generate linked notes in
                       vault/wiki, update vault/index.md, Source Catalog, retrieval index
  search "QUERY"       show matching ORIGINAL passages + file:line locations (no model)
  ask "QUESTION"       standalone factual answer from retrieved sources, with checked
                       citations, or an explicit insufficient-evidence reply
  chat                 personal assistant "Quill": conversation memory, looks up notes
                       only when a turn needs them
  status               model/runtime, memory in use, device, network, index size
  lint                 check links, headings, names, duplicates, source references
  eval                 run the 4 ask-mode tests in evals/questions.json -> evidence cards

configuration: config.json (model, Ollama URL, chunk sizes, top-k, thresholds);
instructions:  prompts/persona.md (chat), prompts/wiki-instructions.md (ask),
               prompts/chat-router.md, prompts/ingest-instructions.md
requires:      Ollama running locally (`ollama serve`) with the model pulled:
               ollama pull gemma4:e2b-it-qat   (search works without it)
outputs:       runs/<mode>/*.md|json (saved results), drafts/ (chat /save)
"""

EXAMPLES = """examples:
  ./wiki ingest vault/raw
  ./wiki search "retrieval augmented generation"
  ./wiki ask "What chunk size does the course recommend?" --mode local
  ./wiki chat
  ./wiki chat --script evals/chat_checks.txt
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki", description=DESCRIPTION, epilog=EXAMPLES,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", help="path to config.json (default: project config.json)")
    p.add_argument("--model", help="override the Ollama model tag from config.json")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    def common(sp):
        sp.add_argument("--mode", choices=["local"], default=None,
                        help="where the model runs (only 'local' is implemented; default)")

    s = sub.add_parser("ingest", help="build/update wiki notes from original sources")
    s.add_argument("path", nargs="?", default=None, help="file or folder (default: vault/raw)")
    s.add_argument("--force", action="store_true", help="regenerate notes even if the source is unchanged")
    s.add_argument("--overwrite-reviewed", action="store_true",
                   help="also regenerate notes marked `reviewed: true`")
    s.add_argument("--relink-all", action="store_true", help="recompute Related notes for every note")
    common(s)

    s = sub.add_parser("search", help="show matching original passages (no model)")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=None, help="number of passages (default from config)")
    s.add_argument("--scope", choices=["raw", "wiki", "all"], default="raw",
                   help="raw = original sources (default), wiki = generated notes, all = both")

    s = sub.add_parser("ask", help="grounded factual answer with citations")
    s.add_argument("question")
    common(s)

    s = sub.add_parser("chat", help="personal assistant with conversation context")
    s.add_argument("--script", help="read user turns from a file (one per line) instead of the keyboard")
    common(s)

    s = sub.add_parser("status", help="show model, runtime, memory, device, network, index")
    common(s)

    s = sub.add_parser("eval", help="run evals/questions.json and write evidence cards")
    s.add_argument("--only", help="run a single test id, e.g. test2")
    s.add_argument("--questions", default=str(ROOT / "evals" / "questions.json"))
    s.add_argument("--out", default=str(ROOT / "evidence" / "ask-tests"))
    common(s)

    sub.add_parser("lint", help="check wiki links, headings, names, duplicates, sources")

    sub.add_parser("help", help="show this help")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in (None, "help"):
        parser.print_help()
        return 0

    try:
        cfg = load_config(args.config, {"model": args.model, "mode": getattr(args, "mode", None)})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        if args.command == "ingest":
            from .ingest import run_ingest
            from .records import save_run
            target = Path(args.path) if args.path else cfg.path("raw_dir")
            print(f"ingest · {cfg.mode} · {cfg.model}")
            report = run_ingest(cfg, target, force=args.force, overwrite_reviewed=args.overwrite_reviewed,
                                relink_all=args.relink_all)
            save_run(cfg, "ingest", "ingest", report, "# ingest\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n")

        elif args.command == "search":
            from .modes import run_search
            run_search(cfg, args.query, args.k or cfg.search_top_k, args.scope)

        elif args.command == "ask":
            from .modes import run_ask
            run_ask(cfg, args.question)

        elif args.command == "chat":
            from .modes import run_chat
            if args.script and not Path(args.script).exists():
                raise FileNotFoundError(f"script not found: {args.script}")
            LocalGemma(cfg).status()                       # fail fast if Ollama is down
            run_chat(cfg, args.script)

        elif args.command == "status":
            from .env import device_specs, network_status
            from .retrieval import build_index
            info = {"execution": cfg.mode, "config": {k: cfg.values[k] for k in
                    ("model", "ollama_url", "num_ctx", "chunk_chars", "ask_top_k", "ask_min_score")}}
            try:
                info["runtime"] = LocalGemma(cfg).status()
            except ModelUnavailable as e:
                info["runtime"] = {"error": str(e)}
            index, _ = build_index(cfg)
            info["index"] = {"passages": len(index.passages),
                             "raw": sum(p.kind == "raw" for p in index.passages),
                             "wiki": sum(p.kind == "wiki" for p in index.passages)}
            info["device"] = device_specs()
            info["network"] = network_status()
            print(json.dumps(info, indent=2))

        elif args.command == "lint":
            from .lint import run_lint
            return run_lint(cfg)

        elif args.command == "eval":
            from .evals import run_evals
            q = Path(args.questions)
            if not q.exists():
                raise FileNotFoundError(f"questions file not found: {q}")
            run_evals(cfg, q, Path(args.out).resolve(), args.only)

    except ModelUnavailable as e:
        print(f"error: local model unavailable: {e}", file=sys.stderr)
        return 3
    except (FileNotFoundError, FileExistsError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 0
