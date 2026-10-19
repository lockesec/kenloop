"""Pathological inputs stay linear: long words, large sheets, many terms, markup and
code-span runs."""
import time

import pytest

from careerloop import ats, cli
from careerloop import facts as F
from careerloop import home as H
from careerloop import jobs as J


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


def _claims(cfg, capsys, resume="resumes/resume.md"):
    capsys.readouterr()
    rc = J.check_claims(cfg, resume)
    return rc, capsys.readouterr().out


HELD_SQL = "## Held\n- SQL\n"


TERMS = ["http", "tls", "dns", "tcp", "ci/cd", "rest", "json", "graphql", "cdn", "docker", "redis",
         "iso", "sql", "postgresql", "r", "go", "kubernetes"]


# --- Pathological inputs stay linear --------------------------------------------------------------

def test_large_sheet_many_terms_is_fast():
    lines = ["## Held"] + [f"- skill{i} used on project {i} for a few years" for i in range(100_000)]
    sheet = "\n".join(lines) + "\n- Docker\n"
    t = time.perf_counter()
    for k in range(50):
        F.holds(f"term{k}", sheet)
    assert time.perf_counter() - t < 15          # parsed once: 50 lookups of one 4 MB sheet


def test_five_mb_paragraph_of_short_lines_is_fast():
    sheet = "## Held\n" + "\n".join(["text line"] * 400_000) + "\n"
    t = time.perf_counter()
    F.analyse(sheet)
    assert time.perf_counter() - t < 8


def test_five_mb_resume_is_fast(tmp_path, capsys):
    cfg, _h = _cfg(tmp_path, HELD_SQL, resume="SQL " + "Zurich caf\u00e9 word " * 300_000 + "\n")
    t = time.perf_counter()
    _claims(cfg, capsys)
    assert time.perf_counter() - t < 20


def test_long_words_are_linear():
    words = F.lexicon_words(TERMS)
    t0 = time.perf_counter()
    for w in ("é" * 20000, "aé" * 10000, "Dockеr" * 4000, "е" * 20000):
        F.disguised("REST " + w, words)
    F.disguised(" ".join(["São"] * 50000), words)
    assert time.perf_counter() - t0 < 2.0


def test_many_code_spans_and_backtick_runs_parse_in_linear_time():
    spans = "## Held\n- " + "`a` " * 100000
    runs = "## Held\n- " + " ".join("`" * k for k in range(1, 880))
    for text in (spans, runs):
        t = time.perf_counter()
        F.analyse(text)
        assert time.perf_counter() - t < 0.6, len(text)


@pytest.mark.parametrize("shape", ["<!--" * 40000, "<script" * 40000, "<script>" * 40000, "<style>" * 40000,
                                   "<a " * 40000, "<!x" * 40000, "<?" * 40000])
def test_strip_html_is_linear(shape):
    import time
    t = time.monotonic()
    ats.strip_html("<p>x</p>" + shape)
    assert time.monotonic() - t < 2.0


def test_latex_reader_is_linear_on_repeated_command_brackets(tmp_path):
    import time
    p = tmp_path / "r.tex"
    p.write_text("\\a[" * 40000)
    t = time.monotonic()
    ats.resume_text(p)
    assert time.monotonic() - t < 2.0


@pytest.mark.parametrize("shape", ["<p>a" + " " * 40000 + "b</p>", "<p>a" + "\t" * 40000 + "b</p>"])
def test_strip_html_is_linear_on_white_space_runs(shape):
    t = time.monotonic()
    ats.strip_html(shape)
    assert time.monotonic() - t < 0.5


@pytest.mark.parametrize("body", [" " * 40000, "\\\\[" * 8000, "a" + " " * 40000 + "\nb"])
def test_latex_reader_is_linear(tmp_path, body):
    p = tmp_path / "r.tex"
    p.write_text(body)
    t = time.monotonic()
    ats.resume_text(p)
    assert time.monotonic() - t < 0.5
