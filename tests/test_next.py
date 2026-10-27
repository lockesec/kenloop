"""`next`: one fixture per rule where it fires and the rule above it does not."""
import json


from kenloop.career import jobs as J
from kenloop.core import learn as L
from kenloop import loop
from kenloop.career import roles as R
from kenloop import certs


def pick(cfg):
    return next(e for e in loop.evaluate(cfg) if e["status"] == "fired")


def test_rule0_nothing_to_work_on(cfg, capsys):
    assert pick(cfg)["rule"] == "empty"
    assert loop.next_action(cfg) == 2


def _topic(cfg, home, slug="t", n=1, origin=""):
    L.plan(cfg, slug, outlets=("career",))
    (home / "topics" / slug / "syllabus.md").write_text(
        "## Concepts\n" + "".join(f"- d :: c{i} :: x\n" for i in range(n)))
    L.sync(cfg, slug, quiet=True)
    conf = L.load_config(cfg, slug)
    if origin:
        conf["origin"] = origin
    L.save_config(cfg, slug, conf)


def test_rule1_drift(cfg, home):
    _topic(cfg, home)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    (home / "topics" / "t" / "log.jsonl").write_text("")
    e = pick(cfg)
    assert e["rule"] == "integrity" and e["argv"][-2:] == ["rebuild", "t"]


def _role(cfg, home, name, fit=None, deadline="", status=None):
    slug, _ = J.intake(cfg, "acme", name, jd="REST", deadline=deadline)
    if not (home / "resumes" / "resume.md").exists():
        (home / "resumes" / "resume.md").write_text("REST")
    J.check(cfg, slug)
    if fit is not None:
        J.score(cfg, slug, fit)
    if status:
        J.status(cfg, slug, status)
    return slug


def test_rule2_deadline_beats_everything_below(cfg, home):
    _role(cfg, home, "a", 4.5)                                   # rule 5 candidate
    s = _role(cfg, home, "b", 4.1, deadline="2030-03-23")        # 3 days: fires
    e = pick(cfg)
    assert e["rule"] == "deadline" and e["argv"] == ["ken", "jobs", "tailor", s]
    m = R.load(cfg, s)
    m["deadline"] = "2030-03-24"                                 # 4 days: one unit short
    R.save(cfg, s, m)
    assert pick(cfg)["rule"] == "role"


def test_rule2_tailoring_role_suggests_applied(cfg, home):
    s = _role(cfg, home, "b", 4.1, deadline="2030-03-21", status="tailoring")
    assert pick(cfg)["argv"] == ["ken", "jobs", "status", s, "applied"]


def _graduate(cfg, home, slug="t", origin=""):
    import os
    _topic(cfg, home, slug, n=4, origin=origin)
    for d, qt in (("2030-03-10", "recall"), ("2030-03-12", "applied"), ("2030-03-15", "recall")):
        os.environ["KENLOOP_TODAY"] = d
        L.record(cfg, slug, "d:c0", "ok", qtype=qt, quiet=True)   # breadth needs typed attempts
    for c in ("d:c1", "d:c2", "d:c3"):
        L.record(cfg, slug, c, "miss", quiet=True)
    os.environ["KENLOOP_TODAY"] = "2030-03-20"


def test_graduation_beats_the_shortlist_and_reviews_beat_graduation(cfg, home):
    _graduate(cfg, home)
    _role(cfg, home, "a", 4.5)
    ev = loop.evaluate(cfg)
    names = [e["rule"] for e in ev]
    assert names.index("reviews") < names.index("question") < names.index("graduation") < names.index("role")
    g = next(e for e in ev if e["rule"] == "graduation")
    assert g["status"] == "fired" and g["argv"][-1] == "--emit"
    (home / "facts.md").write_text("## Held\n- c0\n")                      # after the paste: no longer fires
    assert {e["rule"]: e for e in loop.evaluate(cfg)}["graduation"]["status"] == "not fired"


def _upskill(cfg, home, jd="CORS"):
    (home / "resumes" / "resume.md").write_text("REST")
    s, _ = J.intake(cfg, "acme", "x", jd=jd)
    J.score(cfg, s, 3.0)
    J.check(cfg, s)
    J.upskill(cfg)
    return s


def test_reviews_fire_in_any_topic_an_exam_first_then_demand(cfg, home, monkeypatch):
    _upskill(cfg, home)
    L.plan(cfg, "free")                                          # studied for its own sake: no demand, no exam
    (home / "topics" / "free" / "syllabus.md").write_text("## Concepts\n- d :: c0 :: x\n- d :: c1 :: x\n")
    L.sync(cfg, "free", quiet=True)
    for cid in ("d:c0", "d:c1"):
        L.record(cfg, "free", cid, "miss", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    e = pick(cfg)
    assert e["rule"] == "reviews" and e["argv"][-1] == "free" and "exam" not in e["reason"]
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-20")
    _topic(cfg, home, origin="Unmapped: web/security")
    L.record(cfg, "t", "d:c0", "miss", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    e = pick(cfg)
    assert e["argv"][-1] == "t" and "bucket demand" in e["reason"]   # demand outranks more reviews due
    certs.set_exam_date(cfg, "free", "2030-04-01")                   # an exam 11 days out outranks demand
    e = pick(cfg)
    assert e["argv"][-1] == "free" and "exam in 11 day(s)" in e["reason"]


def test_rule6_banked_unstudied_in_a_linked_topic(cfg, home):
    _upskill(cfg, home)
    _topic(cfg, home, origin="Unmapped: web/security")
    assert pick(cfg)["rule"] != "fresh"                                # no bank yet
    L.bank(cfg, "t", "d:c0", "Q", "A", "ref")
    e = pick(cfg)
    assert e["rule"] == "fresh" and "--interactive" in e["argv"]


def test_rule7_plan_from_the_top_unplanned_bucket(cfg, home):
    _upskill(cfg, home, jd="CORS and CSRF")
    e = pick(cfg)
    assert e["rule"] == "seed" and e["argv"][-2:] == ["--from-gap", "Unmapped: web/security"]
    cfg.min_bucket_demand = 2.01                                 # one unit short
    assert pick(cfg)["rule"] == "fallback"


def test_rule8_score_the_oldest(cfg, home):
    _role(cfg, home, "a")
    e = pick(cfg)
    assert e["rule"] == "score" and e["argv"][3] == "acme-a"


def test_rule9_fallback_and_all_is_auditable(cfg, home, capsys):
    _role(cfg, home, "a", 2.0)
    assert pick(cfg)["rule"] == "fallback"
    loop.next_action(cfg, show_all=True)
    out = capsys.readouterr().out
    assert all(f" {r} " in out for r in ("empty", "integrity", "deadline", "reviews", "onramp", "question", "graduation",
                                          "role", "fresh", "seed", "score", "fallback")) and "NEXT:" in out
    loop.next_action(cfg, as_json=True)
    assert json.loads(capsys.readouterr().out)["rule"] == "fallback"


def test_unknown_demand_is_not_evaluable_not_zero(cfg, home):
    _role(cfg, home, "a", 2.0)
    ev = {e["rule"]: e for e in loop.evaluate(cfg)}
    assert ev["seed"]["status"] == "not evaluable"


def test_an_open_question_from_a_dialogue_comes_next_until_followed_up(cfg, home, monkeypatch):
    monkeypatch.setenv("KENLOOP_GRADER", "test-model")
    _topic(cfg, home)
    L.record(cfg, "t", "d:c0", "ok", mode="dialogue", rubric={"chain": 2, "predict": 2, "limits": 2},
             open_questions=["what happens at the edge?"], quiet=True)
    e = pick(cfg)
    assert e["rule"] == "question" and e["argv"][-3:] == ["talk", "t", "d:c0"]
    assert "what happens at the edge?" in e["reason"]
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-22")
    L.record(cfg, "t", "d:c0", "ok", mode="dialogue", rubric={"chain": 2, "predict": 2, "limits": 2}, quiet=True)
    assert pick(cfg)["rule"] != "question"                       # a later dialogue on it followed it up


def test_a_question_with_no_rungs_comes_next(cfg, home):
    from kenloop.core import questions as Q
    _topic(cfg, home)
    Q.ask(cfg, "why is the sky dark at night?")
    e = pick(cfg)
    assert e["rule"] == "question" and e["argv"][-1] == "ask" and "q1 has no ladder yet" in e["reason"]
    Q.rung(cfg, "q1", "t", existing="d:c0")
    assert pick(cfg)["rule"] != "question"


def test_with_no_targets_the_fallback_is_a_question_not_a_job_search(cfg, home, monkeypatch):
    _topic(cfg, home)
    for day in ("2030-03-01", "2030-03-02"):              # climbed (good), and not due again yet
        monkeypatch.setenv("KENLOOP_TODAY", day)
        L.record(cfg, "t", "d:c0", "ok", quiet=True)
    e = pick(cfg)
    assert e["rule"] == "fallback" and e["argv"][-2] == "ask" and not e["argv_complete"]


def test_an_untouched_unbanked_concept_is_study_not_nothing_is_ripe(cfg, home):
    """Adversarial run: untouched concepts waited while next said 'nothing is ripe', because the
    fresh rule needs banked questions. The study graph's frontier fires instead: a dialogue first."""
    _topic(cfg, home)
    e = pick(cfg)
    assert e["rule"] == "study" and e["argv"][1:] == ["talk", "t", "d:c0"]


def test_study_takes_a_ladder_rung_you_asked_for_first(cfg, home):
    import json
    _topic(cfg, home, n=3)
    with open(home / "asks.jsonl", "a") as f:
        f.write(json.dumps({"event": "ask", "id": "q1", "date": "2030-03-01", "question": "why?"}) + "\n")
        f.write(json.dumps({"event": "rung", "ask": "q1", "date": "2030-03-01", "topic": "t",
                            "concept": "d:c2"}) + "\n")
    e = pick(cfg)
    assert e["rule"] == "study" and e["argv"][-1] == "d:c2" and "a question you asked" in e["reason"]
