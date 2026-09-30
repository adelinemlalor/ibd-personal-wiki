"""The three interaction modes. Each mode loads its own instructions and context:

  search: retrieval tool only -> original passages + locations. No model call.
  ask:    standalone RAG. Research rules + retrieved ORIGINAL sources, no chat
          history, no persona. Citations checked; weak retrieval -> insufficient evidence.
  chat:   persona + recent conversation. Retrieval is a tool the harness calls only
          when the turn needs the notes (router decides); drafts are labeled as suggestions.
"""
from __future__ import annotations

import re
import sys
import textwrap

from . import citations
from .config import Config
from .llm import LocalGemma, ModelUnavailable
from .records import now, save_run
from .retrieval import Hit, build_index

INSUFFICIENT_TEXT = ("Insufficient evidence: the wiki sources do not contain information "
                     "that answers this question.")


def _passage_block(hits: list[Hit], prefix: str) -> str:
    return "\n\n".join(
        f"[{prefix}{i}] {h.passage.location}\n<<<\n{h.passage.text}\n>>>" for i, h in enumerate(hits, 1))


def _hits_md(hits: list[Hit], prefix: str) -> str:
    out = []
    for i, h in enumerate(hits, 1):
        quoted = "\n".join("> " + l for l in h.passage.text.splitlines())
        out.append(f"**[{prefix}{i}]** `{h.passage.location}` — score {h.score}\n\n{quoted}\n")
    return "\n".join(out) or "_(no passages)_"


def _hits_json(hits: list[Hit], prefix: str) -> list[dict]:
    return [{"label": f"{prefix}{i}", "id": h.passage.id, "path": h.passage.path, "kind": h.passage.kind,
             "section": h.passage.section, "lines": [h.passage.start_line, h.passage.end_line],
             "score": h.score, "text": h.passage.text} for i, h in enumerate(hits, 1)]


# ---- search -------------------------------------------------------------------

def run_search(cfg: Config, query: str, k: int, scope: str, out=sys.stdout, save=True) -> list[Hit]:
    index, rebuilt = build_index(cfg)
    kinds = {"raw": ("raw",), "wiki": ("wiki",), "all": ("raw", "wiki")}[scope]
    hits = index.search(query, k=k, kinds=kinds)
    print(f"search · retrieval only (no model) · scope={scope} · "
          f"{len(index.passages)} passages indexed{' (rebuilt)' if rebuilt else ''}", file=out)
    if not hits:
        print("No matching passages.", file=out)
    for i, h in enumerate(hits, 1):
        print(f"\n[{i}] {h.passage.location}  score={h.score}  ({h.passage.kind})", file=out)
        print(textwrap.indent(h.passage.text, "    "), file=out)
    if save:
        md = f"# search: {query}\n\n- mode: search (no model)\n- scope: {scope}\n- time: {now()}\n\n" \
             + _hits_md(hits, "")
        path = save_run(cfg, "search", query, {"mode": "search", "query": query, "scope": scope,
                                                "time": now(), "hits": _hits_json(hits, "")}, md)
        print(f"\nsaved: {path.relative_to(cfg.path('runs_dir').parent)}", file=out)
    return hits


# ---- ask ----------------------------------------------------------------------

def run_ask(cfg: Config, question: str, out=sys.stdout, save=True, tag: str = "") -> dict:
    index, _ = build_index(cfg)
    # Evidence = original sources only. Generated wiki notes and chat are not evidence.
    hits = index.search(question, k=cfg.ask_top_k, kinds=("raw",))
    strong = [h for h in hits if h.score >= cfg.ask_min_score]
    print(f"ask · {cfg.mode} · {cfg.model} · {len(strong)} passage(s) from vault/raw "
          f"(min score {cfg.ask_min_score})", file=out)

    record = {"mode": "ask", "execution": cfg.mode, "model": cfg.model, "time": now(),
              "question": question, "retrieved": _hits_json(hits, "S"),
              "used_passages": len(strong), "min_score": cfg.ask_min_score}

    if not strong:
        # Harness-level guard: nothing relevant was found, so the model is not asked to guess.
        answer, stats, gate = INSUFFICIENT_TEXT, {}, "retrieval-threshold"
        print(answer, file=out)
    else:
        llm = LocalGemma(cfg)
        messages = [
            {"role": "system", "content": cfg.prompt("wiki-instructions.md")},
            {"role": "user", "content":
                f"SOURCES:\n\n{_passage_block(strong, 'S')}\n\nQUESTION: {question}\n\n"
                "Answer from the sources only, citing [S#] after each claim, or reply with the "
                "insufficient-evidence sentence."},
        ]
        print("", file=out)
        reply = llm.chat(messages, temperature=cfg.temperature, stream_to=out)
        answer, stats, gate = reply.text, reply.stats, "model"
        record["model"] = reply.model

    check = citations.check(answer, strong, "S")
    status = "insufficient-evidence" if check["insufficient"] else (
        "cited" if check["cited"] and not check["invalid_labels"] else "citation-problem")
    print(f"\ncitations ({status}):", file=out)
    for line in citations.summary_lines(check) or ["  (none)"]:
        print(line, file=out)
    if stats:
        print(f"time: {stats['wall_seconds']}s total, {stats.get('gen_tokens_per_sec')} tok/s", file=out)

    record.update({"answer": answer, "decided_by": gate, "status": status,
                   "citation_check": check, "stats": stats})
    if save:
        md = (f"# ask: {question}\n\n- mode: ask · execution: {cfg.mode} · model: `{record['model']}`\n"
              f"- time: {record['time']} · status: **{status}** · decided by: {gate}\n\n"
              f"## Answer\n\n{answer}\n\n## Citation check\n\n"
              + "\n".join(citations.summary_lines(check) or ["(none)"])
              + f"\n\n## Retrieved passages (top {cfg.ask_top_k}, raw sources)\n\n{_hits_md(hits, 'S')}")
        path = save_run(cfg, "ask", (tag + " " if tag else "") + question, record, md)
        record["saved"] = str(path)
        print(f"saved: {path.relative_to(cfg.path('runs_dir').parent)}", file=out)
    return record


def _wiki_topics(cfg: Config) -> str:
    """Tell the assistant what the wiki covers (note titles + one-line descriptions from
    index.md), so it can describe its real capabilities without a retrieval call."""
    index = cfg.path("index_file")
    lines = [l for l in index.read_text(encoding="utf-8").splitlines() if l.startswith("- [[")] \
        if index.exists() else []
    topics = "\n".join(re.sub(r"\[\[([^\]|]+)(\|[^\]]*)?\]\]", r"\1", l) for l in lines[:30])
    return ("## Topics in the user's wiki (titles only; ask the harness for the notes' content)\n"
            + (topics or "(the wiki is empty; suggest running `wiki ingest`)"))


# ---- chat ---------------------------------------------------------------------

NO_LOOKUP = re.compile(
    r"^\s*(hi|hey|hello|thanks|thank you|ok|okay|cool|bye)\b|what can (we|you)|help me with\??$|"
    r"who are you|your name|make (that|it|this)|shorter|longer|rewrite|rephrase|simplify|"
    r"more concise|bullet|expand on (that|it)|another version|try again|summari[sz]e (that|it)",
    re.I)

ROUTER_SCHEMA = {"type": "object",
                 "properties": {"retrieve": {"type": "boolean"}, "query": {"type": "string"}},
                 "required": ["retrieve", "query"]}

CHAT_HELP = """chat commands:
  /notes <query>   look up your notes for this question (forces retrieval)
  /search <query>  show matching original passages (no model answer)
  /save [name]     save the last reply as a draft in drafts/ (outside the vault; not evidence)
  /history         show the conversation context being sent to Gemma
  /clear           forget the conversation
  /exit            leave chat"""


class ChatSession:
    def __init__(self, cfg: Config, out=sys.stdout):
        self.cfg, self.out = cfg, out
        self.llm = LocalGemma(cfg)
        self.system = cfg.prompt("persona.md") + "\n\n" + _wiki_topics(cfg)
        self.router_rules = cfg.prompt("chat-router.md")
        self.history: list[dict] = []           # user/assistant text only; never retrieved passages
        self.log: list[dict] = []
        self.index = None

    def _recent(self) -> list[dict]:
        return self.history[-2 * self.cfg.chat_history_turns:]

    def decide(self, text: str) -> tuple[bool, str, str]:
        """Should this turn look up notes? Returns (retrieve, query, reason)."""
        if text.startswith("/notes "):
            return True, text[7:].strip(), "user asked (/notes)"
        if NO_LOOKUP.search(text):
            return False, "", "conversational / follow-up rule"
        last = next((m["content"] for m in reversed(self.history) if m["role"] == "assistant"), "")
        data = self.llm.chat_json([
            {"role": "system", "content": self.router_rules},
            {"role": "user", "content": f"PREVIOUS ASSISTANT MESSAGE (may be empty):\n{last[:600]}\n\n"
                                        f"USER MESSAGE:\n{text}"}], ROUTER_SCHEMA)
        return bool(data.get("retrieve")), (data.get("query") or text).strip(), "router (Gemma)"

    def turn(self, text: str) -> str:
        retrieve, query, reason = self.decide(text)
        hits = []
        if retrieve:
            if self.index is None:
                self.index, _ = build_index(self.cfg)
            hits = [h for h in self.index.search(query, k=self.cfg.chat_top_k)
                    if h.score >= self.cfg.ask_min_score]
        tag = f"notes: {len(hits)} passage(s) for '{query}'" if retrieve else "notes: not needed"
        print(f"  [{tag} · {reason}]", file=self.out)

        messages = [{"role": "system", "content": self.system}] + self._recent()
        if hits:
            messages.append({"role": "system", "content":
                "NOTES RETRIEVED FOR THIS TURN (cite as [N#] when you use them):\n\n"
                + _passage_block(hits, "N")})
        elif retrieve:
            messages.append({"role": "system", "content":
                "A notes lookup found nothing relevant for this turn. Say the notes don't cover it; "
                "you may offer general suggestions clearly labeled as suggestions, not facts about the user. "
                "Do not write any [N#] citations."})
        else:
            messages.append({"role": "system", "content":
                "No notes were retrieved for this turn. Do not write any [N#] citations and do not present "
                "anything as coming from the user's notes; label ideas and drafts as suggestions."})
        messages.append({"role": "user", "content": text})

        print("quill> ", end="", file=self.out)
        reply = self.llm.chat(messages, temperature=self.cfg.chat_temperature, stream_to=self.out)
        check = citations.check(reply.text, hits, "N")
        if hits:
            for line in citations.summary_lines(check):
                print(line, file=self.out)
        elif check["invalid_labels"]:
            # Harness guard: citations with no retrieved passage behind them are not evidence.
            print(f"  ! warning: reply cites {', '.join(check['invalid_labels'])} but no notes were "
                  "retrieved this turn — those citations are invalid", file=self.out)
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply.text}]
        self.log.append({"user": text, "retrieved": retrieve, "query": query, "route_reason": reason,
                         "hits": _hits_json(hits, "N"), "reply": reply.text,
                         "citation_check": check, "stats": reply.stats})
        return reply.text

    def save_transcript(self) -> str | None:
        if not self.log:
            return None
        md = [f"# chat transcript\n\n- mode: chat · execution: {self.cfg.mode} · model: `{self.cfg.model}`"
              f"\n- saved: {now()}\n"]
        for t in self.log:
            md.append(f"**you:** {t['user']}\n\n_harness: "
                      + (f"retrieved {len(t['hits'])} passage(s) for “{t['query']}” ({t['route_reason']})"
                         if t["retrieved"] else f"no notes lookup ({t['route_reason']})") + "_\n")
            for h in t["hits"]:
                md.append(f"> [{h['label']}] `{h['path']}:{h['lines'][0]}-{h['lines'][1]}`")
            md.append(f"\n**quill:** {t['reply']}\n\n---\n")
        path = save_run(self.cfg, "chat", "chat", {"mode": "chat", "model": self.cfg.model,
                                                    "turns": self.log}, "\n".join(md))
        return str(path)


def run_chat(cfg: Config, script: str | None = None, out=sys.stdout):
    session = ChatSession(cfg, out)
    print(f"chat · {cfg.mode} · {cfg.model} · persona: prompts/persona.md · /help for commands, /exit to quit",
          file=out)
    lines = None
    if script:
        with open(script, encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f if l.strip() and not l.startswith("#")]

    try:
        while True:
            if lines is not None:
                if not lines:
                    break
                text = lines.pop(0)
                print(f"\nyou> {text}", file=out)
            else:
                try:
                    text = input("\nyou> ").strip()
                except EOFError:
                    break
            if not text:
                continue
            if text in ("/exit", "/quit"):
                break
            if text == "/help":
                print(CHAT_HELP, file=out)
            elif text == "/clear":
                session.history.clear()
                print("  [conversation cleared]", file=out)
            elif text == "/history":
                for m in session._recent():
                    print(f"  {m['role']}: {m['content'][:120]}", file=out)
            elif text.startswith("/search "):
                run_search(cfg, text[8:], cfg.search_top_k, "raw", out=out)
            elif text.startswith("/save"):
                _save_draft(cfg, session, text[5:].strip(), out)
            else:
                try:
                    session.turn(text)
                except ModelUnavailable as e:
                    print(f"error: {e}", file=out)
    except KeyboardInterrupt:
        print("", file=out)
    path = session.save_transcript()
    if path:
        print(f"\ntranscript saved: {path}", file=out)


def _save_draft(cfg: Config, session: ChatSession, name: str, out):
    last = next((m["content"] for m in reversed(session.history) if m["role"] == "assistant"), None)
    if not last:
        print("  nothing to save yet", file=out)
        return
    folder = cfg.path("runs_dir").parent / "drafts"
    folder.mkdir(exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9 -]", "", name).strip() or f"Draft {now().replace(':', '-')}"
    path = folder / f"{slug}.md"
    path.write_text(f"---\ntype: draft\ngenerated_by: {cfg.model}\nsaved: {now()}\n"
                    f"note: generated in chat; not source evidence\n---\n\n{last}\n", encoding="utf-8")
    print(f"  [saved draft to {path.relative_to(cfg.path('runs_dir').parent)} — not indexed as evidence]", file=out)
