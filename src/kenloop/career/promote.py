"""Promotion: the controlled route from an interest topic to facts.md, one concept at a time.

A topic studied for its own sake never graduates; some of what you learn that way turns out to
be useful for a job, and some never will. Promotion is the per-concept decision that it is:

- it is RECORDED (topics/<slug>/promotions.jsonl, append-only: promote and revoke events, each
  with the day and your reason), so the record shows when and why an interest concept was put
  forward as a resume claim;
- it needs DEMAND: the concept's name or description must hold a term of your keyword packs
  (what postings ask for). A black-holes concept cannot be promoted, which is right;
- it earns nothing by itself: a promoted concept graduates only through the same four evidence
  gates as a career concept (retained, breadth, interference, not suspect).

The topic stays an interest topic; only promoted concepts can cross. A career topic needs no
promotion: all of it may graduate.
"""
from __future__ import annotations

from ..core import home as H
from ..core import learn as L
from ..core import ledger as LG
from ..core.errors import OK, UsageError
from . import ats

LEDGER = "promotions.jsonl"


def _path(cfg, slug):
    return L.tdir(cfg, slug) / LEDGER


def _check(row) -> None:
    if row.get("event") not in ("promote", "revoke") or not row.get("concept"):
        raise ValueError("not a promote/revoke row")


def events(cfg, slug) -> list:
    """Every promote/revoke row, in order. A STRICT ledger: a damaged row is NOT EVALUABLE, never
    skipped, because skipping a revoke would turn a withdrawn claim back on."""
    return LG.read(_path(cfg, slug), _check)[0]


def promoted(cfg, slug) -> set:
    """Concepts whose LAST event is a promote."""
    last: dict = {}
    for row in events(cfg, slug):
        last[row["concept"]] = row["event"]
    return {c for c, e in last.items() if e == "promote"}


def demand_terms(cfg, concept: dict, lex=None) -> list:
    """Keyword-pack terms the concept names (its name and description), case-folded."""
    lex = lex or ats.load_lexicon(cfg)
    text = f"{concept.get('name', '')}. {concept.get('desc', '')}"
    return [t.lower() for t in ats.extract(text, lex, acronyms=False)]


def promote(cfg, slug, cid, why="", revoke=False) -> int:
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    cons = L.load_state(cfg, slug)["concepts"]
    if cid not in cons:
        raise UsageError(f"{slug} has no concept {cid!r} (`{H.PROG} mastery {slug}` lists them)")
    if L.has_outlet(conf, "career"):
        print(f"{slug} is a career topic: every concept may graduate already; nothing to promote")
        return OK
    now = promoted(cfg, slug)
    if revoke:
        if cid not in now:
            print(f"{slug}/{cid} is not promoted; nothing to revoke")
            return OK
        row = {"date": H.today().isoformat(), "event": "revoke", "concept": cid, "why": why}
    else:
        if not why.strip():
            raise UsageError("--why is required: say which job need this concept answers")
        terms = demand_terms(cfg, cons[cid])
        if not terms:
            raise UsageError(f"{slug}/{cid} ({cons[cid].get('name', cid)!r}) names no term of your keyword packs "
                             f"({', '.join(cfg.packs) or 'none configured'}): nothing a posting asks for, so it stays "
                             "interest. Rename the concept if it really is the skill a posting names")
        if cid in now:
            print(f"{slug}/{cid} is already promoted")
            return OK
        row = {"date": H.today().isoformat(), "event": "promote", "concept": cid, "why": why.strip(), "terms": terms}
    LG.append(_path(cfg, slug), row, _check)
    if revoke:
        print(f"{slug}/{cid}: promotion revoked; it can no longer graduate "
              "(a facts.md line you pasted stays until you remove it)")
    else:
        print(f"{slug}/{cid}: promoted (terms: {', '.join(row['terms'])}); it graduates only when it passes the "
              f"four evidence gates: `{H.PROG} jobs graduate {slug}`")
    return OK


def commands(groups) -> None:
    a = groups["jobs"].add_parser("promote", help="put one interest-topic concept forward as a job skill "
                                                  "(recorded; still gated)")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("--why", default="", help="the job need it answers (required to promote)")
    a.add_argument("--revoke", action="store_true", help="withdraw the promotion")
    a.set_defaults(run=lambda cfg, ns: promote(cfg, ns.slug, ns.concept, ns.why, ns.revoke))
