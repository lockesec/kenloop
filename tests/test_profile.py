"""ken profile: the curated learner page a tutor reads first; notes since it was updated follow it."""
from kenloop import session as SS
from kenloop.core import learn as L

from conftest import run


def _notes(home, text):
    (home / "learner.md").write_text(text)


def test_scaffold_writes_once_and_profile_prints_it(cfg, home, capsys):
    run(home, "profile")
    assert "no profile yet" in capsys.readouterr().out
    assert run(home, "profile", "--scaffold")[0] == 0
    p = home / "profile.md"
    assert "\nUpdated:\n" in p.read_text() and "## How to teach them" in p.read_text()
    p.write_text("# Learner profile\n\nUpdated: 2030-03-01\n\n## Who\n\nSecurity.\n")
    run(home, "profile", "--scaffold")
    assert "Security." in p.read_text()
    capsys.readouterr()
    run(home, "profile")
    assert "Security." in capsys.readouterr().out


def test_session_shows_the_profile_then_only_newer_notes(cfg, home, capsys):
    L.plan(cfg, "t")
    _notes(home, "# Notes on the learner\n\n## 2030-02-01\n- old rule\n\n## 2030-03-10\n- new rule\n")
    (home / "profile.md").write_text("# Learner profile\n\nUpdated: 2030-03-01\n\n<!-- hide -->\n## Who\n\nSecurity.\n")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "learner profile (updated 2030-03-01):" in out and "Security." in out and "hide" not in out
    assert "2030-03-10: new rule" in out and "old rule" not in out
    assert "learner notes since the profile: 1 (fold them in); 1 older one(s) are in the profile" in out


def test_a_fresh_scaffold_hides_nothing_and_a_same_day_note_shows(cfg, home, capsys):
    L.plan(cfg, "t")
    _notes(home, "# Notes on the learner\n\n## 2030-02-01\n- old rule\n")
    run(home, "profile", "--scaffold")
    capsys.readouterr()
    run(home, "session", "t")
    assert "old rule" in capsys.readouterr().out                  # empty template: every note shows
    (home / "profile.md").write_text("# Learner profile\n\nUpdated: 2030-03-20\n")
    _notes(home, "# Notes on the learner\n\n## 2030-02-01\n- old rule\n\n## 2030-03-20\n- same day rule\n")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "same day rule" in out and "old rule" not in out


def test_a_future_updated_day_is_flagged_and_hides_nothing(cfg, home, capsys):
    L.plan(cfg, "t")
    _notes(home, "# Notes on the learner\n\n## 2030-02-01\n- old rule\n")
    (home / "profile.md").write_text("# Learner profile\n\nUpdated: 2099-01-01\n")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "later than today" in out and "old rule" in out


def test_without_a_profile_every_note_shows_and_without_a_day_none_are_hidden(cfg, home, capsys):
    L.plan(cfg, "t")
    _notes(home, "# Notes on the learner\n\n## 2030-02-01\n- old rule\n")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "no profile yet" in out and "old rule" in out
    (home / "profile.md").write_text("# Learner profile\n\n## Who\n")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "updated on no stated day" in out and "old rule" in out
    assert SS.profile_updated(cfg) == ""


def test_a_directory_named_profile_is_not_read(cfg, home, capsys):
    (home / "profile.md").mkdir()
    assert SS.profile_updated(cfg) == ""
    run(home, "profile")
    assert "no profile yet" in capsys.readouterr().out
