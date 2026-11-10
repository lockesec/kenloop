"""Gaps an independent verification pass found, each pinned by a test that failed first."""
import json
from pathlib import Path

import pytest

from kenloop import cli
from kenloop.career import sources as S
from kenloop.core import ledger as LG, learn as L
from kenloop.core import home as hm
from kenloop.core.errors import UsageError

from conftest import run


def _topic(home, concepts=("a", "b")):
    assert run(home, "plan", "t")[0] == 0
    p = home / "topics" / "t" / "syllabus.md"
    text = p.read_text().rstrip() + "\n"
    for c in concepts:
        text += f"- d :: {c} :: about {c}\n"
    p.write_text(text)
    assert run(home, "sync", "t")[0] == 0


# --- a same-day repeat on a concept with no earlier quiz -----------------------------------

@pytest.mark.parametrize("first", [["taught", "t", "d:a"], ["record", "t", "d:a", "ok", "--mode", "predict"]])
def test_a_same_day_quiz_after_a_non_quiz_look_is_a_repeat_not_a_crash(home, first):
    _topic(home)
    assert run(home, *first)[0] == 0
    code, _ = run(home, "record", "t", "d:a", "ok")
    assert code == 0
    st = L.load_state(hm.load_config(home), "t")["concepts"]["d:a"]
    assert st.get("repeats") == 1 and not st.get("streak")
    # no credit, but scheduled for tomorrow rather than left due now
    assert st.get("due") == "2030-03-21" and not st.get("interval")


# --- replay does not inflate the taught and prediction counts --------------------------------

def test_replay_keeps_taught_and_prediction_counts_a_function_of_the_log(home):
    _topic(home)
    run(home, "taught", "t", "d:a")
    run(home, "record", "t", "d:b", "ok", "--mode", "predict")
    cfg = hm.load_config(home)
    state = L.load_state(cfg, "t")
    once, _ = L.replay(cfg, "t", state)
    twice, _ = L.replay(cfg, "t", once)
    assert once["concepts"]["d:a"]["taught"] == 1 == twice["concepts"]["d:a"]["taught"]
    assert once["concepts"]["d:b"]["predictions"] == 1 == twice["concepts"]["d:b"]["predictions"]


def test_replay_changes_no_credit_or_schedule_field(home):
    _topic(home)
    run(home, "taught", "t", "d:a")
    run(home, "record", "t", "d:a", "ok")
    run(home, "record", "t", "d:b", "ok")
    cfg = hm.load_config(home)
    state = L.load_state(cfg, "t")
    new, _ = L.replay(cfg, "t", state)
    for cid in state["concepts"]:
        assert L.mastery_view(new["concepts"][cid]) == L.mastery_view(state["concepts"][cid])


# --- line-separator characters in a row ----------------------------------------------------

@pytest.mark.parametrize("ch", ["\x85", " ", " "])
def test_a_ledger_row_with_a_unicode_line_separator_reads_back(tmp_path, ch):
    p = tmp_path / "log.jsonl"
    LG.append(p, {"a": "x" + ch + "y"})
    LG.append(p, {"a": "z"})
    rows, problems = LG.read(p)
    assert problems == [] and [r["a"] for r in rows] == ["x" + ch + "y", "z"]


@pytest.mark.parametrize("ch", ["\x85", " ", " "])
def test_a_note_with_a_line_separator_does_not_lock_the_log(home, ch):
    _topic(home)
    assert run(home, "record", "t", "d:a", "ok", "--note", "pasted" + ch + "note")[0] == 0
    assert run(home, "record", "t", "d:b", "ok")[0] == 0


def test_a_crlf_file_still_reads(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_bytes(b'{"a": 1}\r\n{"a": 2}\r\n')
    assert [r["a"] for r in LG.read(p)[0]] == [1, 2]


# --- a topic slug is a name, never a path -------------------------------------------------------

@pytest.mark.parametrize("slug", ["..", "../../victim", "a/b", "."])
def test_a_slug_that_is_a_path_is_refused_and_nothing_is_written(home, tmp_path, slug):
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "syllabus.md").write_text("## Concepts\n- d :: a :: about a\n")
    code, _ = run(home, "sync", slug)
    assert code == 64
    assert not (victim / "concepts.json").exists() and not (home / "concepts.json").exists()


def test_an_absolute_slug_is_refused(home, tmp_path):
    victim = tmp_path / "victim2"
    victim.mkdir()
    (victim / "syllabus.md").write_text("## Concepts\n- d :: a :: about a\n")
    assert run(home, "sync", str(victim))[0] == 64
    assert not (victim / "concepts.json").exists()


# --- terminal control characters in posting text --------------------------------------------------

def test_posting_text_loses_terminal_control_characters_but_keeps_its_layout():
    p = S._norm("fixture", "o", "1", "Eng \x1b]0;pwned\x07\x1b[2J\x1b[31mRED\x85", "Remote\x1b[1m", "u",
                "line one\n\tline two\r\nend\x07")
    assert not any(ch in p[k] for k in ("title", "location", "jd") for ch in "\x1b\x07\x85\x7f")
    assert p["jd"].startswith("line one\n\tline two\r\nend")
    assert set(p["sanitised"]) >= {"title", "location", "jd"}


# --- rulings from the verification pass -----------------------------------------------------

def test_a_scope_with_a_space_after_the_colon_is_read():
    text = "## Concepts\n- d :: a :: scope: depth\n- d :: b :: scope:  Exam \n"
    assert [c["scope"] for c in L.parse_syllabus(text)] == ["depth", "exam"]


def test_an_unknown_scope_is_still_refused():
    with pytest.raises(UsageError):
        L.parse_syllabus("## Concepts\n- d :: a :: scope: bogus\n")


def _bad_marker(home):
    p = home / "topics" / "t" / "syllabus.md"
    p.write_text(p.read_text() + "- d :: broken :: scope:bogus\n")


def test_a_bad_syllabus_marker_is_reported_for_its_topic_and_doctor_finishes(home, capsys):
    _topic(home)
    _bad_marker(home)
    code = cli.main(["--home", str(home), "doctor"])
    out = capsys.readouterr().out
    assert code == 2 and "NOT EVALUABLE t:" in out and "unknown scope" in out


def test_a_bad_syllabus_marker_does_not_abort_next(home, capsys):
    _topic(home)
    _bad_marker(home)
    cli.main(["--home", str(home), "next"])
    assert "unknown scope" in capsys.readouterr().out


@pytest.mark.parametrize("line", ["- Beginner Docker", "- Rusty Docker", "- [x] Basic Docker",
                                  "- Intro Docker", "Novice Docker"])
def test_a_leading_level_word_qualifies_the_line(line):
    from kenloop.career import facts as F
    assert F.analyse(f"## Held\n{line}\n").blocks[-1].qualified


@pytest.mark.parametrize("line", ["- Docker", "- Basic auth", "- Basic authentication", "- Docker basics"])
def test_a_line_without_a_leading_level_word_stays_held(line):
    from kenloop.career import facts as F
    assert not F.analyse(f"## Held\n{line}\n").blocks[-1].qualified


def test_doctor_flags_a_qualifier_hidden_in_a_comment(home, capsys):
    (home / "facts.md").write_text("## Held\n- Docker <!-- not yet, learning -->\n")
    assert cli.main(["--home", str(home), "doctor"]) != 0
    assert "hides a qualifier" in capsys.readouterr().out


def test_doctor_does_not_flag_a_plain_comment(home, capsys):
    (home / "facts.md").write_text("## Held\n- Docker <!-- from the 2024 job -->\n")
    cli.main(["--home", str(home), "doctor"])
    assert "hides a qualifier" not in capsys.readouterr().out


@pytest.mark.parametrize("text", ["Dock**er**", "Dock<span></span>er", "Dock<!-- x -->er", "Dock&#101;r",
                                  "Dock[er](https://x.example)", "Dock*er*", "Dock`er`"])
def test_markup_splitting_a_word_warns(tmp_path, capsys, text):
    from kenloop.career import ats
    p = tmp_path / "r.md"
    p.write_text(f"Used {text} daily\n")
    ats.resume_text(p)
    assert "splits a word" in capsys.readouterr().err


@pytest.mark.parametrize("text", ["**Docker**", "[Docker](https://x.example)", "`docker`", "snake_case",
                                  "R&D", "2*3", "<b>Docker</b>"])
def test_ordinary_markup_does_not_warn(tmp_path, capsys, text):
    from kenloop.career import ats
    p = tmp_path / "r.md"
    p.write_text(f"Used {text} daily\n")
    ats.resume_text(p)
    assert "splits a word" not in capsys.readouterr().err
