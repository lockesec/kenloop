"""Practice exam (certs): a draw across domains in proportion to their size."""
import re

import pytest

from kenloop import certs
from kenloop.core import learn as L
from kenloop.core.errors import NOT_EVALUABLE

from conftest import run

SYLLABUS = """# Cert

## Concepts
- net :: Ports :: well-known port numbers
- net :: Protocols :: what runs over TCP and UDP
- net :: Subnets :: dividing an address range
- crypto :: Hashing :: one-way functions
- crypto :: History :: why ciphers broke :: scope:depth
"""


@pytest.fixture
def cert(cfg, home):
    L.plan(cfg, "cert")
    (home / "topics" / "cert" / "syllabus.md").write_text(SYLLABUS)
    L.sync(cfg, "cert", quiet=True)
    L.bank(cfg, "cert", "net:ports", "Which port does HTTPS use?", "443", "rfc")
    return home / "topics" / "cert"


def test_the_draw_follows_domain_size_and_leaves_depth_out(cfg, cert, capsys):
    assert certs.exam(cfg, "cert", n=8) == 0
    out = capsys.readouterr().out
    doms = re.findall(r"^\s+\d+\. \[(\w+)\]", out, re.M)
    assert len(doms) == 8 and doms.count("net") == 6 and doms.count("crypto") == 2   # 3:1 over 8
    assert "History" not in out and "1 depth-scope concept(s) left out" in out
    assert "Q: Which port does HTTPS use?" in out and "--mode exam" in out


def test_a_topic_with_no_exam_scope_is_not_evaluable(cfg, home, capsys):
    L.plan(cfg, "deep")
    (home / "topics" / "deep" / "syllabus.md").write_text("## Concepts\n- d :: X :: y :: scope:depth\n")
    L.sync(cfg, "deep", quiet=True)
    assert certs.exam(cfg, "deep") == NOT_EVALUABLE
    assert "no exam-scope concepts" in capsys.readouterr().out


def test_the_cli_runs_it(home, cert):
    assert run(home, "cert", "exam", "cert", "--n", "4")[0] == 0


def test_a_banked_question_is_never_printed_twice_in_one_exam(cfg, cert, capsys):
    """Four concepts and twenty draws: the one banked question is asked once; the other draws
    on that concept ask for a new question, so the pass mark is not computed over repeats."""
    assert certs.exam(cfg, "cert", n=20) == 0
    out = capsys.readouterr().out
    assert out.count("Q: Which port does HTTPS use?") == 1, out
    assert len(re.findall(r"^\s+\d+\. \[", out, re.M)) == 20
