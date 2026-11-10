"""A concept answered today waits until tomorrow in `quiz`: a second answer the same day is counted
but never credited (learn.repeats), so asking it again earns nothing. Anki buries a card's
siblings until the next day for the same reason. kenloop names what it held back."""
import io

from conftest import run
from kenloop.core import home as H
from kenloop.core import learn as L


def _topic(home):
    run(home, "plan", "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: a :: x\n- d :: b :: y\n")
    run(home, "sync", "t")


def _asked(out):
    return [ln.split()[1] for ln in out.splitlines() if ln.startswith("- ")]


def test_an_answered_concept_is_held_and_named(home, capsys):
    _topic(home)
    run(home, "record", "t", "d:a", "ok")
    code, out = run(home, "quiz", "t", capsys=capsys)
    assert code == 0
    assert _asked(out.out) == ["d:b"]
    assert "held until tomorrow: 1 concept(s)" in out.out and "d:a" in out.out


def test_a_miss_is_held_too(home, capsys):
    _topic(home)
    run(home, "record", "t", "d:a", "miss")
    assert "d:a" not in _asked(run(home, "quiz", "t", capsys=capsys)[1].out)


def test_it_comes_back_tomorrow(home, capsys, monkeypatch):
    _topic(home)
    run(home, "record", "t", "d:a", "miss")
    tomorrow = H.today().fromordinal(H.today().toordinal() + 1).isoformat()
    monkeypatch.setenv("KENLOOP_TODAY", tomorrow)
    out = run(home, "quiz", "t", capsys=capsys)[1].out
    assert "d:a" in _asked(out) and "held until tomorrow" not in out


def test_naming_the_concept_asks_it_anyway(home, capsys):
    _topic(home)
    run(home, "record", "t", "d:a", "ok")
    out = run(home, "quiz", "t", "--concept", "d:a", capsys=capsys)[1].out
    assert _asked(out) == ["d:a"] and "held until tomorrow" not in out


def test_all_answered_says_so_instead_of_an_empty_list(home, capsys):
    _topic(home)
    run(home, "record", "t", "d:a", "ok")
    run(home, "record", "t", "d:b", "ok")
    code, out = run(home, "quiz", "t", capsys=capsys)
    assert code == 0 and _asked(out.out) == []
    assert "held until tomorrow: 2 concept(s)" in out.out and "nothing left to ask in t today" in out.out


def test_the_interactive_quiz_holds_them_too(home, cfg, capsys):
    _topic(home)
    run(home, "bank", "t", "d:a", "--q", "Q a?", "--a", "A a", "--ref", "r")
    run(home, "bank", "t", "d:b", "--q", "Q b?", "--a", "A b", "--ref", "r")
    run(home, "record", "t", "d:a", "ok")
    out = io.StringIO()
    L.quiz_interactive(cfg, "t", inp=io.StringIO(""), out=out)
    text = out.getvalue()
    assert "held until tomorrow: 1 concept(s)" in text and "Q a?" not in text and "Q b?" in text
