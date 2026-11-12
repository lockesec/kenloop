"""Found in use (2026-11-10): a cold miss was only rescheduled as another cold recall the next day,
with nothing to teach it in between. The learner: "if its just back tomorrow when am i supposed to
learn it? a cold miss -> cold miss makes no sense".

Now a miss marks the concept re-teach first: `due` says so, and teaching it sets the next cold recall
for the day after the teaching. An unaided right answer clears the mark; a partial does not set it.

Found in use (2026-11-11): four partials each lacked a piece (what a management group is for, what
`extend` does), got a few lines of correction and came back cold the next day: the same hole in a
milder form. A partial recorded with `--piece` (what it lacked) is marked re-teach first too; a
partial that is only a slip of wording is recorded without it and just comes back.
"""
import pytest

from kenloop.core import integrity as I
from kenloop.core import learn as L
from kenloop.core import reviews as R


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: c0 :: x\n- d :: c1 :: y\n")
    L.sync(cfg, "t", quiet=True)
    return home


def c0(cfg):
    return L.load_state(cfg, "t")["concepts"]["d:c0"]


def test_a_miss_is_marked_re_teach_first_and_due_says_so(cfg, t, monkeypatch, capsys):
    L.record(cfg, "t", "d:c0", "miss", qtype="recall", confidence="low", quiet=True)
    assert c0(cfg)["reteach"] == "2030-03-20"
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    capsys.readouterr()
    R.due(cfg, "t")
    out = capsys.readouterr().out
    assert "d:c0" in out and "RE-TEACH FIRST: missed 2030-03-20" in out and "ken taught t d:c0" in out


def test_teaching_after_a_miss_sets_the_recall_for_the_day_after_the_teaching(cfg, t, monkeypatch):
    L.record(cfg, "t", "d:c0", "miss", qtype="recall", confidence="low", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-25")                    # taught four days later
    L.taught(cfg, "t", "d:c0", quiet=True)
    c = c0(cfg)
    assert "reteach" not in c and c["due"] == "2030-03-26"
    assert "d:c0" not in [cid for cid, _ in R.due_list(cfg, "t")]       # not asked cold the same day


def test_an_unaided_right_answer_clears_it_and_a_partial_never_sets_it(cfg, t, monkeypatch):
    L.record(cfg, "t", "d:c0", "miss", qtype="recall", confidence="low", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    L.record(cfg, "t", "d:c0", "ok", qtype="recall", confidence="med", quiet=True)
    assert "reteach" not in c0(cfg)
    L.record(cfg, "t", "d:c1", "partial", qtype="recall", confidence="med", quiet=True)
    assert "reteach" not in L.load_state(cfg, "t")["concepts"]["d:c1"]


def test_rebuild_from_the_log_gives_the_same_mark(cfg, t):
    L.record(cfg, "t", "d:c0", "miss", qtype="recall", confidence="low", quiet=True)
    before = c0(cfg)["reteach"]
    (cfg.home / "topics" / "t" / "concepts.json").unlink()               # derived state gone: replay the log
    I.rebuild(cfg, "t")
    assert c0(cfg)["reteach"] == before


def test_a_partial_with_a_missing_piece_is_marked_and_due_names_the_piece(cfg, t, monkeypatch, capsys):
    L.record(cfg, "t", "d:c0", "partial", qtype="recall", confidence="med", piece="what flows down", quiet=True)
    c = c0(cfg)
    assert c["reteach"] == "2030-03-20" and c["reteach_piece"] == "what flows down"
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    capsys.readouterr()
    R.due(cfg, "t")
    out = capsys.readouterr().out
    assert "RE-TEACH FIRST: partial on 2030-03-20, missing: what flows down; teach that piece" in out
    L.taught(cfg, "t", "d:c0", quiet=True)
    c = c0(cfg)
    assert "reteach" not in c and "reteach_piece" not in c and c["due"] == "2030-03-22"


def test_a_piece_belongs_to_a_partial_only_and_a_later_miss_drops_it(cfg, t, monkeypatch):
    with pytest.raises(L.UsageError):
        L.record(cfg, "t", "d:c0", "miss", qtype="recall", piece="x", quiet=True)
    with pytest.raises(L.UsageError):
        L.record(cfg, "t", "d:c0", "ok", qtype="recall", piece="x", quiet=True)
    L.record(cfg, "t", "d:c0", "partial", qtype="recall", piece="x", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    L.record(cfg, "t", "d:c0", "miss", qtype="recall", confidence="low", quiet=True)
    c = c0(cfg)
    assert c["reteach"] == "2030-03-21" and "reteach_piece" not in c


def test_rebuild_from_the_log_keeps_the_piece(cfg, t):
    L.record(cfg, "t", "d:c0", "partial", qtype="recall", piece="what flows down", quiet=True)
    (cfg.home / "topics" / "t" / "concepts.json").unlink()
    I.rebuild(cfg, "t")
    assert c0(cfg)["reteach_piece"] == "what flows down"
