"""Certs sidecar: a topic studied toward an exam. An exam date makes reviews land before it.

The core schedules with the date (topic.json `exam_date`, read during replay, so a date change
re-derives every schedule from the log); this sets, clears and shows it.
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
        conf["exam_date"] = d.isoformat()
        conf["outlets"] = list(dict.fromkeys([*conf.get("outlets", []), "cert"]))
    elif clear:
        conf.pop("exam_date", None)
        conf["outlets"] = [o for o in conf.get("outlets", []) if o != "cert"]
    else:
        return show_exam(cfg, slug)
    L.save_config(cfg, slug, conf)
    label = f"exam date {conf['exam_date']}" if conf.get("exam_date") else "exam date cleared"
    state, probs = L.replay(cfg, slug, L.load_state(cfg, slug))
    if probs:
        # a replay that skipped rows must not become the stored state (that is what `rebuild --skip-damaged` is for)
        print(f"{slug}: {label}{' and' if clear else ''} saved; schedules NOT re-derived: "
              f"{len(probs)} log problem(s), so the record cannot be read in full")
        return L.log_verdict(cfg, slug)
    L.save_state(cfg, slug, state)
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
