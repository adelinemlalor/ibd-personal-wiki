# Wiki review log (2026-09-29)

Each generated note was compared with its original in `vault/raw/`. Where a note was wrong or misleading, the **note** was corrected; the originals were not touched (their SHA-256 hashes still match the copies in the course folder, see [Source Catalog](../vault/Source%20Catalog.md)). The corrections were applied by [`tools/review_pass_2026-09-29.py`](../tools/review_pass_2026-09-29.py), which is kept as a record. Every reviewed note has `reviewed: true` in its properties, so a later `wiki ingest` will not overwrite it unless `--overwrite-reviewed` is passed.

## Ingestion history

| Run | What happened | Log |
|---|---|---|
| 1 | One Gemma call per slide page (26 calls for the PDF), 9.4 min. It created **5 overlapping notes about the same subject**: `IBD`, `IBD Program`, `International Business Development Program`, `General Information Session`, `IBD Program Information`. | [run1](ingest/run1-before-dedupe.txt), [index then](ingest/run1-index-before-dedupe.md) |
| 2 | Fix: pages are grouped into parts of at most 6,000 characters (2 calls for the PDF instead of 26). Candidate concepts that are just the source's own subject, or spell out its acronym, are dropped by the harness, and Gemma picks distinct subtopics from what remains. 4.3 min, 14 distinct notes. | [run2](ingest/run2-after-dedupe.txt) |
| 3 | Prompt fix: key points must be full factual sentences (run 2 produced topic labels like "IBD Program Structure"). Related-note reasons must not say "candidate". Forced re-ingest updated the notes in place. | [run3](ingest/run3-force-improved-prompts.txt) |
| — | Manual review below. | — |
| 4 | Plain re-ingest: all 3 sources unchanged, the note file list is identical. | [run4](ingest/run4-reingest-unchanged.txt) |
| 5 | Forced re-generation of the slides on a scratch copy: Gemma renamed a concept to "IBD Project Travel Costs", which **created a near-duplicate note**. | [run5](ingest/run5-forced-reingest-scratch-copy.txt) |
| 6 | Fix: a new concept name that contains (or is contained in) the name or alias of a note already linked to the same source reuses that note. Forced re-generation now leaves the file list identical, and lint passes. | [run6](ingest/run6-forced-reingest-after-fix.txt) |

## Corrections made by hand

| Note | Problem found | Fix |
|---|---|---|
| `Team Member Expectations` → **Team Roles and Expectations** | Slide 8 has two columns (members / leads). `pdftotext -layout` merges them line by line, and Gemma wrote "engagement throughout the semester project tasks and assignments" (half member, half lead) and gave members the lead's duty "effective communication with team, team lead, faculty mentor, IBD staff, and clients". The lead's 10–12 h/week was missing. | Rewrote the details from slides 7–8 with members and leads separated; renamed the note so it covers both roles. The old name is kept as an alias, so re-ingest merges into this note. |
| `International Travel Requirements`, `Travel Requirements` → **IBD Project Travel** | Three notes on one subject. One became an orphan with no source after a re-ingest. One paraphrase ("proof of vaccinations for entry visa") changed the meaning. | Merged into `IBD Project Travel` with one fact per bullet and page links (slides 18–23); old names added as aliases. |
| **IBD Program Info Session** | Key point "components such as Case, Entrepreneurial, Market, Sustainability Studies, Activities…" was garbled by the column layout of slide 9. | Rewrote it as the seven project types, reading the slide's columns. |
| All notes | Several generated related-note reasons were vague ("could be a topic for team discussion") or weak cross-topic links. | Replaced with curated links. Each reason names a connection stated in the sources, e.g. *Project Objectives and Outcomes ↔ Goal Alignment: the client's definition of success vs. the team's own measurable goals.* |
| (my own error) | While writing the travel note I first cited slides 16/18/19/20/21, one page off. | Checked each claim with a text search per page and corrected the links to 18/19/20/21/22/23. |

## Checks after review

- `./wiki lint`: 13 notes, 140 links, no broken links, bad PDF pages, heading/filename mismatches, machine-style names, duplicates, or notes without a source link. The linter was itself tested with a planted bad note (`class4-task-1-c8d92e24fd.md`), and it reported all 4 problems.
- Re-ingest: [run4](ingest/run4-reingest-unchanged.txt) (unchanged) and [run6](ingest/run6-forced-reingest-after-fix.txt) (forced) both leave the note list identical.
