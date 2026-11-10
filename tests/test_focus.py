"""Focus: you set what `next` points at (a topic, a lane, or auto), pivot when you want, and every
pivot is kept in focus.jsonl."""
import json

import pytest

from kenloop.core import focus as FO
from kenloop.core import learn as L
from kenloop.core.errors import NotEvaluable, UsageError

from conftest import run


@pytest.fixture
def two(cfg):
    L.plan(cfg, "black-holes")
    L.plan(cfg, "blockchain")
    return cfg


def test_no_focus_is_auto_and_next_says_nothing_about_it(two, home, capsys):
    assert FO.current(two)["focus"] == "auto"
    run(home, "next")
    assert "focus:" not in capsys.readouterr().out


def test_next_answers_inside_the_focus_and_pivots_follow(two, home, capsys):
    run(home, "focus", "black-holes", "--why", "curious tonight")
    capsys.readouterr()
    run(home, "next")
    out = capsys.readouterr().out
    assert out.startswith("NEXT black-holes:") and "focus: black-holes since 2030-03-20" in out
    run(home, "focus", "blockchain")
    capsys.readouterr()
    run(home, "next")
    assert capsys.readouterr().out.startswith("NEXT blockchain:")
    assert [r["focus"] for r in FO.history(two)] == ["black-holes", "blockchain"]
    assert FO.history(two)[0]["why"] == "curious tonight"


def test_explicit_arguments_win_for_one_call_without_moving_the_focus(two, home, capsys):
    run(home, "focus", "black-holes")
    capsys.readouterr()
    run(home, "next", "--topic", "blockchain")
    out = capsys.readouterr().out
    assert out.startswith("NEXT blockchain:") and "focus:" not in out
    assert FO.current(two)["focus"] == "black-holes"


def test_a_lane_focus_and_auto(two, home, capsys):
    run(home, "focus", "interest")
    capsys.readouterr()
    run(home, "next")
    assert capsys.readouterr().out.startswith("NEXT interest:")
    run(home, "focus", "auto")
    capsys.readouterr()
    run(home, "next", "--json")
    assert json.loads(capsys.readouterr().out)["focus"] is None


def test_an_unknown_topic_is_refused_and_a_vanished_one_reads_auto_out_loud(two, home, capsys):
    with pytest.raises(UsageError):
        FO.focus(two, "no-such-topic")
    (home / "focus.jsonl").write_text('{"date": "2030-03-19", "focus": "deleted-topic", "why": ""}\n')
    assert FO.resolve(two) == (None, None, "")
    assert "names no topic any more" in capsys.readouterr().err


def test_a_damaged_focus_ledger_is_not_read_in_part(two, home):
    (home / "focus.jsonl").write_text('{"date": "2030-03-19", "focus": "black-holes"}\nnot json\n')
    with pytest.raises(NotEvaluable):
        FO.current(two)


def test_session_shows_a_focus_elsewhere(two, home, capsys):
    run(home, "focus", "blockchain")
    capsys.readouterr()
    run(home, "session", "black-holes")
    out = capsys.readouterr().out
    assert "focus: blockchain (this session is outside it" in out


def test_doctor_reports_a_focus_on_a_removed_topic(two, home, capsys):
    from kenloop import loop
    (home / "focus.jsonl").write_text('{"date": "2030-03-19", "focus": "deleted-topic", "why": ""}\n')
    capsys.readouterr()
    loop.doctor(two)
    assert "FINDING focus 'deleted-topic' names no topic any more" in capsys.readouterr().out
