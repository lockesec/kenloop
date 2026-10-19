"""`next`: one fixture per rule where it fires and the rule above it does not."""
import json


from careerloop import jobs as J
from careerloop import learn as L
from careerloop import loop
from careerloop import roles as R


def pick(cfg):
    return next(e for e in loop.evaluate(cfg) if e["status"] == "fired")


def test_rule0_nothing_to_work_on(cfg, capsys):
    assert pick(cfg)["rule"] == 0
    assert loop.next_action(cfg) == 2


def _topic(cfg, home, slug="t", n=1, from_gap="none"):
    L.plan(cfg, slug)
    (home / "topics" / slug / "syllabus.md").write_text(
        "## Concepts\n" + "".join(f"- d :: c{i} :: x\n" for i in range(n)))
    L.sync(cfg, slug, quiet=True)
    conf = L.load_config(cfg, slug)
    conf["from_gap"] = from_gap
    L.save_config(cfg, slug, conf)


def test_rule1_drift(cfg, home):
    _topic(cfg, home)
    L.record(cfg, "t", "d:c0", "ok", quiet=True)
    (home / "topics" / "t" / "log.jsonl").write_text("")
    e = pick(cfg)
    assert e["rule"] == 1 and e["argv"][-2:] == ["rebuild", "t"]


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
    assert e["rule"] == 2 and e["argv"] == ["careerloop", "jobs", "tailor", s]
    m = R.load(cfg, s)
    m["deadline"] = "2030-03-24"                                 # 4 days: one unit short
    R.save(cfg, s, m)
    assert pick(cfg)["rule"] == 5


def test_rule2_tailoring_role_suggests_applied(cfg, home):
    s = _role(cfg, home, "b", 4.1, deadline="2030-03-21", status="tailoring")
    assert pick(cfg)["argv"] == ["careerloop", "jobs", "status", s, "applied"]


def _graduate(cfg, home, slug="t", from_gap="none"):
    import os
    _topic(cfg, home, slug, n=4, from_gap=from_gap)
    for d, qt in (("2030-03-10", "recall"), ("2030-03-12", "applied"), ("2030-03-15", "recall")):
        os.environ["CAREERLOOP_TODAY"] = d
        L.record(cfg, slug, "d:c0", "ok", qtype=qt, quiet=True)   # breadth needs typed attempts
    for c in ("d:c1", "d:c2", "d:c3"):
        L.record(cfg, slug, c, "miss", quiet=True)
    os.environ["CAREERLOOP_TODAY"] = "2030-03-20"


def test_rule3_graduation_beats_due_and_shortlist(cfg, home):
    _graduate(cfg, home)
    _role(cfg, home, "a", 4.5)
    e = pick(cfg)
    assert e["rule"] == 3 and e["argv"][-1] == "--emit"
    (home / "facts.md").write_text("## Held\n- c0\n")                      # after the paste: no longer fires
    assert pick(cfg)["rule"] == 5


def _upskill(cfg, home, jd="CORS"):
    (home / "resumes" / "resume.md").write_text("REST")
    s, _ = J.intake(cfg, "acme", "x", jd=jd)
    J.score(cfg, s, 3.0)
    J.check(cfg, s)
    J.upskill(cfg)
    return s


def test_rule4_due_in_a_wanted_topic(cfg, home):
    _upskill(cfg, home)
    _topic(cfg, home, from_gap="Unmapped: web/security")
    L.record(cfg, "t", "d:c0", "miss", quiet=True)
    import os
    os.environ["CAREERLOOP_TODAY"] = "2030-03-21"
    e = pick(cfg)
    assert e["rule"] == 4 and e["argv"][-1] == "t"
    conf = L.load_config(cfg, "t")
    conf["from_gap"] = "none"                                    # no demand, no exam: not wanted
    L.save_config(cfg, "t", conf)
    assert pick(cfg)["rule"] != 4
    L.set_exam_date(cfg, "t", "2030-04-01")                      # an exam 11 days out: wanted again
    assert pick(cfg)["rule"] == 4


def test_rule6_banked_unstudied_in_a_linked_topic(cfg, home):
    _upskill(cfg, home)
    _topic(cfg, home, from_gap="Unmapped: web/security")
    assert pick(cfg)["rule"] != 6                                # no bank yet
    L.bank(cfg, "t", "d:c0", "Q", "A", "ref")
    e = pick(cfg)
    assert e["rule"] == 6 and "--interactive" in e["argv"]


def test_rule7_plan_from_the_top_unplanned_bucket(cfg, home):
    _upskill(cfg, home, jd="CORS and CSRF")
    e = pick(cfg)
    assert e["rule"] == 7 and e["argv"][-2:] == ["--from-gap", "Unmapped: web/security"]
    cfg.min_bucket_demand = 2.01                                 # one unit short
    assert pick(cfg)["rule"] == 9


def test_rule8_score_the_oldest(cfg, home):
    _role(cfg, home, "a")
    e = pick(cfg)
    assert e["rule"] == 8 and e["argv"][3] == "acme-a"


def test_rule9_fallback_and_all_is_auditable(cfg, home, capsys):
    _role(cfg, home, "a", 2.0)
    assert pick(cfg)["rule"] == 9
    loop.next_action(cfg, show_all=True)
    out = capsys.readouterr().out
    assert out.count("rule ") == 10 and "NEXT:" in out
    loop.next_action(cfg, as_json=True)
    assert json.loads(capsys.readouterr().out)["rule"] == 9


def test_unknown_demand_is_not_evaluable_not_zero(cfg, home):
    _role(cfg, home, "a", 2.0)
    ev = {e["rule"]: e for e in loop.evaluate(cfg)}
    assert ev[7]["status"] == "not evaluable"
