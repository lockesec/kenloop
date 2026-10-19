"""Pack aliases: other spellings of one term, and the shipped security pack."""
import pytest

from careerloop import ats
from careerloop import home as H
from careerloop.errors import NotEvaluable

PACK = """name = "ops"
[categories]
platforms = ["kubernetes", "mitre att&ck", "digital forensics"]
tools = ["splunk"]
[aliases]
"k8s" = "kubernetes"
"att&ck" = "mitre att&ck"
"mitre" = "mitre att&ck"
"""


@pytest.fixture
def ops(home):
    (home / "lexicons" / "ops.toml").write_text(PACK)
    (home / "config.toml").write_text('[ats]\npacks = ["ops"]\n')
    return H.load_config(home)


def test_an_alias_in_a_posting_counts_as_its_term(ops):
    lex = ats.load_lexicon(ops)
    assert ats.extract("Run K8s clusters and map detections to ATT&CK", lex) == \
        ["kubernetes", "mitre att&ck"]


def test_the_full_name_and_its_aliases_count_once(ops):
    lex = ats.load_lexicon(ops)
    assert ats.extract("MITRE ATT&CK (MITRE, ATT&CK) mapping", lex) == ["mitre att&ck"]


def test_a_resume_alias_covers_the_posting_term_and_a_held_alias_is_held(ops):
    lex = ats.load_lexicon(ops)
    rep = ats.coverage("Requirements\n- Kubernetes\n- Splunk", "Ran k8s in production", "## Held\n- k8s",
                       ops, lex)
    assert rep["present"] == ["kubernetes"]
    assert [m["term"] for m in rep["missing"]] == ["splunk"]
    rep = ats.coverage("Requirements\n- k8s", "Kubernetes", "## Held\n- Kubernetes", ops, lex)
    assert rep["present"] == ["kubernetes"]


def test_check_claims_accepts_a_term_held_under_an_alias(ops, capsys):
    from careerloop import jobs
    from careerloop import facts as F
    lex = ats.load_lexicon(ops)
    bad, terms, _look, _shown = jobs.claim_report(ops, "Kubernetes operator", "## Held\n- k8s", lex)
    assert terms == ["kubernetes"] and bad == []
    bad, *_ = jobs.claim_report(ops, "Kubernetes operator", "## Held\n- splunk", lex)
    assert [b[1] for b in bad] == ["unsupported"]
    assert F.holds("k8s", "## Held\n- k8s")


def test_an_alias_to_an_unknown_term_is_skipped_with_a_warning(home, capsys):
    (home / "lexicons" / "bad.toml").write_text(
        'name = "bad"\n[categories]\nx = ["rest"]\n[aliases]\n"restful" = "rest"\n"k8s" = "kubernetes"\n')
    (home / "config.toml").write_text('[ats]\npacks = ["bad"]\n')
    lex = ats.load_lexicon(H.load_config(home))
    assert lex.aliases == {"restful": "rest"}
    assert "alias 'k8s' names 'kubernetes', which no loaded pack has" in capsys.readouterr().err


def test_aliases_must_be_a_table_of_strings(home):
    (home / "lexicons" / "bad.toml").write_text('name = "bad"\n[categories]\nx = ["rest"]\n[aliases]\n"r" = 3\n')
    (home / "config.toml").write_text('[ats]\npacks = ["bad"]\n')
    with pytest.raises(NotEvaluable):
        ats.load_lexicon(H.load_config(home))


SOC = """Security Operations Analyst

Requirements
- Alert triage in Splunk or Microsoft Sentinel; write KQL queries
- Investigate with CrowdStrike Falcon and Defender for Endpoint
- Map activity to MITRE ATT&CK; write Sigma rules
- Security+ or CySA+
- Terraform is a plus
"""


def test_the_shipped_security_pack_reads_products_and_aliases(home):
    (home / "config.toml").write_text('[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    lex = ats.load_lexicon(H.load_config(home))
    got = set(ats.extract(SOC, lex))
    assert {"splunk", "microsoft sentinel", "kql", "crowdstrike", "microsoft defender",
            "mitre att&ck", "sigma rules", "security+", "cysa+", "alert triage"} <= got
    assert not {"MITRE", "ATT&CK", "KQL"} & got
    assert len(lex.terms) >= 150


def test_upskill_counts_a_term_held_under_an_alias_as_a_quick_win(ops, capsys):
    from careerloop import cli
    h = ops.home
    (h / "resumes").mkdir(exist_ok=True)
    (h / "resumes" / "resume.md").write_text("Splunk dashboards\n")
    (h / "facts.md").write_text("## Held\n- k8s\n- Splunk\n")
    (h / "jd.txt").write_text("Requirements\n- Kubernetes\n- Splunk\n")
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "Acme", "--role", "SRE",
                     "--jd", str(h / "jd.txt")]) == 0
    slug = next((h / "roles").iterdir()).name
    cli.main(["--home", str(h), "jobs", "check", slug])
    capsys.readouterr()
    assert cli.main(["--home", str(h), "jobs", "upskill"]) == 0
    out = capsys.readouterr().out
    assert "0 bucket(s), 1 quick win(s)" in out


def test_the_documented_pack_counts_are_the_real_ones():
    import re
    from pathlib import Path
    from careerloop.home import PACKAGE_LEXICONS, tomllib
    d = tomllib.loads((PACKAGE_LEXICONS / "security.toml").read_text())
    terms, aliases = sum(len(v) for v in d["categories"].values()), len(d["aliases"])
    root = Path(__file__).resolve().parents[1]
    for doc in ("docs/commands.md", "CHANGELOG.md"):
        m = re.search(r"(\d+) terms,? (?:with )?(\d+) aliases", (root / doc).read_text())
        assert m and (int(m.group(1)), int(m.group(2))) == (terms, aliases), doc
