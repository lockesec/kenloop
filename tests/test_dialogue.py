"""Dialogue: understanding graded by reasoning moves, kept apart from quiz credit.

A dialogue is graded by an assistant, so it may show how you reason but never earns the
evidence graduation reads (streak, retention days, breadth, schedule). The verdict is the
rubric's rule, every grade names its grader, and the log replays to the same state.
"""
import json

import pytest

from kenloop import loop
from kenloop.career import config as CC
from kenloop.core import dialogue as D
from kenloop.core import learn as L
from kenloop.core.errors import UsageError
from kenloop.career import graduate as G

from conftest import rows, run

SYLLABUS = """# Black holes

## Concepts
- spacetime :: Event horizon :: the surface light cannot climb out of
- quantum :: Information paradox :: does information survive evaporation :: status:open
- quantum :: Hawking radiation :: thermal emission from the horizon :: status:frontier
"""
EH = "spacetime:event-horizon"
IP = "quantum:information-paradox"
DIALOGUE = ["record", "bh", IP, "ok", "--mode", "dialogue", "--rubric", "chain=2,limits=2,question=2"]


@pytest.fixture
def bh(cfg, home, monkeypatch):
    monkeypatch.setenv("KENLOOP_GRADER", "test-model")
    L.plan(cfg, "bh")
    (home / "topics" / "bh" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "bh", quiet=True)
    return home / "topics" / "bh"


def _c(cfg, cid):
    return L.load_state(cfg, "bh")["concepts"][cid]


def test_status_marks_land_and_unmarked_is_not_settled(cfg, bh):
    assert _c(cfg, IP)["status"] == "open"
    assert _c(cfg, "quantum:hawking-radiation")["status"] == "frontier"
    assert _c(cfg, EH)["status"] == ""                 # no mark is not a claim that it is settled


def test_unknown_status_refuses_the_sync(cfg, bh):
    (bh / "syllabus.md").write_text("## Concepts\n- d :: X :: desc :: status:probably\n")
    with pytest.raises(UsageError, match="unknown status"):
        L.sync(cfg, "bh", quiet=True)


@pytest.mark.parametrize("rubric,want", [
    ({"chain": 2, "predict": 2, "limits": 1}, "ok"),
    ({"chain": 2, "predict": 2, "limits": 0}, "partial"),    # a 0 blocks ok
    ({"chain": 1, "predict": 1, "pushback": 0}, "miss"),
])
def test_the_verdict_is_one_rule(rubric, want):
    assert L.rubric_result(rubric) == want


def test_a_dialogue_folds_moves_and_gives_no_quiz_credit(cfg, home, bh, capsys):
    code, out = run(home, "record", "bh", EH, "ok", "--mode", "dialogue",
                    "--rubric", "chain=2,predict=1,limits=2", capsys=capsys)
    assert code == 0 and "push on: predict" in out.out
    c = _c(cfg, EH)
    assert c["by_reasoning"] == {"chain": {"probed": 1, "points": 2}, "predict": {"probed": 1, "points": 1},
                                 "limits": {"probed": 1, "points": 2}}       # unprobed moves are absent
    assert c["dialogues"] == 1
    assert not c.get("attempts") and not c.get("streak") and not c.get("correct_days") and not c.get("due")
    assert L.badge(c) == "new"
    r = rows(home, "bh")[-1]
    assert r["mode"] == "dialogue" and r["rubric"]["predict"] == 1 and r["grader"] == "test-model"
    assert run(home, "rebuild", "bh", "--check")[0] == 0          # replay reproduces it


def test_a_dialogue_does_not_reset_a_quiz_streak(cfg, home, bh, monkeypatch):
    L.record(cfg, "bh", EH, "ok", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    L.record(cfg, "bh", EH, "ok", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-25")
    due = _c(cfg, EH)["due"]
    L.record(cfg, "bh", EH, "miss", mode="dialogue", rubric={"chain": 0, "predict": 0, "limits": 1},
             note="thinks light slows near the horizon", quiet=True)
    c = _c(cfg, EH)
    assert c["streak"] == 2 and c["due"] == due and c["attempts"] == 2
    assert c["errors"][-1].endswith("thinks light slows near the horizon")   # the miss is kept as a misconception


def test_reasoning_alone_never_graduates(cfg, home, bh, monkeypatch):
    for day in ("2030-03-20", "2030-03-21", "2030-03-22", "2030-03-23"):     # separate days, strong grades
        monkeypatch.setenv("KENLOOP_TODAY", day)
        L.record(cfg, "bh", EH, "ok", mode="dialogue", rubric={"chain": 2, "predict": 2, "limits": 2}, quiet=True)
    ev = L.graduation_evidence(cfg, "bh")
    assert EH not in sum(ev.values(), [])                  # not even considered: it is not mastered
    assert G.graduation(cfg, "bh")["candidates"] == []


def test_a_result_that_disagrees_with_the_rubric_is_refused(cfg, home, bh):
    code, _ = run(home, "record", "bh", EH, "ok", "--mode", "dialogue", "--rubric", "chain=1,predict=0,limits=1")
    assert code == 64
    assert rows(home, "bh") == []                          # nothing written
    with pytest.raises(UsageError, match="rubric grades this 'miss'"):
        L.record(cfg, "bh", EH, "ok", mode="dialogue", rubric={"chain": 1, "predict": 0, "limits": 1})


def test_too_few_moves_a_stray_rubric_and_a_qtype_are_refused(cfg, home, bh):
    with pytest.raises(UsageError, match="at least 3"):
        L.parse_rubric("chain=2,predict=2")
    with pytest.raises(UsageError, match="unknown reasoning move"):
        L.parse_rubric("chain=2,predict=2,vibes=2")
    assert run(home, "record", "bh", EH, "ok", "--rubric", "chain=2,predict=2,limits=2")[0] == 64
    with pytest.raises(UsageError, match="graded by its rubric"):
        L.record(cfg, "bh", EH, "ok", mode="dialogue")
    with pytest.raises(UsageError, match="--qtype is for quiz"):
        L.record(cfg, "bh", EH, "ok", mode="dialogue", qtype="recall", rubric={"chain": 2, "predict": 2, "limits": 2})


def test_a_dialogue_grade_names_its_grader(cfg, home, bh, monkeypatch, capsys):
    monkeypatch.delenv("KENLOOP_GRADER")
    code, out = run(home, *DIALOGUE, capsys=capsys)
    assert code == 64 and "name who made it" in out.err
    assert run(home, *DIALOGUE, "--grader", "claude-opus-5-5")[0] == 0
    assert rows(home, "bh")[-1]["grader"] == "claude-opus-5-5"
    capsys.readouterr()
    D.beliefs(cfg, "bh")
    assert "graded by claude-opus-5-5" in capsys.readouterr().out


def test_talk_shows_what_humanity_knows_and_picks_the_least_talked_about(cfg, home, bh, capsys):
    run(home, "record", "bh", EH, "ok", "--mode", "dialogue", "--rubric", "chain=2,predict=2,limits=2")
    capsys.readouterr()
    assert D.talk(cfg, "bh", IP) == 0
    out = capsys.readouterr().out
    assert "open: nobody knows yet" in out and "--mode dialogue" in out and "dialogues/2030-03-20-quantum-information-paradox.md" in out
    D.talk(cfg, "bh")
    first = capsys.readouterr().out.splitlines()[0]
    assert EH not in first                                 # the one already talked about is not picked
    D.talk(cfg, "bh", EH)
    assert "not marked in the syllabus" in capsys.readouterr().out


def test_belief_pair_and_open_questions_land_in_the_log_and_the_view(cfg, home, bh, capsys):
    assert run(home, *DIALOGUE, "--before", "information is destroyed", "--confidence", "med",
               "--after", "nobody knows; unitarity says it must come out", "--after-confidence", "low",
               "--open", "does the radiation carry it?", "--open", "what is a Page curve?")[0] == 0
    r = rows(home, "bh")[-1]
    assert r["before"] == "information is destroyed" and r["after_confidence"] == "low"
    assert r["open"] == ["does the radiation carry it?", "what is a Page curve?"]
    assert run(home, "rebuild", "bh", "--check")[0] == 0
    capsys.readouterr()
    assert D.beliefs(cfg, "bh") == 0
    out = capsys.readouterr().out
    assert "before (med): information is destroyed" in out
    assert "1 with a before/after belief, 1 of those changed; you caught the tutor wrong 0" in out
    assert "what is a Page curve?" in out


def test_a_held_belief_is_shown_as_held(cfg, home, bh, capsys):
    run(home, *DIALOGUE, "--before", "Same", "--after", "same")
    capsys.readouterr()
    D.beliefs(cfg, "bh")
    assert "(held)" in capsys.readouterr().out


def test_belief_fields_need_a_dialogue_and_both_ends(cfg, home, bh, capsys):
    code, out = run(home, "record", "bh", EH, "ok", "--open", "why?", capsys=capsys)
    assert code == 64 and "--mode dialogue only" in out.err
    code, out = run(home, *DIALOGUE, "--before", "only one end", capsys=capsys)
    assert code == 64 and "both --before and --after" in out.err


def test_beliefs_with_no_dialogues_says_so(cfg, bh, capsys):
    D.beliefs(cfg, "bh")
    assert "no dialogues recorded yet" in capsys.readouterr().out


def test_break_point_and_a_caught_tutor_error_show_in_beliefs(cfg, home, bh, capsys):
    assert run(home, *DIALOGUE, "--held", "escape speed rises as the mass gets more compact",
               "--broke", "so light slows down near it",
               "--next", "gravitational time dilation: clocks slow, light does not",
               "--claude-wrong", "said the horizon is a physical surface")[0] == 0
    capsys.readouterr()
    D.beliefs(cfg, "bh")
    out = capsys.readouterr().out
    assert "right up to: escape speed rises" in out and "broke at   : so light slows down" in out
    assert "learn next : gravitational time dilation" in out
    assert "you caught the tutor: said the horizon" in out and "you caught the tutor wrong 1 time(s)" in out


def test_the_transcript_is_logged_with_its_hash_and_validate_sees_an_edit(cfg, home, bh, capsys):
    t = L.dialogue_path(cfg, "bh", IP, "2030-03-20")
    t.parent.mkdir(parents=True)
    t.write_text("# transcript\n")
    run(home, *DIALOGUE)
    r = rows(home, "bh")[-1]
    assert r["transcript"] == "dialogues/2030-03-20-quantum-information-paradox.md" and len(r["transcript_sha256"]) == 64
    assert L.problems(cfg, "bh") == ([], [])
    t.write_text("# transcript, edited after the grade\n")
    assert any("changed after it was graded" in h for h in L.problems(cfg, "bh")[0])
    assert run(home, "validate", "bh")[0] == 1                          # a failure, not a note
    ev = {e["rule"]: e for e in loop.evaluate(CC.load(home))}
    assert ev["integrity"]["status"] == "fired" and ev["integrity"]["argv"][-2:] == ["validate", "bh"]
    assert run(home, "doctor")[0] == 1
    t.unlink()
    assert any("is missing" in h for h in L.problems(cfg, "bh")[0])


def test_calibration_leaves_dialogues_out(cfg, home, bh, capsys):
    run(home, *DIALOGUE, "--before", "a", "--confidence", "high", "--after", "b")
    capsys.readouterr()
    assert L.calibration(cfg, "bh") == 2                   # no unaided quiz attempt was rated: NOT EVALUABLE


@pytest.mark.parametrize("change", [
    {"result": "miss"},                                    # not the rubric's verdict
    {"grader": ""},                                        # no grader
    {"rubric": {"chain": 2, "predict": 2}},                # too few moves
    {"rubric": {"chain": 3, "predict": 2, "limits": 2}},   # score out of range
    {"transcript": "../../facts.md", "transcript_sha256": "0" * 64},   # outside dialogues/
])
def test_a_tampered_dialogue_row_is_a_log_problem(cfg, home, bh, change):
    run(home, *DIALOGUE)
    p = bh / "log.jsonl"
    r = json.loads(p.read_text().splitlines()[-1])
    p.write_text(json.dumps({**r, **change}) + "\n")
    assert L.read_log(cfg, "bh")[1], "the row should not be applied"
    assert run(home, "rebuild", "bh", "--check")[0] == 2


def test_talk_picks_in_the_syllabus_order_not_alphabetically(cfg, home, capsys):
    L.plan(cfg, "path")
    (home / "topics" / "path" / "syllabus.md").write_text("## Concepts\n- zeta :: First step :: x\n- alpha :: Second step :: y\n")
    L.sync(cfg, "path", quiet=True)
    capsys.readouterr()
    D.talk(cfg, "path")
    assert "zeta:first-step" in capsys.readouterr().out.splitlines()[0]


def test_a_dialogue_graded_with_no_transcript_is_a_warning(cfg, home, bh):
    run(home, *DIALOGUE)
    assert any("has no transcript" in w for w in L.problems(cfg, "bh")[1])
    assert run(home, "validate", "bh")[0] == 0           # a warning: the grade gives no credit anyway


def test_an_open_question_can_name_its_own_concept(cfg, home, bh, monkeypatch):
    from kenloop import loop
    from kenloop.career import config as CC
    assert run(home, "record", "bh", EH, *DIALOGUE[3:], "--open", "information :: does anything resolve it?")[0] == 0
    assert rows(home, "bh")[-1]["open"] == [f"{IP} :: does anything resolve it?"]     # resolved to the id
    e = {e["rule"]: e for e in loop.evaluate(CC.load(home))}["question"]
    assert e["argv"][-1] == IP and e["reason"].endswith("does anything resolve it?")
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    run(home, "record", "bh", EH, *DIALOGUE[3:])                          # a later talk on another concept
    assert {e["rule"]: e for e in loop.evaluate(CC.load(home))}["question"]["status"] == "fired"
    run(home, *DIALOGUE)                                                  # a later talk on its concept
    assert {e["rule"]: e for e in loop.evaluate(CC.load(home))}["question"]["status"] != "fired"


def test_an_open_question_naming_no_concept_is_refused(cfg, home, bh, capsys):
    code, out = run(home, *DIALOGUE, "--open", "wormholes :: are they real?", capsys=capsys)
    assert code == 64 and "no concept matches" in out.err and rows(home, "bh") == []


def test_a_graded_copy_shows_and_restores_a_changed_transcript(cfg, home, bh):
    t = L.dialogue_path(cfg, "bh", IP, "2030-03-20")
    t.parent.mkdir(parents=True)
    t.write_bytes(b"# transcript\r\nlearner: it is a wall\n")
    run(home, *DIALOGUE)
    g = L.graded_copy(cfg, "bh", rows(home, "bh")[-1]["transcript"])
    assert g.read_bytes() == t.read_bytes()                               # byte for byte
    t.write_text("# transcript\nlearner: obviously not a wall\n")
    h = L.problems(cfg, "bh")[0]
    assert any("the graded copy is dialogues/.graded/" in x and "copy it back" in x for x in h)
    t.write_bytes(g.read_bytes())                                         # restore
    assert L.problems(cfg, "bh")[0] == []
    g.write_text("tampered too")
    t.write_text("tampered")
    assert any("no intact graded copy" in x for x in L.problems(cfg, "bh")[0])

