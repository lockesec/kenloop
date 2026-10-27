"""The heading census, and mapping a heading once in config.

The reader types only headings it knows. `jobs headings` lists the heading-shaped lines it did
not type, counted across every posting taken in, so the parser grows from the user's own
postings; `[headings]` in config.toml maps one to a type."""
import pytest

from kenloop.career import ats, sections
from kenloop import cli
from kenloop.core.errors import NotEvaluable
from kenloop.career import config as CC

A = "## Requirements\n- Splunk\n## Where you will grow\n- KQL\n## Our Stack\n- Kafka\n"
B = "## Requirements\n- SIEM\n## Where you will grow\n- Sigma rules\n## Perks\n- Pet insurance\n"


def intake(home, name, text):
    (home / f"{name}.txt").write_text(text)
    assert cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme", "--role", name,
                     "--jd", str(home / f"{name}.txt")]) == 0


def test_census_lists_unknown_headings_by_how_many_postings_use_them(home, capsys):
    intake(home, "one", A)
    intake(home, "two", B)
    capsys.readouterr()
    assert cli.main(["--home", str(home), "jobs", "headings"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].startswith("headings: 2 not typed, over 2 posting(s)")
    assert "2  Where you will grow" in out and "1  Our Stack" in out
    assert "Requirements" not in out and "Perks" not in out            # typed: not listed


def test_all_lists_typed_headings_too_with_their_type(home, capsys):
    intake(home, "one", A)
    capsys.readouterr()
    cli.main(["--home", str(home), "jobs", "headings", "--all"])
    out = capsys.readouterr().out
    assert "1  Requirements  required" in out


def test_a_config_mapping_types_the_heading_everywhere(home):
    (home / "config.toml").write_text('[ats]\npacks = ["security"]\n[headings]\n'
                                      '"where you will grow" = "preferred"\n"our stack" = "required"\n')
    (home / "lexicons" / "web.toml").unlink()
    cfg = CC.load(home)
    kinds = {ln.text: ln.kind for ln in sections.split(A, cfg.headings) if ln.text and not ln.heading}
    assert kinds == {"Splunk": "required", "KQL": "preferred", "Kafka": "required"}
    rep = ats.coverage(A, "Splunk", "", cfg, ats.load_lexicon(cfg))
    assert rep["sections"]["preferred"]["denom"] == 1                  # kql is preferred now


def test_a_mapping_beats_the_built_in_reading(home):
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n[headings]\n"perks" = "company"\n')
    cfg = CC.load(home)
    kinds = {ln.text: ln.kind for ln in sections.split(B, cfg.headings) if ln.text and not ln.heading}
    assert kinds["Pet insurance"] == "company"


@pytest.mark.parametrize("body", ['[headings]\n"x" = "nonsense"\n', '[headings]\n"x" = 3\n'])
def test_a_bad_mapping_is_not_evaluable(home, body):
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n' + body)
    with pytest.raises(NotEvaluable):
        CC.load(home)


def test_no_postings_is_not_evaluable(home, capsys):
    assert cli.main(["--home", str(home), "jobs", "headings"]) == 2


def test_figures_codes_and_board_tags_are_not_headings():
    t = "$138,000 - $189,200 USD\nP25858_3542380\nBI-Remote\nCANADA\nOTHER NOTICES\n"
    assert [x[0] for x in sections.census(t)] == ["CANADA", "OTHER NOTICES"]


@pytest.mark.parametrize("h,kind", [("What We Do", "company"), ("OTHER NOTICES", "legal"),
                                    ("REFERRAL INSTRUCTIONS", "logistics"),
                                    ("What you can look forward to as an Acme employee!", "benefits")])
def test_headings_the_live_census_found_are_built_in(h, kind):
    assert sections.census("## " + h + "\n") == [(h, kind)]
