"""Graduation into facts.md: the core says which concepts passed every evidence gate; this
says which of those may be written as a held line, prints the line, and proves the printed
block reads back as held before printing it. Nothing here writes facts.md: the owner pastes.
"""
from __future__ import annotations

import re

from ..core import home as H
from ..core import learn as L
from ..core.errors import OK, NotEvaluable
from ..core.learn import (
    BREADTH_RATE,
    BREADTH_TYPES,
    INTERFERENCE_OTHERS,
    RETENTION_DAYS,
)
from . import facts as F
from . import promote as PR

EMIT_SUFFIX = " (held knowledge from study; a knowledge claim, separate from work claims)"


def emit_line(name) -> str:
    return f"- {name}{EMIT_SUFFIX}"


def emit_problem(name) -> str:
    """Why the line `--emit` would print for `name` could not pass the claim gate
    ("" when it can): it must read back as held, with no qualifier, from a
    sheet that holds nothing else."""
    sheet = F.analyse("## Held\n" + emit_line(name))
    bad = [b for b in sheet.blocks if b.held and not b.heading and b.qualified]
    if bad:
        return f"it would read as qualified ({bad[0].why})"
    if not F.holds(name, "## Held\n" + emit_line(name)):
        return "it would not read back as held (markup such as ~~ or <!-- in the name)"
    return ""


def _comment_safe(text) -> str:
    """Text for inside an HTML comment: no `--`, so no early `-->` and no nested `<!--`."""
    return re.sub(r"-{2,}", "-", re.sub(r"\s+", " ", str(text))).replace("<!-", "<!").strip()


def graduation(cfg, slug) -> dict:
    """Candidates for facts.md: concepts that passed every evidence gate, are not held yet and
    can be written as a line that passes the claim gate. Refuses like the evidence does."""
    ev = L.graduation_evidence(cfg, slug)
    state = L.load_state(cfg, slug)
    facts = F.read(cfg)
    out = {"candidates": [], "held": [], "unwritable": [], "not promoted": [],
           **{k: v for k, v in ev.items() if k != "passed"}}
    if not L.has_outlet(L.load_config(cfg, slug), "career"):   # interest topic: promoted concepts only
        ok = PR.promoted(cfg, slug)
        out["not promoted"] = [c for c in ev["passed"] if c not in ok]
        ev = {**ev, "passed": [c for c in ev["passed"] if c in ok]}
        for k in ("suspect", "not retained", "not breadth-tested", "drilled solo"):
            out[k] = [c for c in out[k] if c in ok]          # an unpromoted concept is not held back: it is interest
    for cid in ev["passed"]:
        c = state["concepts"][cid]
        if F.holds(c.get("name", ""), facts):
            out["held"].append(cid)
        elif emit_problem(c.get("name", cid)):
            out["unwritable"].append(cid)        # would fail the claim gate once pasted: never a candidate
        else:
            out["candidates"].append(cid)
    return out


WHY = {"suspect": "a piece of it was answered wrong since you last got it right: answer the piece again",
       "not retained": f"correct on fewer than {RETENTION_DAYS} separate days",
       "not breadth-tested": f"fewer than {BREADTH_TYPES} question types at {int(BREADTH_RATE * 100)}%+ "
                             "(record --qtype)",
       "drilled solo": f"never answered unaided on a day when {INTERFERENCE_OTHERS}+ other concepts were also studied"}


def evidence(c: dict, banked: bool) -> str:
    """One line of what the record holds for a concept, so inflation is visible where you paste."""
    days = c.get("correct_days") or []
    types = sorted(k for k, v in (c.get("by_type") or {}).items() if v.get("correct"))
    parts = [f"right unaided on {len(days)} day(s) ({', '.join(days)})",
             f"types {', '.join(types) or 'none'}",
             f"{c.get('attempts', 0)} attempt(s)"]
    for key, label in (("repeats", "same-day repeat(s)"), ("hints", "hinted"), ("guesses", "guessed")):
        if c.get(key):
            parts.append(f"{c[key]} {label}")
    parts.append("from banked questions" if banked else "no banked question: asked off the record")
    return "; ".join(parts)


def graduate(cfg, slug, emit=False) -> int:
    if not L.has_outlet(L.load_config(cfg, slug), "career") and not PR.promoted(cfg, slug):
        msg = (f"{slug} has no career outlet and no promoted concept: what you master here is for you, and nothing "
               f"graduates into facts.md (`{H.PROG} jobs promote {slug} CONCEPT --why ...` puts one concept forward; "
               f"`{H.PROG} plan {slug} --career --force` makes the whole topic career)")
        print(f"<!-- {msg} -->" if emit else msg)
        return OK
    g = graduation(cfg, slug)
    state = L.load_state(cfg, slug)
    conf = L.load_config(cfg, slug)
    bank = L.load_bank(cfg, slug)

    def ledger(cid):
        return evidence(state["concepts"][cid], bool(bank.get(cid)))
    if emit:
        # Lines only, no heading of their own: the owner pastes them under `## Held`,
        # and the topic title goes in a comment so its words never become held claims.
        for cid in g["unwritable"]:
            name = state["concepts"][cid].get("name", cid)
            H.warn(f"not emitted: {name!r} is mastered but {emit_problem(name)}; rename the concept in "
                   f"{slug}/syllabus.md, then run graduate again")
        if not g["candidates"]:
            print(f"<!-- {slug}: no graduation candidates -->")
            return OK
        for cid in g["candidates"]:          # on stderr: seen at the paste, never pasted
            H.warn(f"evidence {cid}: {ledger(cid)}")
        names = [state["concepts"][c].get("name", c) for c in g["candidates"]]
        names.sort()
        lines = [emit_line(n) for n in names]
        head = (f"<!-- paste the lines below under `## Held` in facts.md: "
                f"`{H.PROG} jobs graduate {slug} --emit` @ {H.today()}: "
                f"{_comment_safe(conf.get('title', slug))}; {len(lines)} retained-mastered -->")
        block = "\n".join([head, *lines])
        # the block must pass its own gate, or nothing is printed
        sheet = "## Held\n" + block
        got = F.analyse(sheet)
        if (got.unclosed or F.contradiction_blocks(sheet) or not all(F.holds(n, sheet) for n in names)
                or len([b for b in got.blocks if b.held and not b.heading]) != len(lines)):
            raise NotEvaluable(f"{slug}: the emitted block would not read back as held; refusing to print it")
        print(block)
        return OK
    print(f"## Ready for facts.md ({len(g['candidates'])})")
    for cid in g["candidates"]:
        print(f"  {cid}")
        print(f"      {ledger(cid)}")
    if g["held"]:
        print(f"## Already held in facts.md ({len(g['held'])})")
        for cid in g["held"]:
            print(f"  {cid}")
    if g["unwritable"]:
        print(f"## Mastered but cannot be written to facts.md ({len(g['unwritable'])}): rename the concept in the syllabus")
        for cid in g["unwritable"]:
            print(f"  {cid}: {emit_problem(state['concepts'][cid].get('name', cid))}")
    if g["not promoted"]:
        print(f"## Mastered, interest only ({len(g['not promoted'])}): not promoted "
              f"(`{H.PROG} jobs promote {slug} CONCEPT --why ...` if a job needs it)")
        for cid in g["not promoted"]:
            print(f"  {cid}")
    for k in ("suspect", "not retained", "not breadth-tested", "drilled solo"):
        if g[k]:
            print(f"## Mastered but held back: {k} ({len(g[k])}): {WHY[k]}")
            for cid in g[k]:
                print(f"  {cid}")
    if g["candidates"]:
        print(f"paste `{H.PROG} jobs graduate {slug} --emit` under ## Held in facts.md yourself; nothing writes it for you")
    return OK


def _words(text: str) -> set:
    return {w.rstrip("s") for w in re.findall(r"[a-z]{4,}", text.lower())}


def held_vs_study(cfg, facts: str) -> list:
    """Warnings for `## Held` lines your study record contradicts. Held is your assertion and
    may come from work, so these never fail anything; they say what the record shows:
    - a concept of a career topic, held but not mastered: not earned by study yet;
    - a line about a topic with no career outlet: that is study for its own sake, and facts.md
      is your resume source."""
    blocks = [b for b in F.analyse(facts).blocks if b.held and not b.heading]
    out = []
    for t in L.topics(cfg):
        try:
            conf, cons = L.load_config(cfg, t), L.load_state(cfg, t)["concepts"]
        except NotEvaluable:
            continue                                   # a damaged topic is reported elsewhere
        career = L.has_outlet(conf, "career")
        try:
            ok = PR.promoted(cfg, t)
        except NotEvaluable:
            ok = set()
        title = _words(f"{conf.get('title', '')} {t.replace('-', ' ')}")
        for b in blocks:
            text = b.text.lstrip("-*+ ").strip()
            named = [cid for cid, c in cons.items() if c.get("name") and F.holds(c["name"], f"## Held\n- {text}")]
            if career:
                for cid in named:
                    if L.badge(cons[cid]) != "mastered":
                        out.append(f"facts.md line {b.line} holds {cons[cid]['name']!r}, but {t}/{cid} is "
                                   f"{L.badge(cons[cid])}: not earned by study yet (fine if it comes from work)")
            elif named and all(cid in ok for cid in named):
                continue                               # a promoted interest concept: the recorded route
            elif named or len(_words(text) & title) >= 2:
                out.append(f"facts.md line {b.line} ({text[:50]!r}) matches {t}, a topic studied for its own "
                           "sake: facts.md is your resume source, and what you learn for yourself stays in the "
                           f"study record (`{H.PROG} mastery {t}`)")
    return out

