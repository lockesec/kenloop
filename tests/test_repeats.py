"""Only the first look at a concept on a day can earn credit. Later rows that day are counted
(attempts, correct, repeats) but move no streak, retention day, breadth, confidence or schedule:
after a quiz, a miss, a hint, a dialogue or a read-through, the learner has seen it."""
import pytest

from kenloop.core import learn as L
from kenloop.core import reviews as R

from conftest import run


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: c0 :: x\n- d :: c1 :: y\n")
    L.sync(cfg, "t", quiet=True)
    return home


def c0(cfg):
    return L.load_state(cfg, "t")["concepts"]["d:c0"]


def test_three_oks_in_one_day_are_one_credit_and_two_counted_repeats(cfg, t):
    for _ in range(3):
        L.record(cfg, "t", "d:c0", "ok", qtype="recall", confidence="high", quiet=True)
    c = c0(cfg)
    assert (c["attempts"], c["correct"], c["repeats"], c["streak"]) == (3, 3, 2, 1)
    assert c["correct_days"] == ["2030-03-20"] and L.badge(c) == "fair"
    assert c["by_type"]["recall"] == {"attempts": 1, "correct": 1}
    assert c["by_conf"]["high"] == {"attempts": 1, "correct": 1}
    assert run(t, "rebuild", "t", "--check")[0] == 0                  # replay applies the same rule


def test_an_ok_after_a_miss_the_same_day_earns_nothing(cfg, t):
    L.record(cfg, "t", "d:c0", "miss", quiet=True)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    c = c0(cfg)
    assert c["streak"] == 0 and not c.get("correct_days") and c["correct"] == 1


def test_a_quiz_after_a_dialogue_the_same_day_earns_nothing(cfg, t, monkeypatch):
    monkeypatch.setenv("KENLOOP_GRADER", "test-model")
    L.record(cfg, "t", "d:c0", "ok", mode="dialogue", rubric={"chain": 2, "predict": 2, "limits": 2}, quiet=True)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    assert c0(cfg).get("streak", 0) == 0 and c0(cfg)["repeats"] == 1


def test_a_miss_on_a_repeat_still_counts_against_you(cfg, t, monkeypatch):
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-18")
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-20")
    L.record(cfg, "t", "d:c0", "ok", quiet=True)                      # streak 2
    L.record(cfg, "t", "d:c0", "miss", note="mixed it up", quiet=True)  # later that day, in an exam
    c = c0(cfg)
    assert c["streak"] == 0 and c["due"] == "2030-03-21" and c["repeats"] == 1
    assert c["errors"][-1].endswith("mixed it up")
    assert run(t, "rebuild", "t", "--check")[0] == 0


def test_a_correct_repeat_neither_raises_nor_resets_and_the_next_day_counts(cfg, t, monkeypatch):
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    due = c0(cfg)["due"]
    L.record(cfg, "t", "d:c0", "ok", guess=True, quiet=True)          # a same-day guess: counted, nothing else
    assert c0(cfg)["streak"] == 1 and c0(cfg)["due"] == due
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    assert c0(cfg)["streak"] == 2 and c0(cfg)["correct_days"] == ["2030-03-20", "2030-03-22"]


def test_other_concepts_the_same_day_are_first_looks(cfg, t):
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    L.record(cfg, "t", "d:c1", "ok", quiet=True)
    assert L.load_state(cfg, "t")["concepts"]["d:c1"]["streak"] == 1


def test_record_says_a_repeat_earned_no_credit(cfg, t, capsys):
    L.record(cfg, "t", "d:c0", "ok")
    capsys.readouterr()
    L.record(cfg, "t", "d:c0", "ok")
    assert "seen already today, so no credit" in capsys.readouterr().out


def test_graduation_shows_the_evidence_beside_each_candidate(cfg, home, monkeypatch, capsys):
    from kenloop.career import graduate as G
    L.plan(cfg, "g", outlets=("career",))
    (home / "topics" / "g" / "syllabus.md").write_text(
        "## Concepts\n" + "".join(f"- d :: c{i} :: x\n" for i in range(4)))
    L.sync(cfg, "g", quiet=True)
    for day, qt in (("2030-03-10", "recall"), ("2030-03-12", "applied"), ("2030-03-15", "applied")):
        monkeypatch.setenv("KENLOOP_TODAY", day)
        for i in range(4):
            L.record(cfg, "g", f"d:c{i}", "ok", qtype=qt, quiet=True)
    L.record(cfg, "g", "d:c0", "ok", quiet=True)                       # a same-day repeat
    capsys.readouterr()
    G.graduate(cfg, "g")
    out = capsys.readouterr().out
    assert "right unaided on 3 day(s) (2030-03-10, 2030-03-12, 2030-03-15); types applied, recall" in out
    assert "1 same-day repeat(s)" in out and "no banked question: asked off the record" in out
    G.graduate(cfg, "g", emit=True)
    got = capsys.readouterr()
    assert "evidence d:c0:" in got.err and "evidence" not in got.out    # never pasted into facts.md


def test_record_warns_on_credit_without_a_banked_question_and_on_a_mismatched_type(cfg, t, capsys, monkeypatch):
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    assert "no banked question" in capsys.readouterr().err
    L.bank(cfg, "t", "d:c1", "Q?", "A", "ref", qtype="recall")
    capsys.readouterr()
    L.record(cfg, "t", "d:c1", "ok", qtype="edge", quiet=True)
    err = capsys.readouterr().err
    assert "matches none of d:c1's banked questions (recall)" in err and "no banked question" not in err
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    L.record(cfg, "t", "d:c1", "ok", qtype="recall", quiet=True)
    assert capsys.readouterr().err == ""                              # an honest, banked answer is quiet


def test_calibration_shows_its_count_and_a_one_day_concentration(cfg, home, capsys):
    L.plan(cfg, "k")
    (home / "topics" / "k" / "syllabus.md").write_text("## Concepts\n" + "".join(f"- d :: c{i} :: x\n" for i in range(4)))
    L.sync(cfg, "k", quiet=True)
    for i in range(4):
        L.record(cfg, "k", f"d:c{i}", "ok", confidence="high", quiet=True)
    L.record(cfg, "k", "d:c0", "ok", confidence="high", quiet=True)      # a repeat: not counted
    capsys.readouterr()
    L.calibration(cfg, "k")
    out = capsys.readouterr().out
    assert "4 rated answer(s), first looks only, on 1 day(s)" in out and "high  4/4" in out
    assert "4 of 4 came from one day (2030-03-20)" in out


def test_a_correct_answer_after_a_prediction_is_scheduled_for_tomorrow_not_left_due_now(cfg, t, monkeypatch):
    # The labs flow: predict first, then answer right the same day.
    # The answer is a repeat, so it earns nothing; but a concept never scheduled must still get a
    # review, or it reads "due unscheduled" (due NOW) and comes straight back as another repeat.
    L.record(cfg, "t", "d:c0", "miss", mode="predict", quiet=True)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    c = c0(cfg)
    assert c["due"] == "2030-03-21" and c.get("streak", 0) == 0 and not c.get("correct_days")
    assert not c.get("interval"), "no credit: the schedule is a first look, not a learned interval"
    assert not any(cid == "d:c0" for cid, _ in R.due_list(cfg, "t"))
    assert run(t, "rebuild", "t", "--check")[0] == 0                  # replay applies the same rule
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    L.record(cfg, "t", "d:c0", "ok", quiet=True)                      # tomorrow is a real first look
    assert c0(cfg)["streak"] == 1 and c0(cfg)["correct_days"] == ["2030-03-21"]


def test_a_correct_repeat_after_teaching_is_scheduled_for_tomorrow(cfg, t):
    L.record(cfg, "t", "d:c0", "ok", mode="teach", quiet=True)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    assert c0(cfg)["due"] == "2030-03-21"
