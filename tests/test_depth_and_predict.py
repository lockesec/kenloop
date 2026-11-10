"""Every row says how deep its question went and whether it was asked because it
was due; the learner's guess before an explanation is a `predict` row, recorded and never credited."""
import json

import pytest

from kenloop.core import learn as L
from kenloop.core.errors import UsageError

from conftest import rows

SYL = """# T

## Path

0. **ground** — what you bring
1. **service** — the product :: depth:exam

## Concepts
- ground :: Tokens :: text to ids
- service :: Deploy :: portal steps
- service :: Prompts :: system vs user :: depth:first-principles
"""


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text(SYL)
    L.sync(cfg, "t", quiet=True)
    return cfg


def test_depth_defaults_from_line_then_rung_then_topic_then_mode(t, home):
    L.record(t, "t", "service:prompts", "ok", quiet=True)
    L.record(t, "t", "service:deploy", "ok", quiet=True)
    L.record(t, "t", "ground:tokens", "ok", quiet=True)
    L.taught(t, "t", "ground:tokens", quiet=True)
    assert [r["depth"] for r in rows(home, "t")] == ["first-principles", "exam", "exam", "mechanism"]
    L.save_config(t, "t", {**L.load_config(t, "t"), "depth": "mechanism"})
    L.record(t, "t", "ground:tokens", "ok", quiet=True)
    assert rows(home, "t")[-1]["depth"] == "mechanism"          # the topic's setting


def test_an_explicit_depth_wins_and_a_bad_one_is_refused(t, home):
    L.record(t, "t", "service:deploy", "ok", depth="mechanism", quiet=True)
    assert rows(home, "t")[-1]["depth"] == "mechanism"
    with pytest.raises(UsageError):
        L.record(t, "t", "service:deploy", "ok", depth="deep", quiet=True)


def test_old_rows_read_a_declared_default_and_a_bad_stored_depth_is_damage(t, home):
    assert L.row_depth({"mode": "practice"}) == "exam" and L.row_depth({}) == "exam"
    assert L.row_depth({"mode": "dialogue"}) == "mechanism" and L.row_depth({"mode": "teach"}) == "mechanism"
    log = home / "topics" / "t" / "log.jsonl"
    log.write_text(json.dumps({"date": "2030-03-19", "concept": "ground:tokens", "result": "ok", "depth": 2}) + "\n")
    assert L.read_log(t, "t")[1]                                   # reported, never read as a depth


def test_a_prediction_is_recorded_never_credited_and_makes_later_answers_repeats(t, home):
    L.record(t, "t", "ground:tokens", "miss", mode="predict", quiet=True)
    c = L.load_state(t, "t")["concepts"]["ground:tokens"]
    assert c["predictions"] == 1 and not c.get("attempts") and not c.get("errors") and not c.get("due")
    L.record(t, "t", "ground:tokens", "ok", quiet=True)
    c = L.load_state(t, "t")["concepts"]["ground:tokens"]
    assert c.get("repeats") == 1 and not c.get("streak")
    assert L.audit(t, "t", L.load_state(t, "t"))[0] == []         # replay agrees with record


def test_due_is_stamped_from_the_schedule(t, home, monkeypatch):
    L.record(t, "t", "ground:tokens", "ok", quiet=True)
    assert rows(home, "t")[-1]["due"] is False                     # never scheduled: incidental
    due = L.load_state(t, "t")["concepts"]["ground:tokens"]["due"]
    monkeypatch.setenv("KENLOOP_TODAY", due)
    L.record(t, "t", "ground:tokens", "ok", quiet=True)
    assert rows(home, "t")[-1]["due"] is True
