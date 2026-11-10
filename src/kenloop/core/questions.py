"""Questions and their ladders: any question can start one.

`ask "why is lithium the best metal for batteries?"` records the question and shows the
concepts already on your map that touch it, so a rung built for one question is reused by the
next instead of written twice. `rung` adds one rung, easiest first: a new concept line in a
topic's syllabus, or an existing concept. `ask` alone lists every question and how far up its
ladder you have climbed. Your assistant proposes rungs; you approve each one.

The record is asks.jsonl in the home: append-only, one event per line, like a topic's log.
"""
from __future__ import annotations

import re

from . import home as H
from . import learn as L
from . import ledger as LG
from .errors import NOT_EVALUABLE, OK, NotEvaluable, UsageError
from .names import slugify

STOP = {"what", "which", "when", "where", "does", "that", "this", "with", "from", "have", "they",
        "their", "there", "about", "would", "could", "should", "best", "most", "some", "into",
        "than", "then", "them", "work", "works"}
CLIMBED = ("good", "mastered")


def path(cfg):
    return cfg.home / "asks.jsonl"


def _check(e) -> None:
    if not isinstance(e, dict) or e.get("event") not in ("ask", "rung"):
        raise ValueError("not an ask or rung event")
    H.iso_date(e["date"])
    if e["event"] == "ask":
        if not (isinstance(e.get("id"), str) and re.fullmatch(r"q[0-9]+", e["id"])
                and isinstance(e.get("question"), str) and e["question"].strip()):
            raise ValueError("an ask needs an id qN and a question")
    elif not all(isinstance(e.get(k), str) and e[k] for k in ("ask", "topic", "concept")):
        raise ValueError("a rung needs ask, topic and concept")


def read(cfg) -> tuple:
    """(events, problems). A line that cannot be read is reported, never skipped in silence."""
    return LG.read(path(cfg), _check)


def _append(cfg, row) -> None:
    LG.append(path(cfg), row, _check)


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP}


def _verdict(problems) -> int:
    if problems:
        print(f"NOT EVALUABLE {len(problems)} unreadable line(s) in asks.jsonl (first: {problems[0]}); "
              "the questions above may be missing some")
        return NOT_EVALUABLE
    return OK


def _badge(cfg, topic, cid) -> str:
    try:
        c = L.load_state(cfg, topic)["concepts"].get(L.canonical(cid, L.renames(cfg, topic)))
    except (NotEvaluable, UsageError):
        return "gone"
    return L.badge(c) if c else "gone"


def ask(cfg, question=None) -> int:
    events, problems = read(cfg)
    asks = [e for e in events if e["event"] == "ask"]
    if not question:
        if not asks:
            print(f'no questions asked yet; `{H.PROG} ask "why is ..."` starts one')
            return _verdict(problems)
        for q in asks:
            rs = [e for e in events if e["event"] == "rung" and e["ask"] == q["id"]]
            print(f"\n  {q['id']}  {q['date']}  {q['question']}")
            if not rs:
                print("      no rungs yet")
                continue
            badges = [_badge(cfg, r["topic"], r["concept"]) for r in rs]
            for r, b in zip(rs, badges):
                print(f"      {b:<8} {r['topic']}/{r['concept']}")
            print(f"      climbed {sum(b in CLIMBED for b in badges)}/{len(rs)} (good or better)")
        return _verdict(problems)
    if problems:      # numbering the next question needs the whole record
        return _verdict(problems)
    qid = f"q{len(asks) + 1}"
    _append(cfg, {"event": "ask", "id": qid, "date": H.today().isoformat(), "question": question.strip()})
    words = _words(question)
    hits = []
    for t in L.topics(cfg):
        try:
            cons = L.load_state(cfg, t)["concepts"]
        except NotEvaluable:
            continue
        for cid, c in cons.items():
            n = len(words & _words(f"{c.get('name', '')} {c.get('desc', '')}"))
            if n:
                hits.append((-n, t, cid, c))
    print(f"{qid}: {question.strip()}")
    if hits:
        print("  already on your map (reuse a rung rather than write a twin):")
        for _n, t, cid, c in sorted(hits)[:8]:
            print(f"    {L.badge(c):<8} {t}/{cid}")
    else:
        print("  nothing on your map touches this yet: the ladder starts from the ground")
    print(f"""
  Build the ladder (your assistant proposes, you approve every rung):
  1. First say your own answer now, and how sure you are. It shows where the ladder starts.
  2. Rungs from the ground up, one concept each, easiest first. A rung may belong to another
     topic (chemistry under batteries): plan that topic if it is missing (`{H.PROG} plan T`).
  3. Reuse a rung already on the map instead of writing a twin.
  4. Mark what humanity knows (`:: status:frontier` or `open`): "best" is often a trade-off.
  5. Add each approved rung in order:
       {H.PROG} rung {qid} TOPIC "DOMAIN :: CONCEPT :: DESCRIPTION"
       {H.PROG} rung {qid} TOPIC --existing CONCEPT-ID""")
    return OK


def rung(cfg, qid, topic, line=None, existing=None) -> int:
    events, problems = read(cfg)
    if problems:
        return _verdict(problems)
    if not any(e["event"] == "ask" and e["id"] == qid for e in events):
        raise UsageError(f"no question {qid!r}; `{H.PROG} ask` lists them")
    state = L.load_state(cfg, topic)
    if existing:
        cid = L.resolve_concept(state, existing)
    else:
        if not line or line.count("::") < 2:
            raise UsageError('a rung is one syllabus line: "DOMAIN :: CONCEPT :: DESCRIPTION" (or --existing ID)')
        syl = L.tdir(cfg, topic) / "syllabus.md"
        text = H.read_text(syl, "syllabus") if syl.exists() else ""
        if not re.search(r"(?m)^## Concepts\s*$", text):
            raise UsageError(f"{topic}/syllabus.md has no '## Concepts' section")
        new_text = L.insert_concepts(text, ["- " + line.strip().lstrip("- ")])
        added = [c for c in L.parse_syllabus(new_text) if c["cid"] not in
                 {o["cid"] for o in L.parse_syllabus(text)}]     # a bad line refuses here, before any write
        if not added:
            raise UsageError(f"{line.strip()!r} is not a concept line, or {topic} already has it")
        c = added[0]
        twin = next((k for k, o in state["concepts"].items() if slugify(o.get("name", "")) == slugify(c["name"])), "")
        if twin:     # the same concept under another domain is still a twin
            raise UsageError(f"{topic}/{twin} already exists; reuse it with --existing {twin}")
        H.write_text(syl, new_text)
        L.sync(cfg, topic, quiet=True)
        cid = c["cid"]
    _append(cfg, {"event": "rung", "ask": qid, "date": H.today().isoformat(), "topic": topic, "concept": cid})
    print(f"{qid} <- rung {topic}/{cid}")
    return OK
