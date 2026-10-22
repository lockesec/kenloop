"""Role directories and discovery: slugs, meta.json validation, damaged roles named, atomic
intake, coverage freshness and the stale-demand cache."""
import json

import pytest

from kenloop import cli, loop
from kenloop.career import jobs as J
from kenloop.career import roles as R
from kenloop.core.errors import UsageError
from kenloop.career import config as CC
from conftest import run


LEX = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services", "bash", "mongodb", "hbase", "firewalls", "aws"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes", "python"]
"""


def _cfg(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_bytes(resume if isinstance(resume, bytes) else resume.encode("utf-8"))
    return CC.load(h), h


def _mk(tmp_path, facts="## Held\n- REST\n"):
    cfg, h = _cfg(tmp_path, facts, "REST and SQL\n")
    jd = tmp_path / "jd.txt"
    jd.write_text("We need REST, Docker and SQL")
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "acme", "--role", "dev",
                     "--jd", str(jd)]) == 0
    assert cli.main(["--home", str(h), "plan", "t1"]) == 0
    return h


def _role(home, jd="REST and Docker and CDN"):
    (home / "facts.md").write_text("## Held\n- REST\n- Docker\n- CDN\n")
    (home / "resumes" / "resume.md").write_text("REST Docker CDN\n")
    slug, _ = J.intake(CC.load(home), "Acme", "Dev", jd=jd)
    return slug


def _damaged_home(home):
    J.intake(CC.load(home), "Acme", "Dev", jd="REST", job_id="7", board="fixture", org="acme")
    (home / "roles" / "broken").mkdir()
    (home / "roles" / "broken" / "meta.json").write_text("{not json")
    (home / "fixtures" / "acme.json").write_text(json.dumps([{"title": "Dev", "ext_id": "7", "jd": "REST"},
                                                               {"title": "Other", "ext_id": "8", "jd": "CDN"}]))


def _role_2(h, body, slug="acme-dev"):
    d = h / "roles" / slug
    d.mkdir(parents=True)
    (d / "meta.json").write_text(body)
    (d / "jd.txt").write_text("Python\n")
    return d


# --- Discovery and intake -------------------------------------------------------------------------

def test_distinct_postings_with_the_same_title_are_both_taken_in(cfg, home):
    (home / "fixtures" / "acme.json").write_text(json.dumps(
        [{"ext_id": "1", "title": "Developer", "jd": "REST"}, {"ext_id": "2", "title": "Developer", "jd": "JSON"}]))
    J.discover(cfg, "fixture", "acme", do_intake=True)
    metas = [json.loads(p.read_text()) for p in (home / "roles").glob("*/meta.json")]
    assert sorted(m["job_id"] for m in metas) == ["1", "2"]
    assert J.discover(cfg, "fixture", "acme", do_intake=True) == 0      # second run: nothing new
    assert len(list((home / "roles").glob("*/meta.json"))) == 2


def test_exclude_senior_prints_how_many_it_excluded(demo, capsys):
    fx = demo / "fixtures" / "example-folio.json"
    data = json.loads(fx.read_text())
    data.append({"ext_id": "s1", "title": "Senior Backend Engineer", "location": "x", "url": "", "jd": "REST"})
    fx.write_text(json.dumps(data))
    capsys.readouterr()
    rc, out = run(demo, "jobs", "discover", "--board", "fixture", "--company", "example-folio",
                  "--exclude-senior", capsys=capsys)
    assert rc == 0 and "2 excluded as senior" in out.out, out.out
    rc, out = run(demo, "jobs", "discover", "--board", "fixture", "--company", "example-folio", capsys=capsys)
    assert "excluded as senior" not in out.out and "Senior Backend Engineer" in out.out


def test_untitled_discover_posting_is_named_and_skipped(tmp_path, capsys, monkeypatch):
    h = _mk(tmp_path)
    from kenloop.career import sources as S
    posts = [{"board": "greenhouse", "org": "acme", "ext_id": "7", "title": "", "location": "", "url": "", "jd": ""},
             {"board": "greenhouse", "org": "acme", "ext_id": "8", "title": "Dev", "location": "", "url": "", "jd": "REST"}]
    monkeypatch.setattr(S, "fetch", lambda b, o, c, k=None: S.FetchResult("ok", list(posts), total=2))
    capsys.readouterr()
    rc, out = run(h, "jobs", "discover", "--board", "greenhouse", "--company", "acme", "--intake", capsys=capsys)
    assert rc == 0 and "SKIPPED" in out.out and "no title" in out.out and "1 without a title skipped" in out.out


def test_a_lone_surrogate_does_not_abort_discovery_or_leave_an_empty_role_dir(home, capsys):
    fx = [{"title": "Good One", "ext_id": "1", "jd": "REST and Docker"},
          {"title": "Bad", "ext_id": "2", "jd": "REST \ud800"},
          {"title": "Good Three", "ext_id": "3", "jd": "CDN"}]
    (home / "fixtures" / "acme.json").write_text(json.dumps(fx))
    code, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "acme", "--intake", capsys=capsys)
    assert "internal error" not in out.err
    dirs = sorted(p.name for p in (home / "roles").iterdir())
    assert len(dirs) == 3, dirs
    assert all((home / "roles" / d / "meta.json").is_file() for d in dirs), dirs
    assert "Bad" in out.out and "2" in out.out
    assert code in (0, 2)


def test_a_failed_intake_leaves_no_role_dir(home, monkeypatch):
    def boom(path, text):
        if path.name == "scorecard.md":
            raise OSError("disk full")
        return real(path, text)
    real = J._write_text
    monkeypatch.setattr(J, "_write_text", boom)
    with pytest.raises(OSError):
        J.intake(CC.load(home), "Acme", "Dev", jd="REST")
    assert not [p for p in (home / "roles").iterdir()]


def test_a_role_dir_without_meta_is_reported(home, capsys):
    (home / "roles" / "orphan").mkdir()
    (home / "roles" / ".hidden").mkdir()
    J.intake(CC.load(home), "Acme", "Dev", jd="REST")
    assert R.scan(CC.load(home))[1] and "orphan" in R.scan(CC.load(home))[1][0]
    code, out = run(home, "jobs", "rank", capsys=capsys)
    assert code == 2 and "orphan" in out.err
    code, out = run(home, "jobs", "board", capsys=capsys)
    assert code == 2 and "orphan" in out.err
    (home / "facts.md").write_text("## Held\n- REST\n")
    code, out = run(home, "doctor", capsys=capsys)
    assert code == 2 and "orphan" in out.out


def test_discover_names_and_skips_an_empty_posting(tmp_path, capsys):
    import json
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    fx = h / "fixtures"
    fx.mkdir(exist_ok=True)
    (fx / "fx.json").write_text(json.dumps([{"title": "Empty", "ext_id": "1", "jd": "<p></p>"},
                                            {"title": "Real", "ext_id": "2", "jd": "Python work"}]))
    cli.main(["--home", str(h), "jobs", "discover", "--board", "fixture", "--company", "fx", "--intake"])
    out = capsys.readouterr().out
    assert "SKIPPED" in out and "Empty" in out
    assert not (h / "roles" / "fx-empty").exists() and (h / "roles" / "fx-real").exists()


# --- Role directories, meta.json and coverage -----------------------------------------------------

def test_a_manual_slug_collision_is_refused_not_merged(cfg):
    J.intake(cfg, "Acme Co", "Dev")
    with pytest.raises(UsageError):
        J.intake(cfg, "Acme-Co", "Dev")


@pytest.mark.parametrize("bad", ["../../escaped", "a/b", "..", ".hidden", "A B"])
def test_unsafe_role_slugs_are_refused(cfg, home, bad):
    with pytest.raises(UsageError):
        J.intake(cfg, "Acme", "Dev", slug=bad)
    assert not (home.parent / "escaped").exists()


def test_coverage_goes_stale_when_an_input_changes(cfg, home, capsys):
    (home / "facts.md").write_text("## Held\n- REST\n- JSON\n")     # doctor also gates the resume's claims
    (home / "resumes" / "resume.md").write_text("REST")
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST and JSON")
    J.check(cfg, slug)
    assert loop.doctor(cfg) == 0
    (home / "resumes" / "resume.md").write_text("REST and JSON")
    assert loop.doctor(cfg) == 1
    assert "stale" in capsys.readouterr().out


def test_demand_is_stale_on_a_new_day(cfg, home, monkeypatch):
    (home / "resumes" / "resume.md").write_text("REST")
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="CORS")
    J.check(cfg, slug)
    J.upskill(cfg)
    from kenloop.career import demand as DM
    assert DM.load(cfg)[1] is False
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    assert DM.load(cfg)[1] is True


def test_tailor_refuses_stale_coverage(home, capsys):
    slug = _role(home)
    assert run(home, "jobs", "check", slug)[0] == 0
    (home / "resumes" / "resume.md").write_text("REST Docker CDN and more\n")
    code, out = run(home, "jobs", "tailor", slug, capsys=capsys)
    assert code == 2 and "stale" in out.err and f"jobs check {slug}" in out.err
    assert not (home / "roles" / slug / "review.md").exists()
    assert run(home, "jobs", "check", slug)[0] == 0                      # the quiet direction
    assert run(home, "jobs", "tailor", slug)[0] == 0


@pytest.mark.parametrize("body", ["null", "[]", "3", '"x"', "true"])
@pytest.mark.parametrize("verb", [["show", "acme-dev"], ["check", "acme-dev"], ["score", "acme-dev", "--fit", "4"],
                                  ["status", "acme-dev", "applied"], ["tailor", "acme-dev"]])
def test_a_non_object_meta_is_damaged_exit_2_naming_the_file(home, capsys, body, verb):
    _role_2(home, body)
    code, out = run(home, "jobs", *verb, capsys=capsys)
    assert code == 2, (verb, out)
    assert "meta.json" in out.err and "damaged" in out.err and "no role" not in out.err


def test_an_absent_role_is_still_unknown_exit_64(home, capsys):
    code, out = run(home, "jobs", "show", "nope", capsys=capsys)
    assert code == 64


@pytest.mark.parametrize("patch,field", [
    ({"fit_score": "high"}, "fit_score"), ({"fit_score": True}, "fit_score"),
    ({"status": "bogus"}, "status"), ({"status": 3}, "status"), ({"slug": 5}, "slug"),
    ({"company": None}, "company"), ({"role": 4}, "role"),
])
def test_a_wrong_field_is_named_and_rank_does_not_omit_the_role(home, capsys, patch, field):
    meta = {"company": "Acme", "role": "Dev", "status": "found", "fit_score": None, "found": "2030-03-01",
            "history": [], "outcome": {}}
    meta.update(patch)
    _role_2(home, json.dumps(meta))
    code, out = run(home, "jobs", "show", "acme-dev", capsys=capsys)
    assert code == 2 and field in out.err
    code, out = run(home, "jobs", "rank", capsys=capsys)
    assert code == 2 and "acme-dev" in out.err and field in out.err


def test_missing_required_key_is_named(home, capsys):
    _role_2(home, json.dumps({"company": "Acme", "status": "found"}))
    code, out = run(home, "jobs", "show", "acme-dev", capsys=capsys)
    assert code == 2 and "role" in out.err


def test_a_valid_meta_is_accepted(home, capsys):
    _role_2(home, json.dumps({"company": "Acme", "role": "Dev", "status": "found", "fit_score": 4.5, "slug": "acme-dev"}))
    code, out = run(home, "jobs", "show", "acme-dev", capsys=capsys)
    assert code == 0


# --- Damaged logs and files are named -------------------------------------------------------------

def test_reconcile_names_a_damaged_role_and_exits_2(home, capsys):
    _damaged_home(home)
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n[sources]\ntargets = [{board = "fixture", org = "acme"}]\n')
    code, out = run(home, "jobs", "reconcile", capsys=capsys)
    assert code == 2 and "broken" in out.out + out.err
    assert "checked 1" in out.out                                       # the rest was still done


def test_discover_intake_names_a_damaged_role_and_still_takes_in_the_rest(home, capsys):
    _damaged_home(home)
    code, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "acme", "--intake", capsys=capsys)
    assert code == 2 and "broken" in out.out + out.err
    assert (home / "roles" / "acme-other" / "meta.json").is_file()
