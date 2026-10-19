"""A company's template, learned from its own postings, kept and labelled.

A line that appears in most of one company's postings is that company's template (about us,
benefits, legal text). It is never deleted: it is labelled, kept out of the "not looked at"
list, still read for skills, and stored in the company's profile for tailoring."""
import json

import pytest

from careerloop import cli, orgs
from careerloop import home as H

ABOUT = "## About Acme\nAcme protects hospitals from ransomware.\n"
TAIL = ("## Benefits\n- Unlimited PTO\n- Pet insurance\n"
        "## Equal Opportunity\nAcme is an equal opportunity employer.\n")


def posting(req):
    return ABOUT + "## Requirements\n" + "".join(f"- {r}\n" for r in req) + TAIL


ROLES = {"soc-1": ["Splunk", "Excellent written communication"],
         "soc-2": ["Microsoft Sentinel", "Comfortable with on-call rotations"],
         "soc-3": ["CrowdStrike", "Excellent written communication"],
         "soc-4": ["KQL", "Mentor junior analysts"]}


@pytest.fixture
def acme(home):
    (home / "config.toml").write_text('[profile]\nresume = "resumes/resume.md"\n[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    (home / "resumes").mkdir(exist_ok=True)
    (home / "resumes" / "resume.md").write_text("Splunk\n")
    (home / "facts.md").write_text("## Held\n- Splunk\n")
    for role, req in ROLES.items():
        (home / f"{role}.txt").write_text(posting(req))
        assert cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme", "--role", role,
                         "--jd", str(home / f"{role}.txt")]) == 0
    return home


def test_lines_most_postings_share_are_the_template_and_role_lines_are_not(acme):
    prof = orgs.profile(H.load_config(acme), "Acme")
    texts = {t["text"]: t["count"] for t in prof["template"]}
    assert texts["Acme protects hospitals from ransomware."] == 4
    assert texts["Acme is an equal opportunity employer."] == 4
    assert texts["Unlimited PTO"] == 4
    assert "Splunk" not in texts and "Mentor junior analysts" not in texts
    assert "Excellent written communication" not in texts         # 2 of 4: under the 60% share
    assert prof["postings"] == 4
    assert prof["about"] == ["Acme protects hospitals from ransomware."]
    assert prof["benefits"] == ["Unlimited PTO", "Pet insurance"]


def test_too_few_postings_is_not_evaluable_not_an_empty_template(home):
    (home / "a.txt").write_text(posting(["Splunk"]))
    cli.main(["--home", str(home), "jobs", "intake", "--company", "Solo", "--role", "x",
              "--jd", str(home / "a.txt")])
    prof = orgs.profile(H.load_config(home), "Solo")
    assert prof["template"] is None and "1 posting" in prof["why"]


def test_check_sets_template_lines_aside_from_not_looked_at_but_still_reads_their_skills(acme, capsys):
    capsys.readouterr()
    cli.main(["--home", str(acme), "jobs", "check", "acme-soc-2"])
    out = capsys.readouterr().out
    assert "company template: 4 line(s) seen in most of Acme's 4 posting(s), set aside" in out
    cov = json.loads((acme / "roles" / "acme-soc-2" / "coverage.json").read_text())
    assert "Acme is an equal opportunity employer." in cov["parts"]["template"]
    assert "Comfortable with on-call rotations" in cov["unread"]["unread"]   # a role line: still listed
    assert cov["sections"]["required"]["denom"] == 1                         # microsoft sentinel


def test_jobs_org_prints_and_writes_the_profile(acme, capsys):
    capsys.readouterr()
    assert cli.main(["--home", str(acme), "jobs", "org", "Acme"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("Acme: 4 posting(s); template: 4 line(s)")
    saved = json.loads((acme / "orgs" / "acme.json").read_text())
    assert saved["about"] == ["Acme protects hospitals from ransomware."]
    assert cli.main(["--home", str(acme), "jobs", "org", "Nobody"]) == 2


def test_a_requirement_every_posting_shares_is_still_a_requirement(home):
    (home / "config.toml").write_text('[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    same = ABOUT + "## Requirements\n- Comfortable with on-call rotations\n- Splunk\n" + TAIL
    for i in range(4):
        (home / f"r{i}.txt").write_text(same)
        cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme", "--role", f"soc {i}",
                  "--jd", str(home / f"r{i}.txt")])
    keys = orgs.template_keys(H.load_config(home), "Acme")
    assert "comfortable with on-call rotations" not in keys and "acme is an equal opportunity employer." in keys


# --- several postings, one company ---------------------------------------------------------------------------

def _roles_of(home, texts, org="Acme"):
    for i, text in enumerate(texts):
        f = home / f"p{i}.txt"
        f.write_text(text)
        assert cli.main(["--home", str(home), "jobs", "intake", "--company", org, "--role", f"r{i}",
                         "--jd", str(f)]) == 0


MIXED = ["Splunk expertise\nAcme protects hospitals.\nAcme is hiring.\n",     # no headings: every line `none`
         "## About Acme\nAcme protects hospitals.\n## Requirements\n- Splunk expertise\n",
         "## About Acme\nAcme protects hospitals.\n## Requirements\n- Splunk expertise\n",
         "## About Acme\nAcme protects hospitals.\n## Requirements\n- Splunk expertise\n"]


@pytest.mark.parametrize("flip", [False, True])
def test_a_line_that_is_required_elsewhere_is_never_a_set_aside_template_line(home, flip, monkeypatch):
    _roles_of(home, MIXED)
    cfg = H.load_config(home)
    real = orgs._postings
    monkeypatch.setattr(orgs, "_postings", (lambda c, o: list(reversed(real(c, o)))) if flip else real)
    prof = orgs.profile(cfg, "Acme")
    by = {t["text"]: t for t in prof["template"]}
    assert by["Splunk expertise"]["count"] == 4 and by["Splunk expertise"]["kind"] == "required"
    assert "splunk expertise" not in orgs.template_keys(cfg, "Acme")
    assert prof["about"] == ["Acme protects hospitals."]            # tailoring text from the sectioned postings


def test_the_profile_is_the_same_in_either_scan_order(home, monkeypatch):
    _roles_of(home, MIXED)
    cfg = H.load_config(home)
    real = orgs._postings
    a = orgs.profile(cfg, "Acme")
    monkeypatch.setattr(orgs, "_postings", lambda c, o: list(reversed(real(c, o))))
    b = orgs.profile(cfg, "Acme")
    a.pop("generated"), b.pop("generated")
    assert a == b


def test_jobs_org_with_too_few_postings_exits_2_and_still_writes_the_profile(home, capsys):
    _roles_of(home, [MIXED[1]], org="Solo")
    capsys.readouterr()
    assert cli.main(["--home", str(home), "jobs", "org", "Solo"]) == 2
    out = capsys.readouterr().out
    assert "NOT EVALUABLE" in out and "1 about line(s)" in out
    assert (home / "orgs" / "solo.json").exists()


def test_postings_of_aliased_org_names_are_pooled(home):
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n[sources]\naliases = {"acme-careers" = "acme"}\n')
    _roles_of(home, MIXED[1:3], org="Acme")
    _roles_of(home, MIXED[3:4], org="Acme-Careers")
    prof = orgs.profile(H.load_config(home), "Acme")
    assert prof["postings"] == 3 and prof["template"] is not None


def test_brief_includes_the_standing_benefits_when_every_benefit_line_is_template(acme, capsys):
    cli.main(["--home", str(acme), "jobs", "check", "acme-soc-1"])
    capsys.readouterr()
    assert cli.main(["--home", str(acme), "jobs", "brief", "acme-soc-1"]) == 0
    out = capsys.readouterr().out
    assert "## Benefits it states" in out and "- Unlimited PTO" in out
    assert "standing benefits" in out
