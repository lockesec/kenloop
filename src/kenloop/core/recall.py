"""`ken recall`: name a concept's pieces from memory, scored against its pieces on the map.

The parts make the whole, and recalling them is retrieval, not drawing: listing a concept's
pieces from memory beat building a concept map, even on a concept-map test (Karpicke & Blunt,
Science 2011). A recall earns no credit and moves no schedule. Its rows (topics/<slug>/recall.jsonl,
append-only) say which pieces you named, which you missed, and anything you named that is not on
the map yet (offered as a branch). `map` shows a piece missed in your latest recall of its whole,
and `next` takes such a piece first among pieces.
"""
from __future__ import annotations

import json
import re

from . import home as H
from . import learn as L
from .errors import FINDINGS, NOT_EVALUABLE, OK, UsageError


def _file(cfg, slug):
    return L.tdir(cfg, slug) / "recall.jsonl"


def read(cfg, slug) -> tuple:
    """(rows, problems). A line that cannot be read is reported, never skipped in silence."""
    p = _file(cfg, slug)
    if not p.exists():
        return [], []
    rows, problems = [], []
    for n, line in enumerate(H.read_text(p, "recall file").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            H.iso_date(r["date"])
            if not (isinstance(r.get("concept"), str)
                    and all(isinstance(r.get(k), list) and all(isinstance(x, str) for x in r[k])
                            for k in ("listed", "recalled", "missed", "extra"))):
                raise ValueError("a recall row needs concept, listed, recalled, missed and extra")
        except (ValueError, KeyError, TypeError) as err:
            problems.append(f"{p.name} line {n}: {err}")
            continue
        rows.append(r)
    return rows, problems


def missed(cfg, slug) -> dict:
    """{piece: (whole, date)} for each piece missed in the LATEST recall of its whole."""
    latest = {}
    for r in sorted(read(cfg, slug)[0], key=lambda r: r["date"]):
        latest[r["concept"]] = r
    return {p: (whole, r["date"]) for whole, r in latest.items() for p in r["missed"]}


def _key(text: str) -> str:
    return L.slugify(text)


def match(listed: list, pieces: dict) -> tuple:
    """(recalled, missed, extra): `pieces` maps a piece's cid to its name. A listed item matches a
    piece by its name or its id (case, spacing and punctuation ignored)."""
    keys = {}
    for cid, name in pieces.items():
        keys[_key(name)] = cid
        keys[_key(cid.split(":", 1)[-1])] = cid
        keys[_key(cid)] = cid
    recalled, extra = [], []
    for item in listed:
        cid = keys.get(_key(item))
        if cid and cid not in recalled:
            recalled.append(cid)
        elif not cid:
            extra.append(item)
    return recalled, [c for c in pieces if c not in recalled], extra


def recall(cfg, slug, concept, listed=None) -> int:
    state = L.load_state(cfg, slug)
    cid = L.resolve_concept(state, concept)
    cons = state["concepts"]
    pieces = {k: c.get("name", k) for k, c in cons.items() if c.get("part_of") == cid and k != cid}
    name = cons[cid].get("name", cid)
    if not pieces:
        print(f"NOT EVALUABLE {cid} has no pieces on the map (no concept is marked `part-of:{cid}`), so there "
              f"is nothing to recall against; `{H.PROG} branch {slug} {cid} ...` adds one")
        return NOT_EVALUABLE
    if listed is None:
        print(f"recall: what are the pieces that make up {name} ({cid})? Name them from memory, without "
              f"looking, then:\n  {H.PROG} recall {slug} {cid} --listed \"first; second; ...\"")
        return OK
    items = [x.strip() for x in re.split(r"[;\n]", listed) if x.strip()]
    if not items:
        raise UsageError("--listed is empty: name at least one piece (separate them with ';')")
    got, miss, extra = match(items, pieces)
    row = {"date": H.today().isoformat(), "concept": cid, "listed": items, "recalled": got,
           "missed": miss, "extra": extra}
    with open(_file(cfg, slug), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{cid}: recalled {len(got)} of {len(pieces)} piece(s) from memory (no credit; a recall is practice)")
    for c in got:
        print(f"  recalled  {c}")
    for c in miss:
        print(f"  missed    {c}  ({pieces[c]})")
    for x in extra:
        print(f"  not on the map: {x!r}; if it is a piece of {cid}: "
              f"`{H.PROG} branch {slug} {cid} \"DOMAIN :: {x} :: ...\" --by learner`")
    return FINDINGS if miss else OK
