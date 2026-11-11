"""`jobs prep`, `jobs research` and `jobs email`: built from the posting, facts.md, the coverage report,
the story bank and [profile]; nothing fixed in the tool.

Each is checked by changing one input and watching the output follow it: a different posting, a skill
moved into ## Held, a story that names a posting's term, a missing name, a stale check, a filled file.
"""
import pytest

from kenloop import cli
from kenloop.career import apply as A
from kenloop.career import config as CC
from kenloop.core.errors import NotEvaluable, Refused

POSTING = """## About Acme
Acme protects hospitals from ransomware.

## What you'll do
- Triage alerts in Splunk
- Lead incident response for clinical systems

## Requirements
- Splunk
- Incident response
- KQL

## Nice to have
- Sigma rules

## Benefits
- Unlimited PTO
"""

OTHER = """## About Globex
Globex builds cloud payroll software.

## What you'll do
- Harden AWS accounts and review IAM policies

## Requirements
- AWS
- Terraform
- Splunk
"""

FACTS = ("## Held\n- Splunk: built 40 dashboards for a 3-person SOC (2024)\n"
         "- Incident response: led 12 ransomware cases end to end\n\n## Learning\n- KQL (course in progress)\n")

BANK = """# Stories

### Ransomware night [ENG]
Led incident response on a hospital ransomware case; contained in four hours.

### Dashboards that stuck
Built Splunk dashboards the whole SOC used.

### Fixing the printer
Nothing security about it.
"""


def setup(home, posting=POSTING, company="Acme", role="SOC Analyst", profile='name = "Jane Doe"\n'):
    (home / "config.toml").write_text(f'[profile]\nresume = "resumes/resume.md"\n{profile}[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink(missing_ok=True)
    (home / "resumes").mkdir(exist_ok=True)
    (home / "resumes" / "resume.md").write_text("SOC analyst. Splunk. Incident response.\n")
    (home / "facts.md").write_text(FACTS)
    (home / "jd.txt").write_text(posting)
    assert cli.main(["--home", str(home), "jobs", "intake", "--company", company, "--role", role,
                     "--jd", str(home / "jd.txt")]) == 0
    slug = f"{company}-{role}".lower().replace(" ", "-")
    assert cli.main(["--home", str(home), "jobs", "check", slug]) in (0, 1)
    return slug


def read(home, slug, name):
    return (home / "roles" / slug / name).read_text()


def cfg_of(home):
    return CC.load(home)


def test_prep_follows_the_posting(home):
    a = setup(home)
    b = setup(home, posting=OTHER, company="Globex", role="Cloud Engineer")
    A.prep(cfg_of(home), a)
    A.prep(cfg_of(home), b)
    pa, pb = read(home, a, "prep.md"), read(home, b, "prep.md")
    assert "Triage alerts in Splunk" in pa and "Triage alerts" not in pb
    assert "Harden AWS accounts" in pb and "Harden AWS" not in pa
    assert "- kql: NOT HELD" in pa and "kql" not in pb
    assert "- aws: NOT HELD" in pb


def test_held_terms_quote_the_facts_line_and_unheld_ones_say_not_held(home):
    slug = setup(home)
    A.prep(cfg_of(home), slug)
    p = read(home, slug, "prep.md")
    assert '- splunk: say "Splunk: built 40 dashboards for a 3-person SOC (2024)"' in p
    assert "- kql: NOT HELD (bridge, never claim)" in p
    # KQL moves into ## Held: after a fresh check the same command says it, with the line
    (home / "facts.md").write_text(FACTS.replace("## Learning\n- KQL (course in progress)\n", "")
                                   + "## Held\n- KQL: wrote 30 hunting queries in Sentinel (2025)\n")
    with pytest.raises(NotEvaluable, match="stale"):
        A.prep(cfg_of(home), slug, force=True)
    assert cli.main(["--home", str(home), "jobs", "check", slug]) in (0, 1)
    A.prep(cfg_of(home), slug, force=True)
    assert '- kql: say "KQL: wrote 30 hunting queries in Sentinel (2025)"' in read(home, slug, "prep.md")


def test_every_command_needs_a_fresh_check(home):
    slug = setup(home)
    (home / "roles" / slug / "jd.txt").write_text(OTHER)                    # the posting changed after the check
    for run in (A.prep, A.research, A.email):
        with pytest.raises(NotEvaluable, match="stale"):
            run(cfg_of(home), slug)
    assert not any((home / "roles" / slug / n).exists() for n in ("prep.md", "research.md", "email.md"))


def test_stories_are_matched_by_the_terms_they_name(home):
    slug = setup(home, profile='name = "Jane Doe"\nstories = "stories.md"\n')
    (home / "stories.md").write_text(BANK)
    A.prep(cfg_of(home), slug)
    p = read(home, slug, "prep.md")
    assert "- Ransomware night: names incident response" in p          # the [ENG] tag is not part of the title
    assert "- Dashboards that stuck: names splunk" in p
    assert "Fixing the printer" not in p and "1 other story name nothing" in p
    order = p.index("Ransomware night"), p.index("Dashboards that stuck")
    assert order[0] != order[1]


def test_no_story_bank_is_said_and_a_missing_one_is_not_evaluable(home):
    slug = setup(home)
    A.prep(cfg_of(home), slug)
    assert "no story bank: set `[profile] stories`" in read(home, slug, "prep.md")
    setup(home, profile='name = "Jane Doe"\nstories = "nope.md"\n')
    with pytest.raises(NotEvaluable, match="nope.md"):
        A.prep(cfg_of(home), slug, force=True)


def test_prep_reads_research_and_names_its_open_sections(home):
    slug = setup(home)
    A.prep(cfg_of(home), slug)
    assert "No research.md yet" in read(home, slug, "prep.md")
    A.research(cfg_of(home), slug)
    A.prep(cfg_of(home), slug, force=True)
    p = read(home, slug, "prep.md")
    assert "still open: Size, stage and ownership, Recent news, Who interviews, Culture and tone" in p
    assert "Acme protects hospitals from ransomware." in p


def test_research_carries_the_company_text_your_other_roles_and_your_angle(home):
    a = setup(home)
    setup(home, role="Detection Engineer")
    A.research(cfg_of(home), a)
    r = read(home, a, "research.md")
    assert "> Acme protects hospitals from ransomware." in r
    assert "- acme-detection-engineer: Detection Engineer (" in r
    assert "Unlimited PTO" in r
    assert "They need: \"Triage alerts in Splunk\". You hold splunk." in r


def test_email_is_signed_from_profile_and_drawn_from_what_you_hold(home):
    slug = setup(home, profile='name = "Jane Doe"\nemail = "jane@example.com"\n')
    A.email(cfg_of(home), slug)
    e = read(home, slug, "email.md")
    assert "**Subject:** SOC Analyst - Jane Doe" in e
    assert "Jane Doe\n[FILL] phone · jane@example.com · [FILL] location" in e
    assert '- splunk: "Splunk: built 40 dashboards' in e and "kql" not in e
    assert "no PDFs yet: `ken jobs build" in e


def test_email_lists_the_built_pdfs(home):
    slug = setup(home)
    d = home / "pdf" / "ready" / slug
    d.mkdir(parents=True)
    (d / "resume-acme.pdf").write_bytes(b"%PDF")
    m = __import__("json").loads((home / "roles" / slug / "meta.json").read_text())
    m["pdf_dir"] = f"pdf/ready/{slug}"
    (home / "roles" / slug / "meta.json").write_text(__import__("json").dumps(m))
    A.email(cfg_of(home), slug)
    assert "[ ] resume-acme.pdf" in read(home, slug, "email.md")


def test_email_without_a_name_is_not_evaluable(home):
    slug = setup(home, profile="")
    with pytest.raises(NotEvaluable, match=r"\[profile\] name"):
        A.email(cfg_of(home), slug)


def test_a_filled_file_is_never_overwritten_without_force(home):
    slug = setup(home)
    for run, name in ((A.prep, "prep.md"), (A.research, "research.md"), (A.email, "email.md")):
        run(cfg_of(home), slug)
        (home / "roles" / slug / name).write_text("my notes")
        with pytest.raises(Refused, match="--force"):
            run(cfg_of(home), slug)
        assert read(home, slug, name) == "my notes"
        run(cfg_of(home), slug, force=True)
        assert read(home, slug, name) != "my notes"


def test_nothing_in_the_output_comes_from_outside_the_inputs(home):
    """jobctl's versions carried one person's name, employer type and a federal-contractor line."""
    slug = setup(home)
    A.prep(cfg_of(home), slug)
    A.research(cfg_of(home), slug)
    A.email(cfg_of(home), slug)
    text = "".join(read(home, slug, n) for n in ("prep.md", "research.md", "email.md")).lower()
    for word in ("msp", "federal", "citizen", "rmm", "seth"):
        assert word not in text


def test_cli_exit_codes(home, capsys):
    slug = setup(home)
    assert cli.main(["--home", str(home), "jobs", "prep", slug]) == 0
    assert cli.main(["--home", str(home), "jobs", "prep", slug]) == 1                # refused: exists
    assert cli.main(["--home", str(home), "jobs", "prep", slug, "--force"]) == 0


def test_an_untyped_posting_lists_every_term_rather_than_none(home):
    slug = setup(home, posting="We want someone who knows Splunk and KQL and has done incident response.\n")
    A.prep(cfg_of(home), slug)
    p = read(home, slug, "prep.md")
    assert "sections were not recognised" in p
    assert "- splunk: say" in p and "- kql: NOT HELD" in p


def test_check_reads_a_sectioned_latex_resume_and_a_section_edit_makes_it_stale(home):
    slug = setup(home)
    src = home / "resumes"
    (src / "sections").mkdir()
    (src / "sections" / "skills.tex").write_text("\\item Splunk dashboards and KQL hunting\n")
    (src / "resume-acme.tex").write_text("\\documentclass{article}\\begin{document}\n"
                                         "\\begin{itemize}\\input{sections/skills}\\end{itemize}\n\\end{document}\n")
    assert cli.main(["--home", str(home), "jobs", "check", slug, "--resume", str(src / "resume-acme.tex")]) in (0, 1)
    cov = __import__("json").loads((home / "roles" / slug / "coverage.json").read_text())
    assert {"splunk", "kql"} <= {t.lower() for t in cov["present"]}
    A.prep(cfg_of(home), slug)
    (src / "sections" / "skills.tex").write_text("\\item Splunk dashboards\n")      # only the section changes
    with pytest.raises(NotEvaluable, match="stale"):
        A.prep(cfg_of(home), slug, force=True)
