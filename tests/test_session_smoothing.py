"""Rough edges found while studying with the tool: a profile brought up to date the same day a note
was written, a second look at a session, a scale with empty rungs, a note that repeats its day."""
import pytest

from kenloop.core import learn as L
from kenloop.core import onramp as O

from conftest import run

NOTES = "# Notes on the learner\n\n## 2030-02-01\n- old rule\n\n## {day}\n- same day rule\n"
SYLLABUS = """# Cloud

## Path

0. **ground** — how it is organised
1. **services** — what you build with
2. **rules** — keeping it in bounds

## Concepts
- ground :: The tree :: levels and what flows down
"""


def _today():
    from kenloop.core import home as H
    return H.today().isoformat()


@pytest.fixture
def cloud(cfg, home):
    L.plan(cfg, "cloud")
    (home / "topics" / "cloud" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "cloud", quiet=True)
    return home


def test_folded_hides_a_note_written_the_day_the_profile_was_updated(cfg, home, capsys):
    L.plan(cfg, "t")
    (home / "learner.md").write_text(NOTES.format(day=_today()))
    (home / "profile.md").write_text(f"# Learner profile\n\nUpdated: {_today()}\n\n## Who\n\nSecurity.\n")
    capsys.readouterr()
    run(home, "session", "t")
    assert "same day rule" in capsys.readouterr().out          # the control: by day alone it shows
    assert run(home, "profile", "--folded")[0] == 0
    text = (home / "profile.md").read_text()
    assert f"Updated: {_today()}\nFolded: 2\n" in text and "Security." in text
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "same day rule" not in out and "Folded" not in out
    assert "learner notes since the profile: none; 2 older one(s) are in the profile" in out


def test_a_note_written_after_folding_shows_and_folding_again_is_stable(cfg, home, capsys):
    L.plan(cfg, "t")
    (home / "learner.md").write_text(NOTES.format(day=_today()))
    (home / "profile.md").write_text("# Learner profile\n\nUpdated: 2030-01-01\n")
    run(home, "profile", "--folded")
    run(home, "note", "--learner", "a later rule")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "a later rule" in out and "same day rule" not in out
    assert "learner notes since the profile: 1 (fold them in); 2 older" in out
    run(home, "profile", "--folded")
    run(home, "profile", "--folded")
    assert (home / "profile.md").read_text().count("Folded: 3\n") == 1
    assert (home / "profile.md").read_text().count("Updated:") == 1


def test_a_folded_count_larger_than_the_notes_is_not_trusted(cfg, home, capsys):
    L.plan(cfg, "t")
    (home / "learner.md").write_text(NOTES.format(day=_today()))
    (home / "profile.md").write_text(f"# Learner profile\n\nUpdated: {_today()}\nFolded: 9\n")
    capsys.readouterr()
    run(home, "session", "t")
    assert "same day rule" in capsys.readouterr().out          # notes were removed: the day rule holds


def test_folded_without_a_profile_or_an_updated_line(cfg, home, capsys):
    code, out = run(home, "profile", "--folded", capsys=capsys)
    assert code != 0 and "no profile yet" in out.err and not (home / "profile.md").exists()
    (home / "profile.md").write_text("# Learner profile\n\n## Who\n")
    run(home, "profile", "--folded")
    assert (home / "profile.md").read_text().startswith(f"# Learner profile\n\nUpdated: {_today()}\nFolded: 0\n")


def test_brief_leaves_the_profile_text_out_and_keeps_new_notes(cfg, home, capsys):
    L.plan(cfg, "t")
    (home / "learner.md").write_text("# Notes on the learner\n\n## 2030-03-10\n- new rule\n")
    (home / "profile.md").write_text("# Learner profile\n\nUpdated: 2030-03-01\n\n## Who\n\nSecurity.\n")
    capsys.readouterr()
    run(home, "session", "t")
    assert "Security." in capsys.readouterr().out
    run(home, "session", "t", "--brief")
    out = capsys.readouterr().out
    assert "Security." not in out and "2 line(s), not shown (--brief)" in out and "new rule" in out


def test_empty_rungs_are_named_by_place_and_session(cfg, cloud, capsys):
    assert O.empty_rungs(L.load_state(cfg, "cloud")["concepts"], O.rungs(cfg, "cloud")) == [1, 2]
    capsys.readouterr()
    run(cloud, "place", "cloud")
    out = capsys.readouterr().out
    line = ("2 of 3 rung(s) have no concepts yet (1 services, 2 rules): add a line under ## Concepts in "
            "syllabus.md, then `ken sync cloud`, before placing")
    assert line in out and "--start 0` starts from the ground up" in out
    run(cloud, "session", "cloud")
    assert line in capsys.readouterr().out


def test_a_full_scale_says_nothing_about_empty_rungs(cfg, cloud, capsys):
    p = cloud / "topics" / "cloud" / "syllabus.md"
    p.write_text(p.read_text() + "- services :: Compute :: machines\n- rules :: Policy :: what may exist\n")
    L.sync(cfg, "cloud", quiet=True)
    capsys.readouterr()
    run(cloud, "place", "cloud")
    run(cloud, "session", "cloud")
    assert "have no concepts yet" not in capsys.readouterr().out


def test_a_note_that_opens_with_todays_date_does_not_repeat_it(cfg, home, capsys):
    run(home, "note", "--learner", f"{_today()}: wants the table first")
    run(home, "note", "--learner", "2001-01-01: an older day is his own text")
    text = (home / "learner.md").read_text()
    assert "- wants the table first\n" in text and "- 2001-01-01: an older day is his own text\n" in text
    code, out = run(home, "note", "--learner", f"{_today()}:", capsys=capsys)
    assert code != 0 and "needs text" in out.err and (home / "learner.md").read_text() == text


def test_the_foundations_scaffold_asks_for_a_say_back_and_what_was_read(cfg, cloud):
    run(cloud, "foundations", "cloud", "ground:the-tree", "--scaffold")
    text = (cloud / "topics" / "cloud" / "foundations" / "ground--the-tree.md").read_text()
    assert "## Their say-back" in text and "- Read on (date):" in text and "- From memory, not checked:" in text
    assert "Write it BEFORE teaching" in text
