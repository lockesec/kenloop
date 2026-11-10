"""On-ramp: the scale a topic is climbed on, where you stand on it, and the pieces a concept is made of.

A topic's `## Path` lists its domains in order, ground first. Each domain is a rung and leans
only on the rungs below it. `place` finds the rung you start on. It asks one open question per
rung: first on the rung you think you stand on, then down until you carry one and up until you
cannot. A partial answer gets a second question. Placement routes study and never earns credit,
so its rows live in placement.jsonl, apart from the log.

Below your start you are probed hard. On it you are taught first (a foundations note, then a
dive), and above it nothing is graded yet. `branch` turns a gap found mid-study into a piece of
the concept (`part-of`), something learned before it (`before`), or a topic of its own that
remembers where it came from. Pieces nest at most two deep: past that, a gap is a topic or a note.
"""
from __future__ import annotations

import re

from . import branches as B
from . import home as H
from . import learn as L
from . import ledger as LG
from .errors import NOT_EVALUABLE, OK, NotEvaluable, UsageError

RESULTS = ("pass", "partial", "miss")
MAX_DEPTH = 2
# The `## Path` grammar and the line > rung > topic settings rule are the kernel's (core/learn.py):
# replay and record read a concept's depth through them. Re-exported here for the on-ramp's callers.
_RUNG = L._RUNG
parse_path = L.parse_path
path_settings = L.path_settings
concept_setting = L.concept_setting


def rungs(cfg, slug) -> list:
    p = L.tdir(cfg, slug) / "syllabus.md"
    return parse_path(H.read_text(p, "syllabus")) if p.exists() else []


def rung_of(c: dict, path: list):
    """A concept's rung: its `rung:` marker when it has one (a foundation that belongs lower than
    its domain), else its domain's place in ## Path."""
    d = L.slugify(c.get("rung") or c.get("domain", ""))
    return path.index(d) if d in path else None


def _file(cfg, slug):
    return L.tdir(cfg, slug) / "placement.jsonl"


def _check(r) -> None:
    H.iso_date(r["date"])
    if not (isinstance(r.get("rung"), int) and r.get("result") in RESULTS
            and isinstance(r.get("probe"), str) and isinstance(r.get("answer"), str)):
        raise ValueError("a placement row needs rung, result, probe and answer")


def read(cfg, slug) -> tuple:
    """(rows, problems). A line that cannot be read is reported, never skipped in silence."""
    return LG.read(_file(cfg, slug), _check)


def standing(rows: list, n: int) -> dict:
    """{start, carried, undecided, feasible, probe, contradiction}. A rung is carried when its
    latest answer passed, not carried on a miss or two partials in a row, undecided on a single
    partial. You start on the lowest rung not carried; with every probed rung carried, on the one
    above the highest.

    A scale is ordered (each rung leans on the ones below), so every answer also narrows where you
    could start (Knowledge Space Theory's placement, as ALEKS uses it): above every carried rung,
    at or below every missed one. `feasible` is that range (lo, hi); `probe` is the rung whose
    answer halves it (an undecided rung first), None once one rung is left. A rung carried above a
    missed one is a `contradiction` (carried, missed): the scale or an answer is off, and asking
    the missed rung again decides which. All of it is inference about where to teach, never
    mastery."""
    by = {}
    for r in rows:
        if 0 <= r["rung"] < n:
            by.setdefault(r["rung"], []).append(r["result"])
    carried = {k for k, v in by.items() if v[-1] == "pass"}
    failed = {k for k, v in by.items() if v[-1] == "miss" or v[-2:] == ["partial", "partial"]}
    undecided = sorted(set(by) - carried - failed)
    if failed:
        start = min(failed)
    elif carried:
        start = min(max(carried) + 1, n - 1)
    else:
        start = None
    lo = min(max(carried) + 1, n - 1) if carried else 0
    hi = min(failed) if failed else n - 1
    contradiction = (max(carried), min(failed)) if carried and failed and max(carried) > min(failed) else None
    feasible = None if (start is None or contradiction) else (lo, hi)
    if undecided:
        probe = undecided[0]
    elif contradiction:
        probe = contradiction[1]
    elif feasible and lo < hi:
        probe = (lo + hi) // 2
    else:
        probe = None
    return {"start": start, "carried": carried, "undecided": undecided, "feasible": feasible,
            "probe": probe if start is not None else None, "contradiction": contradiction}


def placed(cfg, slug, rows: list, n: int) -> dict:
    """standing(), unless the learner CHOSE where to start (`place --start N`, topic.json `start`):
    then the choice is the start and no probe is asked (someone who starts at
    the bottom on purpose wants to learn, not to be tested rung by rung)."""
    st = standing(rows, n)
    s = L.load_config(cfg, slug).get("start")
    if isinstance(s, int) and not isinstance(s, bool) and 0 <= s < n:
        st = {**st, "start": s, "probe": None, "undecided": [], "feasible": None, "contradiction": None,
              "chosen": True}
    return st


def _touched(c: dict) -> bool:
    return bool(c.get("attempts") or c.get("dialogues") or c.get("taught"))


def climbing(cons: dict, path: list, start) -> int | None:
    """The rung you are on: the lowest from your start that has a concept you have not touched."""
    if start is None:
        return None
    for i in range(start, len(path)):
        if any(rung_of(c, path) == i and not _touched(c) for c in cons.values()):
            return i
    return None


def _depth(cons: dict, cid: str) -> int:
    seen, d = set(), 0
    while cons.get(cid, {}).get("part_of") and cid not in seen:
        seen.add(cid)
        cid = cons[cid]["part_of"]
        d += 1
    return d


def _verdict(problems) -> int:
    if problems:
        print(f"NOT EVALUABLE {len(problems)} unreadable line(s) in placement.jsonl (first: {problems[0]}); "
              "the placement above may be missing some")
        return NOT_EVALUABLE
    return OK


PROTOCOL = """\
  How to place (your assistant asks; you answer in your own words, no looking things up):
  1. Say which rung you think you stand on. That is where the first question goes, not the answer.
  2. One open question per rung, a why or a what-if, never multiple choice. "I don't know" is an answer.
  3. After each answer, `place` names the next rung to ask: the one that halves where you could
     still start (a pass rules out the rungs below it, a miss the ones above). A partial: one more
     question there. One rung left, or you stop: that is your start.
  4. After a miss, explain briefly: a failed question still helps the learning that follows.
  5. Record each answer as you go (your words verbatim):
       {prog} place {slug} --rung N --result pass|partial|miss --probe "..." --answer "..."
  Placement earns no credit. It decides where teaching starts and how hard the dialogues push."""


def place(cfg, slug, rung=None, result=None, probe=None, answer=None, start=None, clear_start=False) -> int:
    L.need_topic(cfg, slug)
    path = rungs(cfg, slug)
    if not path:
        raise NotEvaluable(f"{slug} has no scale yet: list its rungs under `## Path` in syllabus.md "
                           "(`0. **domain** — what it covers`, ground first)")
    rows, problems = read(cfg, slug)
    if start is not None or clear_start:
        if rung is not None:
            raise UsageError("--start records where you CHOOSE to start; give it without --rung/--result")
        conf = L.load_config(cfg, slug)
        if clear_start:
            conf.pop("start", None)
        else:
            if not 0 <= start < len(path):
                raise UsageError(f"--start {start} is not on the scale (0-{len(path) - 1})")
            conf["start"] = start
        L.save_config(cfg, slug, conf)
    if rung is not None:
        if problems:
            return _verdict(problems)
        if not 0 <= rung < len(path):
            raise UsageError(f"rung {rung} is not on the scale (0-{len(path) - 1})")
        if result not in RESULTS or not (probe or "").strip() or not (answer or "").strip():
            raise UsageError("a placement answer needs --result pass|partial|miss, --probe and --answer")
        row = {"date": H.today().isoformat(), "rung": rung, "domain": path[rung], "result": result,
               "probe": probe.strip(), "answer": answer.strip()}
        LG.append(_file(cfg, slug), row, _check)
        rows.append(row)
    cons = L.load_state(cfg, slug)["concepts"]
    st = placed(cfg, slug, rows, len(path))
    on = climbing(cons, path, st["start"])
    print(f"place: {L.load_config(cfg, slug).get('title', slug)}, {len(path)} rung(s)"
          + (f"; you chose to start on rung {st['start']} (no probes; `--clear-start` puts placement back)"
             if st.get("chosen") else ""))
    for i, d in enumerate(path):
        n = sum(1 for c in cons.values() if rung_of(c, path) == i)
        mark = ("start" if i == st["start"] else "carried" if i in st["carried"] else
                "one more" if i in st["undecided"] else "")
        here = "  <- climbing" if i == on else ""
        print(f"  {i}  {d:<14} {n:>2} concept(s)  {mark}{here}")
    loose = [cid for cid, c in cons.items() if rung_of(c, path) is None]
    if loose:
        print(f"  {len(loose)} concept(s) on no rung (their domain is not in ## Path): {', '.join(loose[:4])}")
    if st["start"] is None:
        print()
        print(PROTOCOL.format(prog=H.PROG, slug=slug))
    elif st["undecided"]:
        print(f"\n  one more question on rung {st['undecided'][0]} ({path[st['undecided'][0]]}) settles it")
    elif st["contradiction"]:
        hi_c, lo_m = st["contradiction"]
        print(f"\n  your answers disagree: rung {hi_c} ({path[hi_c]}) carried above rung {lo_m} ({path[lo_m]}) missed;"
              f" a scale leans on its lower rungs, so one more question on rung {lo_m} decides which to trust"
              f" (or the scale's order is off). Starting on rung {st['start']} until then.")
    elif st["probe"] is not None:
        lo, hi = st["feasible"]
        k = st["probe"]
        print(f"\n  you could start anywhere on rungs {lo}-{hi}; one question on rung {k} ({path[k]}) halves that"
              f" (a pass: {k + 1}-{hi}; a miss: {lo}-{k}). Starting on rung {st['start']} until then;"
              " stopping here is fine, placement only decides where teaching starts.")
    else:
        print(f"\n  start: rung {st['start']} ({path[st['start']]}). Below it: graded dialogues, pushed hard. "
              f"On it: `{H.PROG} foundations {slug} CONCEPT --scaffold`, then `{H.PROG} dive {slug} CONCEPT`, "
              "then talk. Above it: taught first, not graded yet.")
    return _verdict(problems) if problems else L.log_verdict(cfg, slug)


def next_step(cfg, slug):
    """(argv, reason) for the on-ramp's next move in one topic, or None. A fresh topic with a
    scale is placed first; then the first untaught concept on the rung you are climbing."""
    path = rungs(cfg, slug)
    if not path:
        return None
    cons = L.load_state(cfg, slug)["concepts"]
    rows, _p = read(cfg, slug)
    st = placed(cfg, slug, rows, len(path))
    if st["start"] is None:
        if any(_touched(c) for c in cons.values()):
            return None          # studied before the scale existed: placement is optional there
        return ["place", slug], f"{slug} has a {len(path)}-rung scale and no placement yet"
    if st["probe"] is not None and not any(_touched(c) for c in cons.values()):
        # unsettled and nothing studied yet: one more answer is cheaper now than teaching the wrong rung
        k = st["probe"]
        why = (f"answers disagree about rungs {st['contradiction'][1]} and {st['contradiction'][0]}"
               if st["contradiction"] else
               f"one question on rung {k} settles it" if st["undecided"] else
               f"you could start on rungs {st['feasible'][0]}-{st['feasible'][1]}; rung {k} halves that")
        return ["place", slug], f"{slug} placement: {why} ({path[k]})"
    on = climbing(cons, path, st["start"])
    if on is None:
        return None
    fresh = [k for k, c in cons.items() if rung_of(c, path) == on and not _touched(c)]
    # a concept marked as coming BEFORE an untouched one is taught first: foundations lead
    firsts = [k for k in fresh if cons[k].get("before") in fresh]
    cid = (firsts or fresh)[0]
    if not _note(cfg, slug, cid).exists():
        return ["foundations", slug, cid, "--scaffold"], f"rung {on} ({path[on]}): {cid} has no foundations note yet"
    return ["dive", slug, cid], f"rung {on} ({path[on]}): read the note on {cid}, then go over it together"


def _note(cfg, slug, cid):
    return L.tdir(cfg, slug) / "foundations" / (cid.replace(":", "--") + ".md")


def advice(cfg, slug, cid) -> list:
    """What the on-ramp says about studying this concept now: unplaced, above your rung, on it
    and not yet taught, or made of pieces you have not climbed. Empty when nothing applies."""
    path = rungs(cfg, slug)
    cons = L.load_state(cfg, slug)["concepts"]
    out = []
    pieces = [(k, c) for k, c in cons.items() if c.get("part_of") == cid and k != cid]
    weak = [k for k, c in pieces if L.badge(c) not in ("good", "mastered")]
    if weak:
        out.append(f"made of {len(pieces)} piece(s), {len(weak)} not climbed yet: {', '.join(weak[:3])}; "
                   "climb the pieces first")
    before = [k for k, c in cons.items() if c.get("before") == cid and not _touched(c)]
    if before:
        out.append(f"learn first: {', '.join(before[:3])} (marked as coming before it, not touched yet)")
    if not path:
        return out
    rows, _p = read(cfg, slug)
    st = placed(cfg, slug, rows, len(path))
    r = rung_of(cons.get(cid, {}), path)
    if st["start"] is None:
        if not any(_touched(c) for c in cons.values()):
            out.insert(0, f"not placed yet: `{H.PROG} place {slug}` finds your starting rung before anything is graded")
    elif r is not None and r > st["start"] and not _touched(cons[cid]):
        out.insert(0, f"rung {r} ({path[r]}) is above where you start (rung {st['start']}): teach it first, "
                      f"`{H.PROG} foundations {slug} {cid} --scaffold` then `{H.PROG} dive {slug} {cid}`")
    elif r == st["start"] and not _touched(cons[cid]):
        out.insert(0, f"on your starting rung and not taught yet: read the foundations note and "
                      f"`{H.PROG} dive {slug} {cid}` before a graded dialogue")
    return out


def branch(cfg, slug, frm, line=None, before=False, topic=None, title=None, by=None, gap=None,
           source="", note=None, decline=None, predict="") -> int:
    """A gap found while studying `frm`: a piece of it (default), a concept learned before it
    (--before), with --topic a topic of its own whose origin names where it came from, or only a
    note or a declined offer. Every decision is a row of branches.jsonl, and `by` says who raised it."""
    state = L.load_state(cfg, slug)
    cons = state["concepts"]
    fid = L.resolve_concept(state, frm)
    if by not in B.BY:
        raise UsageError(f"--by is required: who raised the gap ({', '.join(B.BY)}); the offer ratio "
                         "is read from it, so it is never guessed")
    if predict and (topic or note is not None or decline is not None):
        raise UsageError("--predict goes with a piece or a before: only those are concepts you can mark later")
    if note is not None or decline is not None:
        if line or before or topic or (note is not None and decline is not None):
            raise UsageError("--note and --decline record a decision on their own: no syllabus line, "
                             "--before or --topic with them, and not both")
        text, as_ = (note, "note") if note is not None else (decline, "declined")
        B.append(cfg, slug, fid, text, by, as_, source=source)
        print(f"branch: {as_} on {slug}/{fid}, raised by {by}")
        return OK
    if not line or line.count("::") < 2:
        raise UsageError('a branch is one syllabus line: "DOMAIN :: CONCEPT :: DESCRIPTION"')
    parts = [p.strip() for p in line.strip().lstrip("- ").split("::")]
    if topic:
        L.check_slug(topic)
        seed = L.Seed(tag=parts[0], items=[(parts[1], " :: ".join(parts[2:]))])
        code = L.plan(cfg, topic, title=title, origin=f"{slug}/{fid}", seed=seed)
        B.append(cfg, slug, fid, gap or line, by, "topic", target=topic, source=source)
        print(f"branch: {topic} grew from {slug}/{fid}; give it a scale (`## Path`) and `{H.PROG} place {topic}`. "
              f"Its first concept is in domain {parts[0]!r}: make that a rung, or move the line and `{H.PROG} rename` it")
        return code
    if not before and _depth(cons, fid) + 1 > MAX_DEPTH:
        raise UsageError(f"{fid} is already {_depth(cons, fid)} piece(s) deep; a gap below it is a topic of its own "
                         f"(--topic SLUG) or a note (--next on the record), not a third level")
    path = rungs(cfg, slug)
    fr = rung_of(cons[fid], path)
    nr = path.index(L.slugify(parts[0])) if L.slugify(parts[0]) in path else None
    if path and nr is None:
        raise UsageError(f"{parts[0]!r} is not a rung of {slug} ({', '.join(path)}); put the piece on one, "
                         "or add the rung to ## Path first")
    if fr is not None and nr is not None and nr > fr:
        raise UsageError(f"a piece of {fid} (rung {fr}) cannot sit above it on rung {nr}")
    marker = f"before:{fid}" if before else f"part-of:{fid}"
    syl = L.tdir(cfg, slug) / "syllabus.md"
    text = H.read_text(syl, "syllabus")
    if not re.search(r"(?m)^## Concepts\s*$", text):
        raise UsageError(f"{slug}/syllabus.md has no '## Concepts' section")
    new_text = L.insert_concepts(text, [f"- {' :: '.join(parts)} :: {marker}"])
    have = {o["cid"] for o in L.parse_syllabus(text)}
    added = [c for c in L.parse_syllabus(new_text) if c["cid"] not in have]   # a bad line refuses here, before any write
    if not added:
        raise UsageError(f"{line.strip()!r} is not a concept line, or {slug} already has it")
    twin = next((k for k, o in cons.items() if L.slugify(o.get("name", "")) == L.slugify(added[0]["name"])), "")
    if twin:
        raise UsageError(f"{slug}/{twin} already exists; it is the same concept under another domain")
    B.append(cfg, slug, fid, gap or line, by, "before" if before else "piece", target=added[0]["cid"],
             source=source, predict=predict)      # first: a refused row (damaged record) leaves the syllabus as it was
    H.write_text(syl, new_text)
    L.sync(cfg, slug, quiet=True)
    kind = "learned before" if before else "a piece of"
    print(f"branch: {slug}/{added[0]['cid']} is {kind} {fid}")
    return L.log_verdict(cfg, slug)
