"""Settings that survive a save, intent/depth at topic
and line grain, a chosen start rung with no probes, a rung override, and `next` focused on one topic."""
import json

import pytest

from kenloop import loop
from kenloop.core import learn as L
from kenloop.core import onramp as O
from kenloop.core.errors import NotEvaluable, UsageError

from conftest import run

SYL = """# T

## Path

0. **ground** — what you bring
1. **workloads** — kinds of task
2. **models** — how models work

## Concepts
- workloads :: Extraction :: fields from documents
- models :: Attention :: how tokens weigh each other :: rung:workloads :: depth:first-principles
- models :: Deployment types :: standard vs provisioned :: intent:pass
"""


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t", outlets=("career",))
    (home / "topics" / "t" / "syllabus.md").write_text(SYL)
    L.sync(cfg, "t", quiet=True)
    return cfg


def _conf(home):
    return json.loads((home / "topics" / "t" / "topic.json").read_text())


def test_a_key_the_tool_does_not_know_survives_a_save(t, home):
    p = home / "topics" / "t" / "topic.json"
    p.write_text(json.dumps({**_conf(home), "mine": "keep me"}))
    L.save_config(t, "t", L.load_config(t, "t"))
    assert _conf(home)["mine"] == "keep me"


def test_settings_set_show_and_clear_intent_and_depth(t, home, capsys):
    assert run(home, "settings", "t", "--intent", "understand", "--depth", "mechanism")[0] == 0
    assert (_conf(home)["intent"], _conf(home)["depth"]) == ("understand", "mechanism")
    out = capsys.readouterr().out
    assert "intent: understand; 1 concept(s) differ by their line or rung (1 pass)" in out
    assert "depth: mechanism; 1 concept(s) differ by their line or rung (1 first-principles)" in out
    run(home, "settings", "t", "--clear", "depth")
    assert "depth" not in _conf(home) and _conf(home)["intent"] == "understand"


def test_a_line_setting_overrides_its_topic(t):
    conf = {**L.load_config(t, "t"), "intent": "understand"}
    cons = L.load_state(t, "t")["concepts"]
    assert L.setting(conf, cons["models:deployment-types"], "intent") == "pass"
    assert L.setting(conf, cons["workloads:extraction"], "intent") == "understand"
    assert L.setting({}, cons["workloads:extraction"], "intent") == ""


def test_bad_settings_are_refused_at_both_grains(t, home):
    p = home / "topics" / "t" / "topic.json"
    p.write_text(json.dumps({**_conf(home), "intent": "vibes"}))
    with pytest.raises(NotEvaluable, match="intent"):
        L.load_config(t, "t")
    with pytest.raises(UsageError, match="unknown depth"):
        L.parse_syllabus("## Concepts\n- d :: X :: y :: depth:deep\n")


def test_a_chosen_start_skips_the_probes_and_starts_teaching_there(t, home, capsys):
    assert O.next_step(t, "t")[0] == ["place", "t"]                        # unplaced: probes
    assert run(home, "place", "t", "--start", "0")[0] == 0
    assert "you chose to start on rung 0" in capsys.readouterr().out and _conf(home)["start"] == 0
    argv, why = O.next_step(t, "t")
    assert argv[0] == "foundations" and "rung 1" in why                   # ground is empty: teach rung 1
    run(home, "place", "t", "--clear-start")
    assert "start" not in _conf(home) and O.next_step(t, "t")[0] == ["place", "t"]
    with pytest.raises(UsageError, match="not on the scale"):
        O.place(t, "t", start=9)


def test_a_rung_marker_puts_a_foundation_below_its_domain(t):
    path = O.rungs(t, "t")
    cons = L.load_state(t, "t")["concepts"]
    assert O.rung_of(cons["models:attention"], path) == 1          # rung:workloads, though domain is models
    assert O.rung_of(cons["models:deployment-types"], path) == 2


def test_next_focused_on_one_topic_ignores_the_others_and_says_so(t, cfg, home):
    L.plan(cfg, "other")
    (home / "topics" / "other" / "syllabus.md").write_text("# O\n\n## Concepts\n- d :: Z :: z\n")
    L.sync(cfg, "other", quiet=True)
    O.place(t, "t", start=0)
    evals = {e["rule"]: e for e in loop.evaluate(cfg, topic="t")}
    assert all("other" not in e["argv"] for e in evals.values())
    assert evals["role"]["status"] == "off" and "focused on t" in evals["role"]["detail"]


def test_without_the_focus_the_other_topic_is_suggested(t, cfg, home):
    L.plan(cfg, "aaa")                     # sorts first, so unfocused `next` reaches it
    (home / "topics" / "aaa" / "syllabus.md").write_text("# A\n\n## Concepts\n- d :: Z :: z\n")
    L.sync(cfg, "aaa", quiet=True)
    O.place(t, "t", start=0)
    unfocused = [e for e in loop.evaluate(cfg) if e["status"] == "fired"]
    focused = [e for e in loop.evaluate(cfg, topic="t") if e["status"] == "fired"]
    assert any("aaa" in e["argv"] for e in unfocused)
    assert not any("aaa" in e["argv"] for e in focused)


def test_a_before_concept_is_taught_before_the_concept_it_leads_into(t, home):
    syl = (home / "topics" / "t" / "syllabus.md").read_text()
    syl += "- workloads :: Tokens and embeddings :: text becomes vectors :: before:workloads:extraction\n"
    (home / "topics" / "t" / "syllabus.md").write_text(syl)
    L.sync(t, "t", quiet=True)
    O.place(t, "t", start=1)
    argv, _why = O.next_step(t, "t")
    assert argv[2] == "workloads:tokens-and-embeddings"


def test_old_setting_names_are_read_kept_and_renamed_only_on_purpose(cfg, home, capsys):
    """Deadline/complete, with exam_date/passed read as their old names."""
    import json
    from kenloop.core.errors import NotEvaluable
    L.plan(cfg, "old")
    tj = home / "topics" / "old" / "topic.json"
    tj.write_text(json.dumps({"title": "Old", "outlets": ["career", "cert"], "exam_date": "2031-01-01"}))
    assert L.get_key(L.load_config(cfg, "old"), "deadline") == "2031-01-01"
    run(home, "settings", "old", "--intent", "pass")
    assert "exam_date" in json.loads(tj.read_text())               # a save keeps the name the file uses
    run(home, "settings", "old", "--migrate", "--check")
    assert "exam_date" in json.loads(tj.read_text())
    run(home, "settings", "old", "--migrate")
    conf = json.loads(tj.read_text())
    assert conf["deadline"] == "2031-01-01" and "exam_date" not in conf and conf["intent"] == "pass"
    tj.write_text(json.dumps({"title": "Old", "passed": "2030-01-01", "complete": "2030-01-02"}))
    with pytest.raises(NotEvaluable):
        L.load_config(cfg, "old")
