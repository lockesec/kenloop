"""Certs sidecar: a topic studied toward an exam. An exam date makes reviews land before it.

The core schedules with the date (topic.json `exam_date`, read during replay, so a date change
re-derives every schedule from the log); this sets, clears and shows it.

A passed exam is a credential, not a studied concept: `jobs graduate` only emits concepts that
passed the study gates, so without `passed` an earned cert had no route into facts.md but a
hand edit. `passed` records the date (topic.json `passed`) and prints the held line; like every
facts.md line, the owner pastes it - nothing here writes facts.md.
"""
from __future__ import annotations

import datetime as _dt

from .core import fsrs
from .core import home as H
from .core import learn as L
from .core.errors import NOT_EVALUABLE, OK, NotEvaluable, UsageError


def set_exam_date(cfg, slug, set_=None, clear=False) -> int:
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    if set_:
        try:
            d = H.iso_date(set_)
        except ValueError as e:
            raise UsageError(f"--set {set_!r} is not YYYY-MM-DD") from e
        if d <= H.today():
            raise UsageError(f"--set {set_} is not in the future")
        L.set_key(conf, "deadline", d.isoformat())
        conf["outlets"] = list(dict.fromkeys([*conf.get("outlets", []), "cert"]))
    elif clear:
        L.set_key(conf, "deadline", None)
        conf["outlets"] = [o for o in conf.get("outlets", []) if o != "cert"]
    else:
        return show_exam(cfg, slug)
    L.save_config(cfg, slug, conf)
    label = f"exam date {L.get_key(conf, 'deadline')}" if L.get_key(conf, "deadline") else "exam date cleared"
    probs = L.rederive(cfg, slug)
    if probs:
        print(f"{slug}: {label}{' and' if clear else ''} saved; schedules NOT re-derived: "
              f"{len(probs)} log problem(s), so the record cannot be read in full")
        return L.log_verdict(cfg, slug)
    print(f"{slug}: {label}; schedules re-derived from the log")
    return OK


def show_exam(cfg, slug) -> int:
    conf = L.load_config(cfg, slug)
    ex = L.exam_date(conf)
    if ex is None:
        print(f"{slug}: no exam date (set one with --set YYYY-MM-DD)")
        return L.log_verdict(cfg, slug)
    state = L.load_state(cfg, slug)
    cons = [(cid, c) for cid, c in state["concepts"].items() if c.get("scope", "exam") == "exam"]
    if not cons:
        raise NotEvaluable(f"{slug} has no exam-scope concepts: exam readiness cannot be judged")
    print(f"{slug}: exam {ex} ({(ex - H.today()).days} days)")
    for cid, c in cons:
        if not c.get("stability"):
            print(f"  {cid}: not studied")
            continue
        prev = _dt.date.fromisoformat(c["due"]) - _dt.timedelta(days=c["interval"])
        r = fsrs.retrievability(c["stability"], (ex - prev).days)
        flag = "  STRANDED (due after the exam)" if c["due"] >= ex.isoformat() else ""
        print(f"  {cid}: predicted recall at the exam {r:.2f}" + ("  LOW" if r < 0.7 else "") + flag)
    return L.log_verdict(cfg, slug)


EXAM_PASS = 85      # percent; below it, the misses are the next drill


def exam(cfg, slug, n=20) -> int:
    """A practice exam: n questions drawn across the exam-scope concepts, each domain in
    proportion to its size (largest remainder), least recently seen first, rotating through
    the banked questions. Your assistant asks them all unaided, grades them, and records each
    with --mode exam."""
    cons = {cid: c for cid, c in L.load_state(cfg, slug)["concepts"].items() if c.get("scope", "exam") == "exam"}
    if not cons:
        print(f"NOT EVALUABLE {slug}: no exam-scope concepts, so there is no exam to sit; "
              f"study it with `{H.PROG} quiz {slug}` instead")
        return NOT_EVALUABLE
    bank = L.load_bank(cfg, slug)
    by_dom: dict = {}
    for cid, c in cons.items():
        by_dom.setdefault(c.get("domain", ""), []).append((cid, c))
    raw = {d: n * len(v) / len(cons) for d, v in by_dom.items()}
    alloc = {d: int(r) for d, r in raw.items()}
    for d in sorted(raw, key=lambda d: (-(raw[d] - int(raw[d])), d))[:n - sum(alloc.values())]:
        alloc[d] += 1
    picks = []
    for d in sorted(by_dom):
        pool = sorted(by_dom[d], key=lambda kv: (kv[1].get("last_seen", ""), kv[0]))
        for i in range(alloc[d]):
            cid, c = pool[i % len(pool)]
            qs = bank.get(cid, [])
            picks.append((cid, c, qs[(c.get("attempts", 0) + i) % len(qs)] if qs else None))
    depth = len(L.load_state(cfg, slug)["concepts"]) - len(cons)
    print(f"practice exam: {slug}, {len(picks)} question(s) across {len(by_dom)} domain(s); pass at {EXAM_PASS}%"
          + (f"; {depth} depth-scope concept(s) left out" if depth else ""))
    print("Ask every question unaided, grade them, give the score against the pass mark, then record each:")
    print(f"  {H.PROG} record {slug} CONCEPT ok|partial|miss --mode exam\n")
    for i, (cid, c, q) in enumerate(picks, 1):
        print(f"{i:>3}. [{c.get('domain', '')}] {c.get('name', cid)} ({cid})")
        print(f"       Q: {q['q']}" if q else f"       no banked question: write one from \"{c.get('desc', '')}\"")
    print(f"\nAt {EXAM_PASS}% or more the milestone is met; below it, the misses are the next drill "
          f"(`{H.PROG} quiz {slug} --weak`).")
    return L.log_verdict(cfg, slug)


CREDENTIAL_SUFFIX = "credential"


def credential_line(title: str, on: str) -> str:
    return f"- {title} ({CREDENTIAL_SUFFIX}, passed {on})"


def credential_block(slug: str, title: str, on: str) -> str:
    """The paste block, proved to read back as held (unqualified, title held) before it is returned."""
    from .career import facts as F
    from .career.graduate import _comment_safe
    line = credential_line(title, on)
    head = (f"<!-- paste the line below under `## Held` in facts.md: `{H.PROG} cert passed {slug} --emit` "
            f"@ {H.today()}: exam passed {on} -->")
    block = f"{head}\n{line}"
    sheet = "## Held\n" + block
    got = F.analyse(sheet)
    held = [b for b in got.blocks if b.held and not b.heading]
    if (got.unclosed or F.contradiction_blocks(sheet) or len(held) != 1 or held[0].qualified
            or not F.holds(title, sheet)):
        raise NotEvaluable(f"{slug}: the credential line for {_comment_safe(title)!r} would not read back as held; "
                           "change the topic title, then run again")
    return block


def passed(cfg, slug, on=None, emit=False, clear=False) -> int:
    """Record that the exam was passed (default today) and print the credential line for facts.md.
    A passed topic is complete: `next` and an unnamed `due` leave it out. `--clear` puts it back."""
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    if clear:
        if L.get_key(conf, "complete"):
            L.set_key(conf, "complete", None)
            L.save_config(cfg, slug, conf)
            print(f"{slug}: pass cleared; back on the schedule (a facts.md line you pasted stays until you remove it)"
                  + ("; keep studying stays set, so a later pass keeps it on the schedule too"
                     if conf.get("keep_studying") is True else ""))
        else:
            print(f"{slug}: no pass recorded; nothing to clear")
        return OK
    if not L.has_outlet(conf, "cert"):
        raise UsageError(f"{slug} is not studied toward an exam (no cert outlet); "
                         f"`{H.PROG} cert exam-date {slug} --set YYYY-MM-DD` makes it one")
    title = conf.get("title") or slug
    recorded = L.get_key(conf, "complete")
    if on is None and recorded:
        # Re-running (the plain form suggests `--emit`) restates the pass; only --on moves it.
        try:
            d = H.iso_date(recorded)
        except (TypeError, ValueError) as e:
            raise UsageError(f"{slug}: the recorded pass date {recorded!r} is not YYYY-MM-DD; "
                             f"set it with --on YYYY-MM-DD") from e
    elif on is None:
        d = H.today()
    else:
        try:
            d = H.iso_date(on)
        except ValueError as e:
            raise UsageError(f"--on {on!r} is not YYYY-MM-DD") from e
        if d > H.today():
            raise UsageError(f"--on {on} is in the future: record a pass once it has happened")
    block = credential_block(slug, title, d.isoformat())    # refuse before writing anything
    if L.get_key(conf, "complete") != d.isoformat():
        L.set_key(conf, "complete", d.isoformat())
        L.save_config(cfg, slug, conf)
    if emit:
        print(block)
        return OK
    print(f"{slug}: passed {d.isoformat()} recorded; complete and off the schedule "
          f"(`{H.PROG} due {slug}` still reviews it; `{H.PROG} cert passed {slug} --clear` puts it back)")
    print(f"  {credential_line(title, d.isoformat())}")
    print(f"paste `{H.PROG} cert passed {slug} --emit` under ## Held in facts.md yourself; nothing writes it for you")
    return OK


def commands(groups) -> None:
    from .core import args as A
    c = groups[""].add_parser("cert", help="study toward an exam: practice exams and the exam date")
    cs = c.add_subparsers(dest="verb", required=True, parser_class=A.Parser)
    a = cs.add_parser("exam", help="a practice exam: questions drawn across domains by size")
    a.add_argument("slug")
    a.add_argument("--n", type=A.count, default=20)
    a.set_defaults(run=lambda cfg, ns: exam(cfg, ns.slug, ns.n))
    a = cs.add_parser("passed", help="record a passed exam and print its credential line for facts.md")
    a.add_argument("slug")
    a.add_argument("--on", help="the day you passed, YYYY-MM-DD (default today)")
    a.add_argument("--emit", action="store_true", help="print a block to paste into facts.md")
    a.add_argument("--clear", action="store_true", help="forget the pass: the topic goes back on the schedule")
    a.set_defaults(run=lambda cfg, ns: passed(cfg, ns.slug, ns.on, ns.emit, ns.clear))
    a = cs.add_parser("exam-date", help="show, set or clear a topic's exam date")
    a.add_argument("slug")
    g = a.add_mutually_exclusive_group()
    g.add_argument("--set")
    g.add_argument("--clear", action="store_true")
    a.set_defaults(run=lambda cfg, ns: set_exam_date(cfg, ns.slug, ns.set, ns.clear))
