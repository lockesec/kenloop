"""Scouted offers: predicted branches, dormant until the concept is studied, scored when decided."""
import pytest

from kenloop import scouts as S
from kenloop.core import branches as B
from kenloop.core import learn as L
from kenloop.core import onramp as O
from kenloop.core.errors import UsageError

from conftest import run

SYL = "# T\n\n## Concepts\n- m :: Models :: how models work\n- m :: Agents :: tools and loops\n"


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text(SYL)
    L.sync(cfg, "t", quiet=True)
    return cfg


def test_a_scout_is_stored_dormant_and_touches_neither_syllabus_nor_branches(t, home):
    before = (home / "topics" / "t" / "syllabus.md").read_text()
    assert S.scout_cmd(t, "t", "m:models", "m :: Tokens :: what a token is", "you will ask") == 0
    assert (home / "topics" / "t" / "syllabus.md").read_text() == before and B.read(t)[0] == []
    assert S.open_scouts(t, "t") == []                                  # not studied yet: dormant
    assert len(S.open_scouts(t, "t", reached_only=False)) == 1


def test_a_scout_needs_a_reason_and_is_not_stored_twice(t):
    with pytest.raises(UsageError, match="--why"):
        S.scout_cmd(t, "t", "m:models", "m :: Tokens :: x", "")
    S.scout_cmd(t, "t", "m:models", "m :: Tokens :: x", "w")
    with pytest.raises(UsageError, match="already scouted"):
        S.scout_cmd(t, "t", "m:models", "m :: Tokens :: x", "w")


def test_studying_the_concept_surfaces_the_scout_as_an_offer_and_in_talk(t, home, capsys):
    S.scout_cmd(t, "t", "m:models", "m :: Tokens :: what a token is", "w")
    L.record(t, "t", "m:models", "partial", quiet=True)
    assert [c["source"] for c in B.candidates(t, "t")] == ["scout:1"]
    capsys.readouterr()
    run(home, "talk", "t", "m:models")
    assert "predicted branch scout:1" in capsys.readouterr().out


def test_precision_and_recall_score_the_scouting(t, home, capsys):
    S.scout_cmd(t, "t", "m:models", "m :: Tokens :: what a token is", "w")
    S.scout_cmd(t, "t", "m:models", "m :: Sampling :: temperature", "w")
    L.record(t, "t", "m:models", "partial", quiet=True)
    O.branch(t, "t", "m:models", "m :: Tokens :: what a token is", by="tool", source="scout:1")      # taken
    O.branch(t, "t", "m:models", by="tool", source="scout:2", decline="already know it")             # passed up
    O.branch(t, "t", "m:models", "m :: Tool calls :: how a tool call works", by="learner")           # unscouted
    sc = S.scout_score(t, B.read(t)[0], "t")
    assert (sc["decided"], sc["taken"], sc["passed_up"]) == (2, 1, 1)
    assert (sc["predicted"], sc["kept"]) == (1, 2) and sc["unscouted"] == ["m :: Tool calls :: how a tool call works"]
    capsys.readouterr()
    B.report(t, "t")
    out = capsys.readouterr().out
    assert "precision 1/2 scouts taken (1 passed up)" in out and "recall 1/2 kept branches predicted" in out


def test_a_learner_who_raises_a_scouted_gap_first_counts_as_predicted(t):
    S.scout_cmd(t, "t", "m:models", "m :: Tokens :: what a token is", "w")
    O.branch(t, "t", "m:models", "m :: Tokens :: what a token is", by="learner", source="scout:1")
    assert S.scout_score(t, B.read(t)[0], "t")["predicted"] == 1


def test_a_scout_is_decided_once_and_must_exist(t):
    S.scout_cmd(t, "t", "m:models", "m :: Tokens :: x", "w")
    O.branch(t, "t", "m:models", by="tool", source="scout:1", note="later")
    with pytest.raises(UsageError, match="already decided"):
        O.branch(t, "t", "m:models", by="tool", source="scout:1", decline="no")
    with pytest.raises(UsageError, match="not a scouted offer"):
        O.branch(t, "t", "m:models", by="tool", source="scout:9", decline="no")


def test_branches_growing_into_an_existing_topic_add_concepts_and_keep_its_first_origin(t, home):
    L.plan(t, "sec", title="Security", outlets=("career",))
    O.branch(t, "t", "m:models", "inj :: Prompt injection :: input that rewrites instructions", by="tutor", topic="sec")
    O.branch(t, "t", "m:agents", "id :: Managed identity :: no keys in code", by="tutor", topic="sec")
    names = {c["name"] for c in L.load_state(t, "sec")["concepts"].values()}
    conf = L.load_config(t, "sec")
    assert names == {"Prompt injection", "Managed identity"} and conf["title"] == "Security"
    assert conf["origin"] == "t/m:models" and L.has_outlet(conf, "career")
    assert [r["target"] for r in B.read(t)[0]] == ["sec", "sec"]


def test_recall_ignores_branches_made_before_scouting_on_the_same_day(t):
    O.branch(t, "t", "m:models", "m :: Early :: decided before any scout", by="learner")
    S.scout_cmd(t, "t", "m:models", "m :: Tokens :: x", "w")
    sc = S.scout_score(t, B.read(t)[0], "t")
    assert sc["kept"] == 0 and sc["unscouted"] == []
    O.branch(t, "t", "m:models", "m :: Later :: raised after scouting", by="learner")
    assert S.scout_score(t, B.read(t)[0], "t")["unscouted"] == ["m :: Later :: raised after scouting"]
