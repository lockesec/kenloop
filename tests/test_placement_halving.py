"""Placement narrows by half-splits. A scale is ordered, so each answer bounds where you could start:
above every carried rung, at or below every missed one. The next question goes to the rung that
halves what is left (ALEKS places this way, from Knowledge Space Theory); a rung carried above a
missed one is named as a contradiction, never averaged away. All of it decides where teaching
starts and none of it is credit."""
from kenloop.core import learn as L
from kenloop.core import onramp as O

from test_onramp import SYLLABUS, fv  # noqa: F401  (the fixture)


def _rows(*pairs):
    return [{"rung": k, "result": r} for k, r in pairs]


def test_one_pass_low_on_a_tall_scale_is_not_yet_a_placement():
    st = O.standing(_rows((1, "pass")), 5)
    assert st["start"] == 2                       # the working guess, unchanged
    assert st["feasible"] == (2, 4) and st["probe"] == 3


def test_answers_narrow_until_one_rung_is_left():
    st = O.standing(_rows((1, "pass"), (3, "pass")), 5)
    assert st["feasible"] == (4, 4) and st["probe"] is None and st["start"] == 4
    st = O.standing(_rows((1, "pass"), (3, "miss")), 5)
    assert st["feasible"] == (2, 3) and st["probe"] == 2
    st = O.standing(_rows((1, "pass"), (3, "miss"), (2, "pass")), 5)
    assert st["feasible"] == (3, 3) and st["probe"] is None and st["start"] == 3


def test_a_miss_first_halves_downward():
    st = O.standing(_rows((4, "miss")), 5)
    assert st["feasible"] == (0, 4) and st["probe"] == 2
    st = O.standing(_rows((4, "miss"), (2, "miss")), 5)
    assert st["feasible"] == (0, 2) and st["probe"] == 1


def test_a_single_partial_is_asked_again_before_halving():
    st = O.standing(_rows((1, "pass"), (3, "partial")), 5)
    assert st["probe"] == 3


def test_a_carried_rung_above_a_missed_one_is_a_contradiction_not_an_average():
    st = O.standing(_rows((3, "pass"), (1, "miss")), 5)
    assert st["contradiction"] == (3, 1) and st["feasible"] is None
    assert st["probe"] == 1 and st["start"] == 1


def test_place_prints_the_range_and_the_halving_question(cfg, fv, capsys):  # noqa: F811
    O.place(cfg, "fv", 0, "pass", "why do fuzzers miss bugs?", "they sample")
    out = capsys.readouterr().out
    assert "you could start anywhere on rungs 1-2" in out and "rung 1 (code) halves that" in out
    assert "stopping here is fine" in out


def test_place_names_a_contradiction(cfg, fv, capsys):  # noqa: F811
    O.place(cfg, "fv", 2, "pass", "what is a spec?", "a property for all inputs")
    O.place(cfg, "fv", 0, "miss", "why do fuzzers miss bugs?", "no idea")
    out = capsys.readouterr().out
    assert "your answers disagree: rung 2 (basics) carried above rung 0 (ground) missed" in out


def test_next_asks_the_halving_question_until_study_starts(cfg, fv):  # noqa: F811
    O.place(cfg, "fv", 0, "pass", "p", "a")
    step = O.next_step(cfg, "fv")
    assert step[0] == ["place", "fv"] and "rung 1 halves that" in step[1]
    O.place(cfg, "fv", 1, "miss", "p", "a")
    assert O.next_step(cfg, "fv")[0][0] == "foundations"          # settled: teach rung 1


def test_once_study_has_started_next_does_not_nag_to_narrow(cfg, fv):  # noqa: F811
    O.place(cfg, "fv", 0, "pass", "p", "a")
    L.record(cfg, "fv", "code:undefined-behaviour", "ok", quiet=True)
    step = O.next_step(cfg, "fv")
    assert step is None or step[0][0] != "place"
