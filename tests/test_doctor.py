"""What doctor reports: it names the same findings check-claims would, is never clean on
nothing, and says what it checked."""
import json
import os
from pathlib import Path

import pytest

from kenloop import cli, loop
from kenloop.career import facts as F
from kenloop.career import jobs as J
from kenloop.career import config as CC
from conftest import run


def _cfg(tmp_path, facts_text, resume="REST and Docker\n", toml='[ats]\npacks = ["web"]\n'):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text(toml)
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume)
    return CC.load(h), h


def _cfg_2(tmp_path, facts_text, resume="REST and Docker\n"):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return CC.load(h), h


LEX = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes"]
"""


def _cfg_3(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return CC.load(h), h


LEX_2 = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services", "bash", "mongodb", "hbase"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes", "python"]
"""


def _cfg_4(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX_2)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_bytes(resume if isinstance(resume, bytes) else resume.encode("utf-8"))
    return CC.load(h), h


def _doctor_home(tmp_path, capsys, facts, resume, jd="REST and Docker"):
    cfg, h = _cfg_4(tmp_path, facts, resume)
    slug, _ = J.intake(cfg, "acme", "dev", jd=jd)
    J.check(cfg, slug)
    capsys.readouterr()
    return cfg, h


LEX_3 = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services", "bash", "mongodb", "hbase", "firewalls", "aws"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes", "python"]
"""


def _cfg_5(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX_3)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_bytes(resume if isinstance(resume, bytes) else resume.encode("utf-8"))
    return CC.load(h), h


def _mk(tmp_path, facts="## Held\n- REST\n"):
    cfg, h = _cfg_5(tmp_path, facts, "REST and SQL\n")
    jd = tmp_path / "jd.txt"
    jd.write_text("We need REST, Docker and SQL")
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "acme", "--role", "dev",
                     "--jd", str(jd)]) == 0
    assert cli.main(["--home", str(h), "plan", "t1"]) == 0
    return h


ROOT = Path(__file__).resolve().parents[1]


# --- Doctor reports what check-claims would -------------------------------------------------------

def test_doctor_finding_names_line_and_cause(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n- Python\n- Docker (learning)\n")
    loop.doctor(cfg)
    out = capsys.readouterr().out
    assert "FINDING facts.md line 3" in out and "qualifier" in out and "learning" in out


def test_unclosed_comment_after_held_is_a_doctor_finding(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n- Go\n<!-- oops\n- Rust\n")
    assert F.holds("go", cfg.facts.read_text()) and not F.holds("rust", cfg.facts.read_text())
    loop.doctor(cfg)
    out = capsys.readouterr().out
    assert "FINDING facts.md" in out and "never closes" in out and "line 3" in out


def test_doctor_reports_closed_construct_hiding_a_held_line(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n<!--\n- Docker\n-->\n")
    capsys.readouterr()
    assert loop.doctor(cfg) == 1
    out = capsys.readouterr().out
    assert "FINDING facts.md line 4" in out and "hides" in out and "comment" in out


def test_doctor_ignores_an_ordinary_comment(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n<!-- keep sorted -->\n- REST\n")
    capsys.readouterr()
    loop.doctor(cfg)
    assert "hides" not in capsys.readouterr().out


def test_doctor_does_not_say_clean_when_the_resume_is_disguised(tmp_path, capsys):
    cfg, _h = _cfg_3(tmp_path, resume="REST and Dockеr\n")
    slug, _ = J.intake(cfg, "acme", "dev", jd="We need REST")
    J.check(cfg, slug)
    capsys.readouterr()
    rc = loop.doctor(cfg)
    out = capsys.readouterr().out
    assert rc == 1 and "CLEAN" not in out and "suspicious-characters" in out


def test_doctor_stays_clean_for_a_plain_resume(tmp_path, capsys):
    cfg, _h = _cfg_3(tmp_path, resume="REST in São Paulo\n")
    slug, _ = J.intake(cfg, "acme", "dev", jd="We need REST")
    J.check(cfg, slug)
    capsys.readouterr()
    rc = loop.doctor(cfg)
    assert rc == 0 and "CLEAN" in capsys.readouterr().out


def test_held_line_spelled_with_a_look_alike_is_a_doctor_finding(tmp_path, capsys):
    cfg, h = _doctor_home(tmp_path, capsys, "## Held\n- REST\n- Dockеr\n", "REST Docker\n")
    assert J.check_claims(cfg, "resumes/resume.md") == 1
    capsys.readouterr()
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 1 and "FINDING" in out.out and "contradiction" in out.out and "CLEAN" not in out.out, out.out


def test_resume_stating_an_unheld_term_is_a_doctor_finding(tmp_path, capsys):
    cfg, h = _doctor_home(tmp_path, capsys, "## Learning\n- Docker\n## Held\n- REST\n", "REST Docker\n")
    assert J.check_claims(cfg, "resumes/resume.md") == 1
    capsys.readouterr()
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 1 and "docker" in out.out.lower() and "not held" in out.out and "CLEAN" not in out.out, out.out


def test_quiet_direction_a_resume_of_held_terms_is_clean(tmp_path, capsys):
    cfg, h = _doctor_home(tmp_path, capsys, "## Held\n- REST\n- Docker\n", "REST Docker\n")
    assert J.check_claims(cfg, "resumes/resume.md") == 0
    capsys.readouterr()
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 0 and "CLEAN" in out.out, out.out


def test_doctor_scans_the_resume_a_role_names(tmp_path, capsys):
    cfg, h = _doctor_home(tmp_path, capsys, "## Held\n- REST\n", "REST\n")
    (h / "resumes" / "other.md").write_text("REST Docker\n")
    meta = json.loads((h / "roles" / "acme-dev" / "meta.json").read_text())
    meta["resume"] = "resumes/other.md"
    (h / "roles" / "acme-dev" / "meta.json").write_text(json.dumps(meta))
    rc, out = run(h, "doctor", capsys=capsys)
    assert "other.md" in out.out and rc != 0


# --- Doctor reports absence and damage ------------------------------------------------------------

@pytest.mark.parametrize("how", ["empty", "missing"])
def test_doctor_with_empty_or_missing_facts_is_not_evaluable(home, capsys, how):
    assert run(home, "plan", "t1")[0] == 0
    if how == "empty":
        (home / "facts.md").write_text("")
    else:
        (home / "facts.md").unlink()
    capsys.readouterr()
    rc, out = run(home, "doctor", capsys=capsys)
    assert rc == 2, out
    assert "NOT EVALUABLE" in out.out and "facts" in out.out and "CLEAN" not in out.out


def test_doctor_with_facts_still_clean(home, capsys):
    assert run(home, "plan", "t1")[0] == 0
    capsys.readouterr()
    rc, out = run(home, "doctor", capsys=capsys)
    assert rc == 0 and "CLEAN" in out.out


def test_doctor_names_a_missing_resume_and_exits_2(tmp_path, capsys):
    h = _mk(tmp_path, "## Held\n- REST\n- SQL\n")
    assert cli.main(["--home", str(h), "jobs", "check", "acme-dev"]) == 0
    (h / "resumes" / "resume.md").unlink()
    capsys.readouterr()
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 2 and "acme-dev" in out.out and "no resume found" in out.out, out.out


def test_quiet_direction_doctor_with_the_resume_present_is_clean(tmp_path, capsys):
    h = _mk(tmp_path, "## Held\n- REST\n- SQL\n- Docker\n")
    assert cli.main(["--home", str(h), "jobs", "check", "acme-dev"]) == 0
    capsys.readouterr()
    rc, out = run(h, "doctor", capsys=capsys)
    assert "no resume found" not in out.out and rc == 0, out.out


def test_doctor_does_not_say_no_roles_when_a_role_has_no_posting(tmp_path, capsys):
    cfg, h = _cfg_5(tmp_path)
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "a", "--role", "b"]) == 0
    capsys.readouterr()
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 2 and "0 topic(s), 0 role(s)" not in out.out and "none with a posting" in out.out, out.out


def test_doctor_on_a_fresh_empty_home_is_not_evaluable(home, capsys):
    code, out = run(home, "doctor", capsys=capsys)
    assert code == 2
    assert "NOT EVALUABLE" in out.out and "0 topic(s), 0 role(s)" in out.out
    assert "CLEAN" not in out.out


def test_a_clean_doctor_prints_what_it_checked(home, capsys):
    J.intake(__import__("kenloop.career.config", fromlist=["x"]).load(home), "Acme", "Dev", jd="REST")
    (home / "facts.md").write_text("## Held\n- REST\n")      # doctor also gates the resume's claims
    (home / "resumes" / "resume.md").write_text("REST")
    assert run(home, "jobs", "check", "acme-dev", capsys=capsys)[0] == 0
    code, out = run(home, "doctor", capsys=capsys)
    assert code == 0 and "checked 1 role(s)" in out.out and out.out.strip().endswith("CLEAN")


def test_demo_doctor_has_no_duplicate_stale_warning(tmp_path):
    import subprocess
    import sys
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    shim = tmp_path / "bin"
    shim.mkdir()
    (shim / "ken").write_text(f"#!/bin/sh\nexec {sys.executable} -m kenloop \"$@\"\n")
    (shim / "ken").chmod(0o755)
    env["PATH"] = f"{shim}:{env['PATH']}"
    r = subprocess.run(["sh", str(ROOT / "examples" / "demo.sh")], env=env, capture_output=True, text=True)
    assert r.returncode == 0
    assert "stale" not in r.stderr, r.stderr
