"""Tutor gaps: misses the teaching caused, counted against the tutor (tutor_gaps.jsonl).

When a learner sticks on a question the text above it never prepared (a step it skipped, notation it
never explained, an example that did not carry), the gap is the tutor's: the climb method records
nothing against the learner. Without a record of its own, that miss vanishes, and a tool that
measures only the learner cannot tell when the teaching is the problem.

`ken gap SLUG CONCEPT "what the text left out"` records one; `ken gaps [SLUG]` reads them back by
concept, beside how many concepts were taught, so a teaching that keeps failing on one kind of step
shows up. Nothing here is evidence about the learner: no credit, height or schedule reads it.

Most misses are only seen afterwards. `ken gaps SLUG --review` is the tutor's review at the close:
the questions to re-read the session against, what was logged today, and the one question to put to
the learner, whose answer is kept in their words (`--by learner`). A miss about the session and not
one concept takes `-` for the concept. `ken session` shows the latest, so the next tutor starts from them.

Built only through the seams (commands, ledgers), like the session journal.
"""
from __future__ import annotations

from .core import home as H
from .core import learn as L
from .core import ledger as LG
from .core.errors import NOT_EVALUABLE, OK, UsageError

LEDGER = "tutor_gaps.jsonl"
KINDS = ("step", "notation", "example", "order", "unverified", "misread", "process", "other")
BY = ("tutor", "learner")
SESSION = "-"                     # the concept of a miss that belongs to the session, not one idea
REVIEW = (("unverified", "did I teach a fact I had not read today?"),
          ("misread", "did I call a part skipped, or an answer wrong, when the learner had given it?"),
          ("step", "did I ask something the text above never prepared? (or notation, example, order)"),
          ("process", "did I ask a question they did not need, or make the session harder to follow?"))
ASK = "Did you notice any sharp edges: anything I got wrong, or made harder than it needed to be?"


def _path(cfg):
    return cfg.home / LEDGER


def _check(row) -> None:
    H.iso_date(row["date"])
    for k in ("topic", "concept", "gap"):
        if not isinstance(row.get(k), str) or not row[k]:
            raise ValueError(f"no {k}")
    if row.get("kind") not in KINDS:
        raise ValueError(f"kind {row.get('kind')!r}")
    if row.get("by", "tutor") not in BY:
        raise ValueError(f"by {row.get('by')!r}")


def rows(cfg, topic=None) -> list:
    out = LG.read(_path(cfg), _check)[0]
    return [r for r in out if topic is None or r["topic"] == topic]


def gap(cfg, topic, concept, text, kind="step", by="tutor") -> int:
    L.need_topic(cfg, topic)
    if kind not in KINDS:
        raise UsageError(f"--kind takes {', '.join(KINDS)}")
    if by not in BY:
        raise UsageError(f"--by takes {', '.join(BY)}")
    text = text.strip()
    if not text:
        raise UsageError("say what the text left out")
    whole = concept.strip() == SESSION
    cid = SESSION if whole else L.resolve_concept({"concepts": L.load_state(cfg, topic)["concepts"]}, concept)
    LG.append(_path(cfg), {"date": H.today().isoformat(), "topic": topic, "concept": cid, "kind": kind,
                           "gap": text, **({"by": by} if by != "tutor" else {})}, _check)
    taught = whole or L.load_state(cfg, topic)["concepts"][cid].get("taught")
    print(f"tutor gap recorded: {'the session' if whole else cid} ({kind}"
          + (", raised by the learner" if by == "learner" else "") + "); nothing is recorded against the learner"
          + ("" if taught else f"; {cid} is not marked taught (`{H.PROG} taught {topic} {cid}` records the teaching)"))
    return OK


def line(g) -> str:
    return (f"{g['kind']}: {g['gap']}" + (" (the learner's words)" if g.get("by") == "learner" else ""))


def latest(cfg, topic, n=3) -> tuple:
    """(the last n gaps on this topic, how many there are, damaged lines): what `ken session` shows a
    tutor before the first turn. Damage is returned, never read as "no gaps"."""
    good, damaged = LG.read(_path(cfg), _check)
    rs = [r for r in good if r["topic"] == topic]
    return rs[-n:], len(rs), damaged


def review(cfg, topic) -> int:
    """The tutor's review at the close. It reads the ledger and prints the rule; the re-reading is
    the tutor's, and so is asking the learner."""
    L.need_topic(cfg, topic)
    today = H.today().isoformat()
    good, damaged = LG.read(_path(cfg), _check)
    rs = [r for r in good if r["topic"] == topic and r["date"] == today]
    print(f"tutor review: {topic}, {today}")
    print(f"  1. Re-read the session. Log each miss on yourself: `{H.PROG} gap {topic} CONCEPT \"...\" --kind K` "
          f"(`{SESSION}` for CONCEPT when it is about the session)")
    for k, q in REVIEW:
        print(f"       {k:<11} {q}")
    if damaged:
        print(f"  logged today: NOT EVALUABLE, {len(damaged)} damaged line(s) in {LEDGER}; see `{H.PROG} doctor`")
    else:
        print(f"  logged today: {len(rs)}" + ("" if rs else " (none is a finding only after step 1)"))
        for g in rs:
            print(f"    {'the session' if g['concept'] == SESSION else g['concept']}  {line(g)}")
    mine = [g for g in rs if g.get("by", "tutor") == "tutor"]
    print("  2. Tell the learner, then ask:")
    print("       " + (f"\"I found {len(mine)} thing(s) in my own teaching today: (say each in a line). {ASK}\""
                       if mine else f"\"I found nothing in my own teaching today. {ASK}\""))
    print(f"  3. Keep what they say in their words: `{H.PROG} gap {topic} CONCEPT|{SESSION} \"...\" --by learner`. "
          "\"No\" is not recorded.")
    return NOT_EVALUABLE if damaged else OK


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
        print(f"{t} {'(the session)' if c == SESSION else c}: {len(gs)} gap(s)")
        for g in gs:
            print(f"  {g['date']} {line(g)}")
    kinds: dict = {}
    for r in rs:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    untaught = sum(1 for r in rs if r["concept"] != SESSION
                   and not state.get(r["topic"], {}).get(r["concept"], {}).get("taught"))
    whole = sum(1 for r in rs if r["concept"] == SESSION)
    said = sum(1 for r in rs if r.get("by") == "learner")
    print(f"tutor gaps: {len(rs)} on {len({k for k in by if k[1] != SESSION})} concept(s), {taught} concept(s) taught"
          + (f" ({untaught} gap(s) on concepts not marked taught)" if untaught else "")
          + (f"; {whole} about a session" if whole else "")
          + (f"; {said} raised by the learner, {len(rs) - said} found by the tutor" if said else "") + "; by kind: "
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
    a.add_argument("concept", help=f"the concept, or {SESSION} when the miss is about the session")
    a.add_argument("text", help="what the text left out, or what went wrong")
    a.add_argument("--kind", default="step", choices=KINDS)
    a.add_argument("--by", default="tutor", choices=BY, help="who saw it: the tutor's own review (default), or the "
                                                             "learner, in their words")
    a.set_defaults(run=lambda cfg, ns: gap(cfg, ns.topic, ns.concept, ns.text, ns.kind, ns.by))
    b = g.add_parser("gaps", help="tutor gaps by concept, beside how many concepts were taught")
    b.add_argument("topic", nargs="?")
    b.add_argument("--review", action="store_true", help="the tutor's review at the close: what to re-read the "
                                                         "session for, today's gaps, and what to ask the learner")

    def _gaps(cfg, ns):
        if ns.review and not ns.topic:
            raise UsageError("--review is for one session: give its topic")
        return review(cfg, ns.topic) if ns.review else show(cfg, ns.topic)
    b.set_defaults(run=_gaps)
