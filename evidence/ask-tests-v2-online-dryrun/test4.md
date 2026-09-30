# test4 — unsupported question

**Question:** How is the IBD course graded?

**Expected behavior (written before running):** Insufficient evidence. None of the three sources mentions grades or grading (checked by text search before running). The answer must not guess a grading scheme.

**Expected source(s):** none — not in the wiki

## Run

- mode: **ask** · execution: **local** · model: `gemma4:e2b-it-qat` · runtime: ollama 0.34.4
- network at run time: **online** · time: 2026-09-29T21:52:40
- device: Apple M3, 16.0 GB unified (CPU+GPU shared), macOS 15.6.1
- response time: 1.74 s · 47.4 tok/s
- decided by: model · status: **insufficient-evidence**

## Retrieved passages (vault/raw only, top 5; used if score ≥ 2.0)

**[S1]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:56-64` (Page 6) — score 4.453 · used

> ## Page 6
> Spring 2026 IBD Program Class
> ● 3 Unit Elective FTMBA Course
> ● Remote collaboration with clients from January to early-May
> ● 2 weeks of project work overseas in late-May
> ● First year FTMBA students only
> ● 9:00 am-12:00 pm on Thursdays
> ● IBD is a No-Drop Course!

**[S2]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:27-39` (Page 4) — score 3.526 · used

> ## Page 4
> 1,800+  500+  89
> MBA  Global
> Countries
> Students  Projects
> What is IBD?
> ● Management consulting
> elective course
> ● International projects with real
> world clients
> ● Offered to MBAs at Berkeley
> Haas for 34 years!

**[S3]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:191-204` (Page 18) — score 3.211 · used

> ## Page 18
> Jan 22
> First class session, 9-12 pm
> May 7
> Last class session
> May 18-30
> What is the IBD  Teams work on site in-country. This is
> not flexible and students must be
> course schedule?  in-country the entire time
> Mid-September
> Half-day Fall Conference when teams
> present their IBD projects to
> classmates and guests

**[S4]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:147-156` (Page 14) — score 3.146 · used

> ## Page 14
> What content is covered in IBD?
> IBD course content is customized based on the project mix and includes:
> ◦ Project scope and client management tools
> ◦ Problem definition, hypothesis development and testing
> ◦ Market research and analysis, including primary research (qual and/or
> quant)
> ◦ Tools for development of GTM, strategic planning, and assessing
> product-market fit

**[S5]** `vault/raw/IBD Client Questionnaire.docx:32-36` ((6) Engagement Design: Project Timeline & Deliverables) — score 2.252 · used

> ## (6) Engagement Design: Project Timeline & Deliverables
> - How does the project / course timeline integrate into your own organizational review cycles?
> - Are there any major calendar issues within the organization that could affect our project (e.g., end of fiscal year, annual meeting, personal vacations for team members or sponsors).
> - What key deliverables will we need to support our project objectives?
> - What communications style tends to work best in this organizational culture?

## Actual Gemma answer

Insufficient evidence: the wiki sources do not contain information that answers this question.

## Automatic checks

- expected source retrieved: n/a
- cited sources: none
- expected behavior met (automatic): **yes**

## Manual assessment

_PENDING — open each cited passage and check it supports every claim._

Raw run record: `runs/ask/20260929-215242-test4-how-is-the-ibd-course.md` (+ .json)
