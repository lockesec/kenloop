"""part-of / before links: a self-link, a missing target and a cycle fail validate (each was
CLEAN before 2026-10-26: an adversarial run hand-edited all three and talk then looped); a
concept with a history that left the syllabus is warned about, never silently counted."""
import pytest

from kenloop import cli
from kenloop.core import learn as L

from conftest import run


def _syl(lines):
    return L.parse_syllabus("## Concepts\n" + "".join(f"- {x}\n" for x in lines))


def test_a_clean_graph_has_no_problems():
    assert L.edge_problems(_syl(["net :: a :: x :: part-of:net:b", "net :: b :: y",
                                 "net :: c :: z :: before:net:b"])) == []


@pytest.mark.parametrize("lines,want", [
    (["net :: a :: x :: part-of:net:a"], "links the concept to itself"),
    (["net :: a :: x :: part-of:net:zzz"], "does not have"),
    (["net :: a :: x :: part-of:net:b", "net :: b :: y :: part-of:net:a"], "net:a -> net:b -> net:a"),
    (["net :: a :: x :: before:net:b", "net :: b :: y :: part-of:net:c", "net :: c :: z :: before:net:a"],
     "a cycle"),
])
def test_bad_links_are_named(lines, want):
    probs = L.edge_problems(_syl(lines))
    assert len(probs) == 1 and want in probs[0], probs


def test_a_long_chain_is_checked_without_recursion():
    n = 5000
    lines = [f"d :: c{i} :: x" + (f" :: part-of:d:c{i + 1}" if i < n - 1 else "") for i in range(n)]
    assert L.edge_problems(_syl(lines)) == []
    lines[-1] += " :: part-of:d:c0"
    assert "a cycle" in L.edge_problems(_syl(lines))[0]


def _topic(home, body):
    assert cli.main(["--home", str(home), "plan", "net", "--goal", "g"]) == 0
    syl = home / "topics" / "net" / "syllabus.md"
    syl.write_text("## Concepts\n" + body)
    assert cli.main(["--home", str(home), "sync", "net"]) in (0, 1)


def test_validate_fails_on_a_cycle(home, capsys):
    _topic(home, "- net :: a :: x :: part-of:net:b\n- net :: b :: y :: part-of:net:a\n")
    code, out = run(home, "validate", "net", capsys=capsys)
    assert code == 1 and "a cycle of part-of / before links" in out.out


def test_a_renamed_concept_with_history_is_warned_about(home, capsys):
    _topic(home, "- net :: handshake :: x\n- net :: other :: y\n")
    run(home, "record", "net", "net:handshake", "ok", capsys=capsys)
    (home / "topics" / "net" / "syllabus.md").write_text("## Concepts\n- net :: handshake-3way :: x\n- net :: other :: y\n")
    run(home, "sync", "net", capsys=capsys)
    code, out = run(home, "validate", "net", capsys=capsys)
    assert "net/net:handshake: has a history in the log but is no longer in syllabus.md" in out.err


def test_rename_carries_history_links_and_bank_and_clears_the_ghost(home, capsys):
    _topic(home, "- net :: handshake :: x\n- net :: other :: y :: part-of:net:handshake\n")
    d = home / "topics" / "net"
    (d / "questions.md").write_text((d / "questions.md").read_text() + "\n## net:handshake\n")
    run(home, "record", "net", "net:handshake", "ok", capsys=capsys)
    (d / "syllabus.md").write_text("## Concepts\n- net :: handshake-3way :: x\n- net :: other :: y :: part-of:net:handshake\n")
    code, out = run(home, "rename", "net", "net:handshake", "net:handshake-3way", capsys=capsys)
    assert code == 0 and "net:handshake -> net:handshake-3way" in out.out
    cons = L.load_state(cli_cfg(home), "net")["concepts"]
    assert "net:handshake" not in cons and cons["net:handshake-3way"]["attempts"] == 1
    assert "part-of:net:handshake-3way" in (d / "syllabus.md").read_text()
    assert "## net:handshake-3way" in (d / "questions.md").read_text()
    assert run(home, "rebuild", "net", "--check", capsys=capsys)[0] == 0        # replay agrees: no drift
    code, out = run(home, "validate", "net", capsys=capsys)
    assert code == 0 and "no longer in syllabus.md" not in out.err


def test_rename_refuses_what_it_cannot_do_honestly(home, capsys):
    _topic(home, "- net :: a :: x\n- net :: b :: y\n")
    run(home, "record", "net", "net:b", "ok", capsys=capsys)
    assert run(home, "rename", "net", "net:a", "net:zzz", capsys=capsys)[0] == 64      # new not in syllabus
    assert run(home, "rename", "net", "net:a", "net:b", capsys=capsys)[0] == 64        # old still there
    run(home, "record", "net", "net:a", "ok", capsys=capsys)
    (home / "topics" / "net" / "syllabus.md").write_text("## Concepts\n- net :: b :: y\n")
    code, out = run(home, "rename", "net", "net:a", "net:b", capsys=capsys)
    assert code == 64 and "already has a history of its own" in out.err


def cli_cfg(home):
    from kenloop.career import config as CC
    return CC.load(home)


def test_quiz_asks_the_due_banked_concept_first(home, capsys, monkeypatch):
    """Adversarial run: `due` named rainbows:primary, and the default quiz listed five unbanked
    new concepts instead of it."""
    _topic(home, "".join(f"- net :: c{i} :: x\n" for i in range(8)) + "- net :: due-one :: y\n")
    d = home / "topics" / "net"
    (d / "questions.md").write_text("## net:due-one\n### Q: what?\nA: this\nRef: r\n")
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-01")
    run(home, "record", "net", "net:due-one", "ok", capsys=capsys)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-04-30")
    code, out = run(home, "quiz", "net", capsys=capsys)
    assert out.out.splitlines()[0].startswith("- net:due-one"), out.out


def test_filler_rows_do_not_open_the_interference_gate():
    """Adversarial run: learn-mode (read-through) rows the same day made a lone unaided answer
    count as 'answered among 3+ other concepts'. A read-through or a dialogue retrieves nothing."""
    day = "2030-03-10"
    target = {"date": day, "concept": "t:x", "result": "ok"}
    filler = [{"date": day, "concept": f"t:f{i}", "result": "ok", "mode": "learn"} for i in range(2)]
    filler.append({"date": day, "concept": "t:g", "result": "ok", "mode": "dialogue"})
    assert not L.interference_ok([target, *filler], "t:x")
    real = [{"date": day, "concept": f"t:r{i}", "result": "miss"} for i in range(3)]
    assert L.interference_ok([target, *real], "t:x")      # real attempts count, right or wrong


def test_a_dialogue_where_the_tutor_told_the_answer_is_at_most_partial():
    top = {"chain": 2, "predict": 2, "limits": 2}
    assert L.rubric_result(top) == "ok"
    assert L.rubric_result(top, hint_depth=3) == "ok"       # gave a fact: still the learner's reasoning
    assert L.rubric_result(top, hint_depth=4) == "partial"   # told the answer
    assert L.rubric_result({"chain": 0, "predict": 0, "limits": 1}, hint_depth=4) == "miss"


def test_a_second_same_day_dialogue_keeps_the_first_grades_evidence(home, capsys):
    """Adversarial run: a second dialogue on the same concept the same day re-fingerprinted the
    (edited) transcript and replaced the graded copy, so the first grade lost its evidence."""
    _topic(home, "- net :: a :: x\n- net :: b :: y\n- net :: c :: z\n")
    d = home / "topics" / "net"
    def dialogue(text):
        t = L.dialogue_path(cli_cfg(home), "net", "net:a", "2030-03-20")
        t.parent.mkdir(exist_ok=True)
        t.write_text(text)
        assert run(home, "record", "net", "net:a", "ok", "--mode", "dialogue", "--rubric",
                   "chain=2,predict=2,limits=2", "--grader", "g", capsys=capsys)[0] == 0
        return t
    first = dialogue("tutor: why?\nlearner: because\n")
    second = dialogue("tutor: and then?\nlearner: so\n")
    assert first != second and second.name.endswith("-2.md")
    code, out = run(home, "validate", "net", capsys=capsys)
    assert code == 0, out.out
