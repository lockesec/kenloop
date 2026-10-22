"""Outlets: where what you learn may go besides your own head. A topic with none is studied for
its own sake, which is the normal case; "career" lets it graduate into facts.md; "cert" marks
one studied toward an exam."""
import json

import pytest

from kenloop import certs
from kenloop.career import graduate as G
from kenloop.career import seed as SD
from kenloop.core import learn as L
from kenloop.core.errors import OK, NotEvaluable, UsageError

from conftest import run


def test_a_plain_topic_has_no_outlet(cfg, home):
    assert L.plan(cfg, "history", goal="how empires end") == OK
    conf = L.load_config(cfg, "history")
    assert conf.get("outlets", []) == [] and not L.has_outlet(conf, "career")
    assert "outlets" not in json.loads((home / "topics" / "history" / "topic.json").read_text())


def test_career_is_opt_in_and_from_gap_implies_it(cfg, home):
    SD.plan(cfg, "web", career=True)
    assert L.has_outlet(L.load_config(cfg, "web"), "career")
    L.plan(cfg, "web", force=True)                         # outlets are added, never removed by a plan
    assert L.has_outlet(L.load_config(cfg, "web"), "career")
    with pytest.raises(UsageError, match="unknown outlet"):
        L.plan(cfg, "x", outlets=("fame",))


def test_a_topic_with_no_career_outlet_never_graduates(cfg, home, capsys, monkeypatch):
    L.plan(cfg, "math")
    monkeypatch.setattr(G, "graduation", lambda *a, **k: pytest.fail("reached graduation"))
    assert G.graduate(cfg, "math") == OK
    out = capsys.readouterr().out
    assert "no career outlet" in out and "nothing graduates into facts.md" in out and "--career" in out
    assert G.graduate(cfg, "math", emit=True) == OK
    assert capsys.readouterr().out.startswith("<!--")      # an --emit paste stays a comment


def test_no_topic_is_asked_for_a_demand_bucket(cfg):
    L.plan(cfg, "math")
    assert L.problems(cfg, "math") == ([], [])


def test_an_exam_date_sets_and_clears_the_cert_outlet(cfg, home):
    L.plan(cfg, "sec", outlets=("career",))
    certs.set_exam_date(cfg, "sec", "2030-05-01")
    assert L.load_config(cfg, "sec")["outlets"] == ["career", "cert"]
    certs.set_exam_date(cfg, "sec", clear=True)
    assert L.load_config(cfg, "sec")["outlets"] == ["career"]


def test_a_bad_outlets_field_is_not_evaluable(cfg, home):
    L.plan(cfg, "t")
    (home / "topics" / "t" / "topic.json").write_text('{"title": "t", "outlets": ["fame"]}')
    with pytest.raises(NotEvaluable, match="outlets"):
        L.load_config(cfg, "t")


def test_cli_plan_and_career(home):
    assert run(home, "plan", "language", "--goal", "read Spanish")[0] == OK
    assert run(home, "plan", "security", "--career")[0] == OK
    assert json.loads((home / "topics" / "security" / "topic.json").read_text())["outlets"] == ["career"]
