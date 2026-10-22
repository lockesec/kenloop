"""Topic commands: exam dates, calibration and --hint-depth."""
import json

import pytest

from kenloop import cli
from kenloop.career import config as CC
from conftest import run


def _damage(demo):
    with open(demo / "topics" / "http-fundamentals" / "log.jsonl", "a", encoding="utf-8") as fh:
        fh.write("garbage\n")


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


# --- Topic commands -------------------------------------------------------------------------------

def test_exam_date_never_saves_a_partial_replay(demo, capsys):
    _damage(demo)
    before = (demo / "topics" / "http-fundamentals" / "concepts.json").read_text()
    rc, _o = run(demo, "cert", "exam-date", "http-fundamentals", "--set", "2031-01-01", capsys=capsys)
    assert rc == 2
    assert (demo / "topics" / "http-fundamentals" / "concepts.json").read_text() == before
    conf = json.loads((demo / "topics" / "http-fundamentals" / "topic.json").read_text())
    assert conf["exam_date"] == "2031-01-01"            # the date itself is saved


@pytest.mark.parametrize("depth", ["9", "-1", "5"])
def test_hint_depth_out_of_range_is_a_usage_error(demo, capsys, depth):
    log = demo / "topics" / "http-fundamentals" / "log.jsonl"
    before = log.read_text()
    rc, out = run(demo, "record", "http-fundamentals", "basics:headers", "ok", "--hint-depth", depth,
                  capsys=capsys)
    assert rc == 64 and "--hint-depth" in out.err
    assert log.read_text() == before


@pytest.mark.parametrize("depth", ["0", "1", "4"])
def test_hint_depth_in_range_records(demo, capsys, depth):
    rc, _o = run(demo, "record", "http-fundamentals", "basics:headers", "ok", "--hint-depth", depth,
                 capsys=capsys)
    assert rc == 0


def test_help_matches_the_range(capsys):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["record", "--help"])
    out = capsys.readouterr().out
    assert "0-4" in out.replace("\n", " ")


def test_calibration_on_a_missing_topic_is_usage(home, capsys):
    rc, out = run(home, "calibration", "nope", capsys=capsys)
    assert rc == 64 and "no topic 'nope'" in out.err


def test_exam_date_cleared_wording(tmp_path, capsys):
    h = _mk(tmp_path)
    assert cli.main(["--home", str(h), "cert", "exam-date", "t1", "--set", "2031-01-01"]) == 0
    capsys.readouterr()
    rc, out = run(h, "cert", "exam-date", "t1", "--clear", capsys=capsys)
    assert rc == 0 and "exam date cleared;" in out.out and "cleared saved" not in out.out, out.out


def test_exam_date_cleared_with_a_damaged_log_reads_cleared_and_saved(tmp_path, capsys):
    h = _mk(tmp_path)
    assert cli.main(["--home", str(h), "cert", "exam-date", "t1", "--set", "2031-01-01"]) == 0
    with open(h / "topics" / "t1" / "log.jsonl", "a", encoding="utf-8") as fh:
        fh.write("garbage\n")
    capsys.readouterr()
    rc, out = run(h, "cert", "exam-date", "t1", "--clear", capsys=capsys)
    assert rc == 2 and "exam date cleared and saved; schedules NOT re-derived" in out.out, out.out
    assert cli.main(["--home", str(h), "cert", "exam-date", "t1", "--set", "2031-02-01"]) == 2
    assert "exam date 2031-02-01 saved; schedules NOT" in capsys.readouterr().out
