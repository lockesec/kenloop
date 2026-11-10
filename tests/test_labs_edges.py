"""Edges found by a `labs` topic (hands-on demonstrations of theory concepts), 2026-11-04:
#42 a prediction keeps WHAT was predicted (`--mode predict --before`) and `beliefs` shows it beside
what happened; #41 the board shows how the topic's dialogues reasoned, so a strong first day and a
struggling one do not read the same; #38 a lab and its theory concept are linked with `same:`."""
import pytest

from kenloop.core import dialogue as D
from kenloop.core import learn as L
from kenloop.core import views as V
from kenloop.core.errors import UsageError

from conftest import rows, run

SYL = "## Concepts\n- d :: Voice :: a model's outputs as a fingerprint\n- d :: Other :: something else\n"


@pytest.fixture
def t(cfg, home, monkeypatch):
    monkeypatch.setenv("KENLOOP_GRADER", "test-model")
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text(SYL)
    L.sync(cfg, "t", quiet=True)
    return home


# --- #42: a prediction keeps what was predicted -----------------------------------------------

def test_a_prediction_keeps_its_text_and_is_still_never_credited(cfg, t):
    L.record(cfg, "t", "d:voice", "miss", mode="predict", confidence="high",
             belief={"before": "arithmetic gives it away best"}, quiet=True)
    r = rows(t, "t")[-1]
    assert r["mode"] == "predict" and r["before"] == "arithmetic gives it away best"
    c = L.load_state(cfg, "t")["concepts"]["d:voice"]
    assert c["predictions"] == 1 and not c.get("attempts")
    assert L.audit(cfg, "t", L.load_state(cfg, "t"))[0] == []      # replay agrees with record


@pytest.mark.parametrize("extra", [{"belief": {"before": "x", "after": "y"}}, {"rubric": {"chain": 2}},
                                   {"grader": "m"}, {"open_questions": ["why?"]}])
def test_a_prediction_takes_only_before_of_the_dialogue_fields(cfg, t, extra):
    with pytest.raises(UsageError):
        L.record(cfg, "t", "d:voice", "miss", mode="predict", quiet=True, **extra)


def test_the_cli_takes_before_on_a_prediction(cfg, t, capsys):
    code, _ = run(t, "record", "t", "d:voice", "miss", "--mode", "predict", "--before", "haiku worst",
                  capsys=capsys)
    assert code == 0 and rows(t, "t")[-1]["before"] == "haiku worst"


def test_beliefs_shows_each_prediction_beside_what_happened(cfg, t, capsys):
    L.record(cfg, "t", "d:voice", "miss", mode="predict", confidence="high",
             belief={"before": "arithmetic gives it away best"}, quiet=True)
    L.record(cfg, "t", "d:voice", "partial", quiet=True)
    L.record(cfg, "t", "d:other", "ok", mode="predict", quiet=True)          # no text: shown, marked so
    D.beliefs(cfg, "t")
    out = capsys.readouterr().out
    assert "arithmetic gives it away best" in out and "(high)" in out
    assert "then: partial" in out                                             # the next answer on it
    assert "d:other" in out and "no prediction text" in out


# --- #41: the board shows the topic's reasoning -------------------------------------------------

def _dialogue(cfg, cid, scores, result):
    L.record(cfg, "t", cid, result, mode="dialogue", rubric=scores, grader="test-model", quiet=True)


def test_board_shows_reasoning_so_a_strong_and_a_weak_first_day_differ(cfg, t, capsys):
    V.board(cfg)
    assert "reasoning" not in capsys.readouterr().out                         # no dialogue: nothing shown
    _dialogue(cfg, "d:voice", {"chain": 1, "pushback": 0, "limits": 1}, "miss")
    V.board(cfg)
    weak = capsys.readouterr().out
    assert "reasoning 0.7/2 on 1" in weak
    _dialogue(cfg, "d:other", {"chain": 2, "predict": 2, "limits": 2}, "ok")
    V.board(cfg)
    assert "reasoning 1.3/2 on 2" in capsys.readouterr().out                 # the mean of each concept's mean


# --- #38: a lab and its theory concept are one idea with `same:` -------------------------------

def test_a_lab_and_its_theory_concept_link_both_ways_with_same(cfg, home, capsys):
    L.plan(cfg, "math")
    (home / "topics" / "math" / "syllabus.md").write_text(
        "## Concepts\n- probability :: Odds and repeated rolls :: sampling scatters :: same:sampling-scatter\n")
    L.sync(cfg, "math", quiet=True)
    L.plan(cfg, "labs")
    (home / "topics" / "labs" / "syllabus.md").write_text(
        "## Concepts\n- voice :: Many answers one voice :: run it :: same:sampling-scatter\n")
    L.sync(cfg, "labs", quiet=True)
    D.talk(cfg, "math", "probability:odds-and-repeated-rolls")
    assert "the same idea in labs: Many answers one voice" in capsys.readouterr().out
    D.talk(cfg, "labs", "voice:many-answers-one-voice")
    assert "the same idea in math: Odds and repeated rolls" in capsys.readouterr().out
