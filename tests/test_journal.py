"""The session journal, a module built only through the seams; never evidence."""
import json

import pytest

from kenloop import journal as J
from kenloop.core import learn as L
from kenloop.core.errors import NotEvaluable, UsageError

from conftest import run


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("# T\n\n## Concepts\n- d :: Tokens :: text to ids\n")
    L.sync(cfg, "t", quiet=True)
    return cfg


def test_close_records_the_session_and_the_fuzzy_one_opens_the_next(t, home, capsys):
    assert run(home, "close", "t", "--three", "ids", "--three", "vocab", "--fuzzy", "byte-pair merges",
               "--perceived", "4", "--idea", "d:tokens", "--minutes", "30", "--chunks", "6", "--acts", "5",
               "--why", "3", "--what", "1")[0] == 0
    r = J.rows(t)[0]
    assert (r["topic"], r["ideas"], r["three"], r["perceived"], r["acts"], r["chunks"]) == \
        ("t", ["d:tokens"], ["ids", "vocab"], 4, 5, 6)
    assert "fuzzy: byte-pair merges" in (home / "topics" / "t" / "tutor.md").read_text()
    capsys.readouterr()
    run(home, "sessions")
    assert "learner acts: 5/6 chunks (83%) over 1 of 1 session(s) counted" in capsys.readouterr().out


def test_absent_counts_read_as_not_counted_never_zero(t, home, capsys):
    run(home, "close", "t", "--three", "ids")
    capsys.readouterr()
    run(home, "sessions")
    out = capsys.readouterr().out
    assert "acts not counted" in out and "learner acts: not counted in any of 1 session(s)" in out


def test_bad_input_is_refused(t, home):
    with pytest.raises(UsageError):
        J.close(t, "t", three=["a", "b", "c", "d"])
    with pytest.raises(ValueError):
        J._check({"date": "2030-03-20", "topic": "t", "chunks": 2, "acts": 3})
    (home / "sessions.jsonl").write_text(json.dumps({"date": "2030-03-19", "topic": "t", "perceived": 9}) + "\n")
    with pytest.raises(NotEvaluable):
        J.close(t, "t", three=["a"])                      # nothing appended past damage


def test_the_journal_is_never_evidence(t):
    J.close(t, "t", three=["ids"], ideas=["d:tokens"], perceived=5)
    c = L.load_state(t, "t")["concepts"]["d:tokens"]
    assert not c.get("attempts") and not c.get("streak") and not c.get("due")


def test_perceived_takes_the_learners_own_words(t, home, capsys):
    run(home, "close", "t", "--three", "ids", "--perceived", "a little better, some stuck, still weak")
    r = J.rows(t)[0]
    assert r["perceived"] is None and r["felt"] == "a little better, some stuck, still weak"
    capsys.readouterr()
    run(home, "sessions")
    assert "felt: 'a little better, some stuck, still weak'" in capsys.readouterr().out


def test_a_number_out_of_range_is_refused_and_words_are_not_a_number(t):
    with pytest.raises(UsageError):
        J.close(t, "t", three=["a"], perceived="9")
    J.close(t, "t", three=["a"], perceived=" 3 ")
    assert (J.rows(t)[0]["perceived"], "felt" in J.rows(t)[0]) == (3, False)


@pytest.mark.parametrize("v", ["-1", "3.5", "0", "6", "10", "  "])
def test_a_number_shaped_or_blank_value_must_be_a_whole_1_to_5(t, v):
    with pytest.raises(UsageError):
        J.close(t, "t", three=["a"], perceived=v)


@pytest.mark.parametrize("v", ["²", "①"])
def test_digit_like_symbols_are_words_not_a_crash(t, v):
    J.close(t, "t", three=["a"], perceived=v)
    assert J.rows(t)[0]["felt"] == v
