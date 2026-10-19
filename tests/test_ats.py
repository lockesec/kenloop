"""Extraction and coverage."""
import pytest

from careerloop import ats
from careerloop.errors import NotEvaluable


def lex(cfg):
    return ats.load_lexicon(cfg)


def test_nested_term_counts_once_as_the_longer(cfg):
    assert ats.extract("We run HTTP/2 everywhere", lex(cfg)) == ["http/2"]
    assert set(ats.extract("HTTP/2 and plain HTTP", lex(cfg))) == {"http", "http/2"}


def test_acronyms_are_found_and_boilerplate_is_not(cfg):
    got = ats.extract("REQUIREMENTS: know SIEM and GitHub. EEO employer. Req R123456. LI-Remote", lex(cfg))
    assert got == ["SIEM", "GitHub"]


def test_case_insensitive_dedupe_first_spelling_wins(cfg):
    assert ats.extract("JSON json Json", lex(cfg)) == ["json"]


def test_company_exclusion_is_token_bounded(cfg):
    text = "Work on Acme tooling with REST and ACMEAPI"
    got = ats.extract(text, lex(cfg), excluded={"acme"})
    assert "rest" in got and "ACMEAPI" in got   # a longer token that merely contains the name survives


def test_zero_terms_is_not_evaluable_never_zero_percent(cfg):
    with pytest.raises(NotEvaluable):
        ats.coverage("we like nice people", "resume", "", cfg, lex(cfg))


def test_equivalence_requires_the_anchor_to_be_held(cfg):
    cfg.equivalence = {"openapi": "rest"}
    jd, resume = "Document REST with OpenAPI", "Built REST services"
    held = ats.coverage(jd, resume, "## Held\n- REST services", cfg, lex(cfg))
    assert held["equiv"] == [{"term": "openapi", "via": "rest"}]
    unheld = ats.coverage(jd, resume, "## Held\n- Go\n## Learning\n- REST", cfg, lex(cfg))
    assert unheld["equiv"] == [] and unheld["pct"] == 50.0


def test_held_versus_not_held_split(cfg):
    rep = ats.coverage("HTTP, SQL and OAuth", "HTTP", "## Held\n- Wrote SQL reports\n## Learning\n- OAuth", cfg, lex(cfg))
    miss = {m["term"]: m["held"] for m in rep["missing"]}
    assert miss == {"sql": True, "oauth": False}
    assert rep["denom"] == 3 and rep["covered"] == 1


def test_do_not_claim_is_never_held(cfg):
    cfg.do_not_claim = {"graphql"}
    rep = ats.coverage("GraphQL", "", "## Held\n- GraphQL daily", cfg, lex(cfg))
    assert rep["missing"][0]["held"] is False


def test_missing_rows_carry_their_category(cfg):
    rep = ats.coverage("CORS and FooBar", "", "", cfg, lex(cfg))
    cats = {m["term"]: m["category"] for m in rep["missing"]}
    assert cats == {"cors": "web/security", "FooBar": "acronym"}


def test_removing_the_pack_removes_its_terms(cfg, home):
    cfg.packs = []
    assert ats.extract("REST and JSON over HTTP", ats.load_lexicon(cfg)) == ["REST", "JSON", "HTTP"]


def test_a_named_pack_that_does_not_exist_is_not_evaluable(cfg):
    cfg.packs = ["nope"]
    with pytest.raises(NotEvaluable):
        ats.load_lexicon(cfg)


def test_first_pack_wins_a_shared_term(cfg, home):
    (home / "lexicons" / "b.toml").write_text('name = "b"\n[categories]\nx = ["cors", "zzz"]\n')
    cfg.packs = ["web", "b"]
    assert ats.load_lexicon(cfg).category("cors") == "web/security"


def test_latex_resume_keeps_escaped_ampersand(tmp_path):
    p = tmp_path / "r.tex"
    p.write_text("\\item Mapped to MITRE ATT\\&CK % secret comment\n\\textbf{SQL} & more")
    t = ats.resume_text(p)
    assert "ATT&CK" in t and "secret" not in t and "SQL" in t and " & more" not in t


def test_shipped_packs_parse(cfg):
    for name in ("web", "security", "data"):
        cfg.packs = [name]
        (cfg.home / "lexicons" / "web.toml").unlink(missing_ok=True)
        assert ats.load_lexicon(cfg).terms


# --- junk acronyms ----------------------------------------------------------------

JUNK = ("Responsibilities\n- This role is NOT for cyber security newcomers.\n- AI-generated and AI-assisted "
        "reports, DE&TH reviews, ES QL EZ TS notes.\n- ALL ANY candidates AND OR the FOR list.\n")


def test_junk_acronyms_are_not_skills(cfg):
    got = {t.lower() for t in ats.extract(JUNK, lex(cfg))}
    for junk in ("not", "es", "ql", "ez", "ts", "ai-generated", "ai-assisted", "de&th", "and", "or",
                 "all", "any", "the", "for"):
        assert junk not in got, junk


def test_real_acronyms_still_count_beside_the_junk(cfg):
    got = {t.lower() for t in ats.extract(JUNK + "- Experience with SIEM, EDR, KQL, AWS and GCP.\n", lex(cfg))}
    assert {"siem", "edr", "kql", "aws", "gcp"} <= got
    assert not {"not", "es", "ts"} & got


def test_a_two_letter_acronym_beside_a_known_skill_on_its_line_still_counts(cfg):
    assert "ES" in ats.extract("Requirements\n- Docker ES administration\n", lex(cfg))
    assert "ES" not in ats.extract("Requirements\n- ES administration\n", lex(cfg))
