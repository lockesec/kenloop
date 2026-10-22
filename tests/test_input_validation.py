"""Argument values, file contents and names that must be refused or named: usage errors
for bad values, non-UTF-8 input, slugs and board/pack names, dates, counts, scores and fixture entries."""
import json
import math

import pytest

from kenloop.career import ats
from kenloop import cli
from kenloop.career import facts as F
from kenloop.career import jobs as J
from kenloop.core import learn as L
from kenloop.career import roles as R
from kenloop.career import sources as S
from kenloop.core.errors import NotEvaluable
from kenloop.career import config as CC
from conftest import run


def _fixture_cfg(home, data):
    (home / "fixtures").mkdir(exist_ok=True)
    (home / "fixtures" / "x.json").write_text(json.dumps(data), encoding="utf-8")
    return CC.load(home)


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


# --- Slugs and names are validated ----------------------------------------------------------------

@pytest.mark.parametrize("bad", ["../x", "a/b"])
def test_unsafe_board_and_pack_names_are_refused(cfg, bad):
    from kenloop.career import ats, sources
    assert sources.fetch("fixture", bad, cfg).status == "error"
    cfg.packs = [bad]
    with pytest.raises(NotEvaluable):
        ats.load_lexicon(cfg)


@pytest.mark.parametrize("slug", ["", "a" * 65, "a" * 300])
def test_a_bad_topic_slug_is_a_usage_error(home, capsys, slug):
    for extra in ([], ["--force"]):
        code, out = run(home, "plan", slug, *extra, capsys=capsys)
        assert code == 64 and "internal error" not in out.err
    assert not any((home / "topics").iterdir())


def test_a_64_character_slug_is_fine(home):
    assert run(home, "plan", "a" * 64)[0] == 0


def test_a_non_ascii_title_keeps_its_letters_in_the_slug():
    assert R.slugify("\u00dcn\u00ef Caf\u00e9 ##") == "uni-cafe"


def test_slugs_transliterate_letters_that_do_not_decompose():
    assert R.slugify("Straße Œuvre Łódź Ærø") == "strasse-oeuvre-lodz-aero"


# --- Bad argument values are usage errors ---------------------------------------------------------

@pytest.mark.parametrize("data,want", [
    ([1, 2], "entry 1 is not an object"),
    ([{"ext_id": "1", "title": "ok"}, 5], "entry 2 is not an object"),
    ([{"ext_id": None, "title": None, "location": None, "url": None, "jd": None}], "entry 1 has no title"),
    ([{"ext_id": "1", "title": ""}], "entry 1 has no title"),
    ([{"ext_id": "1", "title": 7}], "entry 1 has no title"),
    ([{"ext_id": "1", "title": "t", "jd": 5}], "entry 1: jd must be text"),
    ([{"ext_id": [1], "title": "t"}], "entry 1: ext_id must be"),
])
def test_fixture_entries_are_validated_with_a_clear_message(home, data, want):
    cfg = _fixture_cfg(home, data)
    res = S.fetch("fixture", "x", cfg)
    assert res.status == "error" and want in res.error, res.error


def test_fixture_with_null_optional_fields_is_fine(home):
    cfg = _fixture_cfg(home, [{"ext_id": 7, "title": "Dev", "location": None, "url": None, "jd": None,
                               "deadline": None}])
    res = S.fetch("fixture", "x", cfg)
    assert res.status == "ok" and res.postings[0]["title"] == "Dev" and res.postings[0]["ext_id"] == "7"


def test_discover_reports_a_bad_fixture_entry(home, capsys):
    _fixture_cfg(home, [1])
    rc, out = run(home, "jobs", "discover", "--board", "fixture", "--company", "x", capsys=capsys)
    assert rc == 2 and "entry 1 is not an object" in out.out


def test_board_status_is_validated(home, capsys):
    rc, out = run(home, "jobs", "board", "--status", "bogus", capsys=capsys)
    assert rc == 64 and "bogus" in out.err
    rc, out = run(home, "jobs", "board", "--status", "found", capsys=capsys)
    assert rc == 0


@pytest.mark.parametrize("argv", [("quiz", "t1", "--n", "-1"), ("quiz", "t1", "--n", "0"),
                                  ("due", "--limit", "-3"), ("due", "--limit", "0"),
                                  ("plan", "t2", "--top", "0"), ("plan", "t2", "--top", "x")])
def test_counts_below_one_are_usage_errors(home, capsys, argv):
    rc, out = run(home, *argv, capsys=capsys)
    assert rc == 64 and "1 or more" in out.err or "whole number" in out.err, out.err


def test_counts_of_one_or_more_are_accepted(home, capsys):
    assert run(home, "plan", "t1")[0] == 0
    assert run(home, "due", "--limit", "1")[0] in (0, 2)


@pytest.mark.parametrize("bad", ["20300401", "2030-W14-1", "2030-4-1", "２０３０-04-01"])
def test_dates_must_be_written_yyyy_mm_dd(home, capsys, bad):
    assert run(home, "plan", "t1")[0] == 0
    rc, out = run(home, "cert", "exam-date", "t1", "--set", bad, capsys=capsys)
    assert rc == 64 and "YYYY-MM-DD" in out.err
    rc, out = run(home, "jobs", "intake", "--company", "a", "--role", "b", "--deadline", bad, capsys=capsys)
    assert rc == 64 and "YYYY-MM-DD" in out.err


def test_a_good_date_is_accepted(home, capsys):
    assert run(home, "plan", "t1")[0] == 0
    assert run(home, "cert", "exam-date", "t1", "--set", "2031-04-01")[0] == 0


def test_the_echoed_word_is_capped(tmp_path, capsys):
    long = "Dockеr" + "x" * 500
    sp = F.suspects("REST " + long)
    assert sp and all(len(s.shown) <= 81 for s in sp)
    word = "Dockеr" + "е" * 500                       # a long run of one look-alike
    cfg, _h = _cfg(tmp_path, resume=f"REST Dockеr {word}\n")
    capsys.readouterr()
    J.check_claims(cfg, "resumes/resume.md")
    out = capsys.readouterr().out
    assert max(len(ln) for ln in out.splitlines()) < 600


@pytest.mark.parametrize("argv", [
    ["jobs", "board", "--min-fit", "nan"], ["jobs", "intake", "--company", "", "--role", "x"],
    ["jobs", "intake", "--company", "x", "--role", " "], ["jobs", "reconcile", "--board", "fixture"],
    ["jobs", "discover", "--board", "nosuch", "--company", "acme"],
    ["jobs", "score", "x", "--fit", "nan"],
])
def test_bad_argument_values_are_usage_errors(home, capsys, argv):
    code, out = run(home, *argv, capsys=capsys)
    assert code == 64 and "internal error" not in out.err, argv


def test_a_long_user_term_is_capped_with_a_named_warning(home, capsys):
    long_term = " ".join(f"w{i}" for i in range(12))
    (home / "lexicons" / "mine.toml").write_text(f'name = "mine"\n[categories]\nx = ["{long_term}", "python"]\n')
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\nuser_lexicon = "lexicons/mine.toml"\n')
    lex = ats.load_lexicon(CC.load(home))
    assert long_term not in [t for t, _c in lex.terms] and "python" in [t for t, _c in lex.terms]
    assert "words" in capsys.readouterr().err


@pytest.mark.parametrize("fit", [99, -3, 0, 5.5, math.nan, math.inf])
def test_a_fit_score_out_of_range_is_named(fit):
    m = {"company": "A", "role": "B", "status": "found", "fit_score": fit}
    assert R.meta_problem(m)


@pytest.mark.parametrize("fit", [None, 1, 3, 4.5, 5])
def test_a_fit_score_in_range_is_accepted(fit):
    m = {"company": "A", "role": "B", "status": "found", "fit_score": fit}
    assert not R.meta_problem(m)


def test_a_bad_posting_deadline_names_the_field_not_a_flag(tmp_path, capsys):
    import json
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    fx = h / "fixtures"
    fx.mkdir(exist_ok=True)
    (fx / "acme.json").write_text(json.dumps([{"title": "Dev", "ext_id": "1", "jd": "Python work",
                                               "deadline": "soon"}]))
    cli.main(["--home", str(h), "jobs", "discover", "--board", "fixture", "--company", "acme", "--intake"])
    out = capsys.readouterr()
    text = out.out + out.err
    assert "deadline field" in text and "--deadline" not in text


# --- Non-UTF-8 inputs are named -------------------------------------------------------------------

def test_a_non_utf8_log_row_is_a_damaged_row_not_an_internal_error(tmp_path, capsys):
    h = _mk(tmp_path)
    log = h / "topics" / "t1" / "log.jsonl"
    log.write_bytes(b'{"date": "2030-03-20", "concept": "x", "result": "ok"}\n\xff\xfe broken\n')
    capsys.readouterr()
    rc, out = run(h, "validate", "t1", capsys=capsys)
    s = out.out + out.err
    assert "internal error" not in s and "log.jsonl line 2" in s and "UTF-8" in s, s
    assert rc == 2
    rows, probs = L.read_log(CC.load(h), "t1")
    assert len(rows) == 1 and len(probs) == 1 and "line 2" in probs[0]


def test_a_non_utf8_posting_names_the_file(tmp_path, capsys):
    h = _mk(tmp_path)
    (h / "roles" / "acme-dev" / "jd.txt").write_bytes(b"We need REST \xff\xfe")
    capsys.readouterr()
    rc, out = run(h, "jobs", "check", "acme-dev", capsys=capsys)
    assert rc == 2 and "jd.txt" in out.err and "internal error" not in out.err, out
    rc, out = run(h, "doctor", capsys=capsys)
    assert rc == 2 and "jd.txt" in out.out and "UTF-8" in out.out, out


@pytest.mark.parametrize("name", ["syllabus.md", "questions.md"])
def test_a_non_utf8_topic_file_names_the_file(tmp_path, capsys, name):
    h = _mk(tmp_path)
    (h / "topics" / "t1" / name).write_bytes(b"## Concepts\n- x :: \xff\n")
    capsys.readouterr()
    rc, out = run(h, "validate", "t1", capsys=capsys)
    assert rc == 2 and name in (out.out + out.err) and "internal error" not in (out.out + out.err), out


def test_non_utf8_jd_is_named(home, tmp_path, capsys, monkeypatch):
    bad = tmp_path / "jd.txt"
    bad.write_bytes(b"REST \xff\xfe")
    code, out = run(home, "jobs", "intake", "--company", "A", "--role", "B", "--jd", str(bad), capsys=capsys)
    assert code in (2, 64) and "internal error" not in out.err and "UTF-8" in out.err
    import io
    import sys
    monkeypatch.setattr(sys, "stdin", type("S", (), {"buffer": io.BytesIO(b"REST \xff")})())
    code, out = run(home, "jobs", "intake", "--company", "A", "--role", "B", "--jd", "-", capsys=capsys)
    assert code in (2, 64) and "internal error" not in out.err and "UTF-8" in out.err


def test_quiz_stdin_that_is_not_utf8_is_named(home, monkeypatch, capsys):
    import io
    import sys
    (home / "topics" / "t").mkdir(parents=True)
    assert run(home, "plan", "t2")[0] == 0
    (home / "topics" / "t2" / "syllabus.md").write_text("# T\n\n## Concepts\n\n- d :: Alpha :: x\n")
    assert run(home, "sync", "t2")[0] == 0
    assert run(home, "bank", "t2", "Alpha", "--q", "q?", "--a", "a", "--ref", "r")[0] == 0
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"\xff\xfe\n"), encoding="utf-8"))
    code, out = run(home, "quiz", "t2", "--interactive", capsys=capsys)
    assert "internal error" not in out.err and code in (0, 2)
    if code == 2:
        assert "UTF-8" in out.err
