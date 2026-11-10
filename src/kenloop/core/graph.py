"""The study graph: one read-only answer to "what can I reach from where I stand?"

Built per call from files that already exist (concepts.json, the syllabus's `## Path`,
placement.jsonl, asks.jsonl, marks.jsonl); nothing new is stored. A concept is a node; its edges are the
syllabus links (`part-of`: a piece of a whole; `before`: learned before its target), the rungs
of question ladders (an earlier rung comes first) and the scale (a rung above your start is
taught before it is graded).

A concept is CLIMBED at good or mastered. One that is not is READY when every piece of it,
everything marked to come before it and every earlier rung of a ladder it is on are climbed, and
it is not above your starting rung untaught. Otherwise it WAITS, and the graph says on what.

Structure moves what you are asked next; only you move what you hold. Nothing here writes a
record or changes credit: apply_row and the scheduler stay the only path from an answer to
state, so replay and `rebuild --check` do not depend on this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import home as H
from . import learn as L
from . import marks as M
from . import onramp as O
from . import questions as Q
from . import recall as RC
from .errors import NOT_EVALUABLE, OK, NotEvaluable

CLIMBED = Q.CLIMBED


@dataclass
class Node:
    topic: str
    cid: str
    name: str
    badge: str
    rung: int | None = None
    part_of: str = ""
    pieces: list = field(default_factory=list)       # cids that are part-of this one
    first: list = field(default_factory=list)        # cids marked `before` this one
    elsewhere: list = field(default_factory=list)    # (topic/cid, climbed) in OTHER topics marked `before:<this topic>/<cid>`
    ladders: list = field(default_factory=list)      # (ask id, position, cids below it on that ladder)
    noted: bool = False                               # a foundations note exists
    suspect: tuple = ()                               # (piece, date) when a piece broke since it was right
    recall_missed: tuple = ()                         # (whole, date): missed in the latest recall of its whole
    mark: str = ""                                    # how it feels to you (core/marks.py): never credit
    overruled: str = ""                               # the day a failed attempt outweighed a solid mark

    @property
    def climbed(self) -> bool:
        return self.badge in CLIMBED


@dataclass
class Topic:
    slug: str
    nodes: dict                                       # cid -> Node, in syllabus order
    path: list
    start: int | None
    problems: list


def build(cfg, slug, asks=None) -> Topic:
    """The graph of one topic. `asks` (events from asks.jsonl) may be passed in to read the file once."""
    cons = L.load_state(cfg, slug)["concepts"]
    path = O.rungs(cfg, slug)
    rows, problems = O.read(cfg, slug)
    start = O.placed(cfg, slug, rows, len(path))["start"] if path else None
    nodes = {}
    for cid, c in cons.items():
        nodes[cid] = Node(slug, cid, c.get("name", cid), L.badge(c),
                          O.rung_of(c, path) if path else None, c.get("part_of", "") or "",
                          noted=O._note(cfg, slug, cid).is_file())
    for cid, c in cons.items():
        whole, target = c.get("part_of"), c.get("before")
        if whole in nodes and whole != cid:
            nodes[whole].pieces.append(cid)
        if target in nodes and target != cid:
            nodes[target].first.append(cid)
    for other in L.topics(cfg):         # `before:<topic>/<cid>` in another topic: learned before this one
        if other == slug:
            continue
        try:
            ocons = L.load_state(cfg, other)["concepts"]
        except NotEvaluable:
            continue                    # a damaged topic is its own integrity finding
        for ocid, oc in ocons.items():
            ref = oc.get("before") or ""
            if ref.startswith(slug + "/") and ref[len(slug) + 1:] in nodes:
                nodes[ref[len(slug) + 1:]].elsewhere.append((f"{other}/{ocid}", L.badge(oc) in CLIMBED))
    for whole, (piece, day) in L.suspects(cfg, slug, {"concepts": cons}).items():
        nodes[whole].suspect = (piece, day)
    rec_rows, rec_problems = RC.read(cfg, slug)
    problems = problems + rec_problems
    problems = problems + M.read_marks(cfg, slug)[1]
    for cid, value in M.current(cfg, slug).items():
        if cid in nodes:
            nodes[cid].mark = value
    for cid, day in M.overruled(cfg, slug).items():
        if cid in nodes:
            nodes[cid].mark, nodes[cid].overruled = "", day
    for piece, (whole, day) in RC.missed(cfg, slug).items():
        if piece in nodes:
            nodes[piece].recall_missed = (whole, day)
    if asks is None:
        asks, ask_problems = Q.read(cfg)
        problems = problems + ask_problems
    ladders: dict = {}
    for e in asks:
        if e["event"] == "rung" and e["topic"] == slug and e["concept"] in nodes:
            steps = ladders.setdefault(e["ask"], [])
            if e["concept"] not in steps:         # the same concept twice is one rung, not two
                steps.append(e["concept"])
    for qid, steps in ladders.items():
        for i, cid in enumerate(steps):
            nodes[cid].ladders.append((qid, i + 1, steps[:i]))
    return Topic(slug, nodes, path, start, problems)


def waits(t: Topic, n: Node) -> list:
    """Why a concept is not ready yet: [] when it is. Each reason names what to do first."""
    out = []
    open_pieces = [p for p in n.pieces if not t.nodes[p].climbed]
    if open_pieces:
        out.append(f"made of {len(n.pieces)} piece(s), {len(open_pieces)} not climbed: {', '.join(open_pieces[:3])}")
    open_first = [p for p in n.first if not t.nodes[p].climbed] + [ref for ref, up in n.elsewhere if not up]
    if open_first:
        out.append(f"learn first: {', '.join(open_first[:3])}")
    for qid, pos, below in n.ladders:
        open_below = [p for p in below if not t.nodes[p].climbed]
        if open_below:
            out.append(f"rung {pos} of {qid}: climb {', '.join(open_below[:3])} first")
    if (t.start is not None and n.rung is not None and n.rung > t.start
            and n.badge == "new" and not n.noted):
        out.append(f"rung {n.rung} ({t.path[n.rung]}) is above your start (rung {t.start}): taught first")
    return out


def frontier(t: Topic) -> list:
    """Concepts not yet climbed that are ready now, where study can go next: what you marked a
    problem first, what you marked solid last, otherwise in syllabus order."""
    ready = [n for n in t.nodes.values() if not n.climbed and not waits(t, n)]
    return sorted(ready, key=lambda n: M.RANK.get(n.mark, 2))


def _status(t: Topic, n: Node) -> str:
    if n.suspect:
        return f"SUSPECT: its piece {n.suspect[0]} was answered wrong on {n.suspect[1]}"
    if n.climbed:
        return "climbed"
    w = waits(t, n)
    miss = f"missed in your recall of {n.recall_missed[0]} on {n.recall_missed[1]}; " if n.recall_missed else ""
    return miss + ("READY" if not w else "waits: " + "; ".join(w))


def map_(cfg, slug=None) -> int:
    """`ken map`: each topic's concepts as a tree of wholes and their pieces, by rung when the
    topic has a scale, each with its badge and whether it is climbed, ready or waiting (and on
    what); then the frontier."""
    slugs = [slug] if slug else L.topics(cfg)
    if not slugs:
        print(f"NOT EVALUABLE nothing to map: 0 topic(s) in {cfg.home}")
        return NOT_EVALUABLE
    asks, ask_problems = Q.read(cfg)
    code = OK
    for s in slugs:
        try:
            t = build(cfg, s, asks)
        except NotEvaluable as e:
            print(f"{s}: NOT EVALUABLE ({e})")
            code = NOT_EVALUABLE
            continue
        scale = ""
        if t.path:
            where = f"you start on rung {t.start}" if t.start is not None else "not placed yet"
            scale = f"  (scale: {' > '.join(t.path)}; {where})"
        print(f"{s}{scale}")
        roots = [n for n in t.nodes.values() if n.part_of not in t.nodes or n.part_of == n.cid]
        groups = {}
        for n in roots:
            groups.setdefault(n.rung, []).append(n)
        seen: set = set()
        for rung in sorted(groups, key=lambda r: (r is None, r if r is not None else 0)):
            if t.path:
                label = f"rung {rung} ({t.path[rung]})" if rung is not None else "on no rung"
                print(f"  {label}")
            for n in groups[rung]:
                _print_tree(t, n, depth=2 if t.path else 1, seen=seen)
        stuck = [cid for cid in t.nodes if cid not in seen]
        if stuck:                         # only a part-of cycle leaves a concept with no root
            print(f"  in a part-of cycle (see `validate {s}`): {', '.join(stuck)}")
        f = frontier(t)
        print(f"  frontier: {len(f)} ready to study" + (f": {', '.join(n.cid for n in f[:6])}"
                                                         + (" ..." if len(f) > 6 else "") if f else ""))
        if len(f) > 6 and not any(n.mark for n in t.nodes.values()):
            print(f"  no route yet: `{H.PROG} mark {s} CONCEPT problem` on what feels like the problem")
        for p in t.problems:
            print(f"  DAMAGED {p}")
            code = NOT_EVALUABLE
    for p in ask_problems:
        print(f"DAMAGED {p}")
        code = NOT_EVALUABLE
    return code


def _print_tree(t: Topic, n: Node, depth: int, seen: set) -> None:
    if n.cid in seen:                    # a cycle (validate names it): print once, never loop
        return
    seen.add(n.cid)
    piece = "piece of " + n.part_of + ", " if n.part_of in t.nodes and n.part_of != n.cid else ""
    marked = f"you marked {n.mark}; " if n.mark else f"you marked solid, then missed it {n.overruled}; " if n.overruled else ""
    print(f"{'  ' * depth}{n.badge:<9}{n.cid}  [{piece}{marked}{_status(t, n)}]")
    for p in n.pieces:
        _print_tree(t, t.nodes[p], depth + 1, seen)
