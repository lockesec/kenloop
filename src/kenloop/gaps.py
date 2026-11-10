"""Tutor gaps: misses the teaching caused, counted against the tutor (tutor_gaps.jsonl).

When a learner sticks on a question the text above it never prepared (a step it skipped, notation it
never explained, an example that did not carry), the gap is the tutor's: the climb method records
nothing against the learner. Without a record of its own, that miss vanishes, and a tool that
measures only the learner cannot tell when the teaching is the problem.

`ken gap SLUG CONCEPT "what the text left out"` records one; `ken gaps [SLUG]` reads them back by
concept, beside how many concepts were taught, so a teaching that keeps failing on one kind of step
shows up. Nothing here is evidence about the learner: no credit, height or schedule reads it.

Built only through the seams (commands, ledgers), like the session journal.
"""
from __future__ import annotations

from .core import home as H
from .core import learn as L
from .core import ledger as LG
from .core.errors import NOT_EVALUABLE, OK, UsageError

LEDGER = "tutor_gaps.jsonl"
KINDS = ("step", "notation", "example", "order", "other")


def _path(cfg):
    return cfg.home / LEDGER


def _check(row) -> None:
    H.iso_date(row["date"])
    for k in ("topic", "concept", "gap"):
        if not isinstance(row.get(k), str) or not row[k]:
            raise ValueError(f"no {k}")
    if row.get("kind") not in KINDS:
        raise ValueError(f"kind {row.get('kind')!r}")


def rows(cfg, topic=None) -> list:
    out = LG.read(_path(cfg), _check)[0]
    return [r for r in out if topic is None or r["topic"] == topic]


def gap(cfg, topic, concept, text, kind="step") -> int:
    L.need_topic(cfg, topic)
    if kind not in KINDS:
        raise UsageError(f"--kind takes {', '.join(KINDS)}")
    text = text.strip()
    if not text:
        raise UsageError("say what the text left out")
    cid = L.resolve_concept({"concepts": L.load_state(cfg, topic)["concepts"]}, concept)
    LG.append(_path(cfg), {"date": H.today().isoformat(), "topic": topic, "concept": cid, "kind": kind,
                           "gap": text}, _check)
    taught = L.load_state(cfg, topic)["concepts"][cid].get("taught")
    print(f"tutor gap recorded: {cid} ({kind}); nothing is recorded against the learner"
          + ("" if taught else f"; {cid} is not marked taught (`{H.PROG} taught {topic} {cid}` records the teaching)"))
    return OK


def show(cfg, topic=None) -> int:
    good, damaged = LG.read(_path(cfg), _check)
    rs = [r for r in good if topic is None or r["topic"] == topic]
    tops = [topic] if topic else L.topics(cfg)
    state = {t: L.load_state(cfg, t)["concepts"] for t in tops}
    taught = sum(1 for t in tops for c in state[t].values() if c.get("taught"))
    unread = f"; {len(damaged)} damaged line(s) not read, see `{H.PROG} doctor`" if damaged else ""
    if not rs:
        print(f"no tutor gaps recorded{' in ' + topic if topic else ''} over {taught} taught concept(s){unread}")
        return NOT_EVALUABLE if damaged else OK
    by: dict = {}
    for r in rs:
        by.setdefault((r["topic"], r["concept"]), []).append(r)
    for (t, c), gs in sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"{t} {c}: {len(gs)} gap(s)")
        for g in gs:
            print(f"  {g['date']} {g['kind']}: {g['gap']}")
    kinds: dict = {}
    for r in rs:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    untaught = sum(1 for r in rs if not state.get(r["topic"], {}).get(r["concept"], {}).get("taught"))
    print(f"tutor gaps: {len(rs)} on {len(by)} concept(s), {taught} concept(s) taught"
          + (f" ({untaught} gap(s) on concepts not marked taught)" if untaught else "") + "; by kind: "
          + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])) + unread)
    return NOT_EVALUABLE if damaged else OK


def doctor(cfg) -> list:
    """A damaged line is reported, never skipped."""
    return [("NOT EVALUABLE", f"{LEDGER}: {p}") for p in LG.read(_path(cfg), _check)[1]]


def commands(groups) -> None:
    g = groups[""]
    a = g.add_parser("gap", help="a miss the teaching caused: a step the text never prepared, counted against the "
                                 "tutor, never the learner (tutor_gaps.jsonl)")
    a.add_argument("topic")
    a.add_argument("concept")
    a.add_argument("text", help="what the text left out")
    a.add_argument("--kind", default="step", choices=KINDS)
    a.set_defaults(run=lambda cfg, ns: gap(cfg, ns.topic, ns.concept, ns.text, ns.kind))
    b = g.add_parser("gaps", help="tutor gaps by concept, beside how many concepts were taught")
    b.add_argument("topic", nargs="?")
    b.set_defaults(run=lambda cfg, ns: show(cfg, ns.topic))
