"""Edge cases for the posting reader: what is a heading, required vs preferred, aliases and
acronyms, old coverage files, and Lever lists (each first reproduced on real or hand-made postings)."""
import json

import pytest

from kenloop.career import ats, sections, sources
from kenloop.career import config as CC


def kinds(text):
    return {ln.text: ln.kind for ln in sections.split(text) if ln.text and not ln.heading}


def heads(text):
    return [(ln.text, ln.kind) for ln in sections.split(text) if ln.heading]


@pytest.fixture
def sec(home):
    (home / "config.toml").write_text('[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    c = CC.load(home)
    return c, ats.load_lexicon(c)


# --- only a heading-shaped line is a heading -------------------------------------

def test_a_benefit_line_with_a_cue_word_is_not_a_heading():
    t = ("What We Offer:\n- Stock options\nSubsidised private health insurance through our preferred provider\n"
         "Annual bonus\nSigning bonus\n")
    assert heads(t) == [("What We Offer", "benefits")]
    assert set(kinds(t).values()) == {"benefits"}


def test_html_list_items_are_bullets_never_headings(sec):
    cfg, lex = sec
    html = ("<h2>Requirements</h2><ul><li>Experience with <b>Splunk</b></li><li>Kafka required</li>"
            "<li>2 years of experience</li></ul><h3>Nice to have</h3><ul><li>Experience with "
            "<b>Microsoft Sentinel</b></li></ul>")
    text = ats.strip_html(html, structure=True)
    assert heads(text) == [("Requirements", "required"), ("Nice to have", "preferred")]
    rep = ats.coverage(text, "Splunk", "", cfg, lex)
    assert rep["sections"]["required"] == {"covered": 1, "denom": 1}
    assert rep["sections"]["preferred"] == {"covered": 0, "denom": 1}
    assert "Kafka required" in rep["unread"]["unread"]


def test_a_bare_cue_word_alone_on_a_line_is_still_a_heading():
    assert heads("Experience\n- Splunk\nBonus\n- KQL\n") == [("Experience", "required"),
                                                             ("Bonus", "preferred")]
    assert heads("Experience with Splunk\nKafka required\n") == []


# --- "Preferred X" is preferred --------------------------------------------------

@pytest.mark.parametrize("h", ["Preferred Qualifications", "Preferred Experience:", "Desired Qualifications",
                               "Bonus Skills", "NICE-TO-HAVES", "Nice to haves", "## Bonus points",
                               "**Preferred skills**", "Nice-to-have:"])
def test_preferred_headings(h):
    assert heads(h + "\n- x\n") == [(h.strip("#* ").rstrip(":").strip("*"), "preferred")]


def test_qualifications_then_preferred_qualifications_split_correctly(sec):
    cfg, lex = sec
    md = ("## Qualifications\n- Splunk\n- Microsoft Sentinel\n- CISSP\n## Preferred Qualifications\n"
          "- Terraform\n- KQL\n- 5-7 years of experience in security operations\n## What you'll do\n- triage\n")
    rep = ats.coverage(md, "Splunk Sentinel", "", cfg, lex)
    assert rep["sections"]["required"] == {"covered": 2, "denom": 3}
    # terraform, kql, and "security operations" in the years line
    assert rep["sections"]["preferred"] == {"covered": 0, "denom": 3}
    assert rep["years"][0]["kind"] == "preferred"


# --- "What you'll bring" is required ---------------------------------------------

@pytest.mark.parametrize("h", ["What You'll Bring to the Role", "What you’ll bring:", "WHAT YOU WILL BRING",
                               "About you", "Minimum Qualifications", "Basic qualifications:",
                               "What we're looking for", "Must-haves"])
def test_required_headings(h):
    assert heads(h + "\n- x\n")[0][1] == "required"


@pytest.mark.parametrize("h,kind", [("The Acme Experience", "company"), ("About the role", "responsibilities"),
                                    ("About Us", "company"), ("Benefits & Perks", "benefits"),
                                    ("Equal Opportunity Employer", "legal"), ("What you'll do:", "responsibilities"),
                                    ("Responsibilities", "responsibilities"), ("How to apply", "logistics")])
def test_typed_headings(h, kind):
    assert heads("## " + h + "\n- x\n")[0][1] == kind


# --- aliases and acronyms count once, and only what was asked ------------------

def test_bare_mitre_does_not_ask_for_attack(sec):
    _cfg, lex = sec
    assert ats.extract("Familiar with MITRE D3FEND and MITRE ATLAS.", lex) == ["mitre d3fend", "mitre atlas"]
    assert "mitre att&ck" in ats.extract("Map detections to ATT&CK.", lex)


def test_an_acronym_inside_a_matched_term_is_not_counted_again(sec):
    _cfg, lex = sec
    assert ats.extract("Azure AD and Azure Active Directory", lex) == ["entra id"]


def test_sentinel_one_is_sentinelone_not_microsoft_sentinel(sec):
    cfg, lex = sec
    got = ats.extract("Experience with Sentinel One, SentinelOne and Microsoft Defender.", lex)
    assert "microsoft sentinel" not in got and "sentinelone" in got
    from kenloop.career import jobs
    bad, terms, *_ = jobs.claim_report(cfg, "Used Sentinel One for EDR", "## Held\n- SentinelOne\n- EDR", lex)
    assert bad == [] and "sentinelone" in terms


def test_ordinary_words_do_not_read_as_security_terms(sec):
    _cfg, lex = sec
    got = ats.extract("Lean Six Sigma Black Belt preferred. Generate unique IDs for every record. "
                      "Act as a proxy for the customer.", lex)
    assert not {"sigma rules", "intrusion detection", "web proxy", "ids", "proxy"} & set(got)
    assert "intrusion detection" in ats.extract("Tune IDS/IPS signatures", lex)


# --- an old coverage.json is unmeasured, not "no lines" --------------------------

def test_upskill_names_roles_whose_coverage_predates_the_unread_count(demo, capsys):
    from conftest import run
    run(demo, "jobs", "discover", "--board", "fixture", "--company", "example-folio", "--intake",
        "--exclude-senior")
    for d in sorted((demo / "roles").iterdir()):
        run(demo, "jobs", "check", d.name)
    p = demo / "roles" / "example-folio-web-developer" / "coverage.json"
    cov = json.loads(p.read_text())
    for k in ("unread", "sections", "term_sections", "years"):
        cov.pop(k)
    p.write_text(json.dumps(cov))
    capsys.readouterr()
    run(demo, "jobs", "upskill")
    out = capsys.readouterr().out
    assert "1 role(s) checked before this count existed (re-run `jobs check`)" in out
    assert "the other 4 had no requirement lines to read" in out


# --- an unusable [profile] years says so -----------------------------------------

def test_an_unusable_profile_years_is_not_evaluable(home):
    from kenloop.career import jobs
    (home / "config.toml").write_text('[profile]\nyears = "three"\n[ats]\npacks = ["web"]\n')
    cfg = CC.load(home)
    rep = {"years": [{"min": 5, "max": None, "kind": "required", "text": "5+ years experience"}]}
    (line,) = jobs.placement_lines(cfg, rep)
    assert "[profile] years = 'three' is not a number" in line and "NOT EVALUABLE" in line


# --- pre-existing: Lever keeps requirements in `lists` --------------------------------------

def test_lever_lists_are_part_of_the_posting(monkeypatch):
    posting = [{"id": "p1", "text": "Defensive Security Analyst", "categories": {"location": "Remote"},
                "hostedUrl": "https://jobs.lever.co/x/p1", "descriptionPlain": "We defend things.",
                "lists": [{"text": "What you'll need", "content": "<li>Splunk</li><li>KQL</li>"},
                          {"text": "Nice to have", "content": "<li>Sigma rules</li>"}],
                "additionalPlain": "Benefits: health."}]
    monkeypatch.setattr(sources, "_get_json", lambda url: posting)
    (p,) = sources._lever("x")
    h = heads(p["jd"])
    assert ("What you'll need", "required") in h and ("Nice to have", "preferred") in h
    assert "Splunk" in p["jd"] and "Benefits: health." in p["jd"]


@pytest.mark.parametrize("h,kind", [("## Core Responsibilities", "responsibilities"), ("## What We Require", "required"),
                                    ("## What We Value", "preferred"), ("## Life on the team", "other"),
                                    ("We'd love to see:", "preferred")])
def test_palantir_style_headings(h, kind):
    assert heads(h + "\n- x\n")[0][1] == kind


def test_an_unknown_markdown_heading_closes_the_section_but_a_colon_line_does_not():
    t = "Requirements\n- Splunk\n## Our Stack\n- Kafka\n"
    assert kinds(t)["Kafka"] == "other"
    t = "Requirements\nStrong knowledge of:\n- Splunk\n"
    assert kinds(t)["Splunk"] == "required"
