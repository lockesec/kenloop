"""Tutor gaps: misses the teaching caused, counted against the tutor and never the learner."""
import json

import pytest

from kenloop import gaps as G
from kenloop.core import learn as L
from kenloop.core.errors import NotEvaluable, UsageError

from conftest import run


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("# T\n\n## Concepts\n- d :: Softmax :: scores to shares\n"
                                                        "- d :: Tokens :: text to ids\n")
    L.sync(cfg, "t", quiet=True)
    return cfg


def test_a_gap_is_recorded_and_read_back_beside_what_was_taught(t, home, capsys):
    L.taught(t, "t", "d:softmax", "shares")
    assert run(home, "gap", "t", "d:softmax", "never said the total is per group")[0] == 0
    run(home, "gap", "t", "d:softmax", "led with the formula", "--kind", "order")
    r = G.rows(t)[0]
    assert (r["topic"], r["concept"], r["kind"], r["gap"]) == ("t", "d:softmax", "step", "never said the total is per group")
    capsys.readouterr()
    run(home, "gaps", "t")
    out = capsys.readouterr().out
    assert "t d:softmax: 2 gap(s)" in out and "tutor gaps: 2 on 1 concept(s), 1 concept(s) taught" in out


def test_no_gaps_says_so_with_the_denominator(t, home, capsys):
    run(home, "gaps")
    assert "no tutor gaps recorded over 0 taught concept(s)" in capsys.readouterr().out


def test_a_gap_is_never_evidence_about_the_learner(t):
    G.gap(t, "t", "d:tokens", "skipped the example")
    c = L.load_state(t, "t")["concepts"]["d:tokens"]
    assert not c.get("attempts") and not c.get("streak") and not c.get("due") and not c.get("taught")


def test_bad_input_and_damage_are_refused(t, home):
    with pytest.raises(UsageError):
        G.gap(t, "t", "d:tokens", "   ")
    with pytest.raises(UsageError):
        G.gap(t, "t", "d:tokens", "x", kind="vibes")
    with pytest.raises(UsageError):
        G.gap(t, "nope", "d:tokens", "x")
    (home / "tutor_gaps.jsonl").write_text(json.dumps({"date": "2030-03-19", "topic": "t", "concept": "d:tokens",
                                                       "kind": "vibes", "gap": "x"}) + "\n")
    with pytest.raises(NotEvaluable):
        G.gap(t, "t", "d:tokens", "y")                    # nothing appended past damage
    assert G.doctor(t) and G.doctor(t)[0][0] == "NOT EVALUABLE"


def test_gaps_on_untaught_concepts_are_counted_apart_and_the_record_says_so(t, home, capsys):
    code, out = run(home, "gap", "t", "d:tokens", "skipped the example", capsys=capsys)
    assert "is not marked taught" in out.out
    run(home, "gaps", "t")
    assert "1 on 1 concept(s), 0 concept(s) taught (1 gap(s) on concepts not marked taught)" in capsys.readouterr().out


def test_a_damaged_line_is_named_when_reading_gaps(t, home, capsys):
    G.gap(t, "t", "d:tokens", "skipped the example")
    with (home / "tutor_gaps.jsonl").open("a") as fh:
        fh.write("{not json\n")
    capsys.readouterr()
    code = run(home, "gaps", "t")[0]
    assert code == 2 and "1 damaged line(s) not read" in capsys.readouterr().out
