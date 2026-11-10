"""Read-only views: dive, foundations, mastery and board."""
import pytest

from kenloop.core import learn as L
from kenloop.core import views as V
from kenloop.core.errors import NOT_EVALUABLE

from conftest import run

SYLLABUS = """# Web

## Concepts
- http :: Request :: what a client sends :: cluster:message
- http :: Response :: what a server sends back :: cluster:message
- http :: Status codes :: three digits that say how it went
"""


@pytest.fixture
def web(cfg, home):
    L.plan(cfg, "web")
    (home / "topics" / "web" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "web", quiet=True)
    L.bank(cfg, "web", "http:request", "What does a request always carry?", "a method and a target",
           "notes.md#request", why="the server needs to know what and where")
    return home / "topics" / "web"


def test_dive_menu_puts_a_confident_miss_first(cfg, web, capsys):
    L.record(cfg, "web", "http:status-codes", "miss", quiet=True)
    L.record(cfg, "web", "http:response", "miss", confidence="high", quiet=True)
    capsys.readouterr()
    assert V.dive(cfg, "web") == 0
    out = capsys.readouterr().out.splitlines()
    assert "http:response" in out[1] and "confident miss" in out[2]
    assert any("http:status-codes" in x for x in out) and any("never right unaided" in x for x in out)


def test_dive_with_nothing_flagged_says_so(cfg, web, capsys):
    V.dive(cfg, "web")
    assert "nothing flagged" in capsys.readouterr().out


def test_dive_on_a_concept_opens_the_answers_and_the_look_alikes(cfg, web, capsys):
    L.record(cfg, "web", "http:request", "miss", note="thinks a body is required", quiet=True)
    L.record(cfg, "web", "http:request", "miss", note="thinks a body is required", quiet=True)
    capsys.readouterr()
    assert V.dive(cfg, "web", "http:request") == 0
    out = capsys.readouterr().out
    assert "recurring misconception (x2): thinks a body is required" in out
    assert "A: a method and a target" in out and "ref: notes.md#request" in out
    assert "Look-alikes (cluster message)" in out and "http:response" in out
    assert "--mode learn" in out


def test_a_check_after_a_dive_earns_no_credit(cfg, home, web):
    assert run(home, "record", "web", "http:request", "ok", "--mode", "learn")[0] == 0
    c = L.load_state(cfg, "web")["concepts"]["http:request"]
    assert c["streak"] == 0 and not c.get("correct_days")


def test_foundations_scaffolds_once_and_then_shows_the_note(cfg, web, capsys):
    V.foundations(cfg, "web")
    assert "0/3 concept(s) have a note" in capsys.readouterr().out
    V.foundations(cfg, "web", "http:request")
    assert "--scaffold" in capsys.readouterr().out
    assert V.foundations(cfg, "web", "http:request", scaffold=True) == 0
    note = web / "foundations" / "http--request.md"
    assert note.exists() and "## Where it stops" in note.read_text()
    note.write_text(note.read_text().replace("(the primitives: what it is, from zero)", "bytes on a socket"))
    capsys.readouterr()
    V.foundations(cfg, "web", "http:request", scaffold=True)          # never overwrites
    assert "bytes on a socket" in capsys.readouterr().out
    V.foundations(cfg, "web")
    assert "1/3 concept(s) have a note" in capsys.readouterr().out


def test_mastery_shows_badges_calibration_and_reasoning(cfg, web, capsys, monkeypatch):
    monkeypatch.setenv("KENLOOP_GRADER", "test-model")
    L.record(cfg, "web", "http:request", "ok", confidence="high", qtype="recall", quiet=True)
    L.record(cfg, "web", "http:response", "partial", mode="dialogue",
             rubric={"chain": 2, "predict": 0, "limits": 2}, quiet=True)
    capsys.readouterr()
    assert V.mastery(cfg, "web") == 0
    out = capsys.readouterr().out
    assert out.startswith("web: 0/3 mastered") and "fair 1" in out and "new 2" in out
    assert "calibration (stated vs right): high 1/1" in out
    assert "reasoning (dialogues, mean of 2): chain 2.0 (n=1)  predict 0.0 (n=1)" in out and "weakest: predict" in out
    assert "by question type: recall 1/1\n" in out           # one type: nothing to call a blind spot


def test_board_lists_every_topic_and_reports_a_damaged_one(cfg, home, web, capsys):
    L.plan(cfg, "history")
    capsys.readouterr()
    assert V.board(cfg) == 0
    out = capsys.readouterr().out
    assert "history" in out and "curiosity" in out and "web" in out
    (web / "concepts.json").write_text("{not json")
    assert V.board(cfg) == NOT_EVALUABLE
    assert "NOT EVALUABLE web" in capsys.readouterr().out


def test_the_cli_runs_the_views(home, web, capsys):
    for argv in (["dive", "web"], ["foundations", "web"], ["mastery", "web"],
                 ["board"]):
        assert run(home, *argv)[0] == 0, argv
