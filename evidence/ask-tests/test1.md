# test1 — direct question

**Question:** When is the IBD application deadline?

**Expected behavior (written before running):** Answer 'October 8' with a citation to the IBD Info Session slides (page 7 'How does the IBD Program work?' and/or the sign-up page 16).

**Expected source(s):** `vault/raw/IBD Info Session Spring 2026_Slides.pdf`

**Expected passage:**

> Oct 8: IBD application deadline

## Run

- mode: **ask** · execution: **local** · model: `gemma4:e2b-it-qat` · runtime: ollama 0.34.4
- network at run time: **offline** · time: 2026-09-29T22:49:30
- device: Apple M3, 16.0 GB unified (CPU+GPU shared), macOS 15.6.1
- response time: 2.33 s · 46.1 tok/s
- decided by: model · status: **cited**

## Retrieved passages (vault/raw only, top 5; used if score ≥ 2.0)

**[S1]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:65-77` (Page 7) — score 6.945 · used

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

**[S2]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:166-179` (Page 16) — score 3.699 · used

> ## Page 16
> How to sign up for Spring 2026 IBD?
> ◦  Mid-September: IBD application sent to all first years
> ◦  Early October:
> ○ Oct 8: Applications due; reviewed by IBD faculty and staff
> ○ Mid-month: Team lead applicant interviews
> ◦  Late October: Notification of admission to 2026 IBD program
> ◦  Be aware:
> ○ IBD is a no-drop class!
> ○ All students enrolling in the 2026 IBD program will have 333
> elective points deducted in the Spring Semester and 80 points
> deducted in the following Fall Semester for a total of 413 elective
> points

**[S3]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:205-216` (Page 19) — score 2.957 · used

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

**[S4]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:180-190` (Page 17) — score 2.797 · used

> ## Page 17
> How are students assigned to an IBD team
> and project?
> ◦ As part of the application, we ask if there are project locations you
> are not able to travel to
> ◦ Faculty mentors use this information and assign students to project
> teams based on alignment between client needs and student
> experience and interests
> ◦ All projects are revealed in class on the first class session on
> Thursday, January 22

**[S5]** `vault/raw/IBD Info Session Spring 2026_Slides.pdf:236-250` (Page 22) — score 2.797 · used

> ## Page 22
> International Students are advised
> to contact the Berkeley
> International Office (BIO) before
> completing an application for the
> Attention:  IBD program to ensure that all
> requirements can be met for
> International  international project travel in May
> Students  Please note that international
> students may have additional
> document requirements when
> traveling outside the U.S., such as
> visa, passport, re-entry or other
> requirements

## Actual Gemma answer

The IBD application deadline is October 8 [S1, S2].

## Automatic checks

- expected source retrieved: `vault/raw/IBD Info Session Spring 2026_Slides.pdf` at rank 1
- cited sources: `vault/raw/IBD Info Session Spring 2026_Slides.pdf`
  [S1] vault/raw/IBD Info Session Spring 2026_Slides.pdf:65-77 (Page 7)  (word overlap 75%)
  [S2] vault/raw/IBD Info Session Spring 2026_Slides.pdf:166-179 (Page 16)  (word overlap 75%)
- expected behavior met (automatic): **yes**

## Manual assessment

**PASS.** Retrieval: the expected slide (page 7, "● Oct 8: IBD application deadline") is S1, rank 1. Answer "October 8" is supported by both citations: [S1] page 7 says "Oct 8: IBD application deadline" and [S2] page 16 says "Oct 8: Applications due". No extra claims. (Checked by opening both passages above.)

_Assessed by hand on 2026-09-29 against the original files in vault/raw._

Raw run record: `runs/ask/20260929-224933-test1-when-is-the-ibd-application.md` (+ .json)
