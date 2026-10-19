"""Command-line output: error prefixes, console encodings and what init says."""
import io

from careerloop import cli
from conftest import run


# --- Command-line output --------------------------------------------------------------------------

def test_a_legacy_console_does_not_crash_after_writing(home, monkeypatch):
    buf = io.BytesIO()
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(buf, encoding="cp1252"))
    cli.main(["--home", str(home), "jobs", "intake", "--company", "A", "--role", "B"])
    assert cli.main(["--home", str(home), "jobs", "status", "a-b", "applied"]) == 0


def test_init_names_the_facts_it_recreated(tmp_path, capsys):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    capsys.readouterr()
    assert cli.main(["--home", str(h), "init"]) == 0
    assert "recreated" not in capsys.readouterr().out
    (h / "facts.md").unlink()
    assert cli.main(["--home", str(h), "init"]) == 0
    out = capsys.readouterr().out
    assert "recreated facts.md" in out and (h / "facts.md").exists()


def test_error_prefixes_are_not_doubled(home, capsys):
    code, out = run(home, "--bogus-flag", capsys=capsys)
    assert code == 64 and "careerloop: careerloop" not in out.err
    code, out = run(home, "jobs", capsys=capsys)
    assert code == 64 and "careerloop: careerloop" not in out.err
    code, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "nonexist", capsys=capsys)
    line = [x for x in out.out.splitlines() if x.startswith("ERROR")][0]
    assert line.count("fixture:nonexist") == 1
