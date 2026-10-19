"""Absence is never rendered as a measurement: an empty board, an empty home, empty or
damaged inputs and wrongly typed fields exit 2 with their cause and the denominator beside the count."""
import json

import pytest

from careerloop import cli, loop
from careerloop import home as H
from careerloop import jobs as J
from careerloop import learn as L
from careerloop.errors import NotEvaluable
from conftest import run


LEX = """name = "web"
[categories]
protocols = ["http", "https", "http/2", "tls", "dns", "websockets"]
api = ["rest", "json", "graphql", "openapi"]
security = ["oauth", "cors", "csrf", "rate limiting"]
ops = ["caching", "cdn", "load balancing", "observability", "docker", "redis", "microservices"]
data = ["sql", "postgresql"]
lang = ["go", "kubernetes"]
"""


def _cfg(tmp_path, facts_text, resume="REST and Docker\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


HELD_SQL = "## Held\n- SQL\n"


def _damage(demo):
    with open(demo / "topics" / "http-fundamentals" / "log.jsonl", "a", encoding="utf-8") as fh:
        fh.write("garbage\n")


def _upskill_json(home, analyzed, buckets=()):
    from careerloop import demand as DM
    cfg = H.load_config(home)
    data = {"schema": 2, "generated": H.today().isoformat(), "inputs": DM.inputs_digest(cfg),
            "roles_analyzed": analyzed, "roles_unchecked": [], "roles_damaged": [], "quick_wins": [],
            "buckets": list(buckets)}
    (home / "upskill.json").write_text(DM.dumps(data))


LEX_2 = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services", "bash", "mongodb", "hbase", "firewalls", "aws"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes", "python"]
"""


def _cfg_2(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX_2)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_bytes(resume if isinstance(resume, bytes) else resume.encode("utf-8"))
    return H.load_config(h), h


def _mk(tmp_path, facts="## Held\n- REST\n"):
    cfg, h = _cfg_2(tmp_path, facts, "REST and SQL\n")
    jd = tmp_path / "jd.txt"
    jd.write_text("We need REST, Docker and SQL")
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "acme", "--role", "dev",
                     "--jd", str(jd)]) == 0
    assert cli.main(["--home", str(h), "learn", "plan", "t1"]) == 0
    return h


def _exam_scope_empty(h):
    assert cli.main(["--home", str(h), "learn", "exam-date", "t1", "--set", "2031-01-01"]) == 0


def _upskill_bad(h):
    (h / "upskill.json").write_text("{bad")


def _upskill_old(h):
    (h / "upskill.json").write_text('{"schema": 1}')


def _meta_bad(h):
    (h / "roles" / "acme-dev" / "meta.json").write_text("{bad")


ROWS = [
    ("tailor without coverage.json", None, ("jobs", "tailor", "acme-dev")),
    ("calibration with no rated attempts", None, ("learn", "calibration", "t1")),
    ("quiz on a topic with no concepts", None, ("learn", "quiz", "t1")),
    ("exam-date with no exam-scope concepts", _exam_scope_empty, ("learn", "exam-date", "t1")),
    ("plan --from-gap with no upskill.json", None, ("learn", "plan", "t2", "--from-gap", "x")),
    ("discover --all with no [sources] targets", None, ("jobs", "discover", "--all")),
    ("reconcile with no [sources] targets", None, ("jobs", "reconcile")),
    ("gaps with a damaged upskill.json", _upskill_bad, ("learn", "gaps")),
    ("gaps with a non-schema-2 upskill.json", _upskill_old, ("learn", "gaps")),
    ("show with a damaged meta.json", _meta_bad, ("jobs", "show", "acme-dev")),
    ("check with a damaged meta.json", _meta_bad, ("jobs", "check", "acme-dev")),
    ("tailor with a damaged meta.json", _meta_bad, ("jobs", "tailor", "acme-dev")),
    ("score with a damaged meta.json", _meta_bad, ("jobs", "score", "acme-dev", "--fit", "3")),
    ("status with a damaged meta.json", _meta_bad, ("jobs", "status", "acme-dev", "applied")),
    ("upskill with a damaged meta.json", _meta_bad, ("jobs", "upskill")),
]


def _role(home, jd="REST and Docker and CDN"):
    (home / "facts.md").write_text("## Held\n- REST\n- Docker\n- CDN\n")
    (home / "resumes" / "resume.md").write_text("REST Docker CDN\n")
    slug, _ = J.intake(H.load_config(home), "Acme", "Dev", jd=jd)
    return slug


def _fixture(home, postings):
    (home / "fixtures").mkdir(exist_ok=True)
    (home / "fixtures" / "acme.json").write_text(json.dumps(postings))


def _post(i, title):
    return {"ext_id": str(i), "title": title, "location": "Remote", "url": "", "jd": "REST and JSON"}


def _topic_with_a_bad_row(home):
    from careerloop import home as H
    cfg = H.load_config(home)
    L.plan(cfg, "t", title="T", goal="g")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: a :: x\n- d :: b :: y\n")
    L.sync(cfg, "t", quiet=True)
    L.record(cfg, "t", "d:a", "ok", quiet=True)
    with open(home / "topics" / "t" / "log.jsonl", "a") as f:
        f.write("not json{\n")


# --- Wrongly typed or damaged fields are named, not internal errors -------------------------------

@pytest.mark.parametrize("text", ["ats = 1\n", "[next]\ndeadline_days = 1.9\n", "[demand]\nstatus_weights = 3\n",
                                  "[sources]\ntargets = 5\n", "[gap]\nbucket = 5\n", "gap = []\n"])
def test_wrong_config_shapes_are_not_evaluable(home, text):
    (home / "config.toml").write_text(text)
    with pytest.raises(NotEvaluable):
        H.load_config(home)


def test_an_unreadable_facts_sheet_is_not_evaluable(cfg, home):
    (home / "facts.md").unlink()
    (home / "facts.md").mkdir()
    from careerloop import facts as F
    with pytest.raises(NotEvaluable):
        F.read(cfg)


def test_an_oversized_board_response_is_an_error(cfg, home, monkeypatch):
    from careerloop import sources as S
    (home / "fixtures" / "acme.json").write_text("[" + ",".join(['{"ext_id":"1","title":"x"}'] * 10) + "]")
    monkeypatch.setattr(S, "MAX_BYTES", 50)
    r = S.fetch("fixture", "acme", cfg)
    assert r.status == "error" and "bytes" in r.error


def test_any_crash_exits_2_never_1(home, capsys, monkeypatch):
    from careerloop import loop as lp
    monkeypatch.setattr(lp, "doctor", lambda cfg: 1 / 0)
    assert cli.main(["--home", str(home), "doctor"]) == 2
    assert "internal error" in capsys.readouterr().err


def test_wrong_typed_log_field_is_a_problem_not_a_crash(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: e :: x\n")
    L.sync(cfg, "t", quiet=True)
    with open(home / "topics" / "t" / "log.jsonl", "a") as fh:
        fh.write(json.dumps({"date": "2030-03-01", "concept": "d:e", "result": "ok", "hint_depth": "two"}) + "\n")
        fh.write(json.dumps({"date": "2030-03-01", "concept": "d:e", "result": "yes"}) + "\n")
    rows_, probs = L.read_log(cfg, "t")
    assert rows_ == [] and len(probs) == 2


@pytest.mark.parametrize("patch", [{"found": None}, {"fit_score": "5"}, {"status": "hired"}])
def test_wrong_typed_meta_is_damaged_not_a_crash(cfg, home, patch):
    slug, _ = J.intake(cfg, "Acme", "Dev")
    p = home / "roles" / slug / "meta.json"
    m = json.loads(p.read_text())
    m.update(patch)
    p.write_text(json.dumps(m))
    good, bad = J.R.scan(cfg)
    assert good == [] and bad


def test_wrong_typed_coverage_is_not_evaluable(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST")
    J.check(cfg, slug)
    p = home / "roles" / slug / "coverage.json"
    c = json.loads(p.read_text())
    c["pct"] = "50"
    p.write_text(json.dumps(c))
    assert loop.doctor(cfg) == 2


def test_wrong_field_types_are_named_not_internal_errors(home, capsys):
    slug = _role(home)
    mp = home / "roles" / slug / "meta.json"
    m = json.loads(mp.read_text())
    for key in ("company", "resume"):
        bad = dict(m, **{key: 5})
        mp.write_text(json.dumps(bad))
        code, out = run(home, "jobs", "check", slug, capsys=capsys)
        assert code == 2 and "internal error" not in out.err and "damaged" in out.err, key
    mp.write_text(json.dumps(m))
    assert run(home, "learn", "plan", "t1")[0] == 0
    tp = home / "topics" / "t1" / "topic.json"
    tp.write_text(json.dumps({"title": "T", "exam_date": 5}))
    code, out = run(home, "learn", "exam-date", "t1", capsys=capsys)
    assert code == 2 and "internal error" not in out.err and "exam_date" in out.err
    tp.write_text(json.dumps({"title": "T"}))
    (home / "topics" / "t1" / "concepts.json").write_text(json.dumps({"concepts": {"a": 5}}))
    code, out = run(home, "learn", "due", "t1", capsys=capsys)
    assert code == 2 and "internal error" not in out.err
    (home / "upskill.json").write_text(json.dumps({"schema": 2, "buckets": [5], "inputs": "x", "generated": "x"}))
    code, out = run(home, "learn", "gaps", capsys=capsys)
    assert code == 2 and "internal error" not in out.err


# --- Absence is NOT EVALUABLE, with its cause and denominator -------------------------------------

def test_reconcile_with_an_unreachable_board_is_not_evaluable(cfg, home, capsys):
    (home / "fixtures" / "acme.json").write_text(json.dumps([{"ext_id": "1", "title": "Dev"}]))
    cfg.targets = [{"board": "fixture", "org": "acme"}, {"board": "fixture", "org": "nope"}]
    assert J.reconcile(cfg) == 2
    assert "all 0" not in capsys.readouterr().out


def test_jobs_check_with_empty_facts_is_not_evaluable(tmp_path):
    cfg, _h = _cfg(tmp_path, "")
    slug, _ = J.intake(cfg, "acme", "dev", jd="REST and Docker")
    with pytest.raises(NotEvaluable) as e:
        J.check(cfg, slug)
    assert "facts" in str(e.value)


def test_jobs_check_with_missing_facts_is_not_evaluable(tmp_path):
    cfg, h = _cfg(tmp_path, "x")
    slug, _ = J.intake(cfg, "acme", "dev", jd="REST and Docker")
    (h / "facts.md").unlink()
    with pytest.raises(NotEvaluable):
        J.check(cfg, slug)


@pytest.mark.parametrize("argv", [("learn", "validate"), ("learn", "due"), ("jobs", "upskill"),
                                  ("doctor",), ("next",)])
def test_empty_home_exits_2_and_names_the_cause(home, capsys, argv):
    capsys.readouterr()
    rc, out = run(home, *argv, capsys=capsys)
    text = out.out + out.err
    assert rc == 2, (argv, text)
    assert "NOT EVALUABLE" in text and ("no topics" in text or "no roles" in text or "nothing" in text), text


def test_upskill_on_empty_home_prints_the_denominator_and_writes_nothing(home, capsys):
    capsys.readouterr()
    rc, out = run(home, "jobs", "upskill", capsys=capsys)
    text = out.out + out.err
    assert rc == 2 and "0 role(s)" in text
    assert not (home / "upskill.json").exists()


def test_gaps_with_no_roles_analysed_is_not_evaluable(home, capsys):
    _upskill_json(home, 0)
    capsys.readouterr()
    rc, out = run(home, "learn", "gaps", capsys=capsys)
    assert rc == 2 and "0 role(s)" in out.out + out.err and "NOT EVALUABLE" in out.out + out.err


def test_gaps_with_roles_and_no_buckets_prints_the_denominator_and_exits_0(home, capsys):
    _upskill_json(home, 3)
    capsys.readouterr()
    rc, out = run(home, "learn", "gaps", capsys=capsys)
    assert rc == 0 and "0 demand bucket(s) from 3 role(s)" in out.out


def test_validate_and_due_with_a_topic_keep_their_denominators(home, capsys):
    assert run(home, "learn", "plan", "t1")[0] == 0
    capsys.readouterr()
    rc, out = run(home, "learn", "due", capsys=capsys)
    assert rc == 0 and "t1: 0 due" in out.out
    rc, out = run(home, "learn", "validate", capsys=capsys)
    assert rc == 0 and "validate: 0 failure(s)" in out.out


def test_next_and_gaps_print_the_denominator_on_an_empty_home(home, capsys):
    rc, out = run(home, "next", capsys=capsys)
    assert rc == 2 and "0 role(s)" in out.out and "0 topic(s)" in out.out, out.out
    rc, out = run(home, "learn", "gaps", capsys=capsys)
    assert rc == 2 and "0 role(s)" in (out.out + out.err), out
    # a damaged file does not claim a count it did not read
    (home / "upskill.json").write_text("{bad")
    rc, out = run(home, "learn", "gaps", capsys=capsys)
    assert rc == 2 and "0 role(s)" not in (out.out + out.err) and "damaged" in out.err


@pytest.mark.parametrize("body", ["", "   \n", "I like walking and tea.\n"])
def test_check_on_a_resume_with_no_terms_is_not_evaluable(home, capsys, body):
    (home / "facts.md").write_text("## Held\n- REST\n")
    (home / "resumes" / "resume.md").write_text(body)
    slug, _ = J.intake(H.load_config(home), "Acme", "Dev", jd="REST and Docker and CDN and OAuth")
    code, out = run(home, "jobs", "check", slug, capsys=capsys)
    assert code == 2 and "no lexicon terms" in out.err and "0.0%" not in out.out
    assert not (home / "roles" / slug / "coverage.json").exists()


def test_a_resume_with_terms_but_none_of_the_postings_is_a_real_zero(home, capsys):
    (home / "facts.md").write_text("## Held\n- SQL\n")
    (home / "resumes" / "resume.md").write_text("SQL\n")
    slug, _ = J.intake(H.load_config(home), "Acme", "Dev", jd="REST and Docker")
    code, out = run(home, "jobs", "check", slug, capsys=capsys)
    assert code == 0 and "0/2" in out.out


def test_an_empty_board_exits_2_and_says_why(home, capsys):
    _fixture(home, [])
    code, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "acme", capsys=capsys)
    assert code == 2
    assert "EMPTY" in out.out and "no postings at all" in out.out
    assert "NOT EVALUABLE" in out.err


def test_a_keyword_matching_nothing_on_a_live_board_is_exit_0_with_the_denominator(home, capsys):
    _fixture(home, [_post(1, "Web Developer"), _post(2, "API Engineer"), _post(3, "Designer")])
    code, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "acme",
                    "--keyword", "zebra", capsys=capsys)
    assert code == 0
    assert "0 of 3 posting(s) matched 'zebra'" in out.out


def test_keyword_hits_also_print_the_denominator(home, capsys):
    _fixture(home, [_post(1, "Web Developer"), _post(2, "API Engineer"), _post(3, "Designer")])
    code, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "acme",
                    "--keyword", "engineer", capsys=capsys)
    assert code == 0 and "1 of 3 posting(s) matched 'engineer'" in out.out


def test_the_exam_scope_clause_is_true(home, capsys):
    """A topic with an exam date but only depth-scope concepts is NOT EVALUABLE (exit 2)."""
    from careerloop import home as H
    cfg = H.load_config(home)
    L.plan(cfg, "t", title="T", goal="g")
    (home / "topics" / "t" / "syllabus.md").write_text(
        "## Concepts\n- d :: deep :: only for depth :: scope:depth\n")
    L.sync(cfg, "t", quiet=True)
    assert run(home, "learn", "exam-date", "t", "--set", "2030-04-30", capsys=capsys)[0] in (0, 2)
    code, out = run(home, "learn", "exam-date", "t", capsys=capsys)
    assert code == 2 and "no exam-scope concepts" in out.err


# --- Damaged logs and files are named -------------------------------------------------------------

def test_validate_reports_a_damaged_log_row(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, HELD_SQL)
    L.plan(cfg, "t")
    (h / "topics" / "t" / "syllabus.md").write_text("## Concepts\n- d :: a :: x\n")
    L.sync(cfg, "t", quiet=True)
    L.record(cfg, "t", "d:a", "ok", quiet=True)
    capsys.readouterr()
    assert L.validate(cfg, "t") == 0
    with open(h / "topics" / "t" / "log.jsonl", "a") as fh:
        fh.write("{not json\n")
    capsys.readouterr()
    rc = L.validate(cfg, "t")
    out = capsys.readouterr()
    assert rc == 2 and "log.jsonl line" in (out.out + out.err) and "damaged" in (out.out + out.err)


@pytest.mark.parametrize("argv", [
    ("learn", "calibration", "http-fundamentals"),
    ("learn", "misconceptions", "http-fundamentals"),
    ("learn", "sync", "http-fundamentals"),
    ("learn", "exam-date", "http-fundamentals"),
    ("learn", "exam-date", "http-fundamentals", "--set", "2031-01-01"),
    ("learn", "exam-date", "http-fundamentals", "--clear"),
])
def test_damaged_log_is_reported_and_exits_2(demo, capsys, argv):
    _damage(demo)
    capsys.readouterr()
    rc, out = run(demo, *argv, capsys=capsys)
    assert rc == 2, (argv, out)
    assert "damaged log row" in out.err, out.err


@pytest.mark.parametrize("argv", [
    ("learn", "calibration", "http-fundamentals"),
    ("learn", "misconceptions", "http-fundamentals"),
    ("learn", "sync", "http-fundamentals"),
    ("learn", "exam-date", "http-fundamentals"),
])
def test_undamaged_log_still_exits_0(demo, capsys, argv):
    capsys.readouterr()
    rc, out = run(demo, *argv, capsys=capsys)
    assert rc == 0 and "damaged" not in out.err, (argv, out)


def test_due_on_a_damaged_log_exits_2_after_its_normal_output(home, capsys):
    _topic_with_a_bad_row(home)
    code, out = run(home, "learn", "due", "t", capsys=capsys)
    assert code == 2 and "t: " in out.out and "damaged log row" in out.err


def test_quiz_on_a_damaged_log_exits_2(home, capsys):
    _topic_with_a_bad_row(home)
    code, out = run(home, "learn", "quiz", "t", capsys=capsys)
    assert code == 2 and "damaged log row" in out.err


def test_control_a_clean_log_still_exits_0(home, capsys):
    _topic_with_a_bad_row(home)
    p = home / "topics" / "t" / "log.jsonl"
    p.write_text("".join(x for x in p.read_text().splitlines(True) if x.startswith("{")))
    assert run(home, "learn", "due", "t", capsys=capsys)[0] == 0
    assert run(home, "learn", "quiz", "t", capsys=capsys)[0] == 0


# --- The exit-2 table is true, row by row ---------------------------------------------------------

@pytest.mark.parametrize("name,setup,argv", ROWS, ids=[r[0] for r in ROWS])
def test_each_row_of_the_exit_2_table_exits_2_with_a_cause(tmp_path, capsys, name, setup, argv):
    h = _mk(tmp_path)
    if setup:
        setup(h)
    capsys.readouterr()
    rc, out = run(h, *argv, capsys=capsys)
    assert rc == 2 and (out.out + out.err).strip(), (name, out)


@pytest.mark.parametrize("argv", [("next",), ("doctor",), ("jobs", "board"), ("jobs", "rank"), ("learn", "due"),
                                  ("learn", "gaps"), ("jobs", "upskill"), ("learn", "validate")])
def test_every_command_on_a_missing_home_exits_2(tmp_path, capsys, argv):
    rc, out = run(tmp_path / "nope", *argv, capsys=capsys)
    assert rc == 2 and "no careerloop home" in out.err
