# test2 — paraphrased question

**Question:** If I lead an IBD team, how many hours a week should I plan to spend on it?

**Expected behavior (written before running):** Answer '10-12 hours per week' (the Team Lead expectation), not the 8-10 hours for team members, citing the Info Session slides page 8. The question says 'lead a team' and 'hours a week' while the slide says 'Team Lead Expectations' and '10-12 hours/week'. Risk known before running: pdftotext puts the two slide columns on the same line, so the member and lead hours appear side by side.

**Expected source(s):** `vault/raw/IBD Info Session Spring 2026_Slides.pdf`

**Expected passage:**

> Team Member Expectations  Team Lead Expectations / 8-10 hours/week (including class time  10-12 hours/week

## Run

- mode: **ask** · execution: **local** · model: `gemma4:e2b-it-qat` · runtime: ollama 0.34.4
- network at run time: **offline** · time: 2026-09-29T22:49:33
- device: Apple M3, 16.0 GB unified (CPU+GPU shared), macOS 15.6.1
- response time: 2.62 s · 46.4 tok/s
- decided by: model · status: **cited**

## Retrieved passages (vault/raw only, top 5; used if score ≥ 2.0)

**[S1]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:65-77` (Page 7) — score 13.001 · used

> ## Page 7
> How does the IBD Program work?
> ● Oct 8: IBD application deadline
> ◦ All applicants will be considered for a team member position
> ◦ Those interested in being a team lead indicate this on the application
> ● Week of Oct 13: Review of IBD applications and selected team lead
> candidate interviews
> ● Week of Oct 27: Notification of acceptance into the IBD program
> ● Spring semester:
> ◦  All enrolled students are assigned to a project team advised by a Faculty Mentor
> ◦  Each team has 4 members (including a Team Lead) and 1 Faculty Mentor
> ◦  Teams spend last 2 weeks of May in-country

**[S2]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:78-95` (Page 8) — score 11.383 · used

> ## Page 8
> Team Member & Team Lead Expectations
> Team Member Expectations  Team Lead Expectations
> ●  8-10 hours/week (including class time  ●  10-12 hours/week
> and client calls)  ●  Effective team schedule creation and
> progress management
> ●  Timely, high quality output
> ●  Assurance of on-time completion of
> ●  Engagement throughout the semester  project tasks and assignments
> and project  ●  Best practices coaching of team
> members
> ●  Completion of all client-related tasks  ●  Effective communication with team,
> ●  Cooperation with team lead and  faculty mentor, IBD staff, and clients
> members  ●  Coordination of team travel logistics with
> IBD staff and clients
> ●  Support of team members in  ●  New this year! 1 additional unit
> improving their work products

**[S3]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:104-122` (Page 10) — score 4.646 · used

> ## Page 10
> Agriculture
> Agriculture  Healthcare  High Tech
> Clients  Financial
> Biotechnology
> come  Services
> from
> Ecotourism
> Conservation  Energy
> Hospitality
> many
> sectors  Financial Services
> Ecotourism  Education
> Energy
> Hospitality
> Education  Manufacturing
> Manufacturing  Retail
> Retail

**[S4]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:96-103` (Page 9) — score 4.311 · used

> ## Page 9
> IBD projects include diverse components
> Case  Entrepreneurial  Market  Sustainability
> Studies  Activities  Research  Plans
> Strategic  Feasibility  Financial
> Business Plans  Studies
> Plans  Assessments

**[S5]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:205-216` (Page 19) — score 4.01 · used

> ## Page 19
> How does the IBD Project Travel work?
> Overseas student travel for 2 weeks in May is a critical part of the IBD academic
> and project experience
> ●  IBD works with Berkeley Study Abroad Office to obtain campus approval for
> all IBD overseas student travel
> ●  Participants will be required to sign an IBD Code of Conduct as part of the
> application process
> ●  If IBD project travel is cancelled due to unforeseen circumstances, students
> will continue to work remotely to wrap up the project during those 2 weeks
> in May

## Actual Gemma answer

A Team Lead should plan to spend 10-12 hours per week on the IBD program, which includes class time and client calls [S2].

## Automatic checks

- expected source retrieved: `vault/raw/IBD Info Session Spring 2026_Slides.pdf` at rank 1
- cited sources: `vault/raw/IBD Info Session Spring 2026_Slides.pdf`
  [S2] vault/raw/IBD Info Session Spring 2026_Slides.pdf:78-95 (Page 8)  (word overlap 75%)
- expected behavior met (automatic): **yes**

## Manual assessment

**PARTIAL FAIL: correct number, unsupported qualifier.** Retrieval: correct, page 8 is S2 (rank 2, behind the page-7 overview). "A Team Lead should plan to spend 10-12 hours per week" is supported by [S2] (Team Lead column: "10-12 hours/week"). "…which includes class time and client calls" is **not** supported for leads: on the slide, "(including class time and client calls)" belongs to the *Team Member* column's "8-10 hours/week". Cause: `pdftotext -layout` puts both columns on one text line (`● 8-10 hours/week (including class time  ● 10-12 hours/week`), so the qualifier appears attached to both numbers. The citation points to the right slide, but the slide does not support that detail, so this counts as a misattributed claim. Same result in v1 and v2; see README §7 for the cause and proposed fix.

_Assessed by hand on 2026-09-29 against the original files in vault/raw._

Raw run record: `runs/ask/20260929-224935-test2-if-i-lead-an-ibd.md` (+ .json)
