"""Typed sections: what each part of a posting is, kept, so each use reads its own part.

Safe first: only a clear heading types a line. A line under no heading, or under a heading
nobody recognises, stays `none` / `other` and visible; nothing is dropped."""
import json

import pytest

from kenloop.career import ats, sections
from kenloop.career import config as CC

POSTING = """Security Operations Analyst

## About Acme
We protect hospitals from ransomware.

## What you'll do
- Triage alerts in Splunk
- Hunt with KQL

## Requirements
- Incident response
- 2+ years of experience in a SOC

## Nice to have
- Sigma rules

## Benefits
- Health, dental, vision

## Equal Opportunity
Acme is an equal opportunity employer.

## How to apply
Send a resume.

## Our Stack
- Kafka
"""


def kinds(text):
    return {ln.text: ln.kind for ln in sections.split(text) if ln.text}


@pytest.mark.parametrize("line,kind", [
    ("We protect hospitals from ransomware.", "company"),
    ("Triage alerts in Splunk", "responsibilities"),
    ("Incident response", "required"),
    ("Sigma rules", "preferred"),
    ("Health, dental, vision", "benefits"),
    ("Acme is an equal opportunity employer.", "legal"),
    ("Send a resume.", "logistics"),
    ("Kafka", "other"),                          # an unknown heading: kept, typed as unknown
    ("Security Operations Analyst", "none"),
])
def test_each_part_of_a_posting_gets_its_type(line, kind):
    assert kinds(POSTING)[line] == kind


@pytest.fixture
def sec(home):
    (home / "config.toml").write_text('[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    c = CC.load(home)
    return c, ats.load_lexicon(c)


def test_responsibilities_are_counted_apart_from_elsewhere(sec):
    cfg, lex = sec
    rep = ats.coverage(POSTING, "Splunk, incident response", "", cfg, lex)
    s = rep["sections"]
    assert s["required"] == {"covered": 1, "denom": 1}
    assert s["preferred"] == {"covered": 0, "denom": 1}
    assert s["responsibilities"] == {"covered": 1, "denom": 2}      # splunk, kql
    assert rep["term_sections"]["splunk"] == "responsibilities"


def test_the_posting_parts_are_kept_for_tailoring(sec):
    cfg, lex = sec
    rep = ats.coverage(POSTING, "Splunk", "", cfg, lex)
    parts = rep["parts"]
    assert parts["company"] == ["We protect hospitals from ransomware."]
    assert parts["responsibilities"] == ["Triage alerts in Splunk", "Hunt with KQL"]
    assert parts["benefits"] == ["Health, dental, vision"]
    # every non-empty line is somewhere: nothing is dropped
    lines = [ln for ln in POSTING.splitlines() if ln.strip() and not ln.startswith("#")]
    assert sum(len(v) for v in parts.values()) == len(lines)


def test_check_prints_responsibilities_and_writes_the_parts(home, capsys):
    from kenloop import cli
    (home / "config.toml").write_text('[profile]\nresume = "resumes/resume.md"\n[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    (home / "resumes").mkdir(exist_ok=True)
    (home / "resumes" / "resume.md").write_text("Splunk and incident response\n")
    (home / "facts.md").write_text("## Held\n- Splunk\n- incident response\n")
    (home / "jd.txt").write_text(POSTING)
    assert cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme", "--role", "SOC",
                     "--jd", str(home / "jd.txt")]) == 0
    slug = next((home / "roles").iterdir()).name
    capsys.readouterr()
    cli.main(["--home", str(home), "jobs", "check", slug])
    out = capsys.readouterr().out
    assert "required 1/1 · preferred 0/1 · responsibilities 1/2 · elsewhere in the posting 0/1" in out
    cov = json.loads((home / "roles" / slug / "coverage.json").read_text())
    assert cov["parts"]["company"] == ["We protect hospitals from ransomware."]


def test_a_long_heading_in_capitals_still_opens_its_section():
    t = ("NICE-TO-HAVES\n- Terraform\n\nBENEFITS AVAILABLE TO ALL FULL-TIME ACME EMPLOYEES (GLOBAL)\n"
         "- Flexible PTO\n")
    assert kinds(t)["Flexible PTO"] == "benefits"
    assert kinds("Requirements\n- Experience with Python, Go and Terraform in large production systems\n")[
        "Experience with Python, Go and Terraform in large production systems"] == "required"


def test_acronyms_only_count_where_the_job_is_described(sec):
    cfg, lex = sec
    jd = ("## Requirements\n- Experience with SOAR and EDR\n- Familiar with XSIAM\n"
          "## Benefits\n- HSA and FSA options, AD&D insurance\n- RRSP match (Canada)\n"
          "UNITED STATES\n- 401(k)\n")
    rep = ats.coverage(jd, "EDR", "", cfg, lex)
    terms = set(rep["present"]) | {m["term"] for m in rep["missing"]}
    assert "XSIAM" in terms                                    # an unknown acronym in requirements: kept
    assert not {"HSA", "FSA", "AD&D", "RRSP", "UNITED", "STATES"} & terms
    assert set(rep["acronyms_set_aside"]) >= {"HSA", "FSA", "RRSP"}
