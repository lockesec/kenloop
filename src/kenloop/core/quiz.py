"""Selection and quizzing: which concepts to ask, the quiz, the interactive session and its hints.

Split out of core/learn.py; `learn` re-exports every name, so `L.<name>` still
works for callers. Kernel names are reached through `L.` so the kernel stays the one home of the
record and its rules."""
from __future__ import annotations

import random
import sys
from collections import Counter

from . import home as H
from . import learn as L
from .errors import (
    DRIFT,
    NOT_EVALUABLE,
    OK,
    NotEvaluable,
)


def confident_misses(c) -> int:
    b = (c.get("by_conf") or {}).get("high", {})
    return b.get("attempts", 0) - b.get("correct", 0)


def select(state, n=5, weak=False, concept=None, bank_=None, waiting=(), seen_today=()) -> list:
    """The concepts a quiz asks, best first. With the bank: a concept `due` names (reviewed before,
    due today or earlier) and with a banked question comes first, then any concept with a banked
    question, then the rest; within each, confident misses, low streaks and open errors first.
    A concept already answered today waits until tomorrow (`seen_today`): a second answer the same
    day is counted but never credited, so asking it again spends the learner's time on nothing.
    Naming a concept asks it regardless."""
    cons = state["concepts"]
    if concept:
        return [L.resolve_concept(state, concept)]
    today = H.today().isoformat()

    def tier(cid):
        if bank_ is None:
            return 0
        c, banked = cons[cid], bool(bank_.get(cid))
        due = bool(c.get("attempts")) and (not c.get("due") or c["due"] <= today)
        return 0 if (due and banked) else 1 if banked else 2
    # within a tier, a concept the study graph says waits (its pieces, what comes before it, or a
    # lower ladder rung not climbed yet) comes after the ready ones: it is asked, never hidden
    order = sorted((cid for cid in cons if cid not in seen_today), key=lambda cid: (tier(cid), cid in waiting, -confident_misses(cons[cid]),
                                          cons[cid].get("streak", 0),
                                          -len(L.open_errors(cons[cid])), cons[cid].get("last_seen", ""), cid))
    if weak:
        w = [cid for cid in order if L.badge(cons[cid]) in ("new", "weak", "fair")]
        order = w or order
    return order[:n]


def seen_today(cfg, slug) -> set:
    """Concepts with a row on the log dated today: any further answer today is a repeat."""
    today = H.today().isoformat()
    held = {r["concept"] for r in L.read_log(cfg, slug)[0] if r["date"] == today}
    for cid, c in L.load_state(cfg, slug)["concepts"].items():
        if cid not in held and c.get("same") and L.twin_seen(cfg, slug, cid, today):
            held.add(cid)
    return held


def _held_line(state, held, concept) -> str:
    held = sorted(c for c in held if c in state["concepts"])
    if concept or not held:
        return ""
    return (f"held until tomorrow: {len(held)} concept(s) already answered today (a second answer "
            f"today is counted, never credited): {', '.join(held[:6])}{' ...' if len(held) > 6 else ''}")


def _waiting(cfg, slug) -> set:
    """Concepts the study graph says wait on something not yet climbed (core/graph.py)."""
    from . import graph as SG             # graph reads learn: imported here, not at module load
    g = SG.build(cfg, slug)
    return {k for k, n in g.nodes.items() if not n.climbed and SG.waits(g, n)}


def pick_question(bank_, cid, c):
    qs = bank_.get(cid, [])
    return (qs[c.get("attempts", 0) % len(qs)], c.get("attempts", 0) % len(qs)) if qs else (None, -1)


def dominant_etype(c):
    cnt = Counter(L.etype_of(e) or "other" for _i, e in L.open_errors(c))
    if not cnt:
        return None
    top = max(cnt.values())
    return sorted(k for k, v in cnt.items() if v == top)[0] if top >= 2 else None


def log_verdict(cfg, slug, state=None) -> int:
    """The integrity line every display ends on. The views (`due`, `quiz`, `mastery`, `board`, ...)
    print from the derived concepts.json, so what they showed is only as good as its agreement with
    the log: OK when the log reads in full and a replay matches; a damaged log row warns and exits
    2 (the record was not read in full); drift warns and exits 3, as `rebuild --check` would. They
    still print first: a learner with a damaged file can see what they hold, and is told it."""
    drifted, problems = L.audit(cfg, slug, state)
    if problems:
        H.warn(f"{slug}: {len(problems)} damaged log row(s): what was shown was derived without them and may "
               f"not match the record; run `{H.PROG} validate {slug}` or `rebuild {slug} --check`")
        return NOT_EVALUABLE
    if drifted:
        H.warn(f"{slug}: DRIFT: {len(drifted)} concept(s) shown disagree with the log "
               f"({', '.join(drifted[:5])}{', ...' if len(drifted) > 5 else ''}); `{H.PROG} rebuild {slug}`")
        return DRIFT
    return OK


def quiz(cfg, slug, n=5, weak=False, concept=None) -> int:
    state = L.load_state(cfg, slug)
    if not state["concepts"]:
        raise NotEvaluable(f"{slug} has no concepts yet: add them to syllabus.md and run `{H.PROG} sync {slug}`")
    bank_ = L.load_bank(cfg, slug)
    held = seen_today(cfg, slug)
    picked = select(state, n, weak, concept, bank_, _waiting(cfg, slug), held)
    for cid in picked:
        c = state["concepts"][cid]
        q, _i = pick_question(bank_, cid, c)
        print(f"- {cid} [{L.badge(c)}]" + (f"  Q: {q['q']}" if q else "  (no banked question)"))
        et = dominant_etype(c)
        if et:
            last = L.open_errors(c)[-1][1]
            print(f"    recurring {et}: {L.REASK[et]}  (last: {last})")
    line = _held_line(state, held, concept)
    if line:
        print(line)
    if picked:
        print(f"record each: {H.PROG} record {slug} <concept> ok|partial|miss [--confidence L] [--qtype T]")
    else:
        print(f"nothing left to ask in {slug} today; `{H.PROG} quiz {slug} --concept ID` asks one anyway")
    return log_verdict(cfg, slug)


class _Quit(Exception):
    pass


def _ask(prompt, inp, out):
    out.write(prompt)
    out.flush()
    try:
        line = inp.readline()
    except UnicodeDecodeError as e:
        raise NotEvaluable(f"the input is not valid UTF-8 ({e.reason} at offset {e.start}); answers already "
                           "given are on the log") from e
    if not line:
        raise _Quit
    line = line.strip()
    if line.lower() == "q":
        raise _Quit
    return line


def quiz_interactive(cfg, slug, n=5, weak=False, concept=None, inp=None, out=None) -> int:
    """Ask, hint on request, take confidence BEFORE revealing, reveal, grade,
    record through the same path as `record`. EOF or `q` ends the
    session; every answered item is already on the log."""
    inp, out = inp or sys.stdin, out or sys.stdout
    state = L.load_state(cfg, slug)
    if not state["concepts"]:
        raise NotEvaluable(f"{slug} has no concepts yet")
    bank_ = L.load_bank(cfg, slug)
    done = 0
    held = seen_today(cfg, slug)
    line = _held_line(state, held, concept)
    if line:
        out.write(line + "\n")
    try:
        for cid in select(state, n, weak, concept, bank_, _waiting(cfg, slug), held):
            state = L.load_state(cfg, slug)
            c = state["concepts"][cid]
            q, qi = pick_question(bank_, cid, c)
            if q is None:
                out.write(f"\n{cid}: no banked question; skipped (bank one with `{H.PROG} bank`)\n")
                continue
            out.write(f"\n[{L.badge(c)}] {c.get('name', cid)}\nQ: {q['q']}\n")
            options = None
            if q["d"]:
                options = [(q["a"], None)] + [(o, m) for o, m in q["d"][:7]]
                random.Random(f"{slug}|{cid}|{qi}|{c.get('attempts', 0)}").shuffle(options)
                for i, (o, _m) in enumerate(options):
                    out.write(f"  {'abcdefgh'[i]}) {o}\n")
            rung, answer = 0, None
            while answer is None:
                a = _ask("answer (? for a hint, q to stop)> ", inp, out)
                if a == "?":
                    rung += 1
                    out.write(_hint(state, cid, q, rung) + "\n")
                    if rung >= 4:
                        answer = ""
                elif options and (len(a) != 1 or a.lower() not in "abcdefgh"[:len(options)]):
                    out.write(f"  pick a letter a-{'abcdefgh'[len(options) - 1]}\n")
                else:
                    answer = a
            conf = ""
            if rung < 4:
                cl = _ask("confidence [l/m/h, enter = unstated]> ", inp, out).lower()
                conf = {"l": "low", "m": "med", "h": "high"}.get(cl, "")
            out.write(f"A: {q['a']}\n" + (f"Why: {q['why']}\n" if q["why"] else "") + f"Ref: {q['ref']}\n")
            note, etype = "", ""
            if options and rung < 4:
                picked = options["abcdefgh".index(answer.lower())]
                result = "ok" if picked[1] is None else "miss"
                if result == "miss":
                    note = picked[1] or f"chose {picked[0]!r}"
                    out.write(f"  that option encodes: {note}\n")
            else:
                g = ""
                while g not in ("o", "p", "m"):
                    g = _ask("grade yourself [o = ok, p = partial, m = miss]> ", inp, out).lower()
                result = {"o": "ok", "p": "partial", "m": "miss"}[g]
            stop = False
            try:                               # optional detail: stopping here must not lose the attempt
                if result != "ok" and not (options and rung < 4):
                    note = _ask("what went wrong (enter to skip)> ", inp, out)
                if result != "ok":
                    out.write("  " + "  ".join(f"{i + 1}={e}" for i, e in enumerate(L.ETYPES)) + "\n")
                    e = _ask("error type [1-6, enter = skip]> ", inp, out)
                    if e.isdigit() and 1 <= int(e) <= len(L.ETYPES):
                        etype = L.ETYPES[int(e) - 1]
            except _Quit:
                stop = True
            qtype = q["type"] if q["type"] in L.QTYPES else ""
            row = L.record(cfg, slug, cid, result, note=note, confidence=conf,
                         hint_depth=min(rung, 4), qtype=qtype, etype=etype, quiet=True)
            out.write(f"  recorded {row['result']}" + (f" (hint depth {row['hint_depth']})" if row["hint_depth"] else "") + "\n")
            done += 1
            if stop:
                raise _Quit
    except _Quit:
        pass
    out.write(f"\n{done} item(s) recorded\n")
    return log_verdict(cfg, slug)


def _hint(state, cid, q, rung) -> str:
    c = state["concepts"][cid]
    if rung == 1:
        sib = [x.get("name") for k, x in state["concepts"].items()
               if k != cid and c.get("cluster") and x.get("cluster") == c.get("cluster")]
        return f"  hint 1: domain {c.get('domain', '-')}" + (f"; related to {', '.join(sib)}" if sib else "")
    if rung == 2:
        return f"  hint 2: {c.get('desc') or '(no description in the syllabus)'}"
    if rung == 3:
        return f"  hint 3: {q['why'] or '(no Why line banked)'}"
    return f"  answer: {q['a']}"
