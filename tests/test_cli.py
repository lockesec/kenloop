"""The exit contract: one meaning per code."""
from careerloop import cli

from conftest import run


def test_usage_errors_are_64(home, capsys):
    assert run(home, "jobs", "nope")[0] == 64
    assert run(home, "jobs", "score")[0] == 64
    assert run(home, "jobs", "score", "missing-role", "--fit", "3")[0] == 64
    assert run(home, "learn", "record", "t", "c", "maybe")[0] == 64


def test_missing_home_is_not_evaluable_and_says_how_it_was_resolved(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("CAREERLOOP_HOME", str(tmp_path / "nowhere"))
    assert cli.main(["next"]) == 2
    assert "$CAREERLOOP_HOME" in capsys.readouterr().err


def test_init_is_idempotent(home, capsys):
    (home / "facts.md").write_text("mine")
    assert run(home, "init")[0] == 0
    assert (home / "facts.md").read_text() == "mine"


def test_help_and_version_exit_0(capsys):
    assert cli.main(["--version"]) == 0
    assert cli.main(["--help"]) == 0


def test_rebuild_check_drift_is_3(home, capsys):
    run(home, "learn", "plan", "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: c :: x\n")
    run(home, "learn", "sync", "t")
    run(home, "learn", "record", "t", "d:c", "ok")
    (home / "topics" / "t" / "log.jsonl").write_text("")
    assert run(home, "learn", "rebuild", "t", "--check")[0] == 3
    assert run(home, "doctor")[0] == 3
