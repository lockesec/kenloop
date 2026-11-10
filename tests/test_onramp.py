"""The on-ramp: a scale (## Path), a placement that earns no credit and routes study, and branches
that record the pieces a concept is made of."""
import json

import pytest

from kenloop import loop
from kenloop.core import branches as B
from kenloop.core import learn as L
from kenloop.core import onramp as O
from kenloop.core.errors import NOT_EVALUABLE, NotEvaluable, UsageError

SYLLABUS = """# Formal verification

## Path

0. **ground** — bugs, crashes and fuzzing
1. **code** — how source becomes machine code
2. **basics** — what a proof is

## Concepts
- ground :: Fuzzer limits :: a fuzzer samples a finite slice of the inputs
- code :: Source to machine code :: one source, a binary per instruction set
- code :: Undefined behaviour :: the compiler may assume it never happens
- basics :: Spec versus test :: a spec states a property for every input
"""
STM = "code:source-to-machine-code"


@pytest.fixture
def fv(cfg, home):
    L.plan(cfg, "fv")
    (home / "topics" / "fv" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "fv", quiet=True)
    return home / "topics" / "fv"


def _br(cfg, *a, **k):
    k.setdefault("by", "learner")
    return O.branch(cfg, "fv", *a, **k)


def _place(cfg, rung, result):
    return O.place(cfg, "fv", rung, result, f"probe on rung {rung}", f"answer on rung {rung}")


def test_path_rungs_are_the_bold_domains_in_order():
    assert O.parse_path(SYLLABUS) == ["ground", "code", "basics"]
    assert O.parse_path("## Concepts\n0. **not** — outside the Path section\n") == []
    with pytest.raises(UsageError, match="twice"):
        O.parse_path("## Path\n0. **a** — x\n1. **a** — y\n")


def test_standing_starts_on_the_lowest_rung_not_carried():
    assert O.standing([], 3)["start"] is None
    rows = [{"rung": 0, "result": "pass"}, {"rung": 1, "result": "miss"}]
    assert O.standing(rows, 3)["start"] == 1
    assert O.standing([{"rung": 0, "result": "pass"}, {"rung": 1, "result": "pass"}], 3)["start"] == 2
    one = O.standing([{"rung": 1, "result": "partial"}], 3)
    assert one["start"] is None and one["undecided"] == [1]           # a single partial asks again
    two = O.standing([{"rung": 1, "result": "partial"}, {"rung": 1, "result": "partial"}], 3)
    assert two["start"] == 1
    assert O.standing([{"rung": 0, "result": "miss"}, {"rung": 0, "result": "pass"}], 3)["start"] == 1  # latest wins


def test_placement_earns_no_credit_and_keeps_the_answer_verbatim(cfg, fv, capsys):
    before = json.loads((fv / "concepts.json").read_text())
    assert _place(cfg, 0, "pass") == 0 and _place(cfg, 1, "miss") == 0
    assert json.loads((fv / "concepts.json").read_text()) == before        # state untouched
    assert (fv / "log.jsonl").read_text() == ""                            # and the log too
    rows = [json.loads(x) for x in (fv / "placement.jsonl").read_text().splitlines()]
    assert [r["result"] for r in rows] == ["pass", "miss"] and rows[1]["answer"] == "answer on rung 1"
    assert "start: rung 1 (code)" in capsys.readouterr().out


def test_place_refuses_without_a_scale_or_a_whole_answer(cfg, home):
    L.plan(cfg, "flat")
    with pytest.raises(NotEvaluable, match="no scale yet"):
        O.place(cfg, "flat")
    L.plan(cfg, "fv")
    (home / "topics" / "fv" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "fv", quiet=True)
    with pytest.raises(UsageError, match="not on the scale"):
        O.place(cfg, "fv", 7, "pass", "q", "a")
    with pytest.raises(UsageError, match="--probe and --answer"):
        O.place(cfg, "fv", 0, "pass", "q", "")


def test_a_damaged_placement_line_is_not_evaluable(cfg, fv, capsys):
    (fv / "placement.jsonl").write_text('{"date": "2026-10-22", "rung": 0}\n')
    assert O.place(cfg, "fv") == NOT_EVALUABLE
    assert O.place(cfg, "fv", 0, "pass", "q", "a") == NOT_EVALUABLE       # never appends past damage
    assert len((fv / "placement.jsonl").read_text().splitlines()) == 1


def test_next_places_a_fresh_scale_then_teaches_the_climbing_rung(cfg, fv):
    assert O.next_step(cfg, "fv")[0] == ["place", "fv"]
    _place(cfg, 0, "pass")
    _place(cfg, 1, "miss")
    assert O.next_step(cfg, "fv")[0] == ["foundations", "fv", STM, "--scaffold"]
    note = fv / "foundations" / (STM.replace(":", "--") + ".md")
    note.parent.mkdir(exist_ok=True)
    note.write_text("# note\n")
    assert O.next_step(cfg, "fv")[0] == ["dive", "fv", STM]
    e = next(r for r in loop.evaluate(cfg) if r["rule"] == "onramp")
    assert e["status"] == "fired" and e["argv"][-2:] == ["fv", STM]


def test_a_topic_studied_before_its_scale_is_not_nagged_to_place(cfg, fv):
    L.record(cfg, "fv", "ground:fuzzer-limits", "ok")
    assert O.next_step(cfg, "fv") is None
    assert not any(a.startswith("not placed") for a in O.advice(cfg, "fv", STM))


def test_talk_advice_follows_the_rung(cfg, fv):
    assert O.advice(cfg, "fv", STM)[0].startswith("not placed yet")
    _place(cfg, 0, "pass")
    _place(cfg, 1, "miss")
    assert O.advice(cfg, "fv", STM)[0].startswith("on your starting rung")
    assert O.advice(cfg, "fv", "basics:spec-versus-test")[0].startswith("rung 2 (basics) is above")
    assert O.advice(cfg, "fv", "ground:fuzzer-limits") == []                # below the start: just talk


def test_branch_records_a_piece_and_talk_says_climb_it_first(cfg, fv):
    assert _br(cfg, STM, "code :: What an instruction set is :: the operations a CPU understands") == 0
    cons = L.load_state(cfg, "fv")["concepts"]
    assert cons["code:what-an-instruction-set-is"]["part_of"] == STM
    assert "part-of:" + STM in (fv / "syllabus.md").read_text()
    assert any("climb the pieces first" in a for a in O.advice(cfg, "fv", STM))
    assert _br(cfg, STM, "ground :: Machine code :: numbers a CPU runs", before=True) == 0
    assert L.load_state(cfg, "fv")["concepts"]["ground:machine-code"]["before"] == STM


def test_branch_refuses_a_piece_above_its_whole_a_twin_and_a_third_level(cfg, fv):
    with pytest.raises(UsageError, match="cannot sit above"):
        _br(cfg, STM, "basics :: Proof terms :: x")
    with pytest.raises(UsageError, match="not a rung"):
        _br(cfg, STM, "nowhere :: Thing :: x")
    with pytest.raises(UsageError, match="same concept"):
        _br(cfg, STM, "ground :: Undefined behaviour :: again")
    _br(cfg, STM, "code :: Assembly :: instructions spelled in words")
    _br(cfg, "code:assembly", "code :: Registers :: where a CPU holds values")
    with pytest.raises(UsageError, match="not a third level"):
        _br(cfg, "code:registers", "code :: Register renaming :: x")


def test_branch_to_a_new_topic_remembers_where_it_grew_from(cfg, fv):
    assert _br(cfg, STM, "isa :: Instruction encodings :: how instructions become bytes",
                    topic="computer-architecture") == 0
    conf = L.load_config(cfg, "computer-architecture")
    assert conf["origin"] == f"fv/{STM}" and not conf.get("outlets")      # curiosity: no outlet
    assert "isa:instruction-encodings" in L.load_state(cfg, "computer-architecture")["concepts"]


def test_edges_survive_a_rebuild(cfg, fv):
    _br(cfg, STM, "code :: Assembly :: instructions spelled in words")
    assert L.rebuild(cfg, "fv", check=True) == 0


def _talked(cfg, **belief):
    L.record(cfg, "fv", STM, "partial", mode="dialogue", rubric={"chain": 1, "predict": 1, "limits": 1},
             grader="test-model", hint_depth=belief.pop("hint_depth", 0),
             belief={"before": "b", "after": "a", **belief})


def test_every_decision_is_recorded_and_by_is_never_guessed(cfg, home, fv):
    with pytest.raises(UsageError, match="--by is required"):
        O.branch(cfg, "fv", STM, "code :: Assembly :: words for instructions")
    assert not (home / "branches.jsonl").exists()
    _br(cfg, STM, "code :: Assembly :: words for instructions", by="tutor", gap="what assembly is")
    _br(cfg, STM, note="linkers, some day", by="learner")
    _br(cfg, STM, decline="the history of x86", by="tutor")
    rows, problems = B.read(cfg)
    assert not problems and [(r["by"], r["as"]) for r in rows] == [("tutor", "piece"), ("learner", "note"),
                                                                     ("tutor", "declined")]
    assert rows[0]["target"] == "code:assembly" and rows[0]["gap"] == "what assembly is"
    with pytest.raises(UsageError, match="on their own"):
        _br(cfg, STM, "code :: X :: y", note="both")


def test_the_ratios_print_their_counts_and_say_when_there_are_no_offers(cfg, fv, capsys):
    assert B.report(cfg, "fv") == 0
    assert "no offers yet" in capsys.readouterr().out
    _br(cfg, STM, "code :: Assembly :: words for instructions", by="tutor")
    _br(cfg, STM, decline="the history of x86", by="tutor")
    _br(cfg, STM, "code :: Registers :: where a CPU holds values", by="learner")
    s = B.ratios(cfg, B.read(cfg)[0])
    assert (s["offers"], s["taken"], s["unoffered"], s["kept"], s["built"], s["studied"]) == (2, 1, 1, 2, 2, 0)
    L.record(cfg, "fv", "code:assembly", "ok", mode="learn")
    assert B.ratios(cfg, B.read(cfg)[0])["studied"] == 1
    B.report(cfg, "fv")
    out = capsys.readouterr().out
    assert "1/2 taken" in out and "you raised 1/2" in out and "studied since: 1/2" in out


def test_the_tool_offers_from_the_record_and_forgets_what_is_decided(cfg, fv):
    _talked(cfg, broke="thought the binary is the same on every chip", next="learn about linkers",
            hint_depth=4)
    _place(cfg, 1, "miss")
    srcs = {c["source"].rsplit(":", 1)[-1]: c for c in B.candidates(cfg, "fv")}
    assert {"broke", "next", "hint", "rung1"} <= set(srcs)
    key = srcs["next"]["source"]
    with pytest.raises(UsageError, match="--by is tool"):
        _br(cfg, STM, note="linkers", by="tutor", source=key)
    _br(cfg, STM, note="linkers", by="tool", source=key)
    assert key not in {c["source"] for c in B.candidates(cfg, "fv")}
    assert B.ratios(cfg, B.read(cfg)[0])["by_tool"] == 1


def test_a_gap_already_on_the_syllabus_is_not_offered(cfg, fv):
    _talked(cfg, broke="never heard of undefined behaviour")
    assert not any(c["source"].endswith(":broke") for c in B.candidates(cfg, "fv"))


def test_a_damaged_branch_record_refuses_to_append_and_reports(cfg, home, fv, capsys):
    (home / "branches.jsonl").write_text("{not json\n")
    with pytest.raises(NotEvaluable, match="nothing appended"):
        _br(cfg, STM, "code :: Assembly :: words for instructions")
    assert "code:assembly" not in L.load_state(cfg, "fv")["concepts"]       # the syllabus is untouched too
    assert B.report(cfg) == NOT_EVALUABLE
