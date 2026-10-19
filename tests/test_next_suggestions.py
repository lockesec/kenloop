"""What `next` suggests and in which order, including from a fresh init."""
import json
import os

from careerloop import cli, loop
from careerloop import home as H
from careerloop import jobs as J
from careerloop import learn as L


def _cfg(tmp_path, facts_text, resume="REST and Docker\n", toml='[ats]\npacks = ["web"]\n'):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text(toml)
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume)
    return H.load_config(h), h


# --- next suggestions -----------------------------------------------------------------------------

def test_next_checks_before_suggesting_a_tailor_that_would_refuse(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST", deadline="2030-03-21")
    J.score(cfg, slug, 4.5)
    e = next(e for e in loop.evaluate(cfg) if e["status"] == "fired")
    assert e["rule"] == 2 and e["argv"] == ["careerloop", "jobs", "check", slug]
    J.check(cfg, slug)
    e = next(e for e in loop.evaluate(cfg) if e["status"] == "fired")
    assert e["argv"] == ["careerloop", "jobs", "tailor", slug]


def test_a_damaged_topic_json_still_gives_the_full_rule_table(cfg, home, capsys):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "topic.json").write_text("[1,2]")
    ev = loop.evaluate(cfg)
    assert len(ev) == 10 and next(e for e in ev if e["status"] == "fired")["rule"] == 1


def test_the_acronym_bucket_never_drives_rule_7(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    for n in ("a", "b", "c"):
        s, _ = J.intake(cfg, "acme", n, jd="REST with FooBar, BazQux, QuxQuux")
        J.check(cfg, s)
    J.upskill(cfg)
    ev = {e["rule"]: e for e in loop.evaluate(cfg)}
    assert ev[7]["status"] != "fired"


def test_rule_4_says_when_demand_is_stale(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    s, _ = J.intake(cfg, "acme", "x", jd="CORS")
    J.check(cfg, s)
    J.upskill(cfg)
    L.plan(cfg, "t", from_gap="Unmapped: web/security")
    L.record(cfg, "t", "unmapped-web-security:cors", "miss", quiet=True)
    os.environ["CAREERLOOP_TODAY"] = "2030-03-21"
    e = next(e for e in loop.evaluate(cfg) if e["status"] == "fired")
    assert e["rule"] == 4 and "stale" in e["reason"]


def test_next_from_fresh_init_to_a_taken_in_role(tmp_path, capsys):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "config.toml").write_text('[sources]\ntargets = [{board = "fixture", org = "acme"}]\n')
    (h / "fixtures" / "acme.json").write_text(json.dumps([
        {"ext_id": "1", "title": "Web Developer", "location": "Remote", "url": "https://acme.invalid/1",
         "jd": "REST and CORS"},
        {"ext_id": "2", "title": "Office Manager", "location": "Remote", "url": "https://acme.invalid/2",
         "jd": "filing"}]))
    capsys.readouterr()
    assert cli.main(["--home", str(h), "next", "--json"]) == 2
    first = json.loads(capsys.readouterr().out)
    argv = first["argv"]
    assert first["rule"] == 0 and "--intake" in argv and not first["argv_complete"]
    assert "…" in argv                                   # the one thing only the owner knows
    run = ["Developer" if a == "…" else a for a in argv[1:]]
    assert cli.main(["--home", str(h), *run]) == 0       # the suggestion is a command that takes roles in
    capsys.readouterr()
    assert cli.main(["--home", str(h), "next", "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["rule"] == 8 and second["argv"][3] == "acme-web-developer"


def test_rule9_also_suggests_a_command_that_takes_roles_in(tmp_path):
    cfg, h = _cfg(tmp_path, "## Held\n", toml='[sources]\ntargets = [{board = "fixture", org = "acme"}]\n')
    slug, _ = J.intake(cfg, "acme", "x", jd="REST")
    J.check(cfg, slug)
    J.score(cfg, slug, 2.0)
    e = next(e for e in loop.evaluate(cfg) if e["status"] == "fired")
    assert e["rule"] == 9 and "--intake" in e["argv"] and "--keyword" in e["argv"]
