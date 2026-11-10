"""Marks and the trail: what you say feels like a problem moves what comes next and never credit;
the trail always names the way back; a prediction made when adding a piece is graded against marks."""
import json

import pytest

from kenloop.core import learn as L
from kenloop.core import marks as M
from kenloop.core.errors import NotEvaluable, UsageError

from conftest import run


@pytest.fixture
def topic(cfg, home):
    L.plan(cfg, "maths")
    syl = home / "topics" / "maths" / "syllabus.md"
    syl.write_text(syl.read_text() + "".join(f"- sums :: {n} :: what {n} is\n" for n in ("one", "two", "three")))
    L.sync(cfg, "maths", quiet=True)
    return cfg


def test_a_problem_mark_leads_the_frontier_and_next_says_why(topic, home, capsys):
    run(home, "next", "--topic", "maths")
    assert "sums:one" in capsys.readouterr().out
    run(home, "mark", "maths", "two", "problem", "--why", "lost here")
    capsys.readouterr()
    run(home, "next", "--topic", "maths")
    out = capsys.readouterr().out
    assert "sums:two" in out and "you marked it problem" in out
    run(home, "map", "maths")
    assert "you marked problem" in capsys.readouterr().out


def test_solid_goes_last_and_clear_takes_a_mark_back(topic, home, capsys):
    from kenloop.core import graph as SG
    run(home, "mark", "maths", "one", "solid")
    assert [n.cid for n in SG.frontier(SG.build(topic, "maths"))][-1] == "sums:one"
    run(home, "mark", "maths", "one", "clear")
    assert M.current(topic, "maths") == {}
    assert [n.cid for n in SG.frontier(SG.build(topic, "maths"))][0] == "sums:one"


def test_a_mark_moves_no_credit(topic, home):
    before = json.dumps(L.load_state(topic, "maths")["concepts"], sort_keys=True)
    log = home / "topics" / "maths" / "log.jsonl"
    had = log.read_text() if log.exists() else ""
    assert run(home, "mark", "maths", "one", "solid")[0] == 0
    assert json.dumps(L.load_state(topic, "maths")["concepts"], sort_keys=True) == before
    assert (log.read_text() if log.exists() else "") == had
    assert run(home, "rebuild", "maths", "--check")[0] == 0


def test_a_mark_follows_a_renamed_concept(topic, home):
    run(home, "mark", "maths", "one", "problem")
    syl = home / "topics" / "maths" / "syllabus.md"
    syl.write_text(syl.read_text().replace("- sums :: one ::", "- sums :: uno ::"))
    L.sync(topic, "maths", quiet=True)
    assert run(home, "rename", "maths", "sums:one", "sums:uno")[0] == 0
    assert M.current(topic, "maths") == {"sums:uno": "problem"}


def test_a_mark_on_an_unknown_concept_is_refused_and_damage_is_named(topic, home, capsys):
    with pytest.raises(UsageError):
        M.mark(topic, "maths", "nothing-like-this", "problem")
    p = home / "topics" / "maths" / "marks.jsonl"
    p.write_text("{broken\n")
    with pytest.raises(NotEvaluable):
        M.mark(topic, "maths", "one", "problem")
    assert run(home, "map", "maths")[0] == 2
    assert "DAMAGED" in capsys.readouterr().out


def test_the_trail_goes_down_comes_back_and_shows_in_the_session(topic, home, capsys):
    run(home, "trail")
    assert "empty" in capsys.readouterr().out
    run(home, "trail", "maths", "one", "--why", "started here")
    run(home, "trail", "maths", "two", "--why", "needed for one")
    capsys.readouterr()
    run(home, "trail")
    out = capsys.readouterr().out
    assert out.index("sums:one") < out.index("sums:two") and "needed for one" in out
    run(home, "session", "maths")
    assert "maths/sums:one > maths/sums:two" in capsys.readouterr().out
    run(home, "trail", "--back")
    assert "back to maths/sums:one" in capsys.readouterr().out
    run(home, "trail", "--back")
    assert "trail is empty" in capsys.readouterr().out
    with pytest.raises(UsageError):
        M.back(topic)
    run(home, "session", "maths")
    assert "trail:" not in capsys.readouterr().out


def test_a_damaged_trail_cannot_be_read_in_part(topic, home):
    (home / "trail.jsonl").write_text('{"date": "2030-03-20", "event": "sideways"}\n')
    with pytest.raises(NotEvaluable):
        M.stack(topic)


def test_a_prediction_is_graded_against_later_marks(topic, home, capsys):
    run(home, "branch", "maths", "one", "sums :: guess right :: x", "--by", "tutor", "--predict", "problem")
    run(home, "branch", "maths", "one", "sums :: guess wrong :: x", "--by", "tutor", "--predict", "solid")
    run(home, "branch", "maths", "one", "sums :: unmarked :: x", "--by", "tutor", "--predict", "solid")
    capsys.readouterr()
    run(home, "branch", "maths")
    assert "3 made, 0 marked since, none to grade yet" in capsys.readouterr().out
    run(home, "mark", "maths", "guess-right", "fuzzy")
    run(home, "mark", "maths", "guess-wrong", "problem")
    capsys.readouterr()
    run(home, "branch", "maths")
    assert "3 made, 2 marked since, 1/2 right" in capsys.readouterr().out


def test_a_prediction_goes_only_with_a_piece_or_a_before(topic):
    from kenloop.core import onramp as O
    with pytest.raises(UsageError, match="--predict"):
        O.branch(topic, "maths", "one", "sums :: x :: y", topic="elsewhere", by="tutor", predict="solid")
    with pytest.raises(UsageError, match="--predict"):
        O.branch(topic, "maths", "one", note="just a note", by="tutor", predict="solid")


def test_a_new_topic_says_where_its_first_concept_landed(topic, home, capsys):
    run(home, "branch", "maths", "one", "Loose :: first :: x", "--by", "learner", "--topic", "grown")
    out = capsys.readouterr().out
    assert "domain 'Loose'" in out and "rename" in out


def _torn_marks(home):
    p = home / "topics" / "maths" / "marks.jsonl"
    p.write_text(p.read_text() + '{"date": "2030-03-20", "concept": "sums:two", "mark": "cl')


def test_damaged_marks_are_named_by_doctor_and_next_and_steer_nothing(topic, home, capsys):
    run(home, "mark", "maths", "two", "problem")
    _torn_marks(home)
    capsys.readouterr()
    assert M.current(topic, "maths") == {}
    code, _ = run(home, "next", "--topic", "maths")
    out = capsys.readouterr().out
    assert "you marked it problem" not in out and "validate" in out
    run(home, "session", "maths")
    out = capsys.readouterr().out
    assert "you marked as a problem" not in out and "DAMAGED" in out
    assert run(home, "doctor")[0] != 0
    assert "marks.jsonl" in capsys.readouterr().out
    assert run(home, "validate", "maths")[0] != 0


def _rename_one(topic, home):
    syl = home / "topics" / "maths" / "syllabus.md"
    syl.write_text(syl.read_text().replace("- sums :: one ::", "- sums :: uno ::"))
    L.sync(topic, "maths", quiet=True)
    assert run(home, "rename", "maths", "sums:one", "sums:uno")[0] == 0


def test_a_prediction_follows_a_renamed_piece(topic, home, capsys):
    run(home, "branch", "maths", "two", "sums :: guess :: x", "--by", "tutor", "--predict", "problem")
    run(home, "mark", "maths", "guess", "problem")
    syl = home / "topics" / "maths" / "syllabus.md"
    syl.write_text(syl.read_text().replace("- sums :: guess ::", "- sums :: hunch ::"))
    L.sync(topic, "maths", quiet=True)
    assert run(home, "rename", "maths", "sums:guess", "sums:hunch")[0] == 0
    capsys.readouterr()
    run(home, "branch", "maths")
    assert "1 made, 1 marked since, 1/1 right" in capsys.readouterr().out


def test_the_trail_names_a_renamed_concept(topic, home, capsys):
    run(home, "trail", "maths", "one")
    run(home, "trail", "maths", "two")
    _rename_one(topic, home)
    capsys.readouterr()
    run(home, "trail")
    assert "maths/sums:uno" in capsys.readouterr().out
    run(home, "session", "maths")
    assert "maths/sums:uno > maths/sums:two" in capsys.readouterr().out
    run(home, "trail", "--back")
    assert "back to maths/sums:uno" in capsys.readouterr().out


def test_a_damaged_trail_does_not_stop_a_session_and_doctor_names_it(topic, home, capsys):
    (home / "trail.jsonl").write_text("{torn\n")
    code, _ = run(home, "session", "maths")
    assert code == 0 and "DAMAGED" in capsys.readouterr().out
    assert run(home, "doctor")[0] != 0
    assert "trail.jsonl" in capsys.readouterr().out


def test_a_why_cannot_drive_the_terminal(topic, home, capsys):
    run(home, "trail", "maths", "one", "--why", "x\x1b[2Jy\nz")
    capsys.readouterr()
    run(home, "trail")
    out = capsys.readouterr().out
    assert "\x1b" not in out and "x [2Jy z" in out


def test_a_failed_attempt_overrules_a_solid_mark(topic, home, capsys):
    from kenloop.core import graph as SG
    run(home, "mark", "maths", "one", "solid")
    assert [n.cid for n in SG.frontier(SG.build(topic, "maths"))][-1] == "sums:one"
    assert run(home, "record", "maths", "one", "miss")[0] == 0
    order = [n.cid for n in SG.frontier(SG.build(topic, "maths"))]
    assert order[0] == "sums:one"
    capsys.readouterr()
    run(home, "map", "maths")
    assert "you marked solid, then missed it" in capsys.readouterr().out


def test_a_guess_before_teaching_does_not_overrule_a_solid_mark(topic, home):
    from kenloop.core import graph as SG
    run(home, "mark", "maths", "one", "solid")
    assert run(home, "record", "maths", "one", "miss", "--mode", "predict")[0] == 0
    assert [n.cid for n in SG.frontier(SG.build(topic, "maths"))][-1] == "sums:one"


def test_a_solid_prediction_is_wrong_when_a_miss_overrules_the_mark(topic, home, capsys):
    run(home, "branch", "maths", "one", "sums :: kid :: x", "--by", "tutor", "--predict", "solid")
    run(home, "mark", "maths", "kid", "solid")
    assert run(home, "record", "maths", "kid", "miss")[0] == 0
    capsys.readouterr()
    run(home, "branch", "maths")
    assert "1 made, 1 marked since, 0/1 right" in capsys.readouterr().out


def test_a_later_success_lifts_the_overrule(topic, home, monkeypatch):
    run(home, "mark", "maths", "one", "solid")
    run(home, "record", "maths", "one", "miss")
    assert "sums:one" in M.overruled(topic, "maths")
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    run(home, "record", "maths", "one", "ok")
    assert M.overruled(topic, "maths") == {}


def test_massed_practice_does_not_overrule_a_solid_mark(topic, home):
    run(home, "mark", "maths", "one", "solid")
    assert run(home, "record", "maths", "one", "miss", "--mode", "learn")[0] == 0
    assert M.overruled(topic, "maths") == {}


def test_marking_solid_says_when_a_miss_still_outweighs_it(topic, home, capsys):
    run(home, "record", "maths", "one", "miss")
    capsys.readouterr()
    run(home, "mark", "maths", "one", "solid")
    assert "still outweighs" in capsys.readouterr().out


def test_doctor_names_a_trail_step_into_a_missing_topic(topic, home, capsys):
    (home / "trail.jsonl").write_text('{"date": "2030-03-20", "event": "down", "topic": "gone", "concept": "x:y"}\n')
    capsys.readouterr()
    assert run(home, "doctor")[0] != 0
    assert "trail" in capsys.readouterr().out


def test_a_failed_graded_dialogue_overrules_a_solid_mark(topic, home, capsys):
    run(home, "mark", "maths", "one", "solid")
    code, _ = run(home, "record", "maths", "one", "miss", "--mode", "dialogue", "--grader", "tester",
                  "--rubric", "chain=0,limits=0,question=0")
    assert code == 0
    assert "sums:one" in M.overruled(topic, "maths")
    assert L.load_state(topic, "maths")["concepts"]["sums:one"].get("streak", 0) == 0
    run(home, "record", "maths", "one", "ok", "--mode", "dialogue", "--grader", "tester",
        "--rubric", "chain=2,limits=2,question=2")
    assert M.overruled(topic, "maths") == {}
