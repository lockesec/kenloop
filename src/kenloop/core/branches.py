"""Branches: every gap found mid-study, who raised it, and what became of it.

A gap is raised by the learner, offered by the tutor in a dialogue, or offered by the tool from
the record (a dialogue's `--broke`/`--next` naming nothing on the syllabus, a turn taught at hint
depth 3 or more, an open question with no concept to land on, a placement miss). Each decision is
one row of branches.jsonl in the home: a piece, learned before, a topic of its own, a note, or
declined. From those rows `ken branch` reads how well the offers are picked: how many offers were
taken, how many branches you raised that nobody offered, and how many branches were studied.
The ratios always print with their counts, and with no offers yet they say so instead of a rate.
"""
from __future__ import annotations

import json
import re

from . import home as H
from . import learn as L
from .errors import NOT_EVALUABLE, OK, NotEvaluable, UsageError

BY = ("learner", "tutor", "tool")
AS = ("piece", "before", "topic", "note", "declined")
_STOP = {"what", "which", "when", "where", "does", "that", "this", "with", "from", "have", "they", "their",
         "there", "about", "would", "could", "should", "into", "than", "then", "them", "learn",
         "next", "just", "like", "your", "were", "been", "more", "less", "only", "also", "each", "every"}


def path(cfg):
    return cfg.home / "branches.jsonl"


def _check(r) -> None:
    if not isinstance(r, dict):
        raise ValueError("not an object")
    H.iso_date(r["date"])
    if r.get("by") not in BY or r.get("as") not in AS:
        raise ValueError(f"by must be one of {', '.join(BY)} and as one of {', '.join(AS)}")
    if not all(isinstance(r.get(k), str) for k in ("topic", "concept", "gap", "target", "source")) \
            or not r["gap"].strip():
        raise ValueError("a branch row needs topic, concept, gap, target and source (strings, gap not empty)")


def read(cfg) -> tuple:
    """(rows, problems). A line that cannot be read is reported, never skipped in silence."""
    p = path(cfg)
    if not p.exists():
        return [], []
    rows, problems = [], []
    for n, line in enumerate(H.read_text(p, "branches file").splitlines(), 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            _check(r)
        except (ValueError, KeyError, TypeError) as err:
            problems.append(f"{p.name} line {n}: {err}")
            continue
        rows.append(r)
    return rows, problems


def append(cfg, topic, concept, gap, by, as_, target="", source="") -> dict:
    rows, problems = read(cfg)
    if problems:
        raise NotEvaluable(f"{len(problems)} unreadable line(s) in branches.jsonl (first: {problems[0]}); "
                           "nothing appended past the damage")
    if by not in BY:
        raise UsageError(f"--by is required: who raised the gap ({', '.join(BY)}); the offer ratio is "
                         "read from it, so it is never guessed")
    if source and by != "tool":
        raise UsageError("--source names one of the tool's offers, so --by is tool")
    row = {"date": H.today().isoformat(), "topic": topic, "concept": concept, "gap": (gap or "").strip(),
           "by": by, "as": as_, "target": target, "source": source}
    _check(row)
    with open(path(cfg), "a", encoding="utf-8") as fh:     # an append is the record's own unit
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


def _on_syllabus(cons: dict, text: str) -> bool:
    """Does the text name something already on the syllabus? Two shared words, or one for a
    short name, counts as named."""
    w = _words(text)
    for c in cons.values():
        name = _words(c.get("name", ""))
        if name and len(w & name) >= min(2, len(name)):
            return True
    return False


def candidates(cfg, slug) -> list:
    """The tool's offers for one topic: [{source, concept, gap, why}], decided ones left out."""
    cons = L.load_state(cfg, slug)["concepts"]
    rows, _p = L.read_log(cfg, slug)
    decided = {r["source"] for r in read(cfg)[0] if r["source"]}
    out = []
    for r in rows:
        if r.get("mode") != "dialogue":
            continue
        key = f"dialogue:{r['date']}:{r['concept']}"
        for field in ("broke", "next"):
            text = r.get(field, "")
            if text and not _on_syllabus(cons, text):
                out.append({"source": f"{key}:{field}", "concept": r["concept"], "gap": text,
                            "why": f"the dialogue's --{field} names nothing on the syllabus"})
        for i, q in enumerate(r.get("open", [])):
            cid, text = L.open_target(cons, q, r["concept"])
            if cid == r["concept"] and not _on_syllabus(cons, text):
                out.append({"source": f"{key}:open{i}", "concept": cid, "gap": text,
                            "why": "an open question with no concept to land on"})
        if int(r.get("hint_depth", 0) or 0) >= 3:
            out.append({"source": f"{key}:hint", "concept": r["concept"],
                        "gap": f"taught at hint depth {r['hint_depth']}: a piece of it may be missing",
                        "why": "the dialogue needed the answer told"})
    from . import onramp as O                 # the scale is the on-ramp's; read only
    p_rows, _pp = O.read(cfg, slug)
    for r in p_rows:
        if r["result"] == "miss":
            out.append({"source": f"placement:{r['date']}:rung{r['rung']}", "concept": "",
                        "gap": f"placement missed rung {r['rung']} ({r.get('domain', '')}): {r['answer'][:90]}",
                        "why": "a missed rung: are its pieces on the syllabus?"})
    return [c for c in out if c["source"] not in decided]


def _studied(cfg, r) -> bool:
    try:
        if r["as"] == "topic":
            return any(c.get("attempts") or c.get("dialogues")
                       for c in L.load_state(cfg, r["target"])["concepts"].values())
        c = L.load_state(cfg, r["topic"])["concepts"].get(r["target"], {})
        return bool(c.get("attempts") or c.get("dialogues"))
    except (NotEvaluable, UsageError):
        return False


def ratios(cfg, rows) -> dict:
    offers = [r for r in rows if r["by"] in ("tutor", "tool")]
    taken = [r for r in offers if r["as"] != "declined"]
    kept = [r for r in rows if r["as"] != "declined"]
    raised = [r for r in kept if r["by"] == "learner"]
    built = [r for r in kept if r["as"] in ("piece", "before", "topic")]
    return {"offers": len(offers), "taken": len(taken), "by_tutor": sum(r["by"] == "tutor" for r in offers),
            "by_tool": sum(r["by"] == "tool" for r in offers), "kept": len(kept), "unoffered": len(raised),
            "built": len(built), "studied": sum(_studied(cfg, r) for r in built)}


def _line(n, d, what) -> str:
    return f"{n}/{d} {what}" if d else f"no {what.split()[-1]} yet"


def report(cfg, slug=None) -> int:
    rows, problems = read(cfg)
    if slug:
        L.need_topic(cfg, slug)
        cands = candidates(cfg, slug)
        print(f"branch: {L.load_config(cfg, slug).get('title', slug)}")
        if cands:
            print(f"  the tool's offers ({len(cands)}), from the record:")
            for c in cands:
                print(f"    {c['source']}")
                print(f"      {c['gap'][:110]}")
                print(f"      ({c['why']})")
            print(f"  decide one: {H.PROG} branch {slug} CONCEPT \"DOMAIN :: NAME :: DESC\" --by tool --source KEY"
                  f" [--before | --topic NEW]\n            or --note \"...\" / --decline \"...\" with --by tool --source KEY")
        else:
            print("  the tool has no open offers for this topic")
        rows = [r for r in rows if r["topic"] == slug]
    s = ratios(cfg, rows)
    print(f"  record: {len(rows)} decision(s)"
          + (f"; offers {s['offers']} (tutor {s['by_tutor']}, tool {s['by_tool']}), "
             f"{_line(s['taken'], s['offers'], 'taken')}" if s["offers"] else "; no offers yet (tutor or tool)"))
    if s["kept"]:
        print(f"  you raised {s['unoffered']}/{s['kept']} kept branch(es) yourself, before any offer "
              "(high: the offers are missing gaps)")
    if s["built"]:
        print(f"  studied since: {s['studied']}/{s['built']} branch(es) built as a piece, a before or a topic")
    if problems:
        print(f"NOT EVALUABLE {len(problems)} unreadable line(s) in branches.jsonl (first: {problems[0]}); "
              "the counts above may be missing some")
        return NOT_EVALUABLE
    return OK
