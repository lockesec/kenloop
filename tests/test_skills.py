"""The skill family conforms: what a skill tells a tutor to run exists, every record mode has exactly
one owning skill, the router names every skill (no skill owned
teaching, so the tutor kept quizzing a learner who asked to be taught)."""
import argparse
import re
from pathlib import Path

import pytest

from kenloop import cli
from kenloop.core import learn as L

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
CONTRACTS = [ROOT / "docs" / "dialogue-rules.md", ROOT / "docs" / "tutor-rules.md"]
GROUPS = ("jobs", "cert")          # verbs with a subcommand


def frontmatter(p: Path) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", p.read_text(encoding="utf-8"), re.S)
    assert m, f"{p} has no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    out["modes"] = [x.strip() for x in out.get("modes", "").strip("[]").split(",") if x.strip()]
    return out


def _subparsers(p: argparse.ArgumentParser) -> dict:
    for a in p._actions:                       # argparse keeps subparsers here; no public accessor
        if isinstance(a, argparse._SubParsersAction):
            return a.choices
    return {}


def commands(text: str) -> list:
    """Every `ken ...` command in inline code or a fenced block, continuation lines joined."""
    spans = re.findall(r"```.*?\n(.*?)```", text, re.S) + re.findall(r"`([^`\n]*\bken [^`\n]*)`", text)
    out = []
    for span in spans:
        span = span.replace("\\\n", " ")
        for m in re.finditer(r"(?:^|[\s(])ken ((?:[^\n`|])+)", span):
            out.append(m.group(1).split())
    return out


def check(tokens: list, verbs: dict) -> str:
    """'' when the command parses as far as a doc can say: the verb (and subcommand) exist and
    every --flag is one of that parser's options."""
    if not tokens or tokens[0].startswith(("<", "-")):
        return ""
    verb = tokens[0]
    if verb not in verbs:
        return f"no verb {verb!r}"
    p = verbs[verb]
    if verb in GROUPS and len(tokens) > 1 and not tokens[1].startswith(("<", "-")):
        subs = _subparsers(p)
        if tokens[1] not in subs:
            return f"no subcommand {verb} {tokens[1]!r}"
        p = subs[tokens[1]]
    known = {s for a in p._actions for s in a.option_strings}
    for t in tokens:
        flag = re.match(r"(--[a-z][\w-]*)", t)
        if flag and flag.group(1) not in known:
            return f"{verb}: no option {flag.group(1)}"
    return ""


@pytest.fixture(scope="module")
def verbs():
    return _subparsers(cli.build_parser())


def test_there_is_a_family_and_a_router():
    names = {p.parent.name for p in SKILLS}
    assert {"ken-tutor", "ken-place", "ken-climb", "ken-dialogue", "ken-drill", "ken-exam",
            "ken-scout", "ken-branch"} <= names


def test_the_climb_skill_stays_short():
    """A gap came from one skill carrying one method for everything; the merged skill must not
    grow back into that (a line cap)."""
    assert len((ROOT / "skills" / "ken-climb" / "SKILL.md").read_text(encoding="utf-8").splitlines()) <= 70


@pytest.mark.parametrize("path", SKILLS + CONTRACTS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_every_command_a_skill_tells_the_tutor_to_run_exists(path, verbs):
    cmds = commands(path.read_text(encoding="utf-8"))
    bad = [(" ".join(c[:6]), why) for c in cmds if (why := check(c, verbs))]
    assert not bad, bad


def test_the_command_check_catches_a_wrong_verb_flag_and_subcommand(verbs):
    assert check(["record", "<t>", "<c>", "ok", "--mode", "teach"], verbs) == ""
    assert check(["recrod", "x"], verbs).startswith("no verb")
    assert check(["record", "x", "--modee", "teach"], verbs) == "record: no option --modee"
    assert check(["cert", "passd", "x"], verbs).startswith("no subcommand")


def test_every_record_mode_has_exactly_one_owning_skill():
    owners: dict = {}
    for p in SKILLS:
        fm = frontmatter(p)
        assert fm.get("name") == p.parent.name and fm.get("description"), p
        for m in fm["modes"]:
            assert m in L.MODES, f"{p.parent.name} claims mode {m!r}, which the record does not have"
            owners.setdefault(m, []).append(p.parent.name)
    assert {m: o for m, o in owners.items() if len(o) != 1} == {}, "a mode with two owners"
    assert set(L.MODES) - set(owners) == set(), "a record mode no skill owns"


def test_the_router_names_every_family_skill():
    router = (ROOT / "skills" / "ken-tutor" / "SKILL.md").read_text(encoding="utf-8")
    missing = [p.parent.name for p in SKILLS if p.parent.name != "ken-tutor" and p.parent.name not in router]
    assert missing == []
