"""Marks and the trail: how you move around a topic, kept apart from what you can answer.

`ken mark TOPIC CONCEPT problem|fuzzy|solid` says how an idea feels, with no attempt behind it. A
mark moves what comes next and never moves credit, because a feeling is not evidence: some real gaps
feel solid. `clear` takes a mark back. Rows live in marks.jsonl; the last row for a concept wins.

`ken trail TOPIC CONCEPT --why W` records going down from what you were studying, and `--back`
returns. The trail is a stack across topics, so a session can always name the question that started
it and a gap cannot pull you away from the goal without saying so.
"""
from __future__ import annotations

from . import home as H
from . import learn as L
from . import ledger as LG
from .errors import OK, UsageError

MARKS_LEDGER = "marks.jsonl"
TRAIL_LEDGER = "trail.jsonl"
MARKS = ("problem", "fuzzy", "solid", "clear")
NOT_ATTEMPTS = ("predict", "teach", "learn")
RANK = {"problem": 0, "fuzzy": 1, "solid": 3}         # what comes first; an unmarked idea ranks 2


def _marks_path(cfg, slug):
    return L.tdir(cfg, slug) / MARKS_LEDGER


def _check_mark(r) -> None:
    H.iso_date(r["date"])
    if r.get("mark") not in MARKS or not isinstance(r.get("concept"), str) or not r["concept"]:
        raise ValueError(f"a mark row needs a concept and a mark ({', '.join(MARKS)})")


def read_marks(cfg, slug) -> tuple:
    return LG.read(_marks_path(cfg, slug), _check_mark)


def dated(cfg, slug) -> dict:
    """{concept: (mark, day)}, the last row for each, without those cleared. A damaged ledger steers
    nothing: the row it lost could be the `clear` that matters. `map`, `validate` and `doctor` name it."""
    rows, problems = read_marks(cfg, slug)
    if problems:
        return {}
    now: dict = {}
    names = L.renames(cfg, slug)
    for r in rows:
        now[L.canonical(r["concept"], names)] = (r["mark"], r["date"])
    return {k: v for k, v in now.items() if v[0] != "clear"}


def current(cfg, slug) -> dict:
    """{concept: problem|fuzzy|solid}."""
    return {k: v[0] for k, v in dated(cfg, slug).items()}


def overruled(cfg, slug) -> dict:
    """{concept: day} for a solid mark whose latest attempt, on or after the mark's day, failed:
    evidence beats a feeling, and a later success lifts it. A guess before teaching, teaching and
    massed practice are not attempts; a graded dialogue is, though it never moves credit."""
    solid = {k: v[1] for k, v in dated(cfg, slug).items() if v[0] == "solid"}
    if not solid:
        return {}
    names = L.renames(cfg, slug)
    out: dict = {}
    for r in L.read_log(cfg, slug)[0]:
        cid = L.canonical(r.get("concept", ""), names)
        if cid not in solid or r.get("mode") in NOT_ATTEMPTS or r["date"] < solid[cid]:
            continue
        if r.get("result", "ok" if r.get("correct") else "miss") in ("miss", "partial"):
            out[cid] = r["date"]
        else:
            out.pop(cid, None)
    return out


def mark(cfg, slug, concept, value, why="") -> int:
    cid = L.resolve_concept(L.load_state(cfg, slug), concept)
    if value not in MARKS:
        raise UsageError(f"a mark is one of {', '.join(MARKS)}")
    LG.append(_marks_path(cfg, slug), {"date": H.today().isoformat(), "concept": cid, "mark": value, "why": why},
              _check_mark)
    print(f"mark: {slug}/{cid} is {value}" + (" (no longer marked)" if value == "clear" else "")
          + "; a feeling, so no credit moves")
    if cid in overruled(cfg, slug):
        print(f"  a miss on {overruled(cfg, slug)[cid]} still outweighs it, until a later success")
    return OK


def _trail_path(cfg):
    return cfg.home / TRAIL_LEDGER


def _check_trail(r) -> None:
    H.iso_date(r["date"])
    if r.get("event") == "down":
        if not all(isinstance(r.get(k), str) and r[k] for k in ("topic", "concept")):
            raise ValueError("a trail step needs a topic and a concept")
    elif r.get("event") != "back":
        raise ValueError("a trail row is down or back")


def _printable(text: str) -> str:
    """A note as one line, with nothing that could drive the terminal."""
    return "".join(c if c.isprintable() else " " for c in text)


def stack(cfg) -> list:
    """The steps still open, oldest first. A `back` with nothing open changes nothing."""
    steps: list = []
    for r in LG.read(_trail_path(cfg), _check_trail)[0]:
        if r["event"] == "down":
            steps.append({**r, "concept": L.canonical(r["concept"], L.renames(cfg, r["topic"]))})
        elif steps:
            steps.pop()
    return steps


def show(cfg) -> int:
    steps = stack(cfg)
    if not steps:
        print(f"trail: empty; `{H.PROG} trail TOPIC CONCEPT --why W` records going down")
        return OK
    print("trail, from where you started:")
    for s in steps:
        print(f"  {s['topic']}/{s['concept']}" + (f"  ({_printable(s['why'])})" if s.get("why") else ""))
    return OK


def down(cfg, slug, concept, why="") -> int:
    cid = L.resolve_concept(L.load_state(cfg, slug), concept)
    LG.append(_trail_path(cfg), {"date": H.today().isoformat(), "event": "down", "topic": slug, "concept": cid,
                                 "why": why}, _check_trail)
    print(f"trail: down to {slug}/{cid}; {len(stack(cfg))} step(s) deep")
    return OK


def back(cfg) -> int:
    if not stack(cfg):
        raise UsageError("the trail is empty: nothing to go back from")
    LG.append(_trail_path(cfg), {"date": H.today().isoformat(), "event": "back"}, _check_trail)
    steps = stack(cfg)
    print(f"trail: back to {steps[-1]['topic']}/{steps[-1]['concept']}" if steps
          else "trail: back where you started; the trail is empty")
    return OK


def _trail(cfg, ns) -> int:
    if ns.back:
        if ns.slug:
            raise UsageError("--back takes no topic: it returns to the step before this one")
        return back(cfg)
    if not ns.slug:
        return show(cfg)
    if not ns.concept:
        raise UsageError("going down names a topic and a concept")
    return down(cfg, ns.slug, ns.concept, ns.why)


def commands(groups) -> None:
    g = groups[""]
    a = g.add_parser("mark", help="how an idea feels: problem, fuzzy, solid or clear; moves what comes next, never credit")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("value", choices=MARKS)
    a.add_argument("--why", default="", help="why it feels that way (kept in marks.jsonl)")
    a.set_defaults(run=lambda cfg, ns: mark(cfg, ns.slug, ns.concept, ns.value, ns.why))
    a = g.add_parser("trail", help="the path from what started this: go down to a concept, --back to return; alone, shows it")
    a.add_argument("slug", nargs="?")
    a.add_argument("concept", nargs="?")
    a.add_argument("--why", default="", help="what led here")
    a.add_argument("--back", action="store_true", help="return to the step before this one")
    a.set_defaults(run=_trail)
