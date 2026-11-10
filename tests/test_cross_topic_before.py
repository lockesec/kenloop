"""`before:<topic>/<cid>`: a concept in one topic learned before a concept in another (a math piece
under a model lesson). Within-topic links are unchanged."""
import pytest

from kenloop.core import graph as SG
from kenloop.core import integrity as I
from kenloop.core import learn as L


def _topic(cfg, home, slug, lines):
    L.plan(cfg, slug)
    (home / "topics" / slug / "syllabus.md").write_text(f"# {slug}\n\n## Concepts\n" + "".join(f"- {x}\n" for x in lines))
    L.sync(cfg, slug, quiet=True)


@pytest.fixture
def two(cfg, home):
    _topic(cfg, home, "ml", ["m :: Training :: steps against the gradient"])
    _topic(cfg, home, "math", ["a :: Signed numbers :: minus a minus :: before:ml/m:training",
                               "a :: Decimals :: money"])
    return cfg


def test_the_target_waits_on_the_other_topics_concept(two):
    g = SG.build(two, "ml")
    n = g.nodes["m:training"]
    assert n.elsewhere == [("math/a:signed-numbers", False)]
    assert any("learn first: math/a:signed-numbers" in w for w in SG.waits(g, n))


def test_a_climbed_prerequisite_no_longer_holds_it(two, monkeypatch):
    real = L.badge
    monkeypatch.setattr(L, "badge", lambda c: "mastered" if c.get("name") == "Signed numbers" else real(c))
    g = SG.build(two, "ml")
    assert g.nodes["m:training"].elsewhere == [("math/a:signed-numbers", True)]
    assert SG.waits(g, g.nodes["m:training"]) == []


def test_validate_names_a_missing_topic_or_concept_and_passes_a_good_link(two, home, cfg):
    assert not [p for p in I.problems(cfg, "math")[0] if "before:" in p]
    _topic(cfg, home, "bad", ["x :: One :: :: before:nope/x:y", "x :: Two :: :: before:ml/m:nothing"])
    hard = I.problems(cfg, "bad")[0]
    assert any("names a topic this home does not have" in p for p in hard)
    assert any("names a concept ml does not have" in p for p in hard)


def test_a_within_topic_before_still_needs_its_own_concept(cfg, home):
    _topic(cfg, home, "solo", ["a :: One :: :: before:a:missing"])
    assert any("names a concept this syllabus does not have" in p for p in I.problems(cfg, "solo")[0])


def test_a_cycle_across_topics_is_a_hard_failure(cfg, home):
    _topic(cfg, home, "ml", ["m :: Training :: steps :: before:math/a:signed-numbers"])
    _topic(cfg, home, "math", ["a :: Signed numbers :: minus a minus :: before:ml/m:training"])
    hard = I.problems(cfg, "ml")[0] + I.problems(cfg, "math")[0]
    assert sum("a cycle of before links across topics" in p for p in hard) == 2
    assert any("ml/m:training -> math/a:signed-numbers -> ml/m:training" in p for p in hard)


def test_a_three_step_chain_that_does_not_close_is_fine(cfg, home):
    _topic(cfg, home, "ml", ["m :: Training :: steps"])
    _topic(cfg, home, "math", ["a :: Signed numbers :: x :: before:ml/m:training", "a :: Counting :: y :: before:a:signed-numbers"])
    assert not [p for p in I.problems(cfg, "math")[0] if "cycle" in p]


def test_naming_its_own_topic_is_refused(cfg, home):
    _topic(cfg, home, "self", ["s :: One :: x :: before:self/s:two", "s :: Two :: y"])
    assert any("names this topic; write `before:s:two`" in p for p in I.problems(cfg, "self")[0])


def test_a_damaged_other_topic_is_a_warning_and_this_topics_checks_still_run(two, home, cfg):
    (home / "topics" / "ml" / "concepts.json").write_text("{damaged")
    _topic(cfg, home, "mine", ["x :: One :: :: before:ml/m:training", "x :: Two :: :: before:x:missing"])
    hard, warn = I.problems(cfg, "mine")
    assert any("cannot be checked: ml is damaged" in w for w in warn)
    assert any("names a concept this syllabus does not have" in p for p in hard)
