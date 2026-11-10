"""Branches: every gap found mid-study, who raised it, and what became of it.

A gap is raised by the learner, offered by the tutor in a dialogue, or offered by the tool from
the record (a dialogue's `--broke`/`--next` naming nothing on the syllabus, a turn taught at hint
depth 3 or more, an open question with no concept to land on, a placement miss). Each decision is
one row of branches.jsonl in the home: a piece, learned before, a topic of its own, a note, or
declined. From those rows `ken branch` reads how well the offers are picked: how many offers were
taken, how many branches you raised that nobody offered, and how many branches were studied.
The ratios always print with their counts, and with no offers yet they say so instead of a rate.

Other offer sources plug in as PROVIDERS (below): scouting (kenloop/scouts.py) adds predicted
branches, keyed `scout:N`, and scores them.
"""
from __future__ import annotations

import re

from . import home as H
from . import learn as L
from . import ledger as LG
from . import marks as M
from .errors import NOT_EVALUABLE, OK, NotEvaluable, UsageError

BY = ("learner", "tutor", "tool")
AS = ("piece", "before", "topic", "note", "declined")
PREDICT = ("problem", "solid")
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
    if r.get("predict", "problem") not in PREDICT:
        raise ValueError(f"a branch's prediction is one of {', '.join(PREDICT)}")


def read(cfg) -> tuple:
    """(rows, problems). A line that cannot be read is reported, never skipped in silence."""
    return LG.read(path(cfg), _check)


def append(cfg, topic, concept, gap, by, as_, target="", source="", predict="") -> dict:
    rows, problems = read(cfg)
    if problems:
        raise NotEvaluable(f"{len(problems)} unreadable line(s) in branches.jsonl (first: {problems[0]}); "
                           "nothing appended past the damage")
    if by not in BY:
        raise UsageError(f"--by is required: who raised the gap ({', '.join(BY)}); the offer ratio is "
                         "read from it, so it is never guessed")
    prov = PROVIDERS.get(source.split(":", 1)[0]) if source else None
    if source and prov is None and by != "tool":
        raise UsageError("--source names one of the tool's offers, so --by is tool")
    if prov is not None:                     # a provider's key (scout:N): any --by, checked by its owner
        prov.check_source(cfg, source, rows)
    row = {"date": H.today().isoformat(), "topic": topic, "concept": concept, "gap": (gap or "").strip(),
           "by": by, "as": as_, "target": target, "source": source}
    if predict:
        row["predict"] = predict
    return LG.append(path(cfg), row, _check)


# --- the offers seam: providers outside the core add offers and own their source keys ---------
# A provider is any object with `prefix` (its source keys start "<prefix>:"), `offers(cfg, slug,
# reached_only=True) -> [{source, concept, gap, why}]`, `check_source(cfg, source, rows)` (raise
# UsageError for an unknown or decided key) and `report(cfg, rows, slug) -> [lines]`. Scouting is
# one (kenloop/scouts.py); removing its module removes its offers, keys and report lines.
PROVIDERS: dict = {}


def register_provider(provider) -> None:
    PROVIDERS[provider.prefix] = provider


def provider_offers(cfg, slug, reached_only=True) -> list:
    out = []
    for prov in PROVIDERS.values():
        out += prov.offers(cfg, slug, reached_only)
    return out


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
    out += provider_offers(cfg, slug)
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


def predictions(cfg, rows) -> dict:
    """The predictions written when a piece was added, read against your later marks: a problem
    prediction is right on problem or fuzzy, a solid one on solid, and a solid mark a miss overruled
    reads as a problem. An unmarked piece is not graded."""
    made = [r for r in rows if r.get("predict")]
    graded = right = 0
    for r in made:
        if r["topic"] not in L.topics(cfg):
            continue
        cid = L.canonical(r["target"], L.renames(cfg, r["topic"]))
        m = "problem" if cid in M.overruled(cfg, r["topic"]) else M.current(cfg, r["topic"]).get(cid)
        if m:
            graded += 1
            right += (m in ("problem", "fuzzy")) == (r["predict"] == "problem")
    return {"made": len(made), "graded": graded, "right": right}


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
    p = predictions(cfg, rows)
    if p["made"]:
        print(f"  predictions when a piece was added: {p['made']} made, {p['graded']} marked since, "
              + (f"{p['right']}/{p['graded']} right" if p["graded"] else "none to grade yet"))
    for prov in PROVIDERS.values():
        for line in prov.report(cfg, rows, slug):
            print(line)
    if problems:
        print(f"NOT EVALUABLE {len(problems)} unreadable line(s) in branches.jsonl (first: {problems[0]}); "
              "the counts above may be missing some")
        return NOT_EVALUABLE
    return OK
