"""Property tests written from the README and docs, not from the code.

They check the rules the docs state: what earns study credit and what does not, the dialogue
rubric rule, marks and the trail (a mark moves what comes next and never credit), append-only
ledgers, drift and damaged-log exit codes, and the ## Held claim gate with its qualifier list.
Every home is a fresh directory under pytest's temp dir; HOME and KENLOOP_HOME point there too.
Needs Hypothesis, a test dependency only: `pip install -e .[test]`."""
import contextlib
import datetime as dt
import io
import json
import os
import re

import pytest

from hypothesis import example, given, settings, strategies as st

from kenloop import cli  # noqa: E402
from kenloop.core import ledger  # noqa: E402

BASE = dt.date(2030, 1, 1)
NAMES = ["alpha", "bravo", "charlie"]
MOVES = ["chain", "predict", "pushback", "limits", "connect", "question"]
_state = {"base": None, "n": 0, "shared": {}}


def fast(n):
    return settings(max_examples=n, derandomize=True, database=None, deadline=None)


@pytest.fixture(scope="module", autouse=True)
def _sandbox(tmp_path_factory):
    base = tmp_path_factory.mktemp("props")
    mp = pytest.MonkeyPatch()
    mp.setenv("HOME", str(base / "userhome"))
    mp.setenv("XDG_DATA_HOME", str(base / "xdg"))
    mp.setenv("KENLOOP_TODAY", BASE.isoformat())
    mp.delenv("KENLOOP_HOME", raising=False)
    mp.delenv("KENLOOP_GRADER", raising=False)
    _state.update(base=base, n=0, shared={})
    yield
    mp.undo()


# ---------------------------------------------------------------- helpers
def day(n):
    return (BASE + dt.timedelta(days=n)).isoformat()


def ken(h, *args, d=0):
    os.environ["KENLOOP_TODAY"] = day(d)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            rc = cli.main(["--home", str(h), *args])
        except SystemExit as e:
            rc = e.code
    return rc, buf.getvalue()


def fresh(names=NAMES):
    """A new home with topic t and one concept per name (ids d:NAME)."""
    _state["n"] += 1
    h = _state["base"] / f"home{_state['n']}"
    assert ken(h, "init")[0] == 0
    assert ken(h, "plan", "t")[0] == 0
    p = h / "topics" / "t" / "syllabus.md"
    p.write_text(p.read_text().rstrip() + "\n" + "".join(f"- d :: {n} :: about {n}\n" for n in names))
    assert ken(h, "sync", "t")[0] == 0
    return h


def shared(key):
    if key not in _state["shared"]:
        _state["shared"][key] = fresh()
    return _state["shared"][key]


def rec(h, c, result, *flags, d=0):
    return ken(h, "record", "t", f"d:{c}", result, *flags, d=d)


def log_path(h):
    return h / "topics" / "t" / "log.jsonl"


def log_text(h):
    p = log_path(h)
    return p.read_text() if p.exists() else ""


def badge(h, c, d=0):
    rc, out = ken(h, "mastery", "t", d=d)
    assert rc == 0, out
    lines = [x for x in out.splitlines() if f"d:{c}" in x]
    assert len(lines) == 1, out
    return lines[0].split()[0]


def next_date(out):
    m = re.search(r"next review (\d{4}-\d{2}-\d{2})", out)
    assert m, out
    return dt.date.fromisoformat(m.group(1))


def concepts_named_by_next(out):
    lines = [x for x in out.splitlines() if x.startswith("NEXT:")]
    assert len(lines) == 1, out
    return set(re.findall(r"d:\w+", lines[0]))


def next_concepts(h, d=0):
    rc, out = ken(h, "next", d=d)
    assert rc == 0, out
    return concepts_named_by_next(out)


# ---------------------------------------------------------------- dialogue rubric
def verdict(scores, hint):
    n, s = len(scores), sum(scores)
    if 2 * s >= 3 * n and 0 not in scores:  # mean >= 1.5, no move at 0
        v = "ok"
    elif 4 * s >= 3 * n:  # mean >= 0.75
        v = "partial"
    else:
        v = "miss"
    if hint == 4 and v == "ok":  # told the answer: at most partial
        v = "partial"
    return v


def rubric_arg(r):
    return ",".join(f"{k}={v}" for k, v in r.items())


def dialogue(h, result, r, *flags):
    return rec(h, "alpha", result, "--mode", "dialogue", "--rubric", rubric_arg(r), "--grader", "tester-1", *flags)


@fast(40)
@given(st.dictionaries(st.sampled_from(MOVES), st.integers(0, 2), min_size=3, max_size=6),
       st.sampled_from(["ok", "partial", "miss"]), st.integers(0, 4))
@example({"chain": 2, "predict": 2, "limits": 2}, "ok", 3).via("doc: hint depth 3 is not capped")
@example({"chain": 2, "predict": 2, "limits": 2}, "ok", 4).via("doc: told the answer (4) is graded at most partial")
@example({"chain": 2, "predict": 2, "limits": 2}, "partial", 4).via("doc: told the answer (4) is graded at most partial")
@example({"chain": 2, "predict": 2, "limits": 1}, "ok", 0).via("doc: mean 1.67, ok")
@example({"chain": 2, "predict": 1, "limits": 1}, "ok", 0).via("doc: mean 1.33 is below 1.5")
@example({"chain": 2, "predict": 1, "limits": 1}, "partial", 0).via("doc: mean 1.33 is partial")
@example({"chain": 2, "predict": 2, "limits": 1, "connect": 1}, "ok", 0).via("doc: mean exactly 1.5, ok")
@example({"chain": 2, "predict": 2, "limits": 2, "connect": 0}, "ok", 0).via("doc: no move at 0 for ok, mean is 1.5")
@example({"chain": 2, "predict": 2, "limits": 2, "connect": 0}, "partial", 0).via("doc: a 0 caps it at partial")
@example({"chain": 2, "predict": 2, "limits": 2, "connect": 1, "pushback": 1, "question": 1}, "ok", 0).via("doc: 6 moves, mean exactly 1.5")
@example({"chain": 2, "predict": 2, "limits": 1, "connect": 1, "pushback": 1, "question": 1}, "ok", 0).via("doc: 6 moves, mean 1.33, not ok")
@example({"chain": 2, "predict": 2, "limits": 1, "connect": 1, "pushback": 1}, "ok", 0).via("doc: 5 moves, mean 1.4 is below 1.5")
@example({"chain": 2, "predict": 2, "limits": 1, "connect": 1, "pushback": 1}, "partial", 0).via("doc: 5 moves, mean 1.4 is partial")
@example({"chain": 2, "predict": 2, "limits": 2, "connect": 1, "pushback": 1}, "ok", 0).via("doc: 5 moves, mean 1.6 is ok")
@example({"chain": 1, "predict": 1, "limits": 1, "connect": 0}, "partial", 0).via("doc: mean exactly 0.75, partial")
@example({"chain": 1, "predict": 1, "limits": 1, "connect": 0}, "miss", 0).via("doc: mean exactly 0.75 is not a miss")
@example({"chain": 1, "predict": 1, "limits": 0, "connect": 0}, "partial", 0).via("doc: mean 0.5 is below 0.75")
@example({"chain": 1, "predict": 1, "limits": 0, "connect": 0}, "miss", 0).via("doc: mean 0.5 is a miss")
@example({"chain": 1, "predict": 1, "limits": 1, "connect": 1, "pushback": 1, "question": 0}, "partial", 0).via("doc: 6 moves, mean 0.83")
@example({"chain": 1, "predict": 1, "limits": 1, "connect": 1, "pushback": 0, "question": 0}, "miss", 0).via("doc: 6 moves, mean 0.67")
@example({"chain": 0, "predict": 0, "limits": 0}, "miss", 0).via("doc: all zeros is a miss")
def test_a_dialogue_result_must_be_the_one_the_rubric_gives(rubric, result, hint):
    h = shared("rubric")
    before = log_text(h)
    rc, out = dialogue(h, result, rubric, "--hint-depth", str(hint))
    if result == verdict(list(rubric.values()), hint):
        assert rc == 0, out
        assert len(log_text(h).splitlines()) == len(before.splitlines()) + 1
    else:
        assert rc != 0, out
        assert log_text(h) == before  # a refused grade writes nothing


@pytest.mark.parametrize("move", MOVES)
def test_every_documented_move_is_accepted(move):
    others = [m for m in MOVES if m != move][:2]
    h = shared("moves")
    before = log_text(h)
    rc, out = dialogue(h, "ok", {move: 2, others[0]: 2, others[1]: 2})
    assert rc == 0, out
    assert len(log_text(h).splitlines()) == len(before.splitlines()) + 1


@fast(30)
@given(st.dictionaries(st.sampled_from(MOVES), st.integers(0, 2), min_size=1, max_size=2))
@example({"chain": 2}).via("doc: probe at least three moves, one is too few")
@example({"chain": 2, "predict": 2}).via("doc: probe at least three moves, two is too few")
def test_a_rubric_with_fewer_than_three_probed_moves_is_refused(rubric):
    h = shared("few")
    before = log_text(h)
    rc, out = dialogue(h, verdict(list(rubric.values()), 0), rubric)  # the result is the right one
    assert rc != 0, out
    assert log_text(h) == before


@pytest.mark.parametrize("bad", [-1, 3, 9])
def test_a_move_score_outside_0_to_2_is_refused(bad):
    h = shared("range")
    before = log_text(h)
    rc, out = rec(h, "alpha", "ok", "--mode", "dialogue", "--rubric", f"chain={bad},predict=2,limits=2",
                  "--grader", "tester-1")
    assert rc != 0, out
    assert log_text(h) == before
    assert dialogue(h, "ok", {"chain": 2, "predict": 2, "limits": 2})[0] == 0  # same call with valid scores


def test_a_dialogue_grade_needs_a_grader_and_names_it(monkeypatch):
    h = shared("grader")
    args = ("ok", "--mode", "dialogue", "--rubric", "chain=2,predict=2,limits=2")
    before = log_text(h)
    rc, out = rec(h, "alpha", *args)
    assert rc != 0, out
    assert log_text(h) == before
    rc, out = rec(h, "alpha", *args, "--grader", "model-xyz")
    assert rc == 0, out
    assert "model-xyz" in log_text(h)
    monkeypatch.setenv("KENLOOP_GRADER", "env-grader-7")  # doc: or KENLOOP_GRADER
    rc, out = rec(h, "alpha", *args)
    assert rc == 0, out
    assert "env-grader-7" in log_text(h)


# ---------------------------------------------------------------- study credit
def plain_run(events):
    """Documented credit model for ok/miss only: the first look of a day earns a streak step if it
    is a correct, any miss resets the streak, and a correct repeat earns nothing."""
    streak, seen = 0, set()
    for dd, kind in events:
        first = dd not in seen
        seen.add(dd)
        if kind == "miss":
            streak = 0
        elif first:
            streak += 1
    return streak


def run_plain(h, events):
    for dd, kind in events:
        assert rec(h, "alpha", kind, d=dd)[0] == 0


plain_events = st.lists(st.tuples(st.integers(0, 4), st.sampled_from(["ok", "ok", "miss"])),
                        min_size=1, max_size=9).map(sorted)


@fast(25)
@given(plain_events)
@example([(0, "ok"), (1, "ok"), (2, "ok")]).via("doc: three unaided answers on three days make a concept mastered")
@example([(0, "ok"), (1, "ok")]).via("doc: two is not mastered")
@example([(0, "ok")] * 5 + [(1, "ok")]).via("doc: five correct on one day are one correct")
@example([(0, "ok")] * 5 + [(1, "ok"), (2, "ok")]).via("doc: five on one day then two more days is three")
@example([(0, "ok"), (1, "ok"), (2, "miss"), (3, "ok")]).via("doc: a miss ends the run")
@example([(0, "ok"), (1, "ok"), (2, "miss"), (3, "ok"), (4, "ok"), (4, "ok")]).via("doc: a repeat after a miss credits nothing")
@example([(0, "ok"), (1, "ok"), (1, "miss"), (2, "ok")]).via("doc: a wrong repeat still counts against you")
@example([(0, "ok"), (0, "ok"), (1, "ok"), (2, "ok")]).via("doc: early repeat does not count twice")
def test_mastered_means_three_credited_correct_answers_since_the_last_miss(events):
    h = fresh()
    run_plain(h, events)
    assert (badge(h, "alpha", d=5) == "mastered") == (plain_run(events) >= 3)


def test_three_unaided_answers_on_three_consecutive_days_master_a_concept_early():
    h = fresh()
    for dd in range(3):  # each is before the previous answer's review date
        assert rec(h, "alpha", "ok", d=dd)[0] == 0
    assert badge(h, "alpha", d=2) == "mastered"


AIDED = {
    "guess": ["--guess"],
    "hint1": ["--hint-depth", "1"],
    "hint2": ["--hint-depth", "2"],
    "hint3": ["--hint-depth", "3"],
    "hint4": ["--hint-depth", "4"],
    "lookup": ["--lookup"],
    "learn": ["--mode", "learn"],
    "predict": ["--mode", "predict"],
}


@pytest.mark.parametrize("kind", sorted(AIDED))
def test_an_answer_that_is_not_unaided_earns_no_streak_step(kind):
    h = fresh()
    assert rec(h, "alpha", "ok", d=0)[0] == 0
    assert rec(h, "alpha", "ok", d=1)[0] == 0
    assert rec(h, "alpha", "ok", *AIDED[kind], d=2)[0] == 0
    assert badge(h, "alpha", d=2) != "mastered"
    h2 = fresh()
    assert rec(h2, "alpha", "ok", *AIDED[kind], d=0)[0] == 0
    assert rec(h2, "alpha", "ok", d=1)[0] == 0
    assert rec(h2, "alpha", "ok", d=2)[0] == 0
    assert badge(h2, "alpha", d=2) != "mastered"
    h3 = fresh()  # control: the same three days unaided
    for dd in range(3):
        assert rec(h3, "alpha", "ok", d=dd)[0] == 0
    assert badge(h3, "alpha", d=2) == "mastered"


FIRST_LOOKS = sorted(AIDED) + ["miss", "taught", "dialogue"]


@pytest.mark.parametrize("first", FIRST_LOOKS)
def test_after_any_first_look_a_correct_answer_that_day_is_a_repeat(first):
    h = fresh()
    if first == "miss":
        assert rec(h, "alpha", "miss", d=0)[0] == 0
    elif first == "taught":
        assert ken(h, "taught", "t", "d:alpha", d=0)[0] == 0
    elif first == "dialogue":
        assert dialogue(h, "ok", {"chain": 2, "predict": 2, "limits": 2})[0] == 0
    else:
        assert rec(h, "alpha", "ok", *AIDED[first], d=0)[0] == 0
    assert rec(h, "alpha", "ok", d=0)[0] == 0  # the repeat
    assert rec(h, "alpha", "ok", d=1)[0] == 0
    assert rec(h, "alpha", "ok", d=2)[0] == 0
    assert badge(h, "alpha", d=2) != "mastered"  # only two days earned credit


def test_a_graded_dialogue_does_not_reset_a_quiz_streak():
    h = fresh()
    assert rec(h, "alpha", "ok", d=0)[0] == 0
    assert rec(h, "alpha", "ok", d=1)[0] == 0
    rc, out = rec(h, "alpha", "miss", "--mode", "dialogue", "--rubric", "chain=0,predict=0,limits=0",
                  "--grader", "tester-1", d=2)
    assert rc == 0, out
    assert rec(h, "alpha", "ok", d=3)[0] == 0
    assert badge(h, "alpha", d=3) == "mastered"


def test_a_correct_answer_you_were_unsure_of_still_earns_credit():
    h = fresh()
    for dd in range(3):
        assert rec(h, "alpha", "ok", "--confidence", "low", d=dd)[0] == 0
    assert badge(h, "alpha", d=2) == "mastered"


@fast(22)
@given(st.integers(0, 5), st.integers(1, 40))
@example(0, 1).via("doc: first review")
def test_an_unsure_correct_comes_back_no_later_than_a_sure_one(prior, gap):
    dates = []
    for flags in ([], ["--confidence", "low"]):
        h = fresh()
        for i in range(prior):
            assert rec(h, "alpha", "ok", d=i * 3)[0] == 0
        dd = prior * 3 + gap
        rc, out = rec(h, "alpha", "ok", *flags, d=dd)
        assert rc == 0, out
        dates.append(next_date(out))
    assert dates[1] <= dates[0]


def test_a_first_correct_answer_is_reviewed_two_days_later():
    # FSRS-6 default initial stability for a good answer is about 2.3 days; the interval is whole days
    h = fresh()
    rc, out = rec(h, "alpha", "ok", d=0)
    assert rc == 0, out
    assert next_date(out) == BASE + dt.timedelta(days=2)


@fast(22)
@given(st.lists(st.integers(1, 60), max_size=5), st.integers(1, 60), st.sampled_from([["miss"], ["ok", "--guess"]]))
@example([], 1, ["miss"]).via("doc: a miss on the first look")
@example([5, 30], 7, ["ok", "--guess"]).via("doc: a guess comes back tomorrow")
def test_a_miss_or_a_guess_always_comes_back_tomorrow(gaps, last_gap, args):
    h = fresh()
    dd = 0
    for g in gaps:
        dd += g
        assert rec(h, "alpha", "ok", d=dd)[0] == 0
    dd += last_gap
    rc, out = rec(h, "alpha", *args, d=dd)
    assert rc == 0, out
    assert next_date(out) == BASE + dt.timedelta(days=dd + 1)


@fast(22)
@given(st.integers(1, 30))
@example(1).via("doc: an exam tomorrow")
@example(2).via("doc: an exam the day a first review would land")
@example(30).via("doc: a far exam")
def test_an_exam_date_pulls_reviews_in_front_of_it(k):
    h = fresh()
    assert ken(h, "cert", "exam-date", "t", "--set", day(k), d=0)[0] == 0
    rc, out = rec(h, "alpha", "ok", d=0)
    assert rc == 0, out
    assert next_date(out) <= BASE + dt.timedelta(days=k)


@fast(20)
@given(st.dates(min_value=dt.date(2030, 1, 2), max_value=dt.date(2100, 12, 31)))
@example(dt.date(2030, 2, 28)).via("doc: YYYY-MM-DD")
def test_an_exam_date_takes_the_documented_form_only(date):
    h = shared("exam-date")
    assert ken(h, "cert", "exam-date", "t", "--set", date.isoformat())[0] == 0
    for bad in (date.strftime("%Y%m%d"), f"{date.year}-{date.month}-{date.day:02d}x", date.strftime("%d/%m/%Y")):
        assert ken(h, "cert", "exam-date", "t", "--set", bad)[0] != 0, bad
    assert ken(h, "cert", "exam-date", "t", "--clear")[0] == 0


# ---------------------------------------------------------------- the record: replay, drift, damage
plan_events = st.lists(st.tuples(st.sampled_from(["alpha", "bravo"]), st.sampled_from(["ok", "miss", "partial"])),
                       min_size=1, max_size=6)


def build(h, plan):
    for i, (c, r) in enumerate(plan):
        assert rec(h, c, r, d=i)[0] == 0


def derived(h):
    return (h / "topics" / "t" / "concepts.json").read_bytes()


@fast(22)
@given(plan_events)
def test_rebuild_check_agrees_with_the_record_and_rebuild_is_idempotent(plan):
    h = fresh()
    build(h, plan)
    before = derived(h)
    assert ken(h, "rebuild", "t", "--check", d=len(plan))[0] == 0
    assert ken(h, "rebuild", "t", d=len(plan))[0] == 0
    assert derived(h) == before  # replay of the log is the state
    assert ken(h, "rebuild", "t", "--check", d=len(plan))[0] == 0


def tamper_attempts(h):
    p = h / "topics" / "t" / "concepts.json"
    data = json.loads(p.read_text())
    cid = next(k for k, v in data["concepts"].items() if v.get("attempts"))
    data["concepts"][cid]["attempts"] += 7
    p.write_text(json.dumps(data))


def drop_concept(h):
    p = h / "topics" / "t" / "concepts.json"
    data = json.loads(p.read_text())
    del data["concepts"]["d:alpha"]
    p.write_text(json.dumps(data))


@pytest.mark.parametrize("damage", [tamper_attempts, drop_concept])
def test_a_stored_state_that_disagrees_with_the_log_is_drift(damage):
    h = fresh()
    build(h, [("alpha", "ok"), ("bravo", "ok")])
    damage(h)
    assert ken(h, "rebuild", "t", "--check")[0] == 3
    assert ken(h, "rebuild", "t")[0] == 0
    assert ken(h, "rebuild", "t", "--check")[0] == 0


@pytest.mark.parametrize("view", [("mastery", "t"), ("due", "t"), ("board",)])
def test_a_view_over_drifted_state_prints_then_exits_3(view):
    h = fresh()
    build(h, [("alpha", "ok")])
    tamper_attempts(h)
    rc, out = ken(h, *view, d=5)
    assert rc == 3
    assert out.strip()


DAMAGE = {
    "text": b"{this is not json\n",
    "binary": b"\xff\xfe\x00bad\n",
}


@pytest.mark.parametrize("name", sorted(DAMAGE))
def test_a_damaged_log_row_stops_record_and_reads_as_not_evaluable(name):
    h = fresh()
    build(h, [("alpha", "ok")])
    p = log_path(h)
    p.write_bytes(p.read_bytes() + DAMAGE[name])
    raw = p.read_bytes()
    stored = derived(h)
    assert rec(h, "alpha", "ok", d=5)[0] == 2
    assert p.read_bytes() == raw  # nothing was added to a damaged log
    for verb in (("rebuild", "t", "--check"), ("rebuild", "t"), ("validate", "t"), ("due", "t"),
                 ("misconceptions", "t"), ("sync", "t")):
        rc, out = ken(h, *verb, d=5)
        assert rc == 2, (verb, out)
        assert out.strip(), verb
    assert derived(h) == stored  # a refused rebuild writes nothing


@fast(22)
@given(st.text(max_size=20))
def test_any_line_that_is_not_a_record_damages_the_log(junk):
    h = shared("junk")
    p = log_path(h)
    if not p.exists():
        assert rec(h, "alpha", "ok")[0] == 0
    good = p.read_bytes()
    p.write_bytes(good + b"x" + junk.replace("\n", " ").replace("\r", " ").encode("utf-8", "replace") + b"\n")
    try:
        assert ken(h, "rebuild", "t", "--check")[0] == 2
        assert rec(h, "alpha", "ok", d=3)[0] == 2
    finally:
        p.write_bytes(good)


def empty_home():
    _state["n"] += 1
    h = _state["base"] / f"home{_state['n']}"
    assert ken(h, "init")[0] == 0
    return h


@pytest.mark.parametrize("verb", [("doctor",), ("next",), ("validate",), ("due",), ("jobs", "gaps")])
def test_an_empty_home_is_not_evaluable(verb):
    rc, out = ken(empty_home(), *verb)
    assert rc == 2, out
    assert out.strip()


@pytest.mark.parametrize("verb", [("next",), ("validate",), ("due",), ("jobs", "gaps")])
def test_an_empty_home_prints_its_denominator(verb):
    rc, out = ken(empty_home(), *verb)
    assert re.search(r"\b0 (?:topic|role)\(s\)", out), out


@pytest.mark.parametrize("argv", [("mark", "t", "d:alpha", "bogus"), ("record", "t", "d:alpha", "bogus"),
                                  ("no-such-verb",)])
def test_a_usage_error_exits_64(argv):
    h = fresh()
    assert ken(h, *argv)[0] == 64


# ---------------------------------------------------------------- ledgers
rowdicts = st.dictionaries(st.text("abcdefgh", min_size=1, max_size=4),
                           st.one_of(st.integers(-5, 5), st.text(max_size=8), st.booleans()), max_size=4)


@fast(60)
@given(rows=st.lists(rowdicts, max_size=8))
def test_ledger_rows_read_back_in_the_order_they_were_appended(rows, tmp_path_factory):
    p = tmp_path_factory.mktemp("ledger") / "x.jsonl"
    assert ledger.read(p) == ([], [])
    for r in rows:
        ledger.append(p, r)
    assert ledger.read(p) == (rows, [])


@fast(40)
@given(rows=st.lists(rowdicts, min_size=1, max_size=5), junk=st.sampled_from(["{nope", "[1,2", "not json at all"]))
def test_ledger_names_a_damaged_line_and_will_not_append_past_it(rows, junk, tmp_path_factory):
    p = tmp_path_factory.mktemp("ledger") / "x.jsonl"
    for r in rows:
        ledger.append(p, r)
    with open(p, "a") as f:
        f.write(junk + "\n")
    got, problems = ledger.read(p)
    assert got == rows
    assert len(problems) == 1 and str(len(rows) + 1) in problems[0]  # names the line
    size = p.stat().st_size
    with pytest.raises(Exception):
        ledger.append(p, {"x": 1})
    assert p.stat().st_size == size


# ---------------------------------------------------------------- marks and the trail
CLASS = {"problem": 0, "fuzzy": 1, None: 2, "solid": 3}
mark_ops = st.lists(st.tuples(st.sampled_from(NAMES), st.sampled_from(["problem", "fuzzy", "solid", "clear"])),
                    max_size=7)


@pytest.mark.parametrize("word", ["problem", "fuzzy", "solid", "clear"])
def test_each_documented_mark_word_is_accepted_and_recorded(word):
    h = fresh()
    assert ken(h, "mark", "t", "d:alpha", word)[0] == 0
    assert word in (h / "topics" / "t" / "marks.jsonl").read_text()


def test_an_unknown_mark_word_is_refused_and_writes_nothing():
    h = fresh()
    assert ken(h, "mark", "t", "d:alpha", "fuzzy")[0] == 0
    p = h / "topics" / "t" / "marks.jsonl"
    before = p.read_bytes()
    assert ken(h, "mark", "t", "d:alpha", "shaky")[0] != 0
    assert p.read_bytes() == before


@fast(30)
@given(mark_ops)
@example([("charlie", "problem")]).via("doc: what you marked a problem comes first")
@example([("alpha", "fuzzy"), ("charlie", "problem")]).via("doc: problem before fuzzy")
@example([("bravo", "fuzzy")]).via("doc: fuzzy before what is unmarked")
@example([("alpha", "solid"), ("bravo", "solid")]).via("doc: solid last")
@example([("charlie", "problem"), ("charlie", "clear")]).via("doc: clear takes the mark off")
@example([("charlie", "problem"), ("charlie", "solid")]).via("doc: the latest mark counts")
@example([("alpha", "solid"), ("bravo", "solid"), ("charlie", "solid")]).via("doc: all solid, any may come")
def test_next_takes_the_best_marked_idea_first(ops):
    h = fresh()
    eff = {n: None for n in NAMES}
    for n, w in ops:
        assert ken(h, "mark", "t", f"d:{n}", w)[0] == 0
        eff[n] = None if w == "clear" else w
    best = min(CLASS[eff[n]] for n in NAMES)
    allowed = {f"d:{n}" for n in NAMES if CLASS[eff[n]] == best}
    chosen = next_concepts(h)
    assert len(chosen) == 1 and chosen <= allowed, (eff, chosen)


@pytest.mark.parametrize("result", ["miss", "partial"])
@pytest.mark.parametrize("attempt_day", [0, 3])
def test_a_later_miss_or_partial_outweighs_a_solid_mark(result, attempt_day):
    h = fresh()
    for n in NAMES:  # all three solid
        assert ken(h, "mark", "t", f"d:{n}", "solid", d=0)[0] == 0
    assert rec(h, "charlie", result, d=attempt_day)[0] == 0
    assert next_concepts(h, d=attempt_day) == {"d:charlie"}  # no longer last, though listed last


@fast(22)
@given(mark_ops, st.lists(st.text(alphabet=st.characters(exclude_categories=("Cs", "Cc")), max_size=12), max_size=3))
def test_marks_never_move_credit_the_schedule_or_the_replay(ops, whys):
    h = fresh()
    build(h, [("alpha", "ok"), ("bravo", "miss"), ("alpha", "ok")])

    def snapshot():
        return (derived(h), ken(h, "mastery", "t", d=4), ken(h, "due", "t", d=9), ken(h, "board", d=4))

    before = snapshot()
    for i, (n, w) in enumerate(ops):
        extra = ["--why", whys[i % len(whys)]] if whys else []
        assert ken(h, "mark", "t", f"d:{n}", w, *extra, d=3)[0] == 0
    assert snapshot() == before
    assert ken(h, "rebuild", "t", "--check", d=4)[0] == 0
    assert "mark" not in log_text(h)


def test_a_damaged_marks_file_steers_nothing_and_is_named_until_it_is_fixed():
    h = fresh()
    assert ken(h, "mark", "t", "d:charlie", "problem")[0] == 0
    assert next_concepts(h) == {"d:charlie"}
    p = h / "topics" / "t" / "marks.jsonl"
    good = p.read_bytes()
    p.write_bytes(good + b"{this is not json\n")  # the problem mark above the damage is not used either
    rc, out = ken(h, "next")
    assert rc == 0, out
    assert concepts_named_by_next(out) != {"d:charlie"}, out
    rc, out = ken(h, "session", "t")
    assert rc == 0 and "marks.jsonl" in out and "ignored" in out, out
    p.write_bytes(good)
    assert next_concepts(h) == {"d:charlie"}


trail_ops = st.lists(st.one_of(st.tuples(st.just("down"), st.sampled_from(NAMES)), st.just("back")), max_size=9)


@fast(25)
@given(trail_ops)
@example([("down", "bravo"), ("down", "charlie"), "back"]).via("doc: the way back to what started it")
@example([("down", "bravo"), "back", "back"]).via("doc: back from the first step")
def test_the_trail_is_a_stack_of_steps_down_and_back(ops):
    h = fresh()
    stack = []
    for i, op in enumerate(ops):
        if op == "back":
            if not stack:
                continue
            stack.pop()
            rc, out = ken(h, "trail", "--back")
            assert rc == 0, out
            if stack:
                assert f"d:{stack[-1][0]}" in out  # it names where you are back to
        else:
            why = f"w{i}x"
            rc, out = ken(h, "trail", "t", f"d:{op[1]}", "--why", why)
            assert rc == 0, out
            stack.append((op[1], why))
        rc, out = ken(h, "trail")
        assert rc == 0, out
        steps = [x for x in out.splitlines() if re.search(r"(?<!\w)d:\w+", x)]
        assert len(steps) == len(stack), out
        for line, (c, why) in zip(steps, stack):
            assert f"d:{c}" in line and why in line


@fast(20)
@given(st.lists(st.one_of(st.tuples(st.just("mark"), st.sampled_from(NAMES), st.sampled_from(["problem", "solid", "clear"])),
                          st.tuples(st.just("down"), st.sampled_from(NAMES)),
                          st.tuples(st.just("rec"), st.sampled_from(NAMES), st.sampled_from(["ok", "miss"])),
                          st.just("back")), max_size=8))
def test_the_record_files_only_ever_grow_by_appending(ops):
    h = fresh()
    files = [h / "topics" / "t" / "marks.jsonl", h / "trail.jsonl", log_path(h)]
    seen = {f: b"" for f in files}
    steps = 0
    for op in ops:
        steps += 1
        if op == "back":
            ken(h, "trail", "--back", d=steps)
        elif op[0] == "mark":
            assert ken(h, "mark", "t", f"d:{op[1]}", op[2], d=steps)[0] == 0
        elif op[0] == "down":
            assert ken(h, "trail", "t", f"d:{op[1]}", "--why", "w", d=steps)[0] == 0
        else:
            assert rec(h, op[1], op[2], d=steps)[0] == 0
        for f in files:
            now = f.read_bytes() if f.exists() else b""
            assert now.startswith(seen[f]), f.name  # earlier rows are never rewritten
            seen[f] = now


# ---------------------------------------------------------------- the ## Held claim gate
LEX = """name = "web"
[categories]
ops = ["docker", "redis", "ci/cd", "rate limiting", "machine learning", "regression"]
security = ["oauth", "tls", "tcp", "sql"]
api = ["graphql"]
"""


@pytest.fixture(scope="module")
def gate(_sandbox):
    _state["n"] += 1
    h = _state["base"] / f"home{_state['n']}"
    assert ken(h, "init")[0] == 0
    (h / "lexicons").mkdir(exist_ok=True)
    (h / "lexicons" / "web.toml").write_text(LEX)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    return h


def claims(h, facts, resume):
    (h / "facts.md").write_text(facts, encoding="utf-8")
    (h / "resume.md").write_text(resume, encoding="utf-8")
    return ken(h, "jobs", "check-claims", str(h / "resume.md"))


def held(*lines):
    return "# Facts\n## Held\n" + "".join(x + "\n" for x in lines)


DOCKER = "Worked with Docker daily.\n"
TERMS = ["Docker", "Redis", "OAuth", "GraphQL"]


@fast(40)
@given(st.sets(st.sampled_from(TERMS), min_size=1), st.sets(st.sampled_from(TERMS)), st.sets(st.sampled_from(TERMS)))
@example({"Docker"}, {"Docker"}, set()).via("doc: a held term passes")
@example({"Docker"}, set(), {"Docker"}).via("doc: a term under Learning is not held")
@example({"Docker", "Redis"}, {"Docker"}, set()).via("doc: one unheld term fails the resume")
def test_a_resume_term_passes_only_when_listed_under_held(gate, stated, holds, learning):
    facts = "# Facts\n## Learning\n" + "".join(f"- {t}\n" for t in sorted(learning)) \
        + "## Held\n" + "".join(f"- {t}\n" for t in sorted(holds))
    rc, out = claims(gate, facts, "Worked with " + ", ".join(sorted(stated)) + ".\n")
    missing = {t for t in stated if t not in holds}
    assert rc == (1 if missing else 0), out
    assert f"checked {len(stated)} resume term(s)" in out  # the denominator
    assert f"{len(missing)} violation(s)" in out
    for t in missing:
        assert t.lower() in out.lower()


FAMILIES = {
    "planned": ["planned", "planning to", "will learn", "to be learned", "someday", "eventually", "todo", "wip",
                "aspirational", "[verify", "next year", "down the road", "on my list"],
    "in progress": ["in progress", "pursuing", "not yet", "not-yet", "no active", "getting started",
                    "just started", "starting to", "ramping up"],
    "learning": ["learning", "(learning)", "I am learning", "online learning", "active learning"],
    "wish": ["want to", "hope to", "intend to", "aim to", "wish to", "would like to", "looking to",
             "interested in", "curious about"],
    "exploring": ["dabbled", "experimenting", "tinkering", "reading about"],
    "not held": ["do not claim", "do not list", "never", "not claimed"],
    "not used": ["did not use", "don't have", "not hands-on", "not proficient", "not in production"],
    "no experience": ["no production experience", "no real experience", "no hands-on exposure",
                      "limited experience", "little knowledge", "minimal exposure", "zero familiarity",
                      "lack of proficiency", "lacking hands-on experience", "without direct experience"],
    "familiar": ["familiarity", "coursework", "from a course", "from a tutorial", "from a class",
                 "from a bootcamp", "from a video", "from a book", "via a book"],
    "negation": ["not Redis", "no Redis", "without Redis", "except Redis", "instead of Redis"],
}
QUALIFIED = [f"- Docker, {w}" for ws in FAMILIES.values() for w in ws]
BASIC = ["basic", "beginner", "novice", "elementary", "rudimentary", "entry level", "intro", "introductory", "rusty"]
BASIC_FORMS = ["Docker ({w})", "Docker - {w}", "Docker: {w}", "Docker, {w}", "Docker; {w}", "Docker {w}"]
QUALIFIED += [f"- {f.format(w=w)}" for w in BASIC for f in BASIC_FORMS]
QUALIFIED += ["- Beginner Docker", "- Docker, basic knowledge", "- Docker, basic understanding",
              "- Docker, basic familiarity", "- Docker, PLANNED", "- Docker, Beginner"]


@pytest.mark.parametrize("line", QUALIFIED)
def test_a_qualifier_word_on_a_held_line_is_a_contradiction(gate, line):
    rc, out = claims(gate, held(line), DOCKER)
    assert rc == 1, out


@pytest.mark.parametrize("word", BASIC)
def test_the_message_for_a_basic_level_word_quotes_that_word(gate, word):
    rc, out = claims(gate, held(f"- Docker ({word})"), DOCKER)
    assert rc == 1 and f"qualifier '{word}'" in out, out


ORDINARY = (
    ["- Docker, aspiring", "- Docker, limited", "- Docker, junior"]  # doc: not qualifiers
    + [f"- Docker for {w} learning" for w in
       ["machine", "deep", "reinforcement", "transfer", "supervised", "unsupervised", "federated", "meta",
        "statistical", "ensemble", "contrastive", "representation", "lifelong", "continual", "incremental",
        "curriculum", "multi-task", "few-shot", "zero-shot"]]
    + ["- Docker for e-learning", "- Docker for learning management systems"]
    + ["- Docker, no-code", "- Docker for a not-for-profit", "- Docker, No. 1 choice", "- Docker, No.1 choice",
       "- Docker, No Starch Press", "- Docker, notifications", "- Docker, node", "- Docker, know"]
    + ["- Docker beginner-friendly images", "- Docker for beginners"]
    + ["- Docker (Udemy course)", "- Docker tutorial", "- Docker, bootcamp"]  # doc: known limit, not qualifiers
)


@pytest.mark.parametrize("line", ORDINARY)
def test_ordinary_prose_on_a_held_line_is_not_a_qualifier(gate, line):
    rc, out = claims(gate, held(line), DOCKER)
    assert rc == 0, out


HELD_SHEETS = [
    ("## Held\n- Docker\n", 0),
    ("## held\n- Docker\n", 0),
    ("## HELD ##\n- Docker\n", 0),
    ("##\tHeld\n- Docker\n", 0),
    ("Held\n----\n- Docker\n", 0),
    ("\ufeff## Held\n- Docker\n", 0),  # doc: a leading byte-order mark is ignored
    ("## Held\n### Sub\n- Docker\n", 0),  # doc: a ### inside it stays held
    ("# Facts (work in progress)\n## Held\n- Docker\n", 0),  # doc: a qualifier above Held does not count
    ("## Held\n- [x] Docker\n", 0),
    ("## Held\n1. Docker\n", 0),
    ("## Held\n- [Docker](https://example.invalid/x)\n", 0),  # doc: link text counts as a mention
    ("## Held\n- Python\n## Other\n- Docker\n", 1),  # doc: runs to the next level-2 heading
    ("## Held\n- Python\n# Top\n- Docker\n", 1),  # doc: or a higher one
    ("## Held\n- Python\n##\n- Docker\n", 1),  # doc: an empty heading ends the section
    ("## Learning\n- Docker\n## Held\n- Python\n", 1),
    ("## Held\n- Python\n## Learning\n- Docker\n", 1),
    ("## Held\n- [ ] Docker\n", 1),  # doc: an unchecked box is a to-do
    ("## Held\n1. [ ] Docker\n", 1),
    ("## Held\n- Docker\n  - (learning)\n", 1),  # doc: a nested item governs the one above
    ("## Held\n- Docker\n- Python\n  - Django (learning)\n", 1),  # doc: a qualified child makes a contradiction
    ("## Held\n### Learning\n- Docker\n", 1),  # doc: a qualifier on a sub-heading governs what is beneath
    ("## Held\n- Docker and Redis, planned\n", 1),  # doc: one qualifier disqualifies the block
    ("## Held\n- ~~Docker~~\n", 1),  # doc: struck text states nothing
    ("## Held\n<!--\n- Docker\n-->\n- Python\n", 1),  # doc: comments state nothing
    ("## Held\n```\n- Docker\n```\n- Python\n", 1),  # doc: fenced code states nothing
    ("# Facts\nI know Docker very well.\n## Held\n- Python\n", 1),  # doc: text before the heading is not held
    ("## Held\n- Dock\u0435r\n", 1),  # doc: a Held line spelled with a look-alike holds nothing
]


@pytest.mark.parametrize("sheet,rc", HELD_SHEETS)
def test_what_counts_as_held_follows_the_documented_structure(gate, sheet, rc):
    got, out = claims(gate, sheet, DOCKER)
    assert got == rc, out


NEAR_HELD_HEADING = ["# Held\n- Docker\n", "### Held\n- Docker\n", "## Held:\n- Docker\n", "## Held skills\n- Docker\n",
                     "## Not held\n- Docker\n", "## Skills I hold\n- Docker\n", "## Hel\u200bd\n- Docker\n",
                     "\uff03\uff03 Held\n- Docker\n", "##\u00a0Held\n- Docker\n", "# Facts\n\ufeff## Held\n- Docker\n"]
NOT_A_HEADING = ["####### Held\n- Docker\n", "    ## Held\n- Docker\n", "```\n## Held\n- Docker\n```\n",
                 "<!--\n## Held\n- Docker\n-->\n"]


@pytest.mark.parametrize("sheet", NEAR_HELD_HEADING + NOT_A_HEADING)
def test_a_non_empty_sheet_without_a_real_held_heading_is_not_evaluable(gate, sheet):
    rc, out = claims(gate, sheet, DOCKER)
    assert rc == 2, out
    assert "## held" in out.lower()  # the message says to add the heading


@pytest.mark.parametrize("sheet", NEAR_HELD_HEADING)
def test_the_message_names_the_line_of_a_heading_that_mentions_held(gate, sheet):
    rc, out = claims(gate, sheet, DOCKER)
    assert rc == 2 and re.search(r"line \d+", out), out


def test_a_resume_that_cannot_be_read_or_states_no_term_is_not_evaluable(gate):
    assert claims(gate, held("- Docker"), "I like cats.\n")[0] == 2
    assert claims(gate, held("- Docker"), "")[0] == 2
    assert ken(gate, "jobs", "check-claims", str(gate / "missing-resume.md"))[0] == 2
    (gate / "resume.md").write_bytes(b"\xff\xfeD\x00o\x00c\x00k\x00e\x00r\x00")  # UTF-16, not UTF-8
    assert ken(gate, "jobs", "check-claims", str(gate / "resume.md"))[0] == 2


def test_check_claims_never_modifies_the_facts_sheet(gate):
    facts = "# Facts\n## Held\n- Docker\n- Redis, planned\n"
    claims(gate, facts, "Docker Redis OAuth\n")
    assert (gate / "facts.md").read_text() == facts


def test_a_web_address_states_nothing(gate):
    rc, out = claims(gate, held("- Redis"), "Redis, see https://github.com/me/docker today.\n")
    assert rc == 0, out


def test_a_term_hidden_in_a_comment_is_reported_as_hidden(gate):
    rc, out = claims(gate, "# Facts\n<!--\n- Docker\n-->\n## Held\n- Python\n", DOCKER)
    assert rc == 1 and "hidden" in out, out


DISGUISE_CLEAN = ["Doc\u034fker", "Doc\u200bker", "Dock\u00ader", "Docker\u2122", "\uff24ocker", "Docker\u2019s",
                  "\u201cDocker\u201d", "Docker\u2026", "Doc\u2060ker"]
DISGUISED = ["Dock\u0435r", "Dock\u0435r-based", "Skills:Dock\u0435r", "Docker\u00b9", "Docker\u207a", "Docker\u2116",
             "Dock\u00b7er", "Dock\u2208r"]


@pytest.mark.parametrize("word", DISGUISE_CLEAN)
def test_invisible_and_compatibility_forms_read_as_the_plain_skill(gate, word):
    rc, out = claims(gate, held("- Docker"), f"Worked with {word} daily.\n")
    assert rc == 0, out


@pytest.mark.parametrize("word", DISGUISED)
def test_look_alikes_and_overlays_are_reported_even_when_the_skill_is_held(gate, word):
    rc, out = claims(gate, held("- Docker"), f"Worked with {word} daily.\n")
    assert rc == 1, out


@pytest.mark.parametrize("word", ["S\u0336QL", "S\u20ddQL", "\u0422\u0421\u0420", "r\u00e9gression"])
def test_more_documented_disguises_are_reported(gate, word):
    rc, out = claims(gate, held("- Docker", "- SQL", "- TCP", "- regression"), f"Worked with {word} daily.\n")
    assert rc == 1, out


@pytest.mark.parametrize("text", ["Docker in S\u00e3o Paulo", "Docker and caf\u00e9 in Z\u00fcrich", "Docker at \u041c\u043e\u0441\u043a\u0432\u0430"])
def test_ordinary_words_from_other_languages_are_clean(gate, text):
    rc, out = claims(gate, held("- Docker"), f"{text}\n")
    assert rc == 0, out


JOINERS = [" ", "  ", "\t", "\u00a0", "-", "\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2015", "\u2212", "\ufe58",
           "\ufe63", "\uff0d", "/", " / ", "\u00ad"]
NOT_JOINERS = ["", "_", "\n", "\r\n", "\n\n", ".", "\u00ad\n"]


@pytest.mark.parametrize("joiner", JOINERS)
def test_a_multiword_term_is_found_however_the_documented_joiners_join_it(gate, joiner):
    rc, out = claims(gate, held("- Docker"), f"Built rate{joiner}limiting and Docker.\n")  # only Docker is held
    assert rc == 1 and "rate limiting" in out, out


@pytest.mark.parametrize("joiner", NOT_JOINERS)
def test_nothing_else_joins_the_words_of_a_term(gate, joiner):
    rc, out = claims(gate, held("- Docker"), f"Built rate{joiner}limiting and Docker.\n")
    assert rc == 0, out


@pytest.mark.parametrize("hyphen", ["-", "\u2010", "\u2011", "\ufe63", "\uff0d"])
@pytest.mark.parametrize("brk", ["\n", "\r\n", "\r", "\x0b", "\x0c", "\x85", "\u2028", "\u2029", "\n   ", "\n\t"])
def test_a_word_hyphenated_across_a_line_end_is_rejoined(gate, hyphen, brk):
    rc, out = claims(gate, held("- Docker"), f"Built rate{hyphen}{brk}limiting and Docker.\n")
    assert rc == 1 and "rate limiting" in out, out


@pytest.mark.parametrize("text", ["rate\u2013\nlimiting", "rate/\nlimiting", "rate -\nlimiting", "rate-\n\nlimiting",
                                  "rate-\n- limiting"])
def test_only_a_hyphen_glued_to_the_word_rejoins_across_a_line_end(gate, text):
    rc, out = claims(gate, held("- Docker"), f"Built {text} and Docker.\n")
    assert rc == 0, out


def test_separate_held_items_never_join_into_a_multiword_term(gate):
    rc, out = claims(gate, held("- Rate", "- Limiting"), "Built rate limiting.\n")
    assert rc == 1, out
    rc, out = claims(gate, held("- CI/CD"), "Owned CI / CD and ci-cd and CI\u2013CD.\n")
    assert rc == 0, out
