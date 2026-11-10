"""Reviews, dates and graduation evidence; misconceptions and calibration views.

Split out of core/learn.py; `learn` re-exports every name, so `L.<name>` still
works for callers. Kernel names are reached through `L.` so the kernel stays the one home of the
record and its rules."""
from __future__ import annotations

from collections import Counter

from . import home as H
from . import learn as L
from .errors import (
    NOT_EVALUABLE,
    OK,
    Drifted,
    NotEvaluable,
    UsageError,
)


def suspects(cfg, slug, state=None, rows=None) -> dict:
    """{whole: (piece, date)}: a whole (a `part-of` target) is SUSPECT when one of its pieces was
    last answered wrong after the whole's latest unaided correct answer. A broken piece casts doubt
    on the whole it makes up. Read from the log, so nothing is stored and nothing is revoked: the
    whole is reviewed sooner and cannot graduate until the piece is answered right again."""
    state = state or L.load_state(cfg, slug)
    rows = L.read_log(cfg, slug)[0] if rows is None else rows
    cons = state["concepts"]
    last, last_ok = {}, {}
    for r in sorted(rows, key=lambda r: r["date"]):
        f = L.facets(r)
        if f["massed"] or f["dialogue"] or f["taught"] or f["predicted"]:
            continue                       # a read-through or a dialogue is not an answer
        last[r["concept"]] = (r["date"], f["ok"])
        if f["unaided_ok"]:
            last_ok[r["concept"]] = r["date"]
    out = {}
    for pid, c in cons.items():
        whole = c.get("part_of")
        if not whole or whole == pid or whole not in cons or whole not in last_ok:
            continue
        day, ok = last.get(pid, ("", True))
        if not ok and day >= last_ok[whole] and (whole not in out or day > out[whole][1]):
            out[whole] = (pid, day)
    return out


def due_list(cfg, slug, today=None) -> list:
    """Concepts due for review, earliest first; then any SUSPECT whole (a piece of it broke since
    you last got it right) not already due, marked `suspect`: it is reviewed now, while its stored
    schedule is left as replay derives it."""
    today = today or H.today()
    state = L.load_state(cfg, slug)
    rows = [(cid, c) for cid, c in state["concepts"].items()
            if (c.get("attempts") and (not c.get("due") or c["due"] <= today.isoformat()))
            or (c.get("taught") and c.get("due") and c["due"] <= today.isoformat())]   # first cold recall (#22)
    rows.sort(key=lambda x: (x[1].get("due") or "", x[0]))
    listed = {cid for cid, _c in rows}
    for whole, (piece, day) in sorted(suspects(cfg, slug, state).items()):
        if whole not in listed:
            rows.append((whole, dict(state["concepts"][whole], suspect=[piece, day])))
    return rows


def due(cfg, slug=None, limit=20, lane=None) -> int:
    code = OK
    if not slug and not L.topics(cfg):
        print(f"NOT EVALUABLE nothing to review: 0 topic(s) in {cfg.home}; "
              "an empty home has no reviews due, which is not the same as none being due")
        return NOT_EVALUABLE
    if slug and lane:
        raise UsageError("give a topic or --lane, not both")
    if not slug:
        for t in L.topics(cfg):
            if L.off_schedule(cfg, t) and (lane is None or L.lane_of(cfg, t) == lane):
                print(f"{t}: complete (exam passed {L.passed_on(cfg, t)}), off the schedule; "
                      f"`{H.PROG} due {t}` still reviews it")
    for t in ([slug] if slug else L.scheduled_topics(cfg, lane)):
        rows = due_list(cfg, t)
        shown = rows[:limit] if limit else rows
        print(f"{t}: {len(rows)} due" + (f" (~{2 * len(rows)} min)" if rows else ""))
        for cid, c in shown:
            why = (f"  suspect: its piece {c['suspect'][0]} was answered wrong on {c['suspect'][1]}"
                   if c.get("suspect") else "")
            print(f"  {cid}  due {c.get('due') or 'unscheduled'}  [{L.badge(c)}]{why}")
        if len(rows) > len(shown):
            print(f"  … {len(rows) - len(shown)} more held back by --limit {limit}")
        code = max(code, L.log_verdict(cfg, t))
    return code


def breadth_ok(c) -> bool:
    bt = c.get("by_type") or {}
    if not bt:
        return False            # no typed attempts: breadth was never tested, so it has not passed
    return sum(1 for v in bt.values() if v["attempts"] and v["correct"] / v["attempts"] >= L.BREADTH_RATE) >= L.BREADTH_TYPES


def interference_ok(rows, cid) -> bool:
    """A first-look unaided correct on a day when >= 3 other concepts were also studied. "Studied"
    means an attempt at retrieval, right or wrong, hinted or a guess: a read-through (learn mode)
    or a dialogue retrieves nothing, so it cannot make a session mixed."""
    rows = sorted(rows, key=lambda r: r["date"])
    by_day: dict = {}
    for r in rows:
        f = L.facets(r)
        if not (f["massed"] or f["dialogue"] or f["taught"] or f["predicted"]):
            by_day.setdefault(r["date"], set()).add(r["concept"])
    return any(r["concept"] == cid and not rep and L.facets(r)["unaided_ok"]
               and len(by_day.get(r["date"], set()) - {cid}) >= L.INTERFERENCE_OTHERS
               for r, rep in zip(rows, L.repeats(rows)))


def graduation_evidence(cfg, slug) -> dict:
    """Which mastered concepts passed every evidence gate (retention, breadth, interference),
    from a VALIDATED view only: it refuses (never answers for a subset) when the log was not
    read in full or the cached mastery disagrees with a full replay. What the evidence may be
    used for (a facts.md line) is the career sidecar's business."""
    state = L.load_state(cfg, slug)
    rows, _p = L.read_log(cfg, slug)
    drifted, problems = L.audit(cfg, slug, state)
    if problems:
        raise NotEvaluable(f"{slug}: {len(problems)} log problem(s) (first: {problems[0]}); the record was not read "
                           f"in full, so no graduation is offered; fix the log, then `{H.PROG} rebuild {slug}`")
    if drifted:
        raise Drifted(f"{slug}: {len(drifted)} concept(s) disagree with the log ({', '.join(drifted[:5])}); "
                      f"mastery is stale, so no graduation is offered; run `{H.PROG} rebuild {slug}`")
    out = {"passed": [], "suspect": [], "not retained": [], "not breadth-tested": [], "drilled solo": []}
    broken = suspects(cfg, slug, state, rows)
    for cid, c in state["concepts"].items():
        if L.badge(c) != "mastered":
            continue
        if cid in broken:
            out["suspect"].append(cid)
        elif len(c.get("correct_days", [])) < L.RETENTION_DAYS:
            out["not retained"].append(cid)
        elif not breadth_ok(c):
            out["not breadth-tested"].append(cid)
        elif not interference_ok(rows, cid):
            out["drilled solo"].append(cid)
        else:
            out["passed"].append(cid)
    return out


WHY = {"suspect": "a piece of it was answered wrong since you last got it right: answer the piece again",
       "not retained": f"correct on fewer than {L.RETENTION_DAYS} separate days",
       "not breadth-tested": f"fewer than {L.BREADTH_TYPES} question types at {int(L.BREADTH_RATE * 100)}%+ "
                             "(record --qtype)",
       "drilled solo": f"never answered unaided on a day when {L.INTERFERENCE_OTHERS}+ other concepts were also studied"}


def misconceptions(cfg, slug) -> int:
    state = L.load_state(cfg, slug)
    typed = Counter()
    for cid, c in state["concepts"].items():
        sigs = Counter(L.signature(e) for _i, e in L.open_errors(c))
        for s, k in sigs.items():
            if k >= 2:
                print(f"ACTIVE  {cid}: {s!r} x{k}")
        et = L.dominant_etype(c)
        if et:
            print(f"RECURRING {cid}: {et}; {L.REASK[et]}")
        typed.update(L.etype_of(e) for _i, e in L.open_errors(c) if L.etype_of(e))
    total = sum(typed.values())
    if total >= 3:
        top = max(typed.values())
        tied = sorted(k for k, v in typed.items() if v == top)
        if top / total >= 0.5 and len(tied) == 1:
            print(f"VERDICT {tied[0]} dominates ({top}/{total} open typed errors): {L.REASK[tied[0]]}")
        elif top / total >= 0.5:
            print(f"VERDICT split between {' and '.join(tied)} ({top}/{total} each):")
            for t in tied:
                print(f"  {t}: {L.REASK[t]}")
        else:
            print(f"no dominant error class ({total} open typed errors spread across {len(typed)} classes)")
    else:
        print(f"{total} open typed error(s): too few for a verdict (needs 3)")
    return L.log_verdict(cfg, slug)


def calibration(cfg, slug) -> int:
    L.need_topic(cfg, slug)
    rows, _p = L.read_log(cfg, slug)
    code = L.log_verdict(cfg, slug)
    acc: dict = {}
    days: Counter = Counter()
    rows = sorted(rows, key=lambda r: r["date"])
    for r, rep in zip(rows, L.repeats(rows)):
        f = L.facets(r)
        if not f["conf"] or f["assisted"] or f["massed"] or f["dialogue"] or f["taught"] or f["predicted"] or rep:
            continue
        days[r["date"]] += 1
        a = acc.setdefault(f["conf"], [0, 0])
        a[0] += 1
        a[1] += f["ok"]
    if not acc:
        print(f"{slug}: no confidence-rated unaided attempts yet: calibration NOT EVALUABLE")
        return NOT_EVALUABLE
    total = sum(days.values())
    print(f"{slug}: {total} rated answer(s), first looks only, on {len(days)} day(s)")
    for lvl in L.CONFIDENCE:
        if lvl in acc:
            n, k = acc[lvl]
            print(f"  {lvl:5} {k}/{n} correct ({100 * k / n:.0f}%)")
    day, most = days.most_common(1)[0]
    if total >= 4 and most / total >= 0.5:
        print(f"note: {most} of {total} came from one day ({day}): the figure says as much about that session "
              "as about you")
    if "high" in acc and acc["high"][1] / acc["high"][0] < 0.8:
        print("OVERCONFIDENT: high-confidence answers are right less than 80% of the time")
    if "low" in acc and acc["low"][1] / acc["low"][0] > 0.8:
        print("UNDERCONFIDENT: low-confidence answers are right more than 80% of the time")
    return code
