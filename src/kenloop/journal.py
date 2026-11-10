"""The session journal: what a study session was like, one row per session (sessions.jsonl).

`ken close TOPIC ...` is the one-minute close of a session: the learner names the three things that
matter from memory and the one still fuzzy, says how much they feel they learned (1-5, or in their own words), and the tutor
adds the counts it kept: minutes, chunks explained and how many ended with an act of the learner's,
the learner's questions (why/what-if against what-is), old ideas woven in, digressions.
`ken sessions` reads them back.

Nothing here is evidence: no credit, height or schedule reads the journal. It exists so two
things can be seen that the study log cannot show: whether the learner is doing the work (the
share of chunks closed by their act), and whether feeling they learned tracks what holds later (the
felt-vs-held gap: perceived learning beside the next recall of the same ideas).

Built only through the seams (commands, ledgers): the first module made to the module standard.
"""
from __future__ import annotations

import re

from .core import home as H
from .core import learn as L
from .core import ledger as LG
from .core.errors import OK, UsageError

LEDGER = "sessions.jsonl"
COUNTS = ("minutes", "chunks", "acts", "why", "what", "woven", "digressions")


def _path(cfg):
    return cfg.home / LEDGER


def _check(row) -> None:
    H.iso_date(row["date"])
    if not isinstance(row.get("topic"), str) or not row["topic"]:
        raise ValueError("no topic")
    for k in COUNTS:
        v = row.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
            raise ValueError(f"{k} {v!r}")
    if row.get("acts") is not None and row.get("chunks") is not None and row["acts"] > row["chunks"]:
        raise ValueError("more acts than chunks")
    p = row.get("perceived")
    if p is not None and (isinstance(p, bool) or p not in range(1, 6)):
        raise ValueError(f"perceived {p!r}")
    if not isinstance(row.get("felt", ""), str):
        raise ValueError("felt")
    if not (isinstance(row.get("three", []), list) and all(isinstance(x, str) for x in row.get("three", []))):
        raise ValueError("three")
    if not (isinstance(row.get("ideas", []), list) and all(isinstance(x, str) for x in row.get("ideas", []))):
        raise ValueError("ideas")


def rows(cfg, topic=None) -> list:
    out = LG.read(_path(cfg), _check)[0]
    return [r for r in out if topic is None or r["topic"] == topic]


def _perceived(value):
    """A number 1-5, or the learner's own words, kept as they said them: "a little better, some stuck"
    is better data than a number they were made to pick. Returns (number or None, words)."""
    if value is None:
        return None, ""
    v = str(value).strip()
    if not v:
        raise UsageError("--perceived is empty: give 1-5 or your own words")
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", v):         # number-shaped: a number, so 1-5 or refused
        if not re.fullmatch(r"\d+", v) or int(v) not in range(1, 6):
            raise UsageError(f"--perceived {v!r}: a number must be a whole 1-5; or give your own words")
        return int(v), ""
    return None, v


def close(cfg, topic, three=(), fuzzy="", perceived=None, ideas=(), **counts) -> int:
    perceived, felt = _perceived(perceived)
    L.need_topic(cfg, topic)
    cons = L.load_state(cfg, topic)["concepts"]
    state = {"concepts": cons}
    ids = [L.resolve_concept(state, i) for i in ideas]
    three = [t.strip() for t in three if t.strip()]
    if len(three) > 3:
        raise UsageError("--three takes the three things that matter, at most three")
    row = {"date": H.today().isoformat(), "topic": topic, "ideas": ids, "three": three,
           "fuzzy": fuzzy.strip(), "perceived": perceived, **({"felt": felt} if felt else {}),
           **{k: counts.get(k) for k in COUNTS}}
    LG.append(_path(cfg), row, _check)
    share = (f"; {row['acts']}/{row['chunks']} chunks closed by your act" if row["chunks"] else "")
    print(f"session closed: {topic}, {len(three)} thing(s) from memory{share}"
          + (f"; fuzzy: {row['fuzzy']} (it opens the next session)" if row["fuzzy"] else ""))
    if row["fuzzy"]:
        from . import session as SS
        SS.note(cfg, topic, f"fuzzy: {row['fuzzy']}")
    return OK


def show(cfg, topic=None, n=10) -> int:
    rs = rows(cfg, topic)
    if not rs:
        print(f"no sessions closed yet{' in ' + topic if topic else ''} (`{H.PROG} close TOPIC ...` at the end of one)")
        return OK
    for r in rs[-n:]:
        acts = f"{r['acts']}/{r['chunks']} acts" if r.get("chunks") else "acts not counted"
        print(f"{r['date']} {r['topic']}: {r.get('minutes') or '?'} min, {acts}, "
              f"questions why {r.get('why') if r.get('why') is not None else '?'} / what {r.get('what') if r.get('what') is not None else '?'}, "
              + (f"felt: {r['felt']!r}" if r.get("felt") else f"felt {r.get('perceived') or '?'}/5")
              + (f", fuzzy: {r['fuzzy']}" if r.get("fuzzy") else ""))
    counted = [r for r in rs if r.get("chunks")]
    if counted:      # the denominator is printed: sessions whose chunks were counted, of all closed
        acts = sum(r["acts"] or 0 for r in counted)
        chunks = sum(r["chunks"] for r in counted)
        print(f"learner acts: {acts}/{chunks} chunks ({acts / chunks:.0%}) over {len(counted)} of {len(rs)} session(s) counted")
    else:
        print(f"learner acts: not counted in any of {len(rs)} session(s)")
    return OK


def doctor(cfg) -> list:
    """A damaged journal line is reported, never skipped."""
    return [("NOT EVALUABLE", f"{LEDGER}: {p}") for p in LG.read(_path(cfg), _check)[1]]


def commands(groups) -> None:
    g = groups[""]
    a = g.add_parser("close", help="the one-minute close of a study session: three things from memory, the fuzzy "
                                   "one, how much you feel you learned, and the tutor's counts (sessions.jsonl)")
    a.add_argument("topic")
    a.add_argument("--three", action="append", default=[], help="one thing that matters, from memory (up to 3)")
    a.add_argument("--fuzzy", default="", help="the one thing still fuzzy: the next session opens on it")
    a.add_argument("--perceived", help="how much you feel you learned: 1-5, or in your own words")
    a.add_argument("--idea", action="append", default=[], dest="ideas", help="an idea covered (repeatable)")
    for k in COUNTS:
        a.add_argument(f"--{k}", type=int, help={"acts": "chunks that ended with an act of yours",
                                                 "why": "your why/what-if questions", "what": "your what-is questions",
                                                 "woven": "old ideas woven in"}.get(k, k))
    a.set_defaults(run=lambda cfg, ns: close(cfg, ns.topic, ns.three, ns.fuzzy, ns.perceived, ns.ideas,
                                             **{k: getattr(ns, k) for k in COUNTS}))
    b = g.add_parser("sessions", help="closed study sessions and the share of chunks you closed with an act")
    b.add_argument("topic", nargs="?")
    b.add_argument("--n", type=int, default=10)
    b.set_defaults(run=lambda cfg, ns: show(cfg, ns.topic, ns.n))
