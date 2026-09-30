# Chat and search mode checks (offline run, 2026-09-29 22:49–22:50, Wi-Fi off)

Files: [chat-offline.md](chat-offline.md) (the transcript saved by the harness, with retrieval decisions and passages) · [search-offline.md](search-offline.md) · full terminal output in [../offline/transcript.txt](../offline/transcript.txt). Script of user turns: [evals/chat_checks.txt](../../evals/chat_checks.txt).

| Check | Expected | Actual (offline) | Result |
|---|---|---|---|
| "what can we do?" | Real capabilities, no lookup, no citations, no refusal | `[notes: not needed · conversational / follow-up rule]`. Lists drafting, planning, brainstorming, and wiki lookups; names wiki topics (*Market & Industry*, *Project Objectives and Outcomes*); asks what the user is working on. | ✅ |
| "what can you help me with?" | Same | No lookup. Lists its abilities, names *Team Roles and Expectations*, *IBD Mechanics*, *Central Strategic Challenge*, and suggests concrete starting points. | ✅ |
| Draft request: agenda for a first client meeting "using the questions from my notes" | Looks up notes; claims from notes carry `[N#]` citations | Lookup ran (4 passages). **No `[N#]` citations**, and the harness flagged "16 sentences without a citation". The agenda (meeting frequency, communication tools, roles) comes from the Teams@Haas *internal team coordination* passage, not from the client questionnaire's questions. The only questionnaire passage retrieved (N1) was its title line. | ❌ **fail** (see below) |
| "make that shorter" | Uses the conversation, no lookup | `[notes: not needed · …]`. A 4-line version of the previous agenda. | ✅ |
| Claim only in chat: "the deadline was moved to October 20" | Not treated as source evidence by ask | Quill replies "I've noted that…" (conversation only). The following standalone `wiki ask "When is the IBD application deadline?"` answers **October 8 [S1, S2]** from the slides. | ✅ boundary held |
| `wiki search "team goals success"` | Original passages + locations, no generated answer | 5 passages from `vault/raw` with `file:lines (section)` and BM25 scores; no model call. | ✅ |

## The failure, honestly

This check passed in the two online practice runs (the agenda cited `[N4]` in the last one) and failed in the offline run. The model is not deterministic at chat temperature 0.7, and the retrieval for this turn was weak:

- The router's query ("IBD client meeting agenda questions") matched the questionnaire's **title-only passage** ("IBD / Client Questionnaire Sample Questions"). It carries no content, but it scores high because every query word is in it. The passages with the actual questions ranked lower.
- With no client questions in context, Gemma built the agenda from the team-coordination passage and presented it as client-meeting content without citing it.

What the harness did right: it showed that 4 passages were retrieved and flagged every uncited sentence, so the problem is visible instead of hidden.

Improvements I would make next: (1) merge a title-only section into the section after it during chunking, so a title never becomes a passage of its own; (2) if a turn retrieved notes and the reply cites none of them, re-prompt once asking for `[N#]` labels, and otherwise mark the reply as unsupported. The ask-mode tests are unaffected. Ask uses a fixed rule set at temperature 0.2.
