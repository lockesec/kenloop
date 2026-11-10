"""Found while using it: a taught concept is brought back for a cold recall.

Teaching earns no credit, and a say-back right after it is not evidence. Credit comes from a cold
recall on a later day. But `taught` set no schedule and `due` listed only concepts with attempts,
so a taught concept fell out of every list: measured in a real study home, 5 of 6 taught concepts
had never been recalled 2-7 days on. Now teaching schedules the first cold recall for tomorrow,
still with no credit, and `due` lists it.
"""
import pytest

from kenloop.core import learn as L
from kenloop.core import reviews as R

from conftest import run


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: c0 :: x\n- d :: c1 :: y\n")
    L.sync(cfg, "t", quiet=True)
    return home


def c0(cfg):
    return L.load_state(cfg, "t")["concepts"]["d:c0"]


def due_ids(cfg):
    return [cid for cid, _ in R.due_list(cfg, "t")]


def test_teaching_schedules_a_cold_recall_tomorrow_with_no_credit(cfg, t, monkeypatch):
    L.taught(cfg, "t", "d:c0", quiet=True)
    c = c0(cfg)
    assert c["due"] == "2030-03-21" and not c.get("attempts") and not c.get("streak")
    assert not c.get("interval"), "no credit: a first look, not a learned interval"
    assert "d:c0" not in due_ids(cfg)                                  # not today: it was just taught
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    assert due_ids(cfg) == ["d:c0"]                                    # tomorrow it opens the session
    L.record(cfg, "t", "d:c0", "ok", qtype="recall", confidence="med", quiet=True)
    c = c0(cfg)
    assert c["streak"] == 1 and c["correct_days"] == ["2030-03-21"]    # the cold recall is the credit
    assert c["due"] > "2030-03-21" and c.get("interval")               # and FSRS takes over from here


def test_a_same_day_answer_after_teaching_stays_uncredited_and_keeps_tomorrow(cfg, t):
    L.taught(cfg, "t", "d:c0", quiet=True)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    c = c0(cfg)
    assert c.get("repeats") == 1 and not c.get("streak") and c["due"] == "2030-03-21"


def test_reteaching_does_not_move_an_existing_schedule(cfg, t, monkeypatch):
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-10")
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    due = c0(cfg)["due"]
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-11")
    L.taught(cfg, "t", "d:c0", quiet=True)
    assert c0(cfg)["due"] == due


def test_a_concept_taught_days_ago_and_never_recalled_is_due_now(cfg, t, monkeypatch):
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-13")
    L.taught(cfg, "t", "d:c0", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-20")
    assert due_ids(cfg) == ["d:c0"]
    assert run(t, "rebuild", "t", "--check")[0] == 0                   # replay applies the same rule


def test_untaught_and_unattempted_concepts_are_not_due(cfg, t):
    assert due_ids(cfg) == []


def test_taught_says_when_the_recall_comes(cfg, t, capsys):
    L.taught(cfg, "t", "d:c0")
    assert "cold recall due 2030-03-21" in capsys.readouterr().out
