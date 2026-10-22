"""`jobs brief SLUG`: one bundle for whoever writes the tailored resume and cover letter.

Deterministic: kenloop writes nothing a model would; the brief says what may be claimed
(only what facts.md holds, each with the line that proves it), what must not be, and what the
posting and the company say, typed."""
from kenloop import cli

POSTING = """## About Acme
Acme protects hospitals from ransomware.

## What you'll do
- Triage alerts in Splunk

## Requirements
- Splunk
- Incident response
- KQL
- Excellent written communication

## Nice to have
- Sigma rules

## Benefits
- Unlimited PTO
"""


def setup(home):
    (home / "config.toml").write_text('[profile]\nresume = "resumes/resume.md"\n[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    (home / "resumes").mkdir(exist_ok=True)
    (home / "resumes" / "resume.md").write_text("SOC analyst. Splunk.\n")
    (home / "facts.md").write_text("## Held\n- Splunk: built 40 dashboards for a 3-person SOC (2024)\n"
                                   "- Incident response: led 12 ransomware cases end to end\n\n"
                                   "## Learning\n- KQL (course in progress)\n")
    (home / "jd.txt").write_text(POSTING)
    assert cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme", "--role", "SOC Analyst",
                     "--jd", str(home / "jd.txt")]) == 0
    return "acme-soc-analyst"


def brief(home, slug, capsys):
    capsys.readouterr()
    code = cli.main(["--home", str(home), "jobs", "brief", slug])
    return code, capsys.readouterr().out


def test_brief_needs_a_fresh_coverage(home, capsys):
    slug = setup(home)
    code, _ = brief(home, slug, capsys)
    assert code == 2
    cli.main(["--home", str(home), "jobs", "check", slug])
    (home / "facts.md").write_text((home / "facts.md").read_text() + "- Python\n")
    code, _ = brief(home, slug, capsys)
    assert code == 2                                            # facts changed: stale


def test_brief_quotes_the_proof_for_every_claim_and_lists_what_not_to_claim(home, capsys):
    slug = setup(home)
    cli.main(["--home", str(home), "jobs", "check", slug])
    code, out = brief(home, slug, capsys)
    assert code == 0
    assert out.startswith("# Brief: Acme — SOC Analyst")
    you_hold = out.split("## You hold")[1].split("\n## ")[0]
    assert "splunk" in you_hold and "built 40 dashboards for a 3-person SOC (2024)" in you_hold
    assert "incident response" in you_hold and "led 12 ransomware cases" in you_hold
    dont = out.split("## Do not claim")[1].split("\n## ")[0]
    assert "kql" in dont and "sigma rules" in dont
    assert "splunk" not in dont


def test_brief_carries_the_typed_posting_and_the_company_text(home, capsys):
    slug = setup(home)
    cli.main(["--home", str(home), "jobs", "check", slug])
    _, out = brief(home, slug, capsys)
    req = out.split("### Required")[1].split("\n### ")[0]
    assert "- [held] splunk" in req and "- [not held] kql" in req
    assert "Triage alerts in Splunk" in out.split("### Responsibilities")[1]
    about = out.split("## About the company")[1].split("\n## ")[0]
    assert "Acme protects hospitals from ransomware." in about and "this posting only" in about
    assert "Excellent written communication" in out.split("## Not looked at")[1]
    assert "Only claim what" in out.split("## Rules")[1]
