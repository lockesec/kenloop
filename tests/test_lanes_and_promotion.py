"""Lanes (career | interest), cert implies career, and promotion: an interest concept's recorded,
demand-checked, still-gated route into facts.md."""
import pytest

from kenloop import loop
from kenloop.career import graduate as G
from kenloop.career import promote as PR
from kenloop.core import learn as L
from kenloop.core.errors import NotEvaluable, UsageError

from conftest import run

CAREER = "# C\n\n## Concepts\n- net :: TLS handshakes :: how tls agrees on keys\n"
INTEREST = ("# I\n\n## Concepts\n- math :: TLS by hand :: the tls key exchange worked on paper\n"
            "- space :: Event horizons :: where light cannot leave\n")


@pytest.fixture
def two(cfg, home, monkeypatch):
    L.plan(cfg, "job", outlets=("career",))
    L.plan(cfg, "fun")
    for slug, syl in (("job", CAREER), ("fun", INTEREST)):
        (home / "topics" / slug / "syllabus.md").write_text(syl)
        L.sync(cfg, slug, quiet=True)
    L.record(cfg, "job", "net:tls-handshakes", "miss", quiet=True)
    L.record(cfg, "fun", "space:event-horizons", "miss", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-09-01")         # both reviews are due
    return cfg


def _rule(cfg, name, lane=None):
    return next(r for r in loop.evaluate(cfg, lane) if r["rule"] == name)


def test_a_cert_is_always_career(cfg):
    assert L.has_outlet({"outlets": ["cert"]}, "career")
    assert not L.has_outlet({"outlets": []}, "career")


def test_each_lane_reviews_only_its_own_topics(two):
    assert "job" in _rule(two, "reviews", "career")["argv"]
    assert "fun" in _rule(two, "reviews", "interest")["argv"]
    assert L.scheduled_topics(two, "career") == ["job"] and L.scheduled_topics(two, "interest") == ["fun"]


def test_the_interest_lane_switches_the_job_rules_off(two):
    for name in loop.JOB_RULES:
        r = _rule(two, name, "interest")
        assert r["status"] == "off" and "interest lane" in r["detail"]       # switched off, not "not fired"


def test_due_by_lane(two, home, capsys):
    run(home, "due", "--lane", "interest")
    out = capsys.readouterr().out
    assert "fun:" in out and "job:" not in out
    with pytest.raises(UsageError, match="not both"):
        L.due(two, "fun", lane="career")


def test_promotion_needs_a_reason_and_a_term_a_posting_names(two):
    with pytest.raises(UsageError, match="--why"):
        PR.promote(two, "fun", "math:tls-by-hand")
    with pytest.raises(UsageError, match="names no term"):
        PR.promote(two, "fun", "space:event-horizons", why="curious")
    assert PR.promote(two, "fun", "math:tls-by-hand", why="security roles ask for TLS") == 0
    assert PR.promoted(two, "fun") == {"math:tls-by-hand"}
    row = PR.events(two, "fun")[0]
    assert row["terms"] == ["tls"] and row["why"] == "security roles ask for TLS"


def test_revoke_is_appended_and_wins(two):
    PR.promote(two, "fun", "math:tls-by-hand", why="w")
    PR.promote(two, "fun", "math:tls-by-hand", revoke=True)
    assert PR.promoted(two, "fun") == set() and [e["event"] for e in PR.events(two, "fun")] == ["promote", "revoke"]


def test_a_career_topic_needs_no_promotion(two, capsys):
    PR.promote(two, "job", "net:tls-handshakes", why="w")
    assert "career topic" in capsys.readouterr().out and PR.events(two, "job") == []


def test_only_promoted_interest_concepts_can_graduate_and_still_through_the_gates(two, monkeypatch):
    passed = {"passed": ["math:tls-by-hand", "space:event-horizons"], "suspect": [], "not retained": [],
              "not breadth-tested": [], "drilled solo": []}
    monkeypatch.setattr(L, "graduation_evidence", lambda cfg, slug: passed)
    g = G.graduation(two, "fun")
    assert g["candidates"] == [] and g["not promoted"] == ["math:tls-by-hand", "space:event-horizons"]
    PR.promote(two, "fun", "math:tls-by-hand", why="w")
    g = G.graduation(two, "fun")
    assert g["candidates"] == ["math:tls-by-hand"] and g["not promoted"] == ["space:event-horizons"]
    monkeypatch.setattr(L, "graduation_evidence", lambda cfg, slug: {**passed, "passed": [],
                                                                      "not retained": ["math:tls-by-hand"]})
    g = G.graduation(two, "fun")
    assert g["candidates"] == [] and g["not retained"] == ["math:tls-by-hand"]   # promotion earns nothing alone


def test_a_damaged_ledger_is_not_evaluable_never_skipped(two, home):
    PR.promote(two, "fun", "math:tls-by-hand", why="w")
    with open(home / "topics" / "fun" / PR.LEDGER, "a") as f:
        f.write("{not json\n")
    with pytest.raises(NotEvaluable, match="is damaged"):
        PR.promoted(two, "fun")


def test_a_promoted_concept_on_facts_is_not_warned_as_interest(two, home):
    facts = "## Held\n- TLS by hand\n"
    assert any("studied for its own" in w for w in G.held_vs_study(two, facts))
    PR.promote(two, "fun", "math:tls-by-hand", why="w")
    assert not any("studied for its own" in w for w in G.held_vs_study(two, facts))


def test_a_question_with_no_ladder_is_the_interest_lanes(two, home):
    run(home, "ask", "why is lithium the best metal for batteries?")
    assert _rule(two, "question", "interest")["status"] == "fired"
    assert _rule(two, "question", "career")["status"] == "not fired"
