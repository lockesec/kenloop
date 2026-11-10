"""Height: where an idea stands on the learner's pyramid, read from the record.

The pyramid (cognitive apprenticeship): at the base the tutor explains at length and the learner
interrupts; each step up the learner does more of the work, until the learner teaches it and the
tutor only probes. Height steers the conversation; it never moves credit, and it is never set or
felt: only unaided recall raises it, and a recall that misses steps it down one.

Height is per idea and per DEPTH (exam < mechanism < first-principles). The depth rule: an unaided
correct answer at depth D is evidence for every depth at or below D; a miss at D is evidence
against every depth at or above D. So an exam-level miss breaks all three; a first-principles miss
leaves exam-level standing alone.

  0 new      nothing recorded on the idea
  1 heard    taught, guessed, read through or answered with help, but no unaided recall holding
  2 held     an unaided recall is holding (or one step down from carried after a miss)
  3 carried  two or more unaided recalls in a row, spanning a week or more

The idea's record is its own topic's rows plus its twins' (a shared `:: same:` key): one idea,
one height. Reading twins here moves no credit; each topic's state still comes from its own log.
"""
from __future__ import annotations

import datetime as _dt

from . import learn as L

LEVELS = ("new", "heard", "held", "carried")
DEPTH_ORDER = {d: i for i, d in enumerate(L.DEPTHS)}
CARRIED_STREAK, CARRIED_SPAN_DAYS = 2, 7
NOT_RECALL = ("teach", "predict", "learn", "dialogue")


def idea_rows(cfg, slug, cid) -> list:
    """The idea's rows across its twins, by date (stable: each log keeps its own order)."""
    rows = [r for r in L.read_log(cfg, slug)[0] if r["concept"] == cid]
    for t, k, _n, _b in L.twins(cfg, slug, cid):
        rows += [{**r, "concept": cid} for r in L.read_log(cfg, t)[0] if r["concept"] == k]
    return sorted(rows, key=lambda r: r["date"])


def height_of(rows, depth: str) -> tuple:
    """(level 0-3, why) at `depth` from the idea's rows in order."""
    want = DEPTH_ORDER[depth]
    h, streak, days, why = 0, 0, [], "nothing recorded yet"
    reps = L.repeats(rows)
    if len(reps) != len(rows):  # what zip(strict=True) guaranteed; that needs 3.10, we support 3.9
        raise ValueError(f"repeats() returned {len(reps)} flags for {len(rows)} rows")
    for r, rep in zip(rows, reps):
        f = L.facets(r)
        q = DEPTH_ORDER[f["qdepth"]]
        if r.get("mode") in NOT_RECALL or (rep and f["ok"]):
            if h == 0:
                h, why = 1, f"{r.get('mode') or 'answered'} on {r['date']}, no unaided recall yet"
            continue
        if f["unaided_ok"]:
            if q < want:
                h = max(h, 1)
                continue              # a shallower answer says nothing about this depth
            streak += 1
            days.append(r["date"])
            span = (_dt.date.fromisoformat(days[-1]) - _dt.date.fromisoformat(days[0])).days
            up = 3 if streak >= CARRIED_STREAK and span >= CARRIED_SPAN_DAYS else 2
            if up >= h:
                h = up
                why = (f"{streak} unaided recall(s) in a row over {span} day(s), last {r['date']}" if up == 3
                       else f"unaided recall on {r['date']} holding" + (f" ({streak} in a row)" if streak > 1 else ""))
        else:
            if q > want:
                h = max(h, 1)
                continue              # a deeper miss says nothing against this depth
            streak, days = 0, []
            h = max(1, h - 1)
            why = f"{r.get('result', 'miss')} on {r['date']} ({r.get('depth') or f['qdepth']} question); stepped down"
    return h, why


def height(cfg, slug, cid, depth=None) -> tuple:
    """(level, label, why, depth) for one concept, at its resolved depth unless one is given."""
    c = L.load_state(cfg, slug)["concepts"][cid]
    d = depth or L.question_depth(cfg, slug, c, "practice")
    n, why = height_of(idea_rows(cfg, slug, cid), d)
    return n, LEVELS[n], why, d
