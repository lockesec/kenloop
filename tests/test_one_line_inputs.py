"""A value that becomes one line of a Markdown file is refused when it holds a line break: a
newline in `bank --q` once wrote a second `## concept` section and a question under the wrong
concept, and a newline in `branch` added two concepts and named the wrong one as the piece."""
import pytest

from kenloop import cli

from conftest import run


def _topic(home):
    assert cli.main(["--home", str(home), "plan", "t1", "--goal", "g"]) == 0
    (home / "topics" / "t1" / "syllabus.md").write_text(
        "## Concepts\n- net :: Alpha :: a\n- net :: Beta :: b\n")
    assert cli.main(["--home", str(home), "sync", "t1"]) in (0, 1)


@pytest.mark.parametrize("flag,value", [
    ("--q", "What?\n## net:beta\n### Q: injected"),
    ("--a", "A1\n- **A:** other"),
    ("--ref", "r\nr2"),
    ("--why", "because\r## x"),
])
def test_bank_refuses_a_line_break_and_writes_nothing(home, flag, value):
    _topic(home)
    qs = home / "topics" / "t1" / "questions.md"
    before = qs.read_text() if qs.exists() else None
    args = {"--q": "What?", "--a": "A1", "--ref": "r", "--why": ""}
    args[flag] = value
    argv = ["bank", "t1", "net:alpha"] + [x for k, v in args.items() if v for x in (k, v)]
    code, _ = run(home, *argv)
    assert code == 64
    assert (qs.read_text() if qs.exists() else None) == before


def test_bank_still_takes_one_line_values(home):
    _topic(home)
    code, _ = run(home, "bank", "t1", "net:alpha", "--q", "What?", "--a", "A1", "--ref", "r")
    assert code == 0
    assert run(home, "validate", "t1")[0] == 0


def test_branch_refuses_a_line_break_and_writes_nothing(home):
    _topic(home)
    syl = home / "topics" / "t1" / "syllabus.md"
    before = syl.read_text()
    code, _ = run(home, "branch", "t1", "net:alpha", "net :: Piece :: d\n- net :: Sneak :: x",
                  "--by", "learner")
    assert code == 64 and syl.read_text() == before
