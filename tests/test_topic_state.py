"""Topic state and the learning loop: graduation, emitted blocks that pass their own gate,
drift between the log and the derived state, rebuild, concept ids and the question flow."""
import io
import json
import os
from pathlib import Path

import pytest

from careerloop import cli, loop
from careerloop import demand as DM
from careerloop import facts as F
from careerloop import home as H
from careerloop import jobs as J
from careerloop import learn as L
from careerloop.errors import NotEvaluable
from conftest import rows


@pytest.fixture
def topic(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: a :: x\n- d :: b :: y\n")
    L.sync(cfg, "t", quiet=True)
    L.record(cfg, "t", "d:a", "ok", quiet=True)
    return "t"


def _mastered(cfg, home, slug="k", title="Kubernetes and Terraform", names=("pods", "services", "nodes", "volumes"),
              qtypes=("recall", "applied")):
    L.plan(cfg, slug, title=title)
    (home / "topics" / slug / "syllabus.md").write_text(
        "## Concepts\n" + "".join(f"- core :: {n} :: x\n" for n in names))
    L.sync(cfg, slug, quiet=True)
    for i, d in enumerate(("2030-03-01", "2030-03-02", "2030-03-03")):
        os.environ["CAREERLOOP_TODAY"] = d
        for n in names:
            L.record(cfg, slug, f"core:{n}", "ok", qtype=qtypes[i % len(qtypes)] if qtypes else "", quiet=True)
    os.environ["CAREERLOOP_TODAY"] = "2030-03-20"


def _emit(cfg, slug, capsys):
    capsys.readouterr()
    L.graduate(cfg, slug, emit=True)
    return capsys.readouterr().out


def _log(home):
    return home / "topics" / "k" / "log.jsonl"


def _graduate(home, capsys):
    capsys.readouterr()
    rc = cli.main(["--home", str(home), "learn", "graduate", "k", "--emit"])
    o = capsys.readouterr()
    return rc, o.out, o.err


def _rule3(cfg):
    return {e["rule"]: e for e in loop.evaluate(cfg)}[3]


def _miss(concept="core:pods"):
    return json.dumps(dict(date="2030-03-04", concept=concept, result="miss", correct=False, qtype="recall",
                           mode="practice", confidence="low", hint_depth=0)) + "\n"


def _mastered_with_real_ids(cfg, home, slug="k", title="Kubernetes and Terraform", names=("pods", "services", "nodes", "volumes")):
    """Like _mastered, but ids come from the real concept_id (names may hold spaces/markup)."""
    import os
    L.plan(cfg, slug, title=title)
    (home / "topics" / slug / "syllabus.md").write_text(
        "## Concepts\n" + "".join(f"- core :: {n} :: x\n" for n in names))
    L.sync(cfg, slug, quiet=True)
    for i, d in enumerate(("2030-03-01", "2030-03-02", "2030-03-03")):
        os.environ["CAREERLOOP_TODAY"] = d
        for n in names:
            L.record(cfg, slug, L.concept_id("core", n), "ok", qtype=("recall", "applied")[i % 2], quiet=True)
    os.environ["CAREERLOOP_TODAY"] = "2030-03-20"


def _cfg(tmp_path, facts_text, resume="REST and Docker\n", toml='[ats]\npacks = ["web"]\n'):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text(toml)
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume)
    return H.load_config(h), h


def _paste(h, text):
    with open(h / "facts.md", "a", encoding="utf-8") as fh:
        fh.write(text)


def _emit_out(cfg, slug, capsys):
    capsys.readouterr()
    rc = L.graduate(cfg, slug, emit=True)
    o = capsys.readouterr()
    return rc, o.out, o.err


ROOT = Path(__file__).resolve().parents[1]


# --- Graduation, emit blocks and topic state ------------------------------------------------------

def test_a_concept_missing_from_state_is_drift(cfg, home, topic, capsys):
    (home / "topics" / "t" / "concepts.json").write_text('{"concepts": {}}')
    assert L.drift(cfg, "t") == ["d:a"]
    assert L.rebuild(cfg, "t", check=True) == 3
    assert loop.doctor(cfg) == 3


def test_an_unreadable_log_row_makes_the_check_not_evaluable(cfg, home, topic, capsys):
    with open(home / "topics" / "t" / "log.jsonl", "a") as fh:
        fh.write("{not json\n")
    assert L.rebuild(cfg, "t", check=True) == 2
    assert loop.doctor(cfg) == 2
    assert L.rebuild(cfg, "t") == 2                          # refuses to rebuild from part of the record
    assert L.rebuild(cfg, "t", skip_damaged=True) == 0       # explicit, counted
    assert "skipped 1 damaged" in capsys.readouterr().out


def test_a_damaged_concepts_json_can_be_rebuilt_and_is_preserved(cfg, home, topic, capsys):
    p = home / "topics" / "t" / "concepts.json"
    p.write_text("{broken")
    with pytest.raises(NotEvaluable):
        L.load_state(cfg, "t")
    assert L.rebuild(cfg, "t") == 0
    assert L.load_state(cfg, "t")["concepts"]["d:a"]["attempts"] == 1
    kept = list(p.parent.glob("concepts.json.damaged*"))
    assert kept and kept[0].read_text() == "{broken"


def test_the_paste_closes_the_loop_on_a_fresh_init_home(tmp_path, capsys):
    h = tmp_path / "h"
    cli.main(["--home", str(h), "init"])
    cfg = H.load_config(h)
    _mastered(cfg, h)
    with open(h / "facts.md", "a") as fh:
        fh.write(_emit(cfg, "k", capsys))
    g = L.graduation(cfg, "k")
    assert g["candidates"] == [] and len(g["held"]) == 4


def test_graduating_a_concept_never_makes_the_title_held(cfg, home, capsys):
    _mastered(cfg, home)
    (home / "facts.md").write_text("## Held\n\n" + _emit(cfg, "k", capsys))
    assert F.holds("pods", F.read(cfg))
    assert not F.holds("kubernetes", F.read(cfg)) and not F.holds("terraform", F.read(cfg))


def test_no_question_types_means_not_breadth_tested(cfg, home):
    _mastered(cfg, home, qtypes=())
    g = L.graduation(cfg, "k")
    assert g["candidates"] == [] and len(g["not breadth-tested"]) == 4


def test_too_many_distractors_are_refused(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: e :: x\n")
    L.sync(cfg, "t", quiet=True)
    from careerloop.errors import UsageError
    with pytest.raises(UsageError):
        L.bank(cfg, "t", "d:e", "Q", "A", "r", distractors=[f"o{i} :: m" for i in range(8)])


def test_placeholder_argv_is_marked(cfg, home, capsys):
    J.intake(cfg, "acme", "a")
    loop.next_action(cfg, as_json=True)
    d = json.loads(capsys.readouterr().out)
    assert d["rule"] == 8 and d["argv_complete"] is False


def test_a_back_dated_record_leaves_no_drift(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: c :: x\n")
    L.sync(cfg, "t", quiet=True)
    os.environ["CAREERLOOP_TODAY"] = "2030-03-05"
    L.record(cfg, "t", "d:c", "ok", quiet=True)
    os.environ["CAREERLOOP_TODAY"] = "2030-03-03"
    L.record(cfg, "t", "d:c", "miss", quiet=True)
    assert L.audit(cfg, "t") == ([], [])


def test_stopping_after_a_wrong_answer_keeps_the_miss(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: e :: x\n")
    L.sync(cfg, "t", quiet=True)
    L.bank(cfg, "t", "d:e", "Say it", "it", "r")
    L.quiz_interactive(cfg, "t", inp=io.StringIO("wrong\nh\nm\n"), out=io.StringIO())   # EOF at the note
    got = rows(home, "t")
    assert [r["result"] for r in got] == ["miss"]


def test_concept_ids_are_injective_and_duplicates_refused(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text(
        "## Concepts\n" + "".join(f"- langs :: {n} :: x\n" for n in ("c++", "c#", "c", "node.js", "nodejs")))
    L.sync(cfg, "t", quiet=True)
    assert len(L.load_state(cfg, "t")["concepts"]) == 5
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: a b :: x\n- d :: a-b :: y\n")
    from careerloop.errors import UsageError
    with pytest.raises(UsageError):
        L.sync(cfg, "t", quiet=True)


def test_probed_terms_fold_case_and_follow_the_role_weight(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    s, _ = J.intake(cfg, "a", "b", jd="REST")
    J.check(cfg, s)
    J.status(cfg, s, "interviewing", probed="tls")
    J.status(cfg, s, "interviewing", probed="TLS,Tls")
    items = {i["term"].lower(): i for b in DM.compute(cfg)["buckets"] for i in b["items"]}
    assert items["tls"]["demand"] == 2.0
    J.status(cfg, s, "passed")
    assert not DM.compute(cfg)["buckets"]


def test_only_from_gap_plans_a_bucket_and_none_is_accepted(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    for n in ("a", "b"):
        s, _ = J.intake(cfg, "acme", n, jd="CORS")
        J.check(cfg, s)
    J.upskill(cfg)
    L.plan(cfg, "unmapped-web-security", title="unrelated notes", from_gap="none")
    ev = {e["rule"]: e for e in loop.evaluate(cfg)}
    assert ev[7]["status"] == "fired"
    from careerloop.errors import UsageError
    with pytest.raises(UsageError):
        L.plan(cfg, "fresh", from_gap="No Such Bucket")
    assert not (home / "topics" / "fresh").exists()


def test_control_earned_graduation_emits_all_four(cfg, home, capsys):
    _mastered(cfg, home)
    rc, out, _err = _graduate(home, capsys)
    assert rc == 0 and out.count("held knowledge from study") == 4
    assert _rule3(cfg)["status"] == "fired"


def test_damaged_log_row_refuses_and_emits_nothing(cfg, home, capsys):
    _mastered(cfg, home)
    _log(home).write_text(_log(home).read_text() + "{damaged row\n")
    assert cli.main(["--home", str(home), "learn", "rebuild", "k", "--check"]) == 2
    rc, out, err = _graduate(home, capsys)
    assert rc == 2 and out == ""
    assert "rebuild" in err and "log problem" in err
    assert _rule3(cfg)["status"] != "fired"


def test_valid_later_miss_with_stale_cache_refuses(cfg, home, capsys):
    """Refuse (not silently drop one concept): the cache is known stale, and a
    partial list of skills for the facts sheet would be a usable subset."""
    _mastered(cfg, home)
    _log(home).write_text(_log(home).read_text() + _miss())
    rc, out, err = _graduate(home, capsys)
    assert rc == 3 and out == ""
    assert "core:pods" in err and "learn rebuild k" in err
    assert _rule3(cfg)["status"] != "fired"


def test_rebuild_restores_consistency_and_never_writes_facts(cfg, home, capsys):
    _mastered(cfg, home)
    (home / "facts.md").write_text("## Held\n")
    before = (home / "facts.md").read_text()
    _log(home).write_text(_log(home).read_text() + _miss())
    assert _graduate(home, capsys)[0] == 3
    assert cli.main(["--home", str(home), "learn", "rebuild", "k"]) == 0
    rc, out, _err = _graduate(home, capsys)
    assert rc == 0 and out.count("held knowledge from study") == 3 and "pods" not in out
    assert (home / "facts.md").read_text() == before
    assert _rule3(cfg)["status"] == "fired"


def test_rebuild_check_marks_a_cut_list(tmp_path):
    src = (ROOT / "src" / "careerloop" / "learn.py").read_text(encoding="utf-8")
    assert "', ...' if len(d) > 8" in src


# --- Emitted blocks pass their own gate -----------------------------------------------------------

def test_a_concept_that_reads_as_a_qualifier_is_not_emitted(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "")
    _mastered_with_real_ids(cfg, h, names=("Learning status codes", "pods", "services", "nodes"))
    rc, out, err = _emit_out(cfg, "k", capsys)
    assert rc == 0
    assert "Learning status codes" not in out and out.count("held knowledge from study") == 3
    assert "Learning status codes" in err and "learning" in err.lower()    # said, with the cause
    g = L.graduation(cfg, "k")
    assert len(g["unwritable"]) == 1 and len(g["candidates"]) == 3


def test_paste_then_next_cycle_ends(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "")
    _mastered_with_real_ids(cfg, h, names=("Learning status codes", "pods", "services", "nodes"))
    (h / "facts.md").write_text("## Held\n")
    assert {e["rule"]: e for e in loop.evaluate(cfg)}[3]["status"] == "fired"
    _rc, out, _err = _emit_out(cfg, "k", capsys)
    _paste(h, out)
    r3 = {e["rule"]: e for e in loop.evaluate(cfg)}[3]
    assert r3["status"] == "not fired"                                     # rule 3 cannot loop
    assert F.contradictions(F.read(cfg)) == []
    loop.doctor(cfg)
    assert "under ## Held but qualified" not in capsys.readouterr().out


def test_a_title_with_a_comment_terminator_cannot_leak_words(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n")
    _mastered_with_real_ids(cfg, h, title="Kubernetes --> Redis basics")
    _rc, out, _err = _emit_out(cfg, "k", capsys)
    assert out.splitlines()[0].count("-->") == 1 and out.splitlines()[0].endswith("-->")
    _paste(h, out)
    facts = F.read(cfg)
    assert F.holds("pods", facts)
    assert not F.holds("redis", facts) and not F.holds("kubernetes", facts)


@pytest.mark.parametrize("title", ["a <!-- b", "x -- y", "multi\nline --> z", "---> arrow"])
def test_odd_titles_stay_inside_the_comment(tmp_path, capsys, title):
    cfg, h = _cfg(tmp_path, "## Held\n")
    _mastered_with_real_ids(cfg, h, title=title)
    _rc, out, _err = _emit_out(cfg, "k", capsys)
    _paste(h, out)
    facts = F.read(cfg)
    assert F.holds("pods", facts) and len([b for b in F.blocks(facts) if b.held and not b.heading]) == 4


def test_a_name_that_will_not_read_back_is_excluded_not_looped(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n")
    _mastered_with_real_ids(cfg, h, names=("a ~~b~~ c", "pods", "services", "nodes"))
    _rc, out, err = _emit_out(cfg, "k", capsys)
    _paste(h, out)
    assert {e["rule"]: e for e in loop.evaluate(cfg)}[3]["status"] == "not fired"
    assert "a ~~b~~ c" in err
