"""Questions and their ladders: a question records rungs, reuses what is on the map, and the
record (asks.jsonl) is checked like a topic log: a line that cannot be read is never skipped."""
import pytest

from kenloop.core import learn as L
from kenloop.core import questions as Q
from kenloop.core.errors import NOT_EVALUABLE, UsageError

from conftest import run

SYLLABUS = """# Black holes

## Concepts
- spacetime :: Event horizon :: the surface light cannot climb out of
"""
EH = "spacetime:event-horizon"


@pytest.fixture
def bh(cfg, home):
    L.plan(cfg, "bh")
    (home / "topics" / "bh" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "bh", quiet=True)
    return home / "topics" / "bh"


def test_ask_finds_rungs_on_the_map_and_rung_builds_the_ladder(cfg, home, bh, capsys):
    assert Q.ask(cfg, "why does a horizon trap light?") == 0
    out = capsys.readouterr().out
    assert out.startswith("q1:") and f"bh/{EH}" in out                  # the shared rung is surfaced
    assert Q.rung(cfg, "q1", "bh", existing=EH) == 0
    assert Q.rung(cfg, "q1", "bh", "foundations :: Photons :: light as particles that carry energy") == 0
    assert "foundations:photons" in L.load_state(cfg, "bh")["concepts"]  # synced into state
    capsys.readouterr()
    assert Q.ask(cfg) == 0
    out = capsys.readouterr().out
    assert f"bh/{EH}" in out and "bh/foundations:photons" in out and "climbed 0/2" in out


def test_climbing_counts_good_or_better(cfg, home, bh, capsys, monkeypatch):
    Q.ask(cfg, "what is a horizon?")
    Q.rung(cfg, "q1", "bh", existing=EH)
    for day in ("2030-03-20", "2030-03-22"):
        monkeypatch.setenv("KENLOOP_TODAY", day)
        L.record(cfg, "bh", EH, "ok", quiet=True)
    capsys.readouterr()
    Q.ask(cfg)
    assert "climbed 1/1" in capsys.readouterr().out


def test_rung_refuses_a_twin_a_bad_line_and_an_unknown_question_without_writing(cfg, home, bh):
    Q.ask(cfg, "what is a horizon?")
    before = (bh / "syllabus.md").read_text()
    with pytest.raises(UsageError, match=f"bh/{EH} already exists"):
        Q.rung(cfg, "q1", "bh", "holes :: Event horizon :: again")          # a twin across domains
    with pytest.raises(UsageError, match="unknown status"):
        Q.rung(cfg, "q1", "bh", "holes :: X :: y :: status:maybe")
    with pytest.raises(UsageError, match="no question 'q9'"):
        Q.rung(cfg, "q9", "bh", existing=EH)
    assert (bh / "syllabus.md").read_text() == before
    assert [e["event"] for e in Q.read(cfg)[0]] == ["ask"]


def test_ask_alone_with_no_questions_says_so(cfg, capsys):
    assert Q.ask(cfg) == 0
    assert "no questions asked yet" in capsys.readouterr().out


def test_a_damaged_line_is_reported_by_ask_validate_and_doctor(cfg, home, bh, capsys):
    Q.ask(cfg, "what is a horizon?")
    with open(Q.path(cfg), "a") as fh:
        fh.write('{"event": "ask", "id": "q2"\n')
    capsys.readouterr()
    assert Q.ask(cfg) == NOT_EVALUABLE
    assert "1 unreadable line(s)" in capsys.readouterr().out
    assert Q.ask(cfg, "another?") == NOT_EVALUABLE                         # numbering needs the whole record
    assert len(Q.read(cfg)[0]) == 1                                        # nothing appended
    code, out = run(home, "validate", capsys=capsys)
    assert code == NOT_EVALUABLE and "asks.jsonl line 2" in out.out
    code, out = run(home, "doctor", capsys=capsys)
    assert code == NOT_EVALUABLE and "asks.jsonl line 2" in out.out


def test_init_merges_the_questions_file_by_union(home):
    assert "asks.jsonl merge=union" in (home / ".gitattributes").read_text()


def test_the_cli_runs_the_ladder(cfg, home, bh, capsys):
    assert run(home, "ask", "why does a horizon trap light?")[0] == 0
    assert run(home, "rung", "q1", "bh", "--existing", EH)[0] == 0
    code, out = run(home, "ask", capsys=capsys)
    assert code == 0 and "climbed 0/1" in out.out
