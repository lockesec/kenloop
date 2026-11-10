"""Teach mode in the record, `ken session`, tutor notes, `talk` without the dialogue
method unless asked (tutor notes leaked into syllabi and scouts)."""
import pytest

from kenloop import session as SS
from kenloop.core import learn as L
from kenloop.core import onramp as O
from kenloop.core.errors import UsageError

from conftest import run, rows

SYL = """# T

## Path

0. **ground** — what you bring
1. **workloads** — kinds of task

## Concepts
- workloads :: Embeddings :: text becomes vectors :: before:workloads:extraction
- workloads :: Extraction :: fields from documents :: intent:pass
"""


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t", outlets=("career",))
    (home / "topics" / "t" / "syllabus.md").write_text(SYL)
    L.sync(cfg, "t", quiet=True)
    return cfg


def test_taught_is_recorded_and_earns_nothing(t, home):
    assert run(home, "taught", "t", "workloads:embeddings", "--note", "tokens, vectors, cosine")[0] == 0
    row = rows(home, "t")[-1]
    assert (row["mode"], row["result"], row["note"]) == ("teach", "ok", "tokens, vectors, cosine")
    c = L.load_state(t, "t")["concepts"]["workloads:embeddings"]
    assert c["taught"] == 1 and c["last_taught"] == "2030-03-20"
    assert not c.get("attempts") and not c.get("streak") and not c.get("correct_days") and not c.get("interval")
    assert c["due"] == "2030-03-21"          # no credit, but the first cold recall is tomorrow


def test_a_quiz_after_teaching_the_same_day_is_a_repeat_not_credit(t, home):
    L.taught(t, "t", "workloads:embeddings", quiet=True)
    L.record(t, "t", "workloads:embeddings", "ok", quiet=True)
    c = L.load_state(t, "t")["concepts"]["workloads:embeddings"]
    assert c.get("repeats") == 1 and not c.get("streak") and not c.get("correct_days")


def test_replay_agrees_with_record_for_teach_rows(t):
    L.taught(t, "t", "workloads:embeddings", quiet=True)
    assert L.audit(t, "t", L.load_state(t, "t"))[0] == []        # no drift between record and replay


def test_a_taught_concept_counts_as_touched_and_moves_the_on_ramp_on(t):
    O.place(t, "t", start=1)
    assert O.next_step(t, "t")[0][2] == "workloads:embeddings"
    L.taught(t, "t", "workloads:embeddings", quiet=True)
    assert O.next_step(t, "t")[0][2] == "workloads:extraction"


def test_talk_prints_the_dialogue_method_only_when_asked(t, home, capsys):
    run(home, "talk", "t", "workloads:embeddings")
    plain = capsys.readouterr().out
    run(home, "talk", "t", "workloads:embeddings", "--protocol")
    graded = capsys.readouterr().out
    assert "No explaining before you have tried" not in plain and "ken taught t workloads:embeddings" in plain
    assert "No explaining before you have tried" in graded


def test_notes_are_dated_per_topic_and_for_the_learner(t, home):
    run(home, "note", "t", "the fuzzy-hash analogy for embeddings landed")
    run(home, "note", "--learner", "works in security; lead with the attacker's view")
    assert "## 2030-03-20\n- the fuzzy-hash analogy" in (home / "topics" / "t" / "tutor.md").read_text()
    assert "lead with the attacker's view" in (home / "learner.md").read_text()
    assert SS.last_notes(home / "topics" / "t" / "tutor.md") == ["2030-03-20: the fuzzy-hash analogy for embeddings landed"]
    with pytest.raises(UsageError):
        SS.note(t, None, "no topic and not --learner")


def test_session_shows_what_a_tutor_needs_to_pick_a_mode(t, home, capsys):
    run(home, "settings", "t", "--intent", "understand", "--depth", "mechanism")
    run(home, "place", "t", "--start", "0")
    run(home, "note", "t", "lead with security analogies")
    capsys.readouterr()
    assert run(home, "session", "t")[0] == 0
    out = capsys.readouterr().out
    assert "intent: understand (1 concept(s) differ, by line or rung); depth: mechanism" in out
    assert "mode: teach, workloads:embeddings at height 0 (new), depth mechanism, intent understand" in out
    assert "start 0 (by choice)" in out and "lead with security analogies" in out
    assert "next here:" in out and "ken taught t CONCEPT" in out and "ken ken" not in out


def test_every_learner_note_shows_but_only_the_last_topic_notes(t, home, capsys):
    for i in range(5):
        run(home, "note", "t", f"topic note {i}")
        run(home, "note", "--learner", f"learner fact {i}")
    capsys.readouterr()
    run(home, "session", "t")
    out = capsys.readouterr().out
    assert "learner fact 0" in out and "learner fact 4" in out
    assert "topic note 0" not in out and "topic note 4" in out
