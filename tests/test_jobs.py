"""The job arm."""
import json

import pytest

from kenloop.career import demand as DM
from kenloop.career import jobs as J
from kenloop.career import roles as R
from kenloop.core.errors import NotEvaluable, UsageError


def meta(home, slug):
    return json.loads((home / "roles" / slug / "meta.json").read_text())


def test_reintake_without_force_changes_nothing(cfg, home):
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST")
    before = (home / "roles" / slug / "meta.json").read_bytes()
    assert J.intake(cfg, "Acme", "Dev", jd="other") == (slug, False)
    assert (home / "roles" / slug / "meta.json").read_bytes() == before


def test_force_refresh_keeps_everything_you_wrote(cfg, home):
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST and JSON")
    J.score(cfg, slug, 4.0)
    m = meta(home, slug)
    m["resume"] = "resumes/acme.md"
    R.save(cfg, slug, m)
    (home / "roles" / slug / "scorecard.md").write_text("my notes")
    J.intake(cfg, "Acme", "Dev", url="https://x.invalid", force=True)       # no new posting text
    m = meta(home, slug)
    assert m["fit_score"] == 4.0 and m["status"] == "scored" and m["resume"] == "resumes/acme.md"
    assert (home / "roles" / slug / "jd.txt").read_text().strip() == "REST and JSON"
    assert (home / "roles" / slug / "scorecard.md").read_text() == "my notes"


def test_score_range(cfg):
    slug, _ = J.intake(cfg, "Acme", "Dev")
    for bad in (0.5, 5.5):
        with pytest.raises(UsageError):
            J.score(cfg, slug, bad)


def test_tailor_never_moves_a_role_backwards(cfg, home):
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST")
    (home / "resumes" / "resume.md").write_text("REST")
    J.check(cfg, slug)
    J.status(cfg, slug, "interviewing")
    J.tailor(cfg, slug)
    assert meta(home, slug)["status"] == "interviewing"


def test_status_records_outcome_and_warns_on_backward(cfg, home, capsys):
    slug, _ = J.intake(cfg, "Acme", "Dev")
    J.status(cfg, slug, "applied", date="2030-03-01")
    J.status(cfg, slug, "applied", date="2030-03-05")
    assert meta(home, slug)["applied"] == "2030-03-01"           # first time only
    J.status(cfg, slug, "rejected", stage="interview", reason="rejected", probed="tls, oauth")
    m = meta(home, slug)
    assert m["outcome"]["stage_reached"] == "interview" and m["outcome"]["probed_terms"] == ["oauth", "tls"]
    J.status(cfg, slug, "found")
    assert "backward" in capsys.readouterr().err and "(backward)" in meta(home, slug)["history"][-1]
    with pytest.raises(UsageError):
        J.status(cfg, slug, "hired")


def test_check_needs_a_posting_and_a_resume(cfg, home):
    slug, _ = J.intake(cfg, "Acme", "Dev")
    with pytest.raises(NotEvaluable):
        J.check(cfg, slug)
    J.intake(cfg, "Acme", "Dev", jd="REST", force=True)
    with pytest.raises(NotEvaluable):
        J.check(cfg, slug)


def _role(cfg, home, company, jd, status=None, found=None, **outcome):
    slug, _ = J.intake(cfg, company, "Dev", jd=jd)
    J.check(cfg, slug)
    m = meta(home, slug)
    if status:
        m["status"] = status
    if found:
        m["found"] = found
    if outcome:
        m["outcome"] = outcome
    R.save(cfg, slug, m)
    return slug


def test_weighted_demand(cfg, home):
    (home / "resumes" / "resume.md").write_text("HTTP")
    cfg.half_life_days = 60
    _role(cfg, home, "a", "OAuth")
    _role(cfg, home, "b", "OAuth", status="closed")
    _role(cfg, home, "c", "OAuth", status="rejected")
    _role(cfg, home, "d", "OAuth", status="rejected", stage_reached="interview")
    _role(cfg, home, "e", "OAuth", found="2030-01-19")          # 60 days old: half weight
    _role(cfg, home, "f", "CORS", probed_terms=["tls"])
    data = DM.compute(cfg)
    items = {i["term"]: i for b in data["buckets"] for i in b["items"]}
    assert items["oauth"]["demand"] == round(1 + 0 + 0.25 + 0.5 + 0.5, 2)
    assert items["oauth"]["count"] == 4 and "b-dev" not in items["oauth"]["roles"]
    assert items["tls"]["demand"] == 2.0 and items["tls"]["count"] == 0     # probe bonus only


def test_unmapped_terms_are_grouped_never_noise(cfg, home):
    (home / "resumes" / "resume.md").write_text("HTTP")
    _role(cfg, home, "a", "CORS and load balancing")
    data = DM.compute(cfg)
    names = [b["name"] for b in data["buckets"]]
    assert set(names) == {"Unmapped: web/security", "Unmapped: web/ops"}
    assert not any(i["noise"] for b in data["buckets"] for i in b["items"])
    cfg.ignore = {"cors"}
    data = DM.compute(cfg)
    sec = next(b for b in data["buckets"] if b["name"] == "Unmapped: web/security")
    assert sec["demand"] == 0 and sec["items"][0]["noise"]


def test_a_term_graduated_into_facts_stops_being_a_gap(cfg, home):
    (home / "resumes" / "resume.md").write_text("HTTP")
    _role(cfg, home, "a", "CORS")
    assert DM.compute(cfg)["buckets"]
    (home / "facts.md").write_text("## Held\n- CORS (held knowledge from study)\n")
    d = DM.compute(cfg)
    assert d["buckets"] == [] and d["quick_wins"][0]["term"] == "cors"


def test_upskill_staleness_is_by_content_not_date(cfg, home):
    (home / "resumes" / "resume.md").write_text("HTTP")
    slug = _role(cfg, home, "a", "CORS")
    J.upskill(cfg)
    assert DM.load(cfg)[1] is False
    J.status(cfg, slug, "closed")                                  # same day
    assert DM.load(cfg)[1] is True


def test_check_claims(cfg, home, capsys):
    (home / "facts.md").write_text("## Held\n- REST services\n## Learning\n- OAuth — planned\n")
    r = home / "resumes" / "r.md"
    r.write_text("REST")
    assert J.check_claims(cfg, str(r)) == 0
    r.write_text("REST and OAuth and CORS")
    assert J.check_claims(cfg, str(r)) == 1
    out = capsys.readouterr().out
    assert "not held     oauth" in out and "unsupported  cors" in out
    cfg.do_not_claim = {"rest"}
    r.write_text("REST")
    assert J.check_claims(cfg, str(r)) == 1
    (home / "facts.md").write_text("")
    with pytest.raises(NotEvaluable):
        J.check_claims(cfg, str(r))


def test_check_claims_do_not_claim_by_alias(cfg, home, capsys):
    (home / "lexicons" / "mine.toml").write_text('[aliases]\npostgres = "postgresql"\n')
    cfg.user_lexicon = "lexicons/mine.toml"
    cfg.do_not_claim = {"postgres"}
    (home / "facts.md").write_text("## Held\n- PostgreSQL\n")
    r = home / "resumes" / "r.md"
    r.write_text("PostgreSQL")
    assert J.check_claims(cfg, str(r)) == 1
    assert "do-not-claim" in capsys.readouterr().out


def _fixture(home, rows):
    (home / "fixtures" / "acme.json").write_text(json.dumps(rows))


def test_discover_and_reconcile(cfg, home, capsys):
    cfg.targets = [{"board": "fixture", "org": "acme"}]
    _fixture(home, [{"ext_id": "1", "title": "Dev", "jd": "REST"},
                    {"ext_id": "2", "title": "Senior Dev", "jd": "REST"},
                    {"ext_id": "3", "title": "Engineer II", "jd": "REST"}])
    assert J.discover(cfg, "fixture", "acme", do_intake=True, exclude_senior=True) == 0
    slugs = sorted(p.name for p in (home / "roles").iterdir())
    assert slugs == ["acme-dev", "acme-engineer-ii"]
    _fixture(home, [])
    assert J.reconcile(cfg) == 2                                   # empty board: marks nothing
    assert "still listed" not in capsys.readouterr().out
    assert not meta(home, "acme-dev").get("posting_gone")
    (home / "fixtures" / "acme.json").unlink()
    assert J.reconcile(cfg) == 2                                   # unreachable: marks nothing
    _fixture(home, [{"ext_id": "3", "title": "Engineer II"}])
    assert J.reconcile(cfg) == 0
    assert meta(home, "acme-dev")["posting_gone"] == "2030-03-20"
    assert meta(home, "acme-dev")["status"] == "found"             # status is yours to change


def test_reconcile_with_no_targets_is_not_evaluable(cfg):
    with pytest.raises(NotEvaluable):
        J.reconcile(cfg)


def test_all_intake_needs_a_keyword(cfg):
    cfg.targets = [{"board": "fixture", "org": "acme"}]
    with pytest.raises(UsageError):
        J.discover(cfg, all_targets=True, do_intake=True)


def test_a_damaged_role_is_skipped_and_reported(cfg, home):
    J.intake(cfg, "Acme", "Dev")
    (home / "roles" / "bad").mkdir()
    (home / "roles" / "bad" / "meta.json").write_text("{nope")
    good, bad = R.scan(cfg)
    assert [s for s, _ in good] == ["acme-dev"] and bad
    assert J.board(cfg) == 2


def test_senior_filter():
    from kenloop.career.sources import is_senior
    for t in ("Senior Engineer", "Sr. Analyst", "Staff Engineer", "Head of Security", "Engineer III"):
        assert is_senior(t), t
    for t in ("Engineer II", "Analyst", "Associate Engineer"):
        assert not is_senior(t), t


def test_fetch_error_and_empty_are_distinct(cfg, home):
    from kenloop.career import sources as S
    assert S.fetch("fixture", "acme", cfg).status == "error"
    _fixture(home, [])
    assert S.fetch("fixture", "acme", cfg).status == "empty"
    assert S.fetch("nope", "acme", cfg).status == "error"
