"""How a --resume argument and a resume file are resolved and read: relative paths,
directories and devices, missing files, files that are not text, and a byte order mark."""
import json
from pathlib import Path

import pytest

from careerloop import cli
from careerloop import home as H
from careerloop import jobs as J
from careerloop.errors import NotEvaluable
from conftest import run


LEX = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services", "bash", "mongodb", "hbase"]
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
    return H.load_config(h), h


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


def _role(home, jd="REST and Docker and CDN"):
    (home / "facts.md").write_text("## Held\n- REST\n- Docker\n- CDN\n")
    (home / "resumes" / "resume.md").write_text("REST Docker CDN\n")
    slug, _ = J.intake(H.load_config(home), "Acme", "Dev", jd=jd)
    return slug


def _role_2(h, body, slug="acme-dev"):
    d = h / "roles" / slug
    d.mkdir(parents=True)
    (d / "meta.json").write_text(body)
    (d / "jd.txt").write_text("Python\n")
    return d


# --- Resume paths and files -----------------------------------------------------------------------

def test_an_explicit_missing_resume_is_not_evaluable(cfg, home):
    (home / "resumes" / "resume.md").write_text("REST")
    slug, _ = J.intake(cfg, "Acme", "Dev", jd="REST")
    with pytest.raises(NotEvaluable):
        J.check(cfg, slug, resume="resumes/missing.md")


@pytest.mark.parametrize("name,data", [
    ("utf16", "REST Docker".encode("utf-16")),
    ("utf16be", b"\xfe\xff\x00R\x00E\x00S\x00T"),
    ("nul", b"REST\x00Docker\x00"),
    ("latin1", b"REST caf\xe9 Docker"),
    ("binary", bytes(range(128, 256))),
])
def test_a_resume_that_is_not_utf8_text_is_not_evaluable(tmp_path, capsys, name, data):
    cfg, h = _cfg(tmp_path, "## Held\n- REST\n", data)
    slug, _ = J.intake(cfg, "acme", "dev", jd="REST and Docker")
    capsys.readouterr()
    with pytest.raises(NotEvaluable) as e:
        J.check_claims(cfg, "resumes/resume.md")
    assert "UTF-8" in str(e.value) and "resume" in str(e.value)
    assert run(h, "jobs", "check-claims", "resumes/resume.md", capsys=capsys)[0] == 2
    assert run(h, "jobs", "check", slug, capsys=capsys)[0] == 2
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 2 and "UTF-8" in out.out, out.out


def test_a_utf8_resume_with_a_byte_order_mark_is_still_read(tmp_path, capsys):
    cfg, _h = _cfg(tmp_path, "## Held\n- REST\n", b"\xef\xbb\xbfREST Docker\n")
    capsys.readouterr()
    assert J.check_claims(cfg, "resumes/resume.md") == 1
    assert "docker" in capsys.readouterr().out.lower()


def test_a_relative_resume_is_tried_in_the_current_directory_first_then_the_home(tmp_path, capsys, monkeypatch):
    h = _mk(tmp_path, "## Held\n- REST\n- SQL\n- Docker\n")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "mine.md").write_text("REST SQL Docker\n")
    (h / "mine.md").write_text("REST\n")                       # same name in the home: loses to the cwd
    monkeypatch.chdir(cwd)
    cfg = H.load_config(h)
    assert J.user_path(cfg, "mine.md") == Path("mine.md")
    assert J.resolve_resume(cfg, None, "mine.md") == Path("mine.md").resolve()  # absolute, so coverage stays fresh from any cwd
    (cwd / "mine.md").unlink()
    assert J.user_path(cfg, "mine.md") == h / "mine.md"
    assert J.resolve_resume(cfg, None, "mine.md") == h / "mine.md"
    assert J.check(cfg, "acme-dev", "mine.md") == 0
    capsys.readouterr()
    assert J.check_claims(cfg, "mine.md") == 0


def test_a_relative_resume_leaves_coverage_fresh_from_any_cwd(home, tmp_path, monkeypatch, capsys):
    slug = _role(home)
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "mine.md").write_text("REST Docker CDN\n")
    monkeypatch.chdir(other)
    assert run(home, "jobs", "check", slug, "--resume", "mine.md")[0] == 0
    cov = json.loads((home / "roles" / slug / "coverage.json").read_text())
    assert Path(cov["resume"]).is_absolute() or (home / cov["resume"]).is_file()
    monkeypatch.chdir(tmp_path)                                          # another cwd
    assert not J.coverage_stale(H.load_config(home), slug, cov)
    assert run(home, "jobs", "tailor", slug)[0] == 0
    assert run(home, "doctor", capsys=capsys)[1].out.count("stale") == 0


def test_a_relative_resume_inside_home_is_stored_relative(home, monkeypatch):
    slug = _role(home)
    monkeypatch.chdir(home)
    assert run(home, "jobs", "check", slug, "--resume", "resumes/resume.md")[0] == 0
    cov = json.loads((home / "roles" / slug / "coverage.json").read_text())
    assert cov["resume"] == "resumes/resume.md"
    assert not J.coverage_stale(H.load_config(home), slug, cov)


def test_a_resume_pointer_to_a_missing_file_is_named(home, capsys):
    slug = _role(home)
    mp = home / "roles" / slug / "meta.json"
    m = json.loads(mp.read_text())
    m["resume"] = "resumes/gone.md"
    mp.write_text(json.dumps(m))
    code, out = run(home, "jobs", "check", slug, capsys=capsys)
    assert code == 2 and "gone.md" in out.err


@pytest.mark.parametrize("path", ["/etc", "/dev/null"])
def test_check_claims_names_a_non_regular_file(home, capsys, path):
    (home / "facts.md").write_text("## Held\n- REST\n")
    code, out = run(home, "jobs", "check-claims", path, capsys=capsys)
    assert code == 2 and "not a regular file" in out.err


def test_check_with_a_directory_or_device_resume_says_not_a_regular_file(home, tmp_path, capsys):
    _role_2(home, json.dumps({"company": "Acme", "role": "Dev", "status": "found"}))
    for target in (str(tmp_path), "/dev/null"):
        code, out = run(home, "jobs", "check", "acme-dev", "--resume", target, capsys=capsys)
        assert code == 2 and "not a regular file" in out.err, (target, out.err)
    code, out = run(home, "jobs", "check", "acme-dev", "--resume", str(tmp_path / "missing.md"), capsys=capsys)
    assert code == 2 and "not found" in out.err


def test_an_empty_resume_argument_is_a_usage_error(tmp_path):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    assert cli.main(["--home", str(h), "jobs", "check", "any", "--resume", ""]) == 64
