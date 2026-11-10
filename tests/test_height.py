"""Pyramid height per idea and depth, read from the record; never set, never felt,
never credit. The depth rule: an unaided ok counts for its depth and every shallower one; a miss
counts against its depth and every deeper one."""
import pytest

from kenloop.core import height as HT
from kenloop.core import learn as L


def row(day, result="ok", depth="exam", mode="practice", **kw):
    return {"date": day, "concept": "c", "result": result, "depth": depth, "mode": mode, **kw}


def h(rows, depth="exam"):
    return HT.height_of(rows, depth)[0]


def test_new_heard_held_carried():
    assert h([]) == 0
    assert h([row("2030-03-01", mode="teach")]) == 1
    assert h([row("2030-03-01", mode="predict", result="miss")]) == 1
    assert h([row("2030-03-01", hint_depth=2)]) == 1                        # answered with help
    assert h([row("2030-03-01")]) == 2
    assert h([row("2030-03-01"), row("2030-03-04")]) == 2                    # two in a row, but within a week
    assert h([row("2030-03-01"), row("2030-03-09")]) == 3                    # two in a row, a week apart


def test_a_same_day_answer_after_teaching_never_raises_height():
    assert h([row("2030-03-01", mode="teach"), row("2030-03-01")]) == 1      # a repeat: short-term memory


def test_a_miss_steps_down_one_and_the_streak_re_earns_it():
    carried = [row("2030-03-01"), row("2030-03-09")]
    assert h(carried + [row("2030-03-10", "miss")]) == 2
    assert h([row("2030-03-01"), row("2030-03-02", "miss")]) == 1
    assert h(carried + [row("2030-03-10", "miss"), row("2030-03-11"), row("2030-03-19")]) == 3


def test_the_depth_rule_both_directions():
    deep_ok = [row("2030-03-01", depth="mechanism")]
    assert h(deep_ok, "exam") == 2 and h(deep_ok, "mechanism") == 2 and h(deep_ok, "first-principles") == 1
    shallow_ok = [row("2030-03-01", depth="exam")]
    assert h(shallow_ok, "mechanism") == 1                                   # says nothing about mechanism
    held = [row("2030-03-01", depth="mechanism")]
    assert h(held + [row("2030-03-02", "miss", depth="first-principles")], "exam") == 2   # deeper miss: exam stands
    assert h(held + [row("2030-03-02", "miss", depth="exam")], "mechanism") == 1          # shallower miss: breaks it


def test_old_rows_without_depth_read_their_declared_default():
    assert h([{"date": "2030-03-01", "concept": "c", "result": "ok"}], "exam") == 2
    assert h([{"date": "2030-03-01", "concept": "c", "result": "ok"}], "mechanism") == 1


@pytest.fixture
def twins(cfg, home):
    for slug, line in (("crypto", "- sym :: Symmetric :: one key :: same:sym\n"),
                       ("sec", "- g :: 1.4 Symmetric :: AES :: same:sym\n")):
        L.plan(cfg, slug)
        (home / "topics" / slug / "syllabus.md").write_text("# X\n\n## Concepts\n" + line)
        L.sync(cfg, slug, quiet=True)
    return cfg


def test_one_idea_one_height_across_twins_and_no_credit_moves(twins, monkeypatch):
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-01")
    L.record(twins, "sec", "g:1-dot-4-symmetric", "ok", quiet=True)
    assert HT.height(twins, "crypto", "sym:symmetric")[:2] == (2, "held")
    assert not L.load_state(twins, "crypto")["concepts"]["sym:symmetric"].get("streak")
