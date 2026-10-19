"""Required vs preferred, years of experience, and requirement lines no pack read."""
from careerloop import ats, sections

POSTING = """Platform Engineer

About the role
You will keep our APIs fast and safe.

Responsibilities:
- Operate REST services behind a CDN
- Write runbooks

Requirements:
- 5+ years of experience running production systems
- Strong REST and JSON skills
- PostgreSQL in production
- Terraform and Kafka at scale
- Excellent written communication

Nice to have
- GraphQL
- OAuth experience is a plus
- Experience with Go

Benefits
- Docker stipend (really)
"""


def lex(cfg):
    return ats.load_lexicon(cfg)


def test_headings_split_the_posting_into_sections():
    kinds = {ln.text: ln.kind for ln in sections.split(POSTING) if ln.text}
    assert kinds["Strong REST and JSON skills"] == "required"
    assert kinds["GraphQL"] == "preferred"
    assert kinds["Operate REST services behind a CDN"] == "responsibilities"
    assert kinds["Docker stipend (really)"] == "benefits"
    assert kinds["Platform Engineer"] == "none"


def test_a_plus_inside_a_section_reads_preferred():
    lines = sections.split("Requirements\n- SQL\n- OAuth is a plus\n- ideally TLS\n")
    kinds = {ln.text: ln.kind for ln in lines if ln.text}
    assert kinds["SQL"] == "required"
    assert kinds["OAuth is a plus"] == "preferred"
    assert kinds["ideally TLS"] == "preferred"


def test_coverage_counts_required_and_preferred_separately(cfg):
    rep = ats.coverage(POSTING, "Built REST and JSON services on PostgreSQL", "", cfg, lex(cfg))
    s = rep["sections"]
    assert s["found"] is True
    assert s["required"] == {"covered": 3, "denom": 3}        # rest, json, postgresql
    assert s["preferred"] == {"covered": 0, "denom": 2}       # graphql, oauth
    assert rep["term_sections"]["cdn"] == "responsibilities"
    assert rep["term_sections"]["rest"] == "required"          # required wins over other


def test_without_headings_sections_are_not_evaluable_not_zero(cfg):
    rep = ats.coverage("We use REST and JSON daily.", "REST", "", cfg, lex(cfg))
    assert rep["sections"] == {"found": False, "required": None, "preferred": None,
                              "responsibilities": None}


def test_years_of_experience_are_read_with_their_section():
    ys = sections.years(sections.split(POSTING))
    assert ys == [{"min": 5, "max": None, "kind": "required",
                   "text": "5+ years of experience running production systems"}]
    ys = sections.years(sections.split("Requirements\n- 3-5 years experience in security\n"
                                       "- 10 years old company\n"))
    assert [(y["min"], y["max"]) for y in ys] == [(3, 5)]


def test_requirement_lines_no_pack_read_are_listed_with_a_denominator(cfg):
    rep = ats.coverage(POSTING, "REST", "", cfg, lex(cfg))
    u = rep["unread"]
    assert u["lines"] == 8          # 5 required + 3 preferred
    assert set(u["unread"]) == {"5+ years of experience running production systems",
                                "Terraform and Kafka at scale",
                                "Excellent written communication",
                                "Experience with Go"}
    assert u["matched"] == 4


def test_check_prints_sections_years_and_not_looked_at(home, capsys):
    from careerloop import cli
    (home / "resumes").mkdir(exist_ok=True)
    (home / "resumes" / "resume.md").write_text("Built REST and JSON services on PostgreSQL\n")
    (home / "facts.md").write_text("## Held\n- REST\n- JSON\n- PostgreSQL\n")
    (home / "config.toml").write_text('[profile]\nresume = "resumes/resume.md"\nyears = "3"\n'
                                      '[ats]\npacks = ["web"]\n')
    jd = home / "jd.txt"
    jd.write_text(POSTING)
    assert cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme",
                     "--role", "Platform Engineer", "--jd", str(jd)]) == 0
    capsys.readouterr()
    slug = next((home / "roles").iterdir()).name
    cli.main(["--home", str(home), "jobs", "check", slug])
    out = capsys.readouterr().out
    assert "required 3/3 · preferred 0/2" in out
    assert "experience: asks 5+ years (required); [profile] years = 3" in out
    assert "not looked at: 4 of 8 requirement line(s) mention no skill term it knows" in out
    assert "  - Terraform and Kafka at scale" in out


def test_a_greenhouse_style_html_posting_keeps_its_sections(cfg):
    html = ("<p>We build APIs.</p><h3>Requirements</h3><ul><li>REST and JSON</li>"
            "<li>Terraform</li></ul><h3>Nice to have</h3><ul><li>GraphQL</li></ul>")
    rep = ats.coverage(ats.strip_html(html, structure=True), "REST", "", cfg, lex(cfg))
    assert rep["sections"]["required"] == {"covered": 1, "denom": 2}
    assert rep["sections"]["preferred"] == {"covered": 0, "denom": 1}
    assert rep["unread"]["unread"] == ["Terraform"]


def test_prose_posting_prints_one_not_evaluable_line(home, capsys):
    from careerloop import jobs
    from careerloop import home as H
    rep = ats.coverage("We use REST and JSON daily.", "REST", "", H.load_config(home),
                       ats.load_lexicon(H.load_config(home)))
    lines = jobs.placement_lines(H.load_config(home), rep)
    assert len(lines) == 1 and "NOT EVALUABLE" in lines[0]


def test_upskill_reports_requirement_lines_no_pack_read(demo, capsys):
    from conftest import run
    run(demo, "jobs", "discover", "--board", "fixture", "--company", "example-folio", "--intake",
        "--exclude-senior")
    for d in sorted((demo / "roles").iterdir()):
        run(demo, "jobs", "check", d.name)
    capsys.readouterr()
    run(demo, "jobs", "upskill")
    out = capsys.readouterr().out
    assert "not looked at: 2 of 5 requirement line(s) in 1 of 6 role(s) mention no skill term it knows" in out
    assert "the other 5 had no requirement lines to read" in out


def test_offer_and_perks_headings_close_the_requirements(cfg):
    lines = sections.split("Requirements:\n- SQL\nWhat We Offer:\n- Fully remote work\n"
                           "Perks & Benefits\n- Parental leave\n")
    kinds = {ln.text: ln.kind for ln in lines if ln.text}
    assert kinds["SQL"] == "required"
    assert kinds["Fully remote work"] == "benefits"
    assert kinds["Parental leave"] == "benefits"


def test_time_zones_and_board_tags_are_not_skills(cfg):
    got = ats.extract("Shift in AEST or AWST hours, GMT overlap. BI-Remote LI-Hybrid. Know REST.", lex(cfg))
    assert got == ["rest"]


# --- cue-led requirement lines, and heading gaps ---------------------------------

import pytest as _pytest

from careerloop import sections as _S


@_pytest.mark.parametrize("line", ["EXPERIENCE WITH KAFKA AND HELM IN PRODUCTION",
                                   "**Experience with Kafka and Helm in production**"])
def test_a_cue_led_requirement_line_in_capitals_or_bold_is_not_a_heading(line):
    lines = _S.split("Requirements\n- Splunk\n" + line + "\n- Sentinel\n")
    got = [ln for ln in lines if ln.text and ln.text.strip("*") == line.strip("*")]
    assert len(got) == 1 and not got[0].heading and got[0].kind == "required"
    assert [ln.kind for ln in lines if ln.text == "Sentinel"] == ["required"]


@_pytest.mark.parametrize("line", ["EXPERIENCE WITH SPLUNK AND SENTINEL IN PRODUCTION",
                                   "**Experience with Splunk and Sentinel in production**"])
def test_such_a_line_is_not_dropped_from_parts_or_not_looked_at(home, line):
    from careerloop import ats
    from careerloop import home as H
    (home / "config.toml").write_text('[ats]\npacks = ["security"]\n')
    cfg = H.load_config(home)
    lex = ats.load_lexicon(cfg)
    jd = f"Requirements\n- Incident response\n{line}\nResponsibilities\n- Triage alerts\n"
    rep = ats.coverage(jd, "", "", cfg, lex)
    non_heading = [ln for ln in jd.splitlines() if ln.strip() and ln.strip() not in ("Requirements", "Responsibilities")]
    assert sum(len(v) for v in rep["parts"].values()) == len(non_heading)
    assert any(line.strip("*") in p.strip("*") for p in rep["parts"]["required"])


@_pytest.mark.parametrize("line,kind", [("Experience", "required"), ("Preferred Qualifications", "preferred"),
                                        ("EXPERIENCE", "required"), ("**Preferred Qualifications**", "preferred"),
                                        ("QUALIFICATIONS AND EXPERIENCE", "required")])
def test_real_cue_headings_stay_headings(line, kind):
    lines = _S.split("Responsibilities\n- Triage\n" + line + "\n- Splunk\n")
    h = [ln for ln in lines if ln.heading and ln.kind == kind]
    assert len(h) == 1 and [ln.kind for ln in lines if ln.text == "Splunk"] == [kind]


@_pytest.mark.parametrize("line,kind", [
    ("Roles and Responsibilities", "responsibilities"), ("Duties and Responsibilities", "responsibilities"),
    ("What you'll be doing", "responsibilities"), ("Job Description", "responsibilities"),
    ("WHAT SUCCESS LOOKS LIKE", "responsibilities"), ("TRAVEL", "logistics"), ("Education", "required"),
    ("Compensation & Benefits", "benefits"), ("Salary and Benefits", "benefits"),
    ("Benefits at Acme", "benefits"), ("What we offer you", "benefits"), ("About Acme Corp", "company"),
])
def test_plain_heading_lines_close_the_section_above(line, kind):
    above = "Benefits\n- Health\n" if kind == "required" else "Requirements\n- Splunk\n"
    lines = _S.split(above + line + "\nSome text under it\n")
    under = [ln for ln in lines if ln.text == "Some text under it"][0]
    assert under.kind == kind, (line, under.kind)
    assert [ln for ln in lines if ln.text == line][0].heading


@_pytest.mark.parametrize("line", ["Education is a priority for us and we invest in it.",
                                   "Travel to customer sites is expected a few times a year.",
                                   "About half the team is remote"])
def test_prose_starting_with_a_new_cue_is_not_a_heading(line):
    lines = _S.split("Requirements\n- Splunk\n" + line + "\n")
    assert not [ln for ln in lines if ln.text == line][0].heading
