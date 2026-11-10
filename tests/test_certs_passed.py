"""A passed exam is a credential: `cert passed` records it and prints a held line for facts.md."""
import json

import pytest

from kenloop import certs
from kenloop.career import facts as F
from kenloop.core import learn as L
from kenloop.core.errors import UsageError

from conftest import run


@pytest.fixture
def cert(cfg, home):
    L.plan(cfg, "secplus")
    conf = L.load_config(cfg, "secplus")
    L.save_config(cfg, "secplus", {**conf, "title": "CompTIA Security+ (SY0-701)", "outlets": ["career", "cert"]})
    return home / "topics" / "secplus"


def test_passed_records_the_date_and_emits_a_line_that_reads_back_as_held(cfg, home, cert, capsys):
    code, out = run(home, "cert", "passed", "secplus", "--on", "2030-03-18", "--emit", capsys=capsys)
    assert code == 0
    assert json.loads((cert / "topic.json").read_text())["complete"] == "2030-03-18"
    block = out.out.strip()
    assert block.startswith("<!--") and block.endswith("- CompTIA Security+ (SY0-701) (credential, passed 2030-03-18)")
    sheet = "## Held\n" + block
    assert F.holds("security+", sheet) and F.holds("CompTIA Security+ (SY0-701)", sheet)


def test_default_is_today_and_the_plain_form_says_who_pastes(cfg, home, cert, capsys):
    code, out = run(home, "cert", "passed", "secplus", capsys=capsys)
    assert code == 0 and "passed 2030-03-20 recorded" in out.out and "yourself; nothing writes it" in out.out
    assert (home / "facts.md").read_text().count("Security+") == 0          # facts.md is never written


def test_the_suggested_emit_on_a_later_day_keeps_the_recorded_pass_date(cfg, home, cert, capsys):
    """The plain form tells you to run `--emit`; running it days later must not move the pass."""
    run(home, "cert", "passed", "secplus", "--on", "2030-03-01", capsys=capsys)
    code, out = run(home, "cert", "passed", "secplus", "--emit", capsys=capsys)   # today is 03-20
    assert code == 0 and out.out.strip().endswith("(credential, passed 2030-03-01)")
    code, out = run(home, "cert", "passed", "secplus", capsys=capsys)
    assert code == 0 and "passed 2030-03-01 recorded" in out.out
    assert L.get_key(L.load_config(cfg, "secplus"), "complete") == "2030-03-01"
    run(home, "cert", "passed", "secplus", "--on", "2030-03-02", capsys=capsys)     # an explicit date corrects it
    assert L.get_key(L.load_config(cfg, "secplus"), "complete") == "2030-03-02"


def test_a_future_or_malformed_date_and_a_non_cert_topic_are_refused(cfg, home, cert):
    with pytest.raises(UsageError, match="future"):
        certs.passed(cfg, "secplus", "2030-03-21")
    with pytest.raises(UsageError, match="YYYY-MM-DD"):
        certs.passed(cfg, "secplus", "March 18")
    assert "passed" not in L.load_config(cfg, "secplus")                    # nothing recorded on refusal
    L.plan(cfg, "notes")
    with pytest.raises(UsageError, match="no cert outlet"):
        certs.passed(cfg, "notes")


def test_the_passed_date_survives_an_exam_date_change(cfg, home, cert):
    certs.passed(cfg, "secplus", "2030-03-18")
    certs.set_exam_date(cfg, "secplus", "2030-06-01")
    assert L.get_key(L.load_config(cfg, "secplus"), "complete") == "2030-03-18"


SYL = "# S\n\n## Concepts\n- net :: Ports :: well-known port numbers\n"


def _due_today(cfg, home, slug, monkeypatch):
    (home / "topics" / slug / "syllabus.md").write_text(SYL)
    L.sync(cfg, slug, quiet=True)
    L.record(cfg, slug, "net:ports", "miss", quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-09-01")             # months later: the review is due
    assert L.due_list(cfg, slug, L.H.today())


def test_a_passed_topic_leaves_next_and_due_but_named_review_still_works(cfg, home, cert, capsys, monkeypatch):
    _due_today(cfg, home, "secplus", monkeypatch)
    from kenloop import loop
    reviews = lambda: next(r for r in loop.evaluate(cfg) if r["rule"] == "reviews")  # noqa: E731
    assert reviews()["status"] == "fired" and "secplus" in reviews()["argv"]
    certs.passed(cfg, "secplus", "2030-03-18")
    assert reviews()["status"] == "not fired"
    capsys.readouterr()
    run(home, "due", capsys=None)
    out = capsys.readouterr().out
    assert "secplus: complete (exam passed 2030-03-18), off the schedule" in out and "net:ports" not in out
    run(home, "due", "secplus")
    assert "net:ports" in capsys.readouterr().out                           # going back by name still works
    assert L.load_state(cfg, "secplus")["concepts"]["net:ports"]["attempts"] == 1   # record untouched


def test_clear_puts_a_passed_topic_back_on_the_schedule(cfg, home, cert, capsys, monkeypatch):
    _due_today(cfg, home, "secplus", monkeypatch)
    certs.passed(cfg, "secplus", "2030-03-18")
    assert "secplus" not in L.scheduled_topics(cfg)
    certs.passed(cfg, "secplus", clear=True)
    assert "secplus" in L.scheduled_topics(cfg) and "passed" not in L.load_config(cfg, "secplus")


def test_a_passed_topic_set_to_keep_studying_stays_on_the_schedule(cfg, home, cert, capsys):
    run(home, "cert", "passed", "secplus", "--on", "2030-03-18")
    assert "secplus" not in L.scheduled_topics(cfg)                       # passed: off the schedule
    code, out = run(home, "settings", "secplus", "--keep-studying", "on", capsys=capsys)
    assert code == 0 and "still studied" in out.out
    assert "secplus" in L.scheduled_topics(cfg) and L.off_schedule(cfg, "secplus") == ""
    assert L.passed_on(cfg, "secplus") == "2030-03-18"                    # the credential stands
    code, out = run(home, "due", capsys=capsys)
    assert "secplus: 0 due" in out.out and "off the schedule" not in out.out
    run(home, "settings", "secplus", "--keep-studying", "off")
    assert "secplus" not in L.scheduled_topics(cfg) and "keep_studying" not in L.load_config(cfg, "secplus")


def test_an_old_named_pass_keeps_studying_too(cfg, home, cert):
    conf = L.load_config(cfg, "secplus")
    L.save_config(cfg, "secplus", {**conf, "passed": "2030-03-18", "keep_studying": True})
    assert "secplus" in L.scheduled_topics(cfg)


def test_keep_studying_before_a_pass_says_when_it_applies_and_doctor_flags_a_bad_value(cfg, home, cert, capsys):
    code, out = run(home, "settings", "secplus", "--keep-studying", "on", capsys=capsys)
    assert code == 0 and "takes effect once the exam is passed" in out.out
    from kenloop.core import settings as ST
    assert ST.doctor(cfg) == []
    conf = L.load_config(cfg, "secplus")
    L.save_config(cfg, "secplus", {**conf, "keep_studying": "yes"})
    found = ST.doctor(cfg)
    assert found[0][0] == "FINDING" and "'yes'" in found[0][1]


def test_session_and_pass_clear_say_keep_studying(cfg, home, cert, capsys):
    run(home, "cert", "passed", "secplus", "--on", "2030-03-18")
    run(home, "settings", "secplus", "--keep-studying", "on")
    capsys.readouterr()
    run(home, "session", "secplus")
    assert "still studied" in capsys.readouterr().out
    code, out = run(home, "cert", "passed", "secplus", "--clear", capsys=capsys)
    assert "keep studying stays set" in out.out
