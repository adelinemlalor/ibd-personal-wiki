"""`wiki eval`: run the fixed ask-mode test set in evals/questions.json and write one
evidence card per test to evidence/ask-tests/. The test file lives outside the vault,
so the answer key can never be retrieved as evidence.

Each card records: question, expected behavior and sources (written before the run),
retrieved passages with ranks, the actual Gemma answer, the automatic citation check,
model/runtime/device/network facts, and the human assessment from questions.json."""
from __future__ import annotations

import io
import json
from pathlib import Path

from . import citations
from .config import ROOT, Config
from .env import device_specs, network_status
from .llm import LocalGemma
from .modes import run_ask


def _rel(p: Path) -> str:
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if ROOT in p.parents else str(p)


def run_evals(cfg: Config, questions_file: Path, out_dir: Path, only: str | None = None, echo=print):
    tests = json.loads(questions_file.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        runtime = LocalGemma(cfg).status()
    except Exception as e:                     # still record the failure in the card
        runtime = {"error": str(e)}
    net, device = network_status(), device_specs()
    summary = []

    for t in tests:
        if only and t["id"] != only:
            continue
        echo(f"\n=== {t['id']}: {t['question']}")
        buf = io.StringIO()
        rec = run_ask(cfg, t["question"], out=buf, tag=t["id"])
        echo(buf.getvalue())

        expected = t.get("expected_sources", [])
        ranks = {src: next((i for i, h in enumerate(rec["retrieved"], 1) if h["path"] == src), None)
                 for src in expected}
        cited_paths = sorted({c["id"].split("#")[0] for c in rec["citation_check"]["cited"]})
        # Pass only if every expected source is cited and nothing outside them is cited.
        behavior_ok = (rec["status"] == "insufficient-evidence") if t.get("type") == "unsupported" \
            else (rec["status"] == "cited" and set(cited_paths) == set(expected))

        lines = [
            f"# {t['id']} — {t.get('type', '')} question", "",
            f"**Question:** {t['question']}", "",
            f"**Expected behavior (written before running):** {t.get('expected_behavior', '')}", "",
            "**Expected source(s):** " + (", ".join(f"`{s}`" for s in expected) or "none — not in the wiki"), "",
        ]
        if t.get("expected_passage"):
            lines += ["**Expected passage:**", "", "> " + t["expected_passage"].replace("\n", "\n> "), ""]
        lines += [
            "## Run", "",
            f"- mode: **ask** · execution: **{cfg.mode}** · model: `{rec['model']}` · "
            f"runtime: {runtime.get('runtime', runtime.get('error'))}",
            f"- network at run time: **{net}** · time: {rec['time']}",
            f"- device: {device['chip']}, {device['memory_gb']} GB {device['memory_type']}, {device['os']}",
            f"- response time: {rec['stats'].get('wall_seconds', 'n/a (model not called)')} s"
            + (f" · {rec['stats'].get('gen_tokens_per_sec')} tok/s" if rec["stats"] else ""),
            f"- decided by: {rec['decided_by']} · status: **{rec['status']}**", "",
            "## Retrieved passages (vault/raw only, top "
            f"{cfg.ask_top_k}; used if score ≥ {cfg.ask_min_score})", "",
        ]
        for h in rec["retrieved"]:
            used = "used" if h["score"] >= cfg.ask_min_score else "below threshold"
            lines += [f"**[{h['label']}]** `{h['path']}:{h['lines'][0]}-{h['lines'][1]}`"
                      f"{' (' + h['section'] + ')' if h['section'] else ''} — score {h['score']} · {used}", "",
                      "> " + h["text"].replace("\n", "\n> "), ""]
        if not rec["retrieved"]:
            lines += ["_(no passages matched)_", ""]
        lines += ["## Actual Gemma answer", "", rec["answer"], "",
                  "## Automatic checks", "",
                  "- expected source retrieved: " + (", ".join(
                      f"`{s}` at rank {r}" if r else f"`{s}` NOT retrieved" for s, r in ranks.items()) or "n/a"),
                  "- cited sources: " + (", ".join(f"`{p}`" for p in cited_paths) or "none"),
                  ]
        lines += ["  " + l.strip() for l in citations.summary_lines(rec["citation_check"])]
        lines += [f"- expected behavior met (automatic): **{'yes' if behavior_ok else 'NO'}**", "",
                  "## Manual assessment", "",
                  t.get("assessment") or "_PENDING — open each cited passage and check it supports every claim._",
                  "", f"Raw run record: `{_rel(rec['saved'])}` (+ .json)", ""]
        card = out_dir / f"{t['id']}.md"
        card.write_text("\n".join(lines), encoding="utf-8")
        summary.append((t["id"], rec["status"], ranks, behavior_ok, card))
        echo(f"card: {_rel(card)}")

    echo("\nsummary:")
    for tid, status, ranks, ok, card in summary:
        echo(f"  {tid}: status={status} retrieval={ranks or '-'} expected-behavior={'yes' if ok else 'NO'}")
    echo(f"network: {net}")
