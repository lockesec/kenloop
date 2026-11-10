"""One idea, one record. The same idea in two topics (a shared `:: same:` key)
is one held set: once it has been taught, hinted or answered under one topic today, an answer under
the other topic the same day is a repeat, never a credited first look."""
import pytest

from kenloop.core import learn as L

from conftest import rows

CRYPTO = "# C\n\n## Concepts\n- sym :: Symmetric encryption :: one key :: same:crypto-symmetric\n"
SEC = "# S\n\n## Concepts\n- 1-general :: 1.4 Symmetric encryption :: AES etc :: same:crypto-symmetric\n"
CRYPTO_ID, SEC_ID = "sym:symmetric-encryption", "1-general:1-dot-4-symmetric-encryption"


@pytest.fixture
def two(cfg, home):
    for slug, syl in (("crypto", CRYPTO), ("sec", SEC)):
        L.plan(cfg, slug)
        (home / "topics" / slug / "syllabus.md").write_text(syl)
        L.sync(cfg, slug, quiet=True)
    return cfg


def test_taught_under_one_topic_is_a_repeat_under_its_twin_the_same_day(two):
    L.taught(two, "crypto", CRYPTO_ID, quiet=True)
    L.record(two, "sec", SEC_ID, "ok", quiet=True)
    c = L.load_state(two, "sec")["concepts"][SEC_ID]
    assert c.get("repeats") == 1 and not c.get("streak") and not c.get("correct_days")


def test_an_answer_under_a_twin_on_a_later_day_is_a_first_look(two, monkeypatch):
    L.taught(two, "crypto", CRYPTO_ID, quiet=True)
    monkeypatch.setenv("KENLOOP_TODAY", "2030-03-21")
    L.record(two, "sec", SEC_ID, "ok", quiet=True)
    c = L.load_state(two, "sec")["concepts"][SEC_ID]
    assert c.get("streak") == 1 and not c.get("repeats")


def test_the_row_keeps_where_it_was_seen_and_replay_agrees(two, home):
    L.taught(two, "crypto", CRYPTO_ID, quiet=True)
    L.record(two, "sec", SEC_ID, "ok", quiet=True)
    assert rows(home, "sec")[-1]["seen_in"] == ["crypto"]
    assert L.audit(two, "sec", L.load_state(two, "sec"))[0] == []      # replay reads only this topic's log


def test_the_quiz_picker_holds_an_idea_seen_under_its_twin_today(two):
    assert SEC_ID not in L.seen_today(two, "sec")
    L.record(two, "crypto", CRYPTO_ID, "ok", quiet=True)
    assert SEC_ID in L.seen_today(two, "sec")


def test_idea_keys():
    assert L.idea_key("sec", SEC_ID, {"same": "crypto-symmetric"}) == "crypto-symmetric"
    assert L.idea_key("sec", "a:b", {}) == "sec/a:b"
