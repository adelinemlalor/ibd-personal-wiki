"""One-off human review pass (2026-09-29). Applies corrections found by comparing the
generated notes with the original sources. Kept in the repo so the edits are traceable."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# NOTE: already applied on 2026-09-29; it deletes/renames notes, so it is a record, not meant to be re-run.
from wikicli.config import load_config
from wikicli.notes import load_notes, write_note, set_block, get_block
from wikicli.ingest import write_index, write_catalog, source_link
from wikicli.retrieval import build_index

cfg = load_config()
wiki = cfg.path("wiki_dir")
RAW = {"info": cfg.path("raw_dir") / "IBD Info Session Spring 2026_Slides.pdf",
       "quest": cfg.path("raw_dir") / "IBD Client Questionnaire.docx",
       "teams": cfg.path("raw_dir") / "Teams@Haas Collaborative Plan .docx"}
SID_INFO = "src-ibd-info-session-spring-2026-slides"
notes = {n.title: n for n in load_notes(wiki)}
p = lambda page: source_link(cfg, RAW["info"], f"Page {page}")

# 1. Merge the travel notes into IBD Project Travel -----------------------------------
travel = notes["IBD Project Travel"]
travel.props["description"] = "Two weeks of in-country project work in May, what IBD covers, and what students must arrange."
travel.props["aliases"] = ["International Travel Requirements", "Travel Requirements"]
travel.body = set_block(travel.body, f"from:{SID_INFO}", f"""### From [[IBD Program Info Session]]
- Overseas travel for 2 weeks in May is a critical part of the IBD academic and project experience; teams work on site in-country May 18–30. ({p(19)}, {p(18)})
- IBD works with the Berkeley Study Abroad Office to get campus approval for all overseas student travel, and participants sign an IBD Code of Conduct as part of the application. ({p(19)})
- If travel is cancelled, students keep working remotely to wrap up the project during those 2 weeks. ({p(19)})
- Flights and accommodations are paid by IBD and the project clients; students book flights through UC Travel and pay for in-country meals, entertainment, visas, and vaccinations. ({p(20)})
- Students must enroll in UC Travel Insurance; countries may require proof of vaccination to enter or to get an entry visa. ({p(21)})
- International students should contact the Berkeley International Office, and scholarship students should check whether their scholarship allows overseas travel, before applying. ({p(22)}, {p(23)})

Original: {source_link(cfg, RAW["info"])}""")
travel.body = travel.body.replace("# IBD Project Travel\n\nThe requirement for overseas student travel as a critical part of the academic and project experience.",
                                  "# IBD Project Travel\n\n" + travel.props["description"])
for old in ("International Travel Requirements", "Travel Requirements"):
    if old in notes:
        notes[old].path.unlink()
        del notes[old]

# 2. Replace the spliced "Team Member Expectations" note -------------------------------
old = notes.pop("Team Member Expectations")
old.path.unlink()
roles = old
roles.title = "Team Roles and Expectations"
roles.path = wiki / "Concepts" / "Team Roles and Expectations.md"
roles.props["description"] = "How IBD teams are made up and what the program expects of team members and team leads."
roles.props["aliases"] = ["Team Member Expectations", "Team Lead Expectations"]
roles.body = f"""# Team Roles and Expectations

{roles.props['description']}

## Details by source

<!-- wiki:from:{SID_INFO}:start -->
### From [[IBD Program Info Session]]
- Each team has 4 members, including a Team Lead, and 1 Faculty Mentor. ({p(7)})
- **Team members:** 8–10 hours/week including class time and client calls; timely, high-quality output; engagement throughout the semester; completing all client-related tasks; cooperating with the team lead and members; helping teammates improve their work. ({p(8)})
- **Team leads:** 10–12 hours/week; building the team schedule and managing progress; making sure tasks are done on time; coaching team members; communicating with the team, faculty mentor, IBD staff, and clients; coordinating travel logistics; new this year, 1 additional unit. ({p(8)})

Original: {source_link(cfg, RAW["info"])}
<!-- wiki:from:{SID_INFO}:end -->

## Related notes

<!-- wiki:related:start -->
<!-- wiki:related:end -->
"""

# 3. Fix the garbled key point (slide 9 is laid out in columns) ------------------------
info = notes["IBD Program Info Session"]
kp = get_block(info.body, "keypoints")
kp = "\n".join(
    f"- IBD projects include case studies, entrepreneurial activities, market research, sustainability plans, strategic business plans, feasibility studies, and financial plans and assessments. — {p(9)}"
    if l.startswith("- IBD projects include diverse components") else l for l in kp.splitlines())
info.body = set_block(info.body, "keypoints", kp)

# 4. Curated related links (each reason is a connection stated in the sources) ---------
notes["Team Roles and Expectations"] = roles
notes["IBD Project Travel"] = travel
R = {
 "IBD Program Info Session": [
   ("IBD Client Questionnaire", "IBD projects are consulting work with real international clients; the questionnaire is the program's guide for the first client conversations."),
   ("Teams@Haas Collaborative Plan", "Every IBD team (4 students and a mentor) uses this plan to agree on goals, norms, and roles.")],
 "IBD Client Questionnaire": [
   ("IBD Program Info Session", "Explains the program the questionnaire is used in: semester-long projects with real clients, then 2 weeks in-country."),
   ("Teams@Haas Collaborative Plan", "The questionnaire sets goals and success criteria with the client; the Teams@Haas plan sets them inside the team.")],
 "Teams@Haas Collaborative Plan": [
   ("Team Roles and Expectations", "The program's member and team-lead duties are the starting point for the plan's roles and responsibilities section."),
   ("IBD Client Questionnaire", "Its counterpart for the client side: the team defines its own goals here and the client's goals with the questionnaire.")],
 "Central Strategic Challenge": [
   ("Project Objectives and Outcomes", "The project objective is defined as what would get the client 'a long way toward meeting the challenge'."),
   ("Market & Industry", "The industry structure and competition are the context the challenge sits in.")],
 "Project Objectives and Outcomes": [
   ("Central Strategic Challenge", "Objectives are framed as progress toward this challenge."),
   ("Goal Alignment", "Both define success: the client's view of success here, the team's own challenging, consequential, and measurable goals there.")],
 "Market & Industry": [
   ("Customer Insights", "The criteria the industry competes on connect to why customers buy from the client instead of alternatives."),
   ("Central Strategic Challenge", "Market forces and competition shape the client's most pressing challenge.")],
 "Customer Insights": [
   ("Market & Industry", "Customer decisions are made among the competitors and offerings described in the market questions.")],
 "Goal Alignment": [
   ("Project Objectives and Outcomes", "The client-side definition of success that the team's goals should support."),
   ("Team Climate", "The team's norms are meant to support meeting these shared goals.")],
 "Team Climate": [
   ("Goal Alignment", "Norms are chosen to help the team meet the goals it agreed on."),
   ("Team Knowledge Coordination", "Climate covers norms and accountability; coordination covers the meetings, tools, and roles that put them into practice.")],
 "Team Knowledge Coordination": [
   ("Team Roles and Expectations", "The program already defines member and team-lead duties that the team's roles should reflect."),
   ("Team Climate", "Coordination practices put the team's agreed norms into daily work.")],
 "Team Roles and Expectations": [
   ("Team Knowledge Coordination", "Where the team turns these expectations into concrete roles, meeting practices, and response times."),
   ("IBD Mechanics", "How students are placed onto the 4-person teams these roles belong to.")],
 "IBD Mechanics": [
   ("Team Roles and Expectations", "What is expected of students once they are placed on a team."),
   ("IBD Project Travel", "The program timeline ends with 2 weeks of in-country work in May.")],
 "IBD Project Travel": [
   ("IBD Mechanics", "The application and team-assignment steps that come before travel, including the Code of Conduct.")],
}
for title, links in R.items():
    n = notes[title]
    n.body = set_block(n.body, "related", "\n".join(f"- [[{t}]] — {why}" for t, why in links), "Related notes")

# 5. Point any remaining links at the new names, mark everything reviewed --------------
renames = {"Team Member Expectations": "Team Roles and Expectations",
           "International Travel Requirements": "IBD Project Travel", "Travel Requirements": "IBD Project Travel"}
for n in notes.values():
    for a, b in renames.items():
        n.body = n.body.replace(f"[[{a}]]", f"[[{b}]]")
    # concept list lines that now duplicate each other
    seen, lines = set(), []
    for l in n.body.split("\n"):
        key = l.split(" — ")[0] if l.startswith("- [[") else None
        if key and key in seen and "wiki:related" not in l:
            continue
        if key:
            seen.add(key)
        lines.append(l)
    n.body = "\n".join(lines)
    n.props["reviewed"] = True
    n.props["reviewed_on"] = "2026-09-29"
    write_note(n)

all_notes = load_notes(wiki)
write_index(cfg, all_notes)
write_catalog(cfg, all_notes)
build_index(cfg, force=True)
print(len(all_notes), "notes:", ", ".join(sorted(n.title for n in all_notes)))
