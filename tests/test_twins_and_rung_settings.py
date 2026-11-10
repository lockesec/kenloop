"""The same idea in two topics is linked by a
shared `:: same:` key and shown, never credited across; intent/depth set on a whole `## Path` rung,
so ingested concept lines need no marker."""
import pytest

from kenloop.core import learn as L
from kenloop.core import onramp as O
from kenloop.core.errors import UsageError

from conftest import run

CRYPTO = "# C\n\n## Concepts\n- sym :: Symmetric encryption :: one key :: same:crypto-symmetric\n"
SEC = "# S\n\n## Concepts\n- 1-general :: 1.4 Symmetric encryption :: AES etc :: same:crypto-symmetric\n" \
      "- 1-general :: 1.4 Hashing :: one-way\n"
SCALED = """# A

## Path

0. **ground** — what you bring
1. **concepts** — how it works
2. **service** — the vendor's product :: intent:pass :: depth:exam

## Concepts
- concepts :: Tokens :: text to ids
- service :: Deploy a model :: portal steps
- service :: Prompt basics :: system vs user :: intent:understand
"""


@pytest.fixture
def two(cfg, home):
    for slug, syl in (("crypto", CRYPTO), ("sec", SEC)):
        L.plan(cfg, slug)
        (home / "topics" / slug / "syllabus.md").write_text(syl)
        L.sync(cfg, slug, quiet=True)
    return cfg


def test_twins_are_found_across_topics_by_their_shared_key(two):
    assert [(t, k) for t, k, _n, _b in L.twins(two, "crypto", "sym:symmetric-encryption")] == [
        ("sec", "1-general:1-dot-4-symmetric-encryption")]
    assert L.twins(two, "sec", "1-general:1-dot-4-hashing") == []          # no key, no twin


def test_talk_shows_the_twin_and_no_credit_moves(two, home, capsys):
    L.record(two, "sec", "1-general:1-dot-4-symmetric-encryption", "ok", quiet=True)
    capsys.readouterr()
    run(home, "talk", "crypto", "sym:symmetric-encryption")
    assert "the same idea in sec: 1.4 Symmetric encryption" in capsys.readouterr().out
    assert not L.load_state(two, "crypto")["concepts"]["sym:symmetric-encryption"].get("attempts")


def test_a_rung_sets_intent_and_depth_and_a_line_still_wins(cfg, home):
    L.plan(cfg, "a")
    (home / "topics" / "a" / "syllabus.md").write_text(SCALED)
    L.sync(cfg, "a", quiet=True)
    run(home, "settings", "a", "--intent", "understand", "--depth", "mechanism")
    cons = L.load_state(cfg, "a")["concepts"]
    eff = {k: (O.concept_setting(cfg, "a", c, "intent"), O.concept_setting(cfg, "a", c, "depth")) for k, c in cons.items()}
    assert eff["concepts:tokens"] == ("understand", "mechanism")          # the topic's
    assert eff["service:deploy-a-model"] == ("pass", "exam")             # the rung's
    assert eff["service:prompt-basics"] == ("understand", "exam")        # its own line, then the rung


def test_a_bad_rung_setting_is_refused():
    with pytest.raises(UsageError, match="unknown intent"):
        O.path_settings("## Path\n\n1. **x** — y :: intent:maybe\n")
