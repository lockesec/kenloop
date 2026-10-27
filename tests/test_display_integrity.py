"""Plan finding 0.6: the displays print from the derived concepts.json, so they must say when it
cannot be trusted. Drift (concepts.json disagrees with a replay of the log) exits 3, a damaged log
row exits 2, after the normal output; `record` refuses to append to a damaged log."""
import pytest

from conftest import run

DISPLAYS = [("mastery", "t"), ("due", "t"), ("due",), ("board",), ("quiz", "t")]


def _topic(home):
    run(home, "plan", "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: a :: x\n- d :: b :: y\n")
    run(home, "sync", "t")
    run(home, "record", "t", "d:a", "ok")


def _drift(home):
    (home / "topics" / "t" / "log.jsonl").write_text("")      # concepts.json still holds the answer


def _damage(home):
    with open(home / "topics" / "t" / "log.jsonl", "a") as fh:
        fh.write("{not json\n")


@pytest.mark.parametrize("argv", DISPLAYS)
def test_a_clean_record_exits_0(home, capsys, argv):
    _topic(home)
    code, out = run(home, *argv, capsys=capsys)
    assert code == 0 and "DRIFT" not in out.err and "damaged" not in out.err, (argv, out)


@pytest.mark.parametrize("argv", DISPLAYS)
def test_drift_prints_then_exits_3(home, capsys, argv):
    _topic(home)
    _drift(home)
    code, out = run(home, *argv, capsys=capsys)
    assert code == 3, (argv, out)
    assert out.out.strip() and "DRIFT" in out.err and "d:a" in out.err and "rebuild t" in out.err


@pytest.mark.parametrize("argv", DISPLAYS)
def test_a_damaged_log_prints_then_exits_2(home, capsys, argv):
    _topic(home)
    _damage(home)
    code, out = run(home, *argv, capsys=capsys)
    assert code == 2, (argv, out)
    assert out.out.strip() and "damaged log row" in out.err


def test_rebuild_clears_the_drift(home, capsys):
    _topic(home)
    _drift(home)
    run(home, "rebuild", "t")
    assert run(home, "mastery", "t", capsys=capsys)[0] == 0


def test_record_refuses_a_damaged_log_and_appends_nothing(home, capsys):
    _topic(home)
    _damage(home)
    log = home / "topics" / "t" / "log.jsonl"
    before = log.read_bytes()
    code, out = run(home, "record", "t", "d:b", "ok", capsys=capsys)
    assert code == 2 and "nothing recorded" in (out.out + out.err)
    assert log.read_bytes() == before


def test_record_works_again_once_the_line_is_fixed(home, capsys):
    _topic(home)
    _damage(home)
    log = home / "topics" / "t" / "log.jsonl"
    log.write_text("".join(x for x in log.read_text().splitlines(True) if x.startswith('{"')))
    assert run(home, "record", "t", "d:b", "ok", capsys=capsys)[0] == 0
