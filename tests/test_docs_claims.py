"""The documents say what the code does: command tables, trust rules, DESIGN and the
CHANGELOG are checked against behaviour."""
from pathlib import Path

import pytest

from kenloop.career import facts as F
from conftest import run


ROOT = Path(__file__).resolve().parents[1]


def _section(path, heading):
    text = (ROOT / path).read_text(encoding="utf-8")
    start = text.index(heading)
    nxt = text.find("\n## ", start + 1)
    return text[start:nxt if nxt > 0 else len(text)]


# --- Documentation states what is true ------------------------------------------------------------

def test_bom_before_held_on_line_one():
    assert F.has_held_section("﻿## Held\n- Go\n") and F.holds("go", "﻿## Held\n- Go\n")


@pytest.mark.parametrize("sheet", [
    "```\n## Held\n- Go\n```\n",
    "   ```\n## Held\n- Go\n   ```\n",
    "```\n## Held\n- Go\n",                 # never closed
    "    ## Held\n- Go\n",                  # 4-space indented code
    "~~~~\n## Held\n- Go\n~~~\n",           # a shorter closer does not close it
    "<!-- opened\n## Held\n- Go\n",         # an unclosed comment hides the rest
])
def test_held_heading_inside_code_or_comment_does_not_count(sheet):
    assert not F.has_held_section(sheet) and not F.holds("go", sheet)


@pytest.mark.parametrize("sheet", [
    "    Held\n---\n- Docker\n",
    "> Held\n---\n- Docker\n",
])
def test_indented_code_and_blockquote_are_not_setext_titles(sheet):
    assert not F.has_held_section(sheet) and not F.holds("docker", sheet)


def test_nbsp_after_hashes_is_not_a_heading():
    assert not F.has_held_section("##\u00a0Held\n- Docker\n")


def test_docs_do_not_overclaim():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    text = "\n".join((root / p).read_text(encoding="utf-8") for p in
                    ("docs/trust-rules.md", "README.md", "CHANGELOG.md", "docs/commands.md"))
    for stale in ("every mixed-script", "minus as many letters", "no table of look-alikes",
                  "a word with an ASCII letter and any other non-ASCII"):
        assert stale not in text, stale


def test_docs_say_exactly_which_commands_exit_2_on_absence():
    sec = _section("docs/commands.md", "## When a command cannot look")
    for phrase in ("doctor", "next", "validate", "due", "jobs gaps", "jobs upskill",
                   "calibration", "misconceptions", "sync", "cert exam-date",
                   "jobs check-claims", "jobs check"):
        assert phrase in sec, phrase
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/commands.md#when-a-command-cannot-look" in readme


def test_accent_rule_and_remedy_are_stated_where_the_overclaim_was():
    for p in ("docs/trust-rules.md", "docs/commands.md"):
        text = (ROOT / p).read_text(encoding="utf-8")
        assert "four or more letters" in text and "retype" in text and "accent" in text, p
    assert "ordinary\n  non-English words, and anything the look-alike" not in \
        (ROOT / "README.md").read_text(encoding="utf-8")


def test_docs_say_which_resumes_doctor_scans():
    text = (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
    assert "doctor scans" in text


def test_docs_keep_calling_the_table_a_short_list():
    text = (ROOT / "docs" / "trust-rules.md").read_text(encoding="utf-8")
    assert "a list, not a complete Unicode confusables set" in text


def test_added_qualifiers_are_listed_in_the_docs():
    doc = (ROOT / "docs" / "trust-rules.md").read_text(encoding="utf-8")
    for w in ("will learn", "to be learned", "just started", "trailing"):
        assert w in doc, w


def test_changelog_records_the_absence_changes():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Absence: `doctor` exits 2 on an empty or missing `facts.md`" in text


def test_the_doc_claim_is_true_for_every_command_it_names(home, capsys):
    text = (ROOT / "docs" / "trust-rules.md").read_text(encoding="utf-8")
    assert "`next`" in text and "`jobs gaps`" in text
    for argv in (("doctor",), ("next",), ("validate",), ("due",), ("jobs", "upskill"),
                 ("jobs", "gaps")):
        rc, out = run(home, *argv, capsys=capsys)
        s = out.out + out.err
        assert rc == 2 and "0 role(s)" in s or "0 topic(s)" in s or "no roles and no topics" in s, (argv, s)


def test_docs_no_longer_claim_the_list_is_exhaustive_and_name_each_row():
    text = (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
    assert "Exactly these exit 2" not in text
    assert "Any command that cannot look exits 2" in text
    for phrase in ("without `coverage.json`", "no confidence-rated", "no concepts", "exam-scope", "--from-gap",
                   "no `[sources]` targets", "missing home", "schema-2", "`meta.json`"):
        assert phrase in text, phrase


def test_design_describes_the_current_disguise_rule_not_the_fail_closed_one():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert "fails closed" not in text.split("## Decision: held is structural")[0] or "superseded" in text
    assert "carries a character that is not plain ASCII" not in text
    assert "altered" in text and "parts" in text and "possessive" in text


def test_docs_state_the_rule():
    assert "current directory" in (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")


def test_docs_state_what_is_matched_and_which_rows_exit_2():
    cmds = (ROOT / "docs" / "commands.md").read_text(encoding="utf-8")
    trust = (ROOT / "docs" / "trust-rules.md").read_text(encoding="utf-8")
    for phrase in ("is stale", "role directory without `meta.json`", "not a regular file", "states no lexicon term",
                   "1 to 64 characters", "`reconcile --board` needs"):
        assert phrase in cmds, phrase
    for phrase in ("How a term is matched", "U+2010 to U+2015", "`Open ID Connect`", "Load<U+00AD>Balancing",
                   "consecutive words", "private-use"):
        assert phrase in trust, phrase
    assert "`facts.md` missing, empty or without `## Held`" in cmds
