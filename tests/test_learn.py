"""The learn arm: credit rules, the log as the record, graduation, the seam."""
import io
import json

import pytest

from careerloop import home as H
from careerloop import learn as L
from careerloop.errors import NotEvaluable, UsageError

from conftest import rows


@pytest.fixture
def topic(cfg, home):
    L.plan(cfg, "t", title="T", goal="g")
    (home / "topics" / "t" / "syllabus.md").write_text(
        "# T\n\n## Concepts\n\n"
        + "".join(f"- d :: c{i} :: desc {i} :: cluster:k\n" for i in range(6))
        + "- d :: deep :: only for depth :: scope:depth\n")
    L.sync(cfg, "t")
    return "t"


def rec(cfg, cid, result="ok", **kw):
    return L.record(cfg, "t", cid, result, quiet=True, **kw)


def con(cfg, cid):
    return L.load_state(cfg, "t")["concepts"][cid]


def test_unaided_ok_is_the_only_credit(cfg, topic, monkeypatch):
    rec(cfg, "d:c0", qtype="recall")
    assert con(cfg, "d:c0")["streak"] == 1 and con(cfg, "d:c0")["correct_days"] == ["2030-03-20"]
    for kw in ({"guess": True}, {"hint_depth": 1}, {"lookup": True}, {"mode": "learn"}):
        rec(cfg, "d:c1", qtype="recall")                         # an established streak...
        rec(cfg, "d:c1", qtype="recall", **kw)                   # ...is RESET, not held
        c = con(cfg, "d:c1")
        assert c["streak"] == 0, kw
        assert c["interval"] == 1, kw


def test_low_confidence_correct_keeps_credit_but_comes_back_sooner(cfg, topic):
    rec(cfg, "d:c0")
    rec(cfg, "d:c1")
    H._dt  # noqa
    import os
    os.environ["CAREERLOOP_TODAY"] = "2030-03-22"
    rec(cfg, "d:c0", confidence="low")
    rec(cfg, "d:c1", confidence="high")
    lo, hi = con(cfg, "d:c0"), con(cfg, "d:c1")
    assert lo["streak"] == hi["streak"] == 2
    assert lo["interval"] < hi["interval"]


def test_by_conf_uses_raw_correctness_and_by_type_unaided(cfg, topic):
    rec(cfg, "d:c0", guess=True, confidence="high", qtype="recall")
    c = con(cfg, "d:c0")
    assert c["by_conf"]["high"] == {"attempts": 1, "correct": 1}
    assert c["by_type"]["recall"] == {"attempts": 1, "correct": 0}


def test_log_is_written_before_state(cfg, topic, home, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(L, "save_state", boom)
    with pytest.raises(OSError):
        rec(cfg, "d:c0")
    assert len(rows(home, "t")) == 1            # the log is ahead; rebuild recovers
    monkeypatch.undo()
    assert L.rebuild(cfg, "t", check=True) == 3
    assert L.rebuild(cfg, "t") == 0 and L.rebuild(cfg, "t", check=True) == 0


def test_replay_reproduces_record_exactly(cfg, topic):
    import os
    for day, cid, res, kw in [("2030-03-01", "d:c0", "ok", {"qtype": "recall"}),
                              ("2030-03-01", "d:c1", "miss", {"note": "x", "etype": "detail-slip"}),
                              ("2030-03-03", "d:c0", "ok", {"confidence": "low"}),
                              ("2030-03-03", "d:c1", "ok", {"qtype": "recall"}),
                              ("2030-03-04", "d:c2", "partial", {"hint_depth": 2}),
                              ("2030-03-09", "d:c0", "ok", {"mode": "learn"})]:
        os.environ["CAREERLOOP_TODAY"] = day
        rec(cfg, cid, res, **kw)
    state = L.load_state(cfg, "t")
    assert any(c.get("attempts") for c in state["concepts"].values())
    assert L.drift(cfg, "t") == []
    new, _ = L.replay(cfg, "t", state)
    for cid, c in state["concepts"].items():
        assert L.mastery_view(c) == L.mastery_view(new["concepts"][cid])


def test_replay_is_order_stable_across_a_merged_log(cfg, topic, home):
    import os
    for day, cid in [("2030-03-01", "d:c0"), ("2030-03-02", "d:c1"), ("2030-03-03", "d:c0")]:
        os.environ["CAREERLOOP_TODAY"] = day
        rec(cfg, cid)
    log = home / "topics" / "t" / "log.jsonl"
    lines = log.read_text().splitlines()
    log.write_text("\n".join([lines[2], lines[0], lines[1]]) + "\n")
    assert L.drift(cfg, "t") == []


def test_an_undated_row_is_reported_never_replayed_today(cfg, topic, home, capsys):
    log = home / "topics" / "t" / "log.jsonl"
    log.write_text(json.dumps({"concept": "d:c0", "result": "ok"}) + "\nnot json\n")
    L.rebuild(cfg, "t")
    err = capsys.readouterr().err
    assert "line 1" in err and "line 2" in err
    assert not con(cfg, "d:c0").get("attempts")


def test_a_damaged_topic_json_is_refused_not_overwritten(cfg, topic, home):
    p = home / "topics" / "t" / "topic.json"
    p.write_text("{broken")
    with pytest.raises(NotEvaluable):
        L.set_exam_date(cfg, "t", "2030-05-01")
    assert p.read_text() == "{broken"


def test_unknown_scope_refuses_the_sync(cfg, topic, home):
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: x :: y :: scope:maybe\n")
    with pytest.raises(UsageError):
        L.sync(cfg, "t")


def test_errors_resolve_only_through_a_testing_qtype(cfg, topic):
    rec(cfg, "d:c0", "miss", note="n", etype="concept-conflation")
    rec(cfg, "d:c0", qtype="recall")                  # recall does not test conflation
    assert len(L.open_errors(con(cfg, "d:c0"))) == 1
    rec(cfg, "d:c0", guess=True, qtype="comparison")  # a guess resolves nothing
    assert len(L.open_errors(con(cfg, "d:c0"))) == 1
    rec(cfg, "d:c0", qtype="comparison")
    assert L.open_errors(con(cfg, "d:c0")) == []
    assert len(con(cfg, "d:c0")["errors"]) == 1       # history is never erased


def test_graduation_gates(cfg, topic, home, capsys):
    import os
    day = {1: "2030-03-10", 2: "2030-03-12", 3: "2030-03-15"}
    for n, qt in ((1, "recall"), (2, "applied"), (3, "comparison")):
        os.environ["CAREERLOOP_TODAY"] = day[n]
        rec(cfg, "d:c0", qtype=qt)
    g = L.graduation(cfg, "t")
    assert g["drilled solo"] == ["d:c0"]                  # never answered among 3 others
    for other in ("d:c1", "d:c2", "d:c3"):
        rec(cfg, other, hint_depth=1)                     # assisted rows still make it a mixed session
    rec(cfg, "d:c0", qtype="recall")
    assert L.graduation(cfg, "t")["candidates"] == ["d:c0"]
    (home / "facts.md").write_text("## Held\n- Go\n## Learning\n- c0\n")     # a mention outside Held is not held
    assert L.graduation(cfg, "t")["candidates"] == ["d:c0"]
    (home / "facts.md").write_text("## Held\n- c0\n")
    assert L.graduation(cfg, "t")["held"] == ["d:c0"]


def test_learn_mode_row_never_satisfies_interference(cfg, topic):
    import os
    for d in ("2030-03-10", "2030-03-12"):
        os.environ["CAREERLOOP_TODAY"] = d
        rec(cfg, "d:c0")                                  # solo days
    os.environ["CAREERLOOP_TODAY"] = "2030-03-14"
    for other in ("d:c1", "d:c2", "d:c3"):
        rec(cfg, other)
    rec(cfg, "d:c0", mode="learn")                        # a massed pass in a mixed session
    assert L.interference_ok(L.read_log(cfg, "t")[0], "d:c0") is False
    rec(cfg, "d:c0")                                      # control: a real retrieval that day
    assert L.interference_ok(L.read_log(cfg, "t")[0], "d:c0") is True


def test_bank_requires_ref_and_dedupes(cfg, topic, home):
    with pytest.raises(UsageError):
        L.bank(cfg, "t", "d:c0", "Q?", "A", "")
    L.bank(cfg, "t", "d:c0", "Q?", "A", "notes#1", qtype="recall", distractors=["B :: thinks B"])
    L.bank(cfg, "t", "d:c0", "q?", "A", "notes#1")
    b = L.load_bank(cfg, "t")["d:c0"]
    assert len(b) == 1 and b[0]["d"] == [("B", "thinks B")]


def test_validate_finds_orphans_and_ungrounded_questions(cfg, topic, home):
    (home / "topics" / "t" / "questions.md").write_text(
        "## d:nope\n### Q: x\n- **A:** y\n- **Ref:** r\n## d:c0\n### Q: z\n- **A:** w\n")
    assert L.validate(cfg, "t") == 1


def test_exam_date_clamps_and_rebuild_stays_clean(cfg, topic):
    rec(cfg, "d:c0")
    assert L.set_exam_date(cfg, "t", "2030-03-25") == 0
    import os
    os.environ["CAREERLOOP_TODAY"] = "2030-03-21"
    rec(cfg, "d:c0")
    c = con(cfg, "d:c0")
    assert c["due"] < "2030-03-25" and c.get("exam_clamp")
    assert L.drift(cfg, "t") == []
    with pytest.raises(UsageError):
        L.set_exam_date(cfg, "t", "2030-03-01")          # not in the future


def test_interactive_session_logs_the_same_rows_as_record(cfg, topic, home):
    L.bank(cfg, "t", "d:c0", "Pick", "right", "r", qtype="recall", distractors=["wrong :: the misconception"])
    L.bank(cfg, "t", "d:c1", "Say it", "it", "r", why="because", qtype="applied")
    out = io.StringIO()
    # c0 is multiple choice: find which letter is wrong from the rendered options
    probe = io.StringIO()
    L.quiz_interactive(cfg, "t", n=2, inp=io.StringIO(""), out=probe)
    text = probe.getvalue()
    wrong = next(line.strip()[0] for line in text.splitlines() if line.strip().endswith(") wrong"))
    script = f"{wrong}\nh\n1\n?\n?\n?\nit\nl\no\n"
    L.quiz_interactive(cfg, "t", n=2, concept=None, inp=io.StringIO(script), out=out)
    got = rows(home, "t")
    assert [r["concept"] for r in got] == ["d:c0", "d:c1"]
    assert got[0]["result"] == "miss" and got[0]["note"] == "the misconception"
    assert got[0]["confidence"] == "high" and got[0]["etype"] == "term-confusion"
    assert got[1]["hint_depth"] == 3 and got[1]["result"] == "ok" and got[1]["confidence"] == "low"
    manual = L.record(cfg, "t", "d:c2", "ok", quiet=True)
    assert set(got[0]) == set(manual)
    assert L.rebuild(cfg, "t", check=True) == 0


def test_interactive_skips_a_concept_with_no_question(cfg, topic, home):
    out = io.StringIO()
    L.quiz_interactive(cfg, "t", n=1, inp=io.StringIO("x\n"), out=out)
    assert "no banked question" in out.getvalue() and rows(home, "t") == []


def test_calibration_ignores_assisted_rows(cfg, topic, capsys):
    for _ in range(5):
        rec(cfg, "d:c0", confidence="low", lookup=True)
    assert L.calibration(cfg, "t") == 2                  # nothing unaided to judge
    assert "UNDERCONFIDENT" not in capsys.readouterr().out
    for _ in range(5):
        rec(cfg, "d:c1", confidence="low")
    L.calibration(cfg, "t")
    assert "UNDERCONFIDENT" in capsys.readouterr().out   # negative control: genuine case fires


def test_even_spread_gives_no_verdict(cfg, topic, capsys):
    for i, et in enumerate(("term-confusion", "wrong-scope", "detail-slip")):
        rec(cfg, f"d:c{i}", "miss", note="n", etype=et)
    L.misconceptions(cfg, "t")
    assert "no dominant" in capsys.readouterr().out


def test_quiz_puts_confident_misses_first(cfg, topic):
    rec(cfg, "d:c3", "miss", confidence="high")
    rec(cfg, "d:c4", "miss", confidence="low")
    assert L.select(L.load_state(cfg, "t"), n=2)[0] == "d:c3"


def test_interference_needs_three_others_not_three_including_itself(cfg, topic):
    for other in ("d:c1", "d:c2"):
        rec(cfg, other)
    rec(cfg, "d:c0")
    assert L.interference_ok(L.read_log(cfg, "t")[0], "d:c0") is False     # 2 others
    rec(cfg, "d:c3")
    assert L.interference_ok(L.read_log(cfg, "t")[0], "d:c0") is True      # 3 others


def test_assisted_and_massed_rows_never_reach_by_conf(cfg, topic):
    rec(cfg, "d:c0", confidence="high", lookup=True)
    rec(cfg, "d:c0", confidence="high", hint_depth=2)
    rec(cfg, "d:c0", confidence="high", mode="learn")
    assert not con(cfg, "d:c0").get("by_conf")
    rec(cfg, "d:c0", confidence="high")                                    # control
    assert con(cfg, "d:c0")["by_conf"] == {"high": {"attempts": 1, "correct": 1}}
