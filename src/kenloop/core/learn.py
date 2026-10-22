"""The learn arm: topics, concepts, a question bank, and a record of every attempt.

A topic lives in ``HOME/topics/<slug>/``:

    topic.json     settings you set (title, goal, origin, outlets, exam_date)
    syllabus.md    the concepts, one line each, under a "## Concepts" heading:
                   - <domain> :: <name> :: <description> [:: cluster:<id>] [:: scope:exam|depth]
    questions.md   the bank, a "## <concept id>" section per concept
    log.jsonl      one line per attempt, append-only: THE RECORD
    concepts.json  mastery and schedule, DERIVED from the log (``rebuild``)

Credit is strict on purpose. A correct answer earns streak, retention and
breadth credit only when it was UNAIDED: not a guess, no hint, not read off
the page, not in a massed "learn" pass. A correct you were unsure of
(``--confidence low``) still earns credit but is reviewed sooner.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass

from . import fsrs
from . import home as H
from .errors import (
    DRIFT,
    FINDINGS,
    NOT_EVALUABLE,
    OK,
    Drifted,
    NotEvaluable,
    UsageError,
)
from .names import slugify

RESULTS = ("ok", "partial", "miss")
CONFIDENCE = ("low", "med", "high")

# A dialogue shows understanding by reasoning, not recall: can you build the idea, run it
# forward, defend it and say where it stops? Each move is scored 0-2 only when it was probed;
# an unprobed move is absent, never a 0. `question` grades curiosity: asking, not only answering.
REASONING_MOVES = {
    "chain": "builds the causal chain: why it happens, not just what",
    "predict": "runs the idea forward on a case not seen before",
    "pushback": "holds a sound claim under challenge, or revises a weak one for a reason",
    "limits": "says where the idea stops: what is settled, open or unknown",
    "connect": "links it to another idea with an analogy or contrast that carries",
    "question": "asks a question that goes deeper, or notices what does not fit",
}
RUBRIC_MIN_MOVES = 3          # fewer probed moves is a chat, not an assessment
BELIEF_FIELDS = ("before", "after", "after_confidence", "held", "broke", "next", "claude_wrong")
# What humanity knows about a concept, separate from what you know (syllabus `:: status:`).
# Unmarked is its own state: no mark is not a claim that the matter is settled.
STATUSES = {
    "settled": "textbook and tested: you should be able to defend it",
    "frontier": "active research: the evidence is partial, and saying so earns credit",
    "open": "nobody knows yet: reasoning about the candidate answers earns credit; "
            "calling it solved is a 0 on limits",
}
MODES = ("practice", "exam", "diagnose", "learn", "dialogue")
QTYPES = ("recall", "applied", "edge", "comparison", "debugging")
ETYPES = ("term-confusion", "concept-conflation", "wrong-scope", "detail-slip", "misapplication", "other")
TESTED_BY = {"term-confusion": {"recall"}, "detail-slip": {"recall"},
             "concept-conflation": {"comparison"}, "wrong-scope": {"comparison"},
             "misapplication": {"applied"}}
RESOLVES_ALL = {"edge", "debugging"}
MAX_SLUG = 64
CONFIG_KEYS = ("title", "goal", "origin", "exam_date")      # text
# Where what you learn in a topic may go besides your own head. None is the normal case:
# studied for its own sake. "career": it may graduate into facts.md. "cert": toward an exam.
OUTLETS = ("career", "cert")
# kind "interest": a topic studied for its own sake (math, history, a science). Same quizzes,
# schedule and record as any topic; it is never tied to job demand and never graduates into
# facts.md. A topic with no kind is a career topic.
IDENTITY = ("name", "domain", "desc", "cluster", "scope", "status")
MASTERY_FIELDS = ("attempts", "correct", "streak", "partials", "guesses", "hints", "correct_days",
                  "errors", "resolved_idx", "by_type", "by_conf", "last_seen", "stability",
                  "difficulty", "interval", "due", "exam_clamp", "dialogues", "by_reasoning", "repeats")
RETENTION_DAYS = 2
INTERFERENCE_OTHERS = 3
BREADTH_TYPES, BREADTH_RATE = 2, 0.6
REASK = {"term-confusion": "ask for the term from its definition, then contrast it with its look-alike",
         "concept-conflation": "ask a comparison: when does each apply, and why not the other",
         "wrong-scope": "ask where the idea stops applying",
         "detail-slip": "ask for the exact detail, cold",
         "misapplication": "give a scenario and ask which to use",
         "other": "rephrase the question and ask again"}


# --- files ------------------------------------------------------------------

def tdir(cfg, slug):
    return cfg.topics / slug


def topics(cfg) -> list:
    if not cfg.topics.is_dir():
        return []
    return sorted(d.name for d in cfg.topics.iterdir() if (d / "syllabus.md").exists()
                  or (d / "topic.json").exists())


def need_topic(cfg, slug):
    if not tdir(cfg, slug).is_dir():
        known = ", ".join(topics(cfg)) or "none yet"
        raise UsageError(f"no topic {slug!r} (topics: {known}); create it with `{H.PROG} plan`")


def load_config(cfg, slug) -> dict:
    """Topic settings. A damaged topic.json is NOT EVALUABLE and is never
    overwritten: it may hold the only copy of your exam date."""
    data = H.read_json(tdir(cfg, slug) / "topic.json", "topic settings")
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'} is not a JSON object; fix it by hand")
    for k in CONFIG_KEYS:
        if k in data and not isinstance(data[k], str):
            raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'}: `{k}` must be text, not "
                               f"{type(data[k]).__name__}; fix it by hand")
    o = data.get("outlets", [])
    if not isinstance(o, list) or not all(x in OUTLETS for x in o):
        raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'}: `outlets` must be a list of "
                           f"{', '.join(OUTLETS)}; fix it by hand")
    return data


def save_config(cfg, slug, conf: dict) -> None:
    load_config(cfg, slug)          # refuses over a damaged file
    out = {k: conf[k] for k in CONFIG_KEYS if k in conf}
    if conf.get("outlets"):
        out["outlets"] = [o for o in OUTLETS if o in conf["outlets"]]
    H.write_json(tdir(cfg, slug) / "topic.json", out)


def has_outlet(conf: dict, name: str) -> bool:
    return name in conf.get("outlets", [])


def exam_date(conf: dict):
    try:
        return _dt.date.fromisoformat(conf.get("exam_date") or "")
    except ValueError:
        return None


def load_state(cfg, slug) -> dict:
    need_topic(cfg, slug)
    data = H.read_json(tdir(cfg, slug) / "concepts.json", "concept state")
    if data is None:
        return {"concepts": {}}
    if (not isinstance(data, dict) or not isinstance(data.get("concepts"), dict)
            or not all(isinstance(c, dict) for c in data["concepts"].values())):
        raise NotEvaluable(f"{tdir(cfg, slug) / 'concepts.json'} is damaged; `{H.PROG} rebuild {slug}`")
    return data


def save_state(cfg, slug, state) -> None:
    H.write_json(tdir(cfg, slug) / "concepts.json", state)


# --- grammars -----------------------------------------------------------------

def name_slug(name: str) -> str:
    """Injective enough for skill names: "c++", "c#" and "c" stay distinct."""
    n = name.replace("++", " plus plus ").replace("+", " plus ").replace("#", " sharp ").replace(".", " dot ")
    return slugify(n)


def concept_id(domain: str, name: str) -> str:
    return f"{slugify(domain)}:{name_slug(name)}" if domain else name_slug(name)


def parse_syllabus(text: str) -> list:
    """Concept lines under the "## Concepts" heading. An unknown scope refuses
    the whole parse rather than guessing."""
    out, inside = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "concepts"
            continue
        if not inside or not line.lstrip().startswith("-") or "::" not in line:
            continue
        parts = [p.strip() for p in line.lstrip()[1:].split("::")]
        c = {"domain": parts[0], "name": parts[1] if len(parts) > 1 else "", "desc": "",
             "cluster": "", "scope": "exam", "status": ""}
        desc = []
        for p in parts[2:]:
            key, _, val = p.partition(":")
            if key in ("cluster", "scope", "status") and val and " " not in key:
                if key == "scope" and val not in ("exam", "depth"):
                    raise UsageError(f"syllabus line {n}: unknown scope {val!r} (exam or depth)")
                if key == "status" and val.strip().lower() not in STATUSES:
                    raise UsageError(f"syllabus line {n}: unknown status {val!r} ({', '.join(STATUSES)})")
                c[key] = slugify(val) if key == "cluster" else val.strip().lower() if key == "status" else val
            else:
                desc.append(p)
        c["desc"] = " :: ".join(desc)
        if not c["name"] or c["name"] == "(concept)":
            continue
        c["cid"] = concept_id(c["domain"], c["name"])
        if any(o["cid"] == c["cid"] for o in out):
            raise UsageError(f"syllabus line {n}: {c['name']!r} gives concept id {c['cid']!r}, "
                             "which an earlier line already has; rename one")
        out.append(c)
    return out


def parse_questions(text: str) -> dict:
    """{concept id: [question]}. Each question: q, a, why, ref, type,
    d = [(option, misconception)], provenance."""
    bank: dict = {}
    cid, q = None, None
    fields = {"A": "a", "Why": "why", "Ref": "ref", "Type": "type", "Provenance": "provenance"}
    for line in text.splitlines():
        if line.startswith("## "):
            cid, q = line[3:].strip(), None
            bank.setdefault(cid, [])
            continue
        if cid is None:
            continue
        if line.startswith("### Q:"):
            q = {"q": line[6:].strip(), "a": "", "why": "", "ref": "", "type": "", "d": [],
                 "provenance": ""}
            bank[cid].append(q)
            continue
        m = re.match(r"^\s*-\s+\*\*(\w+):\*\*\s*(.*)$", line)
        if q is None or not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key == "D":
            opt, _, why = val.partition("::")
            q["d"].append((opt.strip(), why.strip()))
        elif key in fields:
            q[fields[key]] = val
    return bank


def load_bank(cfg, slug) -> dict:
    p = tdir(cfg, slug) / "questions.md"
    return parse_questions(H.read_text(p, "question bank")) if p.exists() else {}


# --- the log and the credit rules ---------------------------------------------

def read_log(cfg, slug) -> tuple:
    """(rows, problems). An undecodable line or a row with no valid date is
    reported and skipped; it is never replayed at today's date."""
    rows, problems = [], []
    p = tdir(cfg, slug) / "log.jsonl"
    if not p.exists():
        return rows, problems
    try:
        lines = [(n, ln) for n, ln in enumerate(p.read_bytes().decode("utf-8").splitlines(), 1)]
    except UnicodeDecodeError:                    # decode line by line so only the bad rows are lost
        lines = []
        for n, raw in enumerate(p.read_bytes().split(b"\n"), 1):
            try:
                lines.append((n, raw.decode("utf-8").rstrip("\r")))
            except UnicodeDecodeError as e:
                problems.append(f"log.jsonl line {n}: not UTF-8 (byte 0x{e.object[e.start]:02x} at offset {e.start})")
                lines.append((n, ""))
    for n, line in lines:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            _check_row(r)
        except (ValueError, KeyError, TypeError) as e:
            problems.append(f"log.jsonl line {n}: {type(e).__name__} {e}")
            continue
        rows.append(r)
    return rows, problems


def _check_row(r) -> None:
    """Raise if a log row's fields cannot be applied exactly as `record` would."""
    if not isinstance(r, dict):
        raise TypeError("row is not an object")
    H.iso_date(r["date"])
    if not isinstance(r.get("concept"), str) or not r["concept"]:
        raise KeyError("concept")
    if "result" in r and r["result"] not in RESULTS:
        raise ValueError(f"result {r['result']!r}")
    if "result" not in r and not isinstance(r.get("correct"), bool):
        raise ValueError("neither result nor correct")
    hd = r.get("hint_depth", 0)
    if isinstance(hd, bool) or not isinstance(hd, int) or not 0 <= hd <= 4:
        raise ValueError(f"hint_depth {hd!r}")
    for k, allowed in (("confidence", CONFIDENCE), ("mode", MODES), ("qtype", QTYPES), ("etype", ETYPES)):
        v = r.get(k, "")
        if v not in ("",) + tuple(allowed):
            raise ValueError(f"{k} {v!r}")
    if not isinstance(r.get("guess", False), bool) or not isinstance(r.get("note", ""), str):
        raise ValueError("guess/note type")
    if r.get("mode") == "dialogue":
        rubric = check_rubric(r.get("rubric"))
        if r.get("result") != rubric_result(rubric):
            raise ValueError(f"result {r.get('result')!r} is not the rubric's {rubric_result(rubric)!r}")
        if not isinstance(r.get("grader"), str) or not r["grader"].strip():
            raise ValueError("a dialogue row names no grader")
        if not all(isinstance(r.get(k, ""), str) for k in BELIEF_FIELDS) or not (
                isinstance(r.get("open", []), list) and all(isinstance(q, str) for q in r.get("open", []))):
            raise ValueError("belief/open field type")
        t = r.get("transcript")
        if t is not None and not (isinstance(t, str) and re.fullmatch(r"dialogues/[a-z0-9][a-z0-9._-]*\.md", t)
                                  and isinstance(r.get("transcript_sha256"), str)):
            raise ValueError(f"transcript {t!r} (a file under dialogues/, with its sha256)")
    elif "rubric" in r:
        raise ValueError("a rubric on a row that is not a dialogue")


def check_rubric(rubric) -> dict:
    """A rubric as stored: {move: 0|1|2}, known moves only, at least RUBRIC_MIN_MOVES probed."""
    if not isinstance(rubric, dict) or not all(
            k in REASONING_MOVES and isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 2
            for k, v in rubric.items()):
        raise ValueError(f"rubric {rubric!r}")
    if len(rubric) < RUBRIC_MIN_MOVES:
        raise ValueError(f"rubric has {len(rubric)} probed move(s), fewer than {RUBRIC_MIN_MOVES}")
    return rubric


def parse_rubric(text: str) -> dict:
    """'chain=2,predict=1,limits=2' as typed on the command line."""
    out = {}
    for part in (text or "").split(","):
        if not part.strip():
            continue
        k, _, v = part.partition("=")
        k = k.strip().lower()
        if k not in REASONING_MOVES:
            raise UsageError(f"unknown reasoning move {k!r} (moves: {', '.join(REASONING_MOVES)})")
        if v.strip() not in ("0", "1", "2"):
            raise UsageError(f"move {k!r} needs a score 0-2, got {v.strip()!r}")
        out[k] = int(v)
    if len(out) < RUBRIC_MIN_MOVES:
        raise UsageError(f"a dialogue grade needs at least {RUBRIC_MIN_MOVES} probed moves, got {len(out)}; "
                         "probe more, or record it as a quiz")
    return out


def rubric_result(rubric: dict) -> str:
    """The one rule from scores to verdict: the grader gives the scores, this gives the result.
    ok: mean >= 1.5 and no move at 0. partial: mean >= 0.75. Otherwise miss."""
    mean = sum(rubric.values()) / len(rubric)
    if mean >= 1.5 and min(rubric.values()) > 0:
        return "ok"
    return "partial" if mean >= 0.75 else "miss"


def add_reasoning(c: dict, rubric: dict) -> None:
    br = c.setdefault("by_reasoning", {})
    for k, v in rubric.items():
        m = br.setdefault(k, {"probed": 0, "points": 0})
        m["probed"] += 1
        m["points"] += v


def reasoning_means(c: dict) -> dict:
    """Mean score per probed move; a move never probed is absent."""
    return {k: m["points"] / m["probed"] for k, m in (c.get("by_reasoning") or {}).items() if m.get("probed")}


def open_errors(c: dict) -> list:
    closed = set(c.get("resolved_idx", []))
    return [(i, e) for i, e in enumerate(c.get("errors", [])) if i not in closed]


def etype_of(entry: str) -> str:
    m = re.match(r"^\d{4}-\d{2}-\d{2}: \[([a-z-]+)\] ", entry)
    return m.group(1) if m else ""


def signature(entry: str) -> str:
    s = re.sub(r"^\d{4}-\d{2}-\d{2}: ", "", entry)
    s = re.sub(r"^\[[a-z-]+\] ", "", s)
    return re.sub(r"\s+", " ", s.lower()).strip()


def _resolve_errors(c: dict, qtype: str) -> None:
    for i, e in open_errors(c):
        et = etype_of(e) or "other"
        if et == "other" or qtype in RESOLVES_ALL or qtype in TESTED_BY.get(et, ()):
            c.setdefault("resolved_idx", []).append(i)


def facets(row: dict) -> dict:
    """The derived flags every reader of the log must agree on."""
    ok = row.get("result", "ok" if row.get("correct") else "miss") == "ok"
    guess = bool(row.get("guess")) and ok
    conf = row.get("confidence")
    if conf is None:
        conf = "low" if row.get("guess") else ""
    depth = int(row.get("hint_depth", 0) or 0)
    massed = row.get("mode", "practice") == "learn"
    dialogue = row.get("mode") == "dialogue"
    return {"ok": ok, "guess": guess, "conf": conf, "depth": depth, "assisted": depth > 0,
            "massed": massed, "dialogue": dialogue,
            "unaided_ok": ok and not guess and depth == 0 and not massed and not dialogue,
            "effortful": ok and conf == "low" and not guess}


def repeats(rows) -> list:
    """For each row (in the order given), whether an earlier row that day was on the same concept.
    Only the first look at a concept on a day can be a fresh retrieval: after a quiz, a miss, a
    hint, a dialogue or a read-through, the learner has seen it."""
    seen, out = set(), []
    for r in rows:
        key = (r["date"], r["concept"])
        out.append(key in seen)
        seen.add(key)
    return out


def apply_row(c: dict, row: dict, exam, repeat=False) -> None:
    """The one code path from an attempt to state: `record` and `rebuild` both call it."""
    f = facets(row)
    day = row["date"]
    if repeat and not f["dialogue"]:
        c["repeats"] = c.get("repeats", 0) + 1
    if repeat and not f["dialogue"] and f["ok"]:
        # A correct repeat is counted, never credited: no streak, retention day, breadth, confidence
        # or schedule. A miss or partial on a repeat counts against you as usual (below): being
        # shown it and still getting it wrong is honest evidence, however soon it comes.
        c["attempts"] = c.get("attempts", 0) + 1
        c["correct"] = c.get("correct", 0) + f["ok"]
        c["partials"] = c.get("partials", 0) + (row.get("result") == "partial")
        c["last_seen"] = day
        if not f["ok"] and row.get("note"):
            et = row.get("etype") or ""
            c.setdefault("errors", []).append(f"{day}: " + (f"[{et}] " if et else "") + row["note"])
        return
    if f["dialogue"]:
        # A dialogue is graded by an assistant, so it is evidence of reasoning, kept apart from
        # quiz evidence: it never moves the streak, the retention days, breadth or the review
        # schedule, so it can never graduate a skill into facts.md. A miss it exposes is kept
        # as a misconception, which an unaided quiz pass later resolves.
        c["dialogues"] = c.get("dialogues", 0) + 1
        add_reasoning(c, row["rubric"])
        if not f["ok"] and row.get("note"):
            et = row.get("etype") or ""
            c.setdefault("errors", []).append(f"{day}: " + (f"[{et}] " if et else "") + row["note"])
        return
    result = row.get("result", "ok" if row.get("correct") else "miss")
    c["attempts"] = c.get("attempts", 0) + 1
    c["correct"] = c.get("correct", 0) + f["ok"]
    c["partials"] = c.get("partials", 0) + (result == "partial")
    c["streak"] = c.get("streak", 0) + 1 if f["unaided_ok"] else 0
    c["guesses"] = c.get("guesses", 0) + f["guess"]
    c["hints"] = c.get("hints", 0) + f["assisted"]
    c["last_seen"] = day
    if f["unaided_ok"] and day not in c.setdefault("correct_days", []):
        c["correct_days"].append(day)
    if not f["ok"] and row.get("note"):
        et = row.get("etype") or ""
        c.setdefault("errors", []).append(f"{day}: " + (f"[{et}] " if et else "") + row["note"])
    qt = row.get("qtype") or ""
    if qt:
        bt = c.setdefault("by_type", {}).setdefault(qt, {"attempts": 0, "correct": 0})
        bt["attempts"] += 1
        bt["correct"] += f["unaided_ok"]
    if f["conf"] and not f["assisted"] and not f["massed"] and not repeat:
        bc = c.setdefault("by_conf", {}).setdefault(f["conf"], {"attempts": 0, "correct": 0})
        bc["attempts"] += 1
        bc["correct"] += f["ok"]
    if f["unaided_ok"]:
        _resolve_errors(c, qt)
    if not f["ok"] or f["guess"] or f["assisted"] or f["massed"]:
        g = fsrs.AGAIN
    elif f["effortful"]:
        g = fsrs.HARD
    else:
        g = fsrs.GOOD
    fsrs.update(c, g, _dt.date.fromisoformat(day), exam)


def badge(c: dict) -> str:
    if not c.get("attempts"):
        return "new"
    return ("weak", "fair", "good")[c["streak"]] if c.get("streak", 0) < 3 else "mastered"


def mastery_view(c: dict) -> dict:
    return {k: c[k] for k in MASTERY_FIELDS if c.get(k) not in (None, "", 0, [], {})}


def replay(cfg, slug, state) -> tuple:
    """(new state, problems): identity from `state`, mastery from the log only.
    Rows are applied in stable date order, so merged logs rebuild identically."""
    rows, problems = read_log(cfg, slug)
    exam = exam_date(load_config(cfg, slug))
    new = {k: v for k, v in state.items() if k != "concepts"}
    new["concepts"] = {cid: {k: v for k, v in c.items() if k not in MASTERY_FIELDS}
                       for cid, c in state["concepts"].items()}
    syl = tdir(cfg, slug) / "syllabus.md"
    if syl.exists():                  # a lost concepts.json rebuilds from syllabus + log
        for c in parse_syllabus(H.read_text(syl, "syllabus")):
            new["concepts"].setdefault(c["cid"], {k: c[k] for k in IDENTITY})
    ordered = sorted(rows, key=lambda r: r["date"])
    for r, rep in zip(ordered, repeats(ordered)):
        c = new["concepts"].get(r["concept"])
        if c is None:
            problems.append(f"log row for unknown concept {r['concept']!r} ({r['date']}) skipped")
            continue
        apply_row(c, r, exam, rep)
    return new, problems


def audit(cfg, slug, state=None) -> tuple:
    """(drifted concept ids, replay problems). Compares the UNION of stored and
    replayed concepts, so a concept dropped from concepts.json is drift too.
    Any replay problem means the record was not read in full: the caller must
    treat the comparison as NOT EVALUABLE, not as clean."""
    state = state or load_state(cfg, slug)
    new, problems = replay(cfg, slug, state)
    ids = set(state["concepts"]) | set(new["concepts"])
    drifted = sorted(cid for cid in ids if mastery_view(state["concepts"].get(cid, {}))
                     != mastery_view(new["concepts"].get(cid, {})))
    return drifted, problems


def drift(cfg, slug, state=None) -> list:
    return audit(cfg, slug, state)[0]


def resolve_concept(state, ref: str) -> str:
    cons = state["concepts"]
    if ref in cons:
        return ref
    for pool in ([c for c in cons if c.startswith(ref)],
                 [c for c in cons if ref.lower() in c.lower() or ref.lower() == cons[c].get("name", "").lower()]):
        if len(pool) == 1:
            return pool[0]
        if len(pool) > 1:
            raise UsageError(f"{ref!r} matches {len(pool)} concepts: {', '.join(sorted(pool)[:8])}{', ...' if len(pool) > 8 else ''}")
    raise UsageError(f"no concept matches {ref!r}")


def dialogue_path(cfg, slug, cid, day):
    """Where one dialogue's transcript is kept: the evidence behind its grade."""
    return tdir(cfg, slug) / "dialogues" / f"{day}-{slugify(cid)}.md"


def open_target(cons, text, default):
    """(concept, question) for one open question: "CONCEPT :: question" names its own concept,
    anything else belongs to the dialogue's concept."""
    head, sep, q = text.partition(" :: ")
    return (head, q) if sep and head in cons else (default, text)


def _open_entry(state, text) -> str:
    """An --open value as stored: a "CONCEPT :: question" prefix is resolved to the concept's id,
    or refused, so a typo never attaches a question to the wrong concept."""
    head, sep, q = text.partition(" :: ")
    if not sep:
        return text
    try:
        cid = resolve_concept(state, head.strip())
    except UsageError as e:
        raise UsageError(f"--open {text!r}: {e} (write \"CONCEPT :: question\", or no prefix for this concept)") from e
    return f"{cid} :: {q.strip()}"


def _dialogue_fields(cfg, slug, cid, result, mode, qtype, rubric, grader, belief, open_questions, state=None) -> dict:
    """The extra row fields of a dialogue, checked; {} for a quiz attempt (which may carry none)."""
    belief = {k: str(v).strip() for k, v in (belief or {}).items() if v and str(v).strip()}
    open_questions = [q.strip() for q in open_questions or () if q and q.strip()]
    if state is not None:
        open_questions = [_open_entry(state, q) for q in open_questions]
    unknown = set(belief) - set(BELIEF_FIELDS)
    if unknown:
        raise UsageError(f"unknown belief field(s): {', '.join(sorted(unknown))}")
    if mode != "dialogue":
        if rubric or grader or belief or open_questions:
            raise UsageError("--rubric, --grader, the belief options and --open are for --mode dialogue only")
        return {}
    if not rubric:
        raise UsageError("a dialogue is graded by its rubric: give --rubric move=score,...")
    if qtype:
        raise UsageError("--qtype is for quiz attempts; a dialogue is graded by its rubric")
    want = rubric_result(rubric)
    if result != want:
        raise UsageError(f"the rubric grades this {want!r}, not {result!r}: the verdict is the rubric's rule; "
                         "change the scores if they are wrong")
    grader = (grader or os.environ.get("KENLOOP_GRADER", "")).strip()
    if not grader:
        raise UsageError("a dialogue grade is a judgement: name who made it (--grader MODEL, or KENLOOP_GRADER)")
    if bool(belief.get("before")) != bool(belief.get("after")):
        raise UsageError("give both --before and --after: a belief with one end is not a change you can read")
    if belief.get("after_confidence", "") not in ("",) + CONFIDENCE:
        raise UsageError(f"--after-confidence {belief['after_confidence']!r} is not one of {', '.join(CONFIDENCE)}")
    out = {"rubric": rubric, "grader": grader, **belief}
    if open_questions:
        out["open"] = open_questions
    t = dialogue_path(cfg, slug, cid, H.today().isoformat())
    if t.exists():
        out["transcript"] = t.relative_to(tdir(cfg, slug)).as_posix()
        out["transcript_sha256"] = hashlib.sha256(t.read_bytes()).hexdigest()
    return out


def graded_copy(cfg, slug, transcript: str):
    """The copy of a transcript kept as it was when graded: dialogues/.graded/NAME."""
    return tdir(cfg, slug) / "dialogues" / ".graded" / transcript.split("/", 1)[1]


def record(cfg, slug, concept, result, note="", guess=False, confidence="", hint_depth=0,
           lookup=False, mode="practice", qtype="", etype="", quiet=False, rubric=None, grader="",
           belief=None, open_questions=()) -> dict:
    if result not in RESULTS:
        raise UsageError(f"result must be one of {', '.join(RESULTS)}")
    for val, allowed, what in ((confidence, CONFIDENCE, "--confidence"), (mode, MODES, "--mode"),
                               (qtype, QTYPES, "--qtype"), (etype, ETYPES, "--etype")):
        if val and val not in allowed:
            raise UsageError(f"{what} {val!r} is not one of {', '.join(allowed)}")
    hint_depth = 0 if hint_depth is None else hint_depth
    if isinstance(hint_depth, bool) or not isinstance(hint_depth, int) or not 0 <= hint_depth <= 4:
        raise UsageError(f"--hint-depth {hint_depth!r} is outside 0-4 (0 = no hint, 4 = read the answer)")
    state = load_state(cfg, slug)
    cid = resolve_concept(state, concept)
    extra = _dialogue_fields(cfg, slug, cid, result, mode, qtype, rubric, grader, belief, open_questions, state)
    ok = result == "ok"
    depth = 4 if lookup else hint_depth
    row = {"date": H.today().isoformat(), "concept": cid, "correct": ok, "result": result,
           "guess": bool(guess) and ok, "qtype": qtype or "", "etype": etype or "",
           "confidence": confidence or ("low" if guess else ""), "hint_depth": depth,
           "mode": mode or "practice", "note": note or "", **extra}
    c = state["concepts"][cid]
    earlier, _ = read_log(cfg, slug)
    repeat = any(r["date"] == row["date"] and r["concept"] == cid for r in earlier)
    if not repeat and not extra and mode not in ("learn",):
        qs = load_bank(cfg, slug).get(cid, [])
        if ok and not qs and facets(row)["unaided_ok"]:
            H.warn(f"warn: {cid} has no banked question, so this credit rests on a question asked off the record; "
                   f"bank it (`{H.PROG} bank {slug} {cid} ...`) so the evidence can be read back")
        types = {q.get("type") for q in qs if q.get("type")}
        if qtype and types and qtype not in types:
            H.warn(f"warn: --qtype {qtype} matches none of {cid}'s banked questions ({', '.join(sorted(types))}); "
                   "record the type of the question you actually asked")
    apply_row(c, row, exam_date(load_config(cfg, slug)), repeat)
    with open(tdir(cfg, slug) / "log.jsonl", "a", encoding="utf-8") as fh:   # the log first
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if row.get("transcript"):           # kept as graded, so a later change can be seen and undone
        g = graded_copy(cfg, slug, row["transcript"])
        H.write_bytes(g, (tdir(cfg, slug) / row["transcript"]).read_bytes())
    if any(r["date"] > row["date"] for r in earlier):
        # back-dated (clock skew between machines): state must be the date-ordered replay
        state, _p = replay(cfg, slug, state)
        c = state["concepts"][cid]
    save_state(cfg, slug, state)
    d, probs = audit(cfg, slug, state)
    if d or probs:
        H.warn(f"DRIFT: {len(d)} concept(s) disagree with the log, {len(probs)} log problem(s); "
               f"`{H.PROG} rebuild {slug} --check`")
    if quiet:
        return row
    if extra:
        means = reasoning_means(c)
        weak = min(means, key=lambda k: (means[k], k))
        print(f"{cid}: dialogue {result}, graded by {extra['grader']}; reasoning "
              + "  ".join(f"{k} {v:.1f}/2" for k, v in sorted(means.items()))
              + f"; push on: {weak} (reasoning is kept apart from quiz credit)")
    elif repeat:
        print(f"{cid}: {result}, counted; seen already today, so no credit → {badge(c)} "
              f"(streak {c.get('streak', 0)}), next review {c.get('due') or 'not scheduled'}")
    else:
        print(f"{cid}: {result} → {badge(c)} (streak {c.get('streak', 0)}), next review {c['due']}"
              + (f" [{c['exam_clamp']}]" if c.get("exam_clamp") else ""))
    return row


# --- plan / sync / bank ----------------------------------------------------------

SYLLABUS = """# {title}

Goal: {goal}

One concept per line under the Concepts heading:
- <domain> :: <name> :: <what it covers> [:: cluster:<id>] [:: scope:exam|depth] [:: status:settled|frontier|open]

## Concepts

"""


def sync(cfg, slug, quiet=False) -> int:
    need_topic(cfg, slug)
    p = tdir(cfg, slug) / "syllabus.md"
    parsed = parse_syllabus(H.read_text(p, "syllabus") if p.exists() else "")
    state = load_state(cfg, slug)
    added = 0
    for c in parsed:
        cur = state["concepts"].get(c["cid"])
        if cur is None:
            added += 1
            cur = state["concepts"][c["cid"]] = {}
        for k in IDENTITY:
            if c.get(k) or k in ("desc", "scope", "status"):
                cur[k] = c.get(k, "")
    save_state(cfg, slug, state)
    d = drift(cfg, slug, state)
    if d:
        H.warn(f"DRIFT: {len(d)} concept(s) disagree with the log; `{H.PROG} rebuild {slug} --check`")
    if not quiet:
        print(f"{slug}: {len(parsed)} concept(s) in the syllabus, {added} new")
    return log_verdict(cfg, slug)       # the drift check above read a log that may be damaged


@dataclass
class Seed:
    """Concepts offered to a new or existing topic by something outside study (a sidecar).
    `tag` is the domain the concept lines get; `items` are (term, description) pairs."""
    tag: str
    items: list


def check_slug(slug) -> None:
    if not slug or slug != slugify(slug):
        raise UsageError(f"topic slug {slug!r} should be {slugify(slug)!r}" if slug
                         else "the topic slug must not be empty")
    if len(slug) > MAX_SLUG:
        raise UsageError(f"topic slug is {len(slug)} characters; the limit is {MAX_SLUG}")


def plan(cfg, slug, title=None, goal=None, origin=None, seed=None, force=False, outlets=(),
         is_known=lambda term: False) -> int:
    """Create or update a topic. With no outlet it is studied for its own sake. `origin` says
    where it came from (a sidecar's own name for it); `seed` adds concepts to its syllabus,
    skipping any `is_known` or already present; `outlets` are added, never removed."""
    check_slug(slug)
    d = tdir(cfg, slug)
    exists = d.is_dir()
    if exists and not (force or origin):
        raise UsageError(f"topic {slug} exists; pass --force to update its title/goal (the syllabus is never overwritten)")
    d.mkdir(parents=True, exist_ok=True)
    conf = load_config(cfg, slug)
    conf.setdefault("title", title or slug.replace("-", " "))
    if title:
        conf["title"] = title
    if goal:
        conf["goal"] = goal
    for o in outlets:
        if o not in OUTLETS:
            raise UsageError(f"unknown outlet {o!r} ({', '.join(OUTLETS)})")
        conf.setdefault("outlets", [])
        if o not in conf["outlets"]:
            conf["outlets"].append(o)
    syl = d / "syllabus.md"
    if not syl.exists():
        H.write_text(syl, SYLLABUS.format(title=conf["title"], goal=conf.get("goal", "")))
    if not (d / "questions.md").exists():
        H.write_text(d / "questions.md",
                     f"# Question bank — {conf['title']}\n\nAdd with `{H.PROG} bank {slug} <concept> --q --a --ref`.\n\n")
    (d / "log.jsonl").touch()
    added = skipped = 0
    if seed is not None:
        text = H.read_text(syl, "syllabus")
        have = {c["name"].lower() for c in parse_syllabus(text)}
        new_lines = []
        for term, desc in seed.items:
            if is_known(term) or term.lower() in have:
                skipped += 1
                continue
            have.add(term.lower())
            new_lines.append(f"- {seed.tag} :: {term} :: {desc}")
            added += 1
        if new_lines:
            if not re.search(r"(?m)^## Concepts\s*$", text):
                text = text.rstrip("\n") + "\n\n## Concepts\n\n"
            H.write_text(syl, insert_concepts(text, new_lines))
    if origin:
        conf["origin"] = origin
    save_config(cfg, slug, conf)
    if not (d / "concepts.json").exists():
        save_state(cfg, slug, {"concepts": {}})
    code = sync(cfg, slug, quiet=True)
    msg = f"{slug}: {'updated' if exists else 'created'} {d.relative_to(cfg.home)}"
    if seed is not None:
        msg += f"; from {origin!r}: {added} concept(s) added, {skipped} skipped (held or present)"
    print(msg)
    return code


def insert_concepts(text: str, new_lines: list) -> str:
    """Append lines at the end of the Concepts section, never reordering it."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if re.match(r"^## Concepts\s*$", ln))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[:end] + new_lines + lines[end:]) + "\n"


def bank(cfg, slug, concept, q, a, ref, why="", qtype="", distractors=()) -> int:
    state = load_state(cfg, slug)
    cid = resolve_concept(state, concept)
    if not ref:
        raise UsageError("--ref is required: every question names where its answer comes from")
    if qtype and qtype not in QTYPES:
        raise UsageError(f"--qtype must be one of {', '.join(QTYPES)}")
    if len(distractors) > 7:
        raise UsageError("at most 7 distractors per question (8 options in all)")
    ds = []
    for d in distractors:
        opt, sep, mis = d.partition("::")
        if not sep or not opt.strip():
            raise UsageError(f"--d {d!r} must be 'option :: the misconception it encodes'")
        ds.append((opt.strip(), mis.strip()))
    p = tdir(cfg, slug) / "questions.md"
    text = H.read_text(p, "question bank") if p.exists() else ""
    if any(x["q"].lower() == q.strip().lower() for x in parse_questions(text).get(cid, [])):
        print(f"{cid}: that question is already banked; skipped")
        return OK
    block = [f"### Q: {q.strip()}", f"- **A:** {a.strip()}"]
    if why:
        block.append(f"- **Why:** {why.strip()}")
    block.append(f"- **Ref:** {ref.strip()}")
    if qtype:
        block.append(f"- **Type:** {qtype}")
    block += [f"- **D:** {o} :: {m}" for o, m in ds]
    lines = text.splitlines()
    try:
        h = lines.index(f"## {cid}")
        end = next((i for i in range(h + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        while end > h + 1 and not lines[end - 1].strip():
            end -= 1
        lines = lines[:end] + [""] + block + lines[end:]
    except ValueError:
        lines = lines + ["", f"## {cid}", ""] + block
    H.write_text(p, "\n".join(lines).strip("\n") + "\n")
    print(f"{cid}: question banked")
    return OK


# --- selection and quizzing ---------------------------------------------------

def confident_misses(c) -> int:
    b = (c.get("by_conf") or {}).get("high", {})
    return b.get("attempts", 0) - b.get("correct", 0)


def select(state, n=5, weak=False, concept=None) -> list:
    cons = state["concepts"]
    if concept:
        return [resolve_concept(state, concept)]
    order = sorted(cons, key=lambda cid: (-confident_misses(cons[cid]), cons[cid].get("streak", 0),
                                          -len(open_errors(cons[cid])), cons[cid].get("last_seen", ""), cid))
    if weak:
        w = [cid for cid in order if badge(cons[cid]) in ("new", "weak", "fair")]
        order = w or order
    return order[:n]


def pick_question(bank_, cid, c):
    qs = bank_.get(cid, [])
    return (qs[c.get("attempts", 0) % len(qs)], c.get("attempts", 0) % len(qs)) if qs else (None, -1)


def dominant_etype(c):
    cnt = Counter(etype_of(e) or "other" for _i, e in open_errors(c))
    if not cnt:
        return None
    top = max(cnt.values())
    return sorted(k for k, v in cnt.items() if v == top)[0] if top >= 2 else None


def log_verdict(cfg, slug) -> int:
    """OK when the log reads in full; otherwise warn and NOT_EVALUABLE. `due` and
    `quiz` read the derived concepts.json, so a damaged log row means what they
    printed may not match the record: they still print, then exit 2."""
    bad = len(read_log(cfg, slug)[1])
    if not bad:
        return OK
    H.warn(f"{slug}: {bad} damaged log row(s): what was shown was derived without them and may not match "
           f"the record; run `{H.PROG} validate {slug}` or `rebuild {slug} --check`")
    return NOT_EVALUABLE


def quiz(cfg, slug, n=5, weak=False, concept=None) -> int:
    state = load_state(cfg, slug)
    if not state["concepts"]:
        raise NotEvaluable(f"{slug} has no concepts yet: add them to syllabus.md and run `{H.PROG} sync {slug}`")
    bank_ = load_bank(cfg, slug)
    for cid in select(state, n, weak, concept):
        c = state["concepts"][cid]
        q, _i = pick_question(bank_, cid, c)
        print(f"- {cid} [{badge(c)}]" + (f"  Q: {q['q']}" if q else "  (no banked question)"))
        et = dominant_etype(c)
        if et:
            last = open_errors(c)[-1][1]
            print(f"    recurring {et}: {REASK[et]}  (last: {last})")
    print(f"record each: {H.PROG} record {slug} <concept> ok|partial|miss [--confidence L] [--qtype T]")
    return log_verdict(cfg, slug)


class _Quit(Exception):
    pass


def _ask(prompt, inp, out):
    out.write(prompt)
    out.flush()
    try:
        line = inp.readline()
    except UnicodeDecodeError as e:
        raise NotEvaluable(f"the input is not valid UTF-8 ({e.reason} at offset {e.start}); answers already "
                           "given are on the log") from e
    if not line:
        raise _Quit
    line = line.strip()
    if line.lower() == "q":
        raise _Quit
    return line


def quiz_interactive(cfg, slug, n=5, weak=False, concept=None, inp=None, out=None) -> int:
    """Ask, hint on request, take confidence BEFORE revealing, reveal, grade,
    record through the same path as `record`. EOF or `q` ends the
    session; every answered item is already on the log."""
    inp, out = inp or sys.stdin, out or sys.stdout
    state = load_state(cfg, slug)
    if not state["concepts"]:
        raise NotEvaluable(f"{slug} has no concepts yet")
    bank_ = load_bank(cfg, slug)
    done = 0
    try:
        for cid in select(state, n, weak, concept):
            state = load_state(cfg, slug)
            c = state["concepts"][cid]
            q, qi = pick_question(bank_, cid, c)
            if q is None:
                out.write(f"\n{cid}: no banked question; skipped (bank one with `{H.PROG} bank`)\n")
                continue
            out.write(f"\n[{badge(c)}] {c.get('name', cid)}\nQ: {q['q']}\n")
            options = None
            if q["d"]:
                options = [(q["a"], None)] + [(o, m) for o, m in q["d"][:7]]
                random.Random(f"{slug}|{cid}|{qi}|{c.get('attempts', 0)}").shuffle(options)
                for i, (o, _m) in enumerate(options):
                    out.write(f"  {'abcdefgh'[i]}) {o}\n")
            rung, answer = 0, None
            while answer is None:
                a = _ask("answer (? for a hint, q to stop)> ", inp, out)
                if a == "?":
                    rung += 1
                    out.write(_hint(state, cid, q, rung) + "\n")
                    if rung >= 4:
                        answer = ""
                elif options and (len(a) != 1 or a.lower() not in "abcdefgh"[:len(options)]):
                    out.write(f"  pick a letter a-{'abcdefgh'[len(options) - 1]}\n")
                else:
                    answer = a
            conf = ""
            if rung < 4:
                cl = _ask("confidence [l/m/h, enter = unstated]> ", inp, out).lower()
                conf = {"l": "low", "m": "med", "h": "high"}.get(cl, "")
            out.write(f"A: {q['a']}\n" + (f"Why: {q['why']}\n" if q["why"] else "") + f"Ref: {q['ref']}\n")
            note, etype = "", ""
            if options and rung < 4:
                picked = options["abcdefgh".index(answer.lower())]
                result = "ok" if picked[1] is None else "miss"
                if result == "miss":
                    note = picked[1] or f"chose {picked[0]!r}"
                    out.write(f"  that option encodes: {note}\n")
            else:
                g = ""
                while g not in ("o", "p", "m"):
                    g = _ask("grade yourself [o = ok, p = partial, m = miss]> ", inp, out).lower()
                result = {"o": "ok", "p": "partial", "m": "miss"}[g]
            stop = False
            try:                               # optional detail: stopping here must not lose the attempt
                if result != "ok" and not (options and rung < 4):
                    note = _ask("what went wrong (enter to skip)> ", inp, out)
                if result != "ok":
                    out.write("  " + "  ".join(f"{i + 1}={e}" for i, e in enumerate(ETYPES)) + "\n")
                    e = _ask("error type [1-6, enter = skip]> ", inp, out)
                    if e.isdigit() and 1 <= int(e) <= len(ETYPES):
                        etype = ETYPES[int(e) - 1]
            except _Quit:
                stop = True
            qtype = q["type"] if q["type"] in QTYPES else ""
            row = record(cfg, slug, cid, result, note=note, confidence=conf,
                         hint_depth=min(rung, 4), qtype=qtype, etype=etype, quiet=True)
            out.write(f"  recorded {row['result']}" + (f" (hint depth {row['hint_depth']})" if row["hint_depth"] else "") + "\n")
            done += 1
            if stop:
                raise _Quit
    except _Quit:
        pass
    out.write(f"\n{done} item(s) recorded\n")
    return log_verdict(cfg, slug)


def _hint(state, cid, q, rung) -> str:
    c = state["concepts"][cid]
    if rung == 1:
        sib = [x.get("name") for k, x in state["concepts"].items()
               if k != cid and c.get("cluster") and x.get("cluster") == c.get("cluster")]
        return f"  hint 1: domain {c.get('domain', '-')}" + (f"; related to {', '.join(sib)}" if sib else "")
    if rung == 2:
        return f"  hint 2: {c.get('desc') or '(no description in the syllabus)'}"
    if rung == 3:
        return f"  hint 3: {q['why'] or '(no Why line banked)'}"
    return f"  answer: {q['a']}"


# --- reviews, dates, graduation ---------------------------------------------------

def due_list(cfg, slug, today=None) -> list:
    today = today or H.today()
    state = load_state(cfg, slug)
    rows = [(cid, c) for cid, c in state["concepts"].items()
            if c.get("attempts") and (not c.get("due") or c["due"] <= today.isoformat())]
    rows.sort(key=lambda x: (x[1].get("due") or "", x[0]))
    return rows


def due(cfg, slug=None, limit=20) -> int:
    code = OK
    if not slug and not topics(cfg):
        print(f"NOT EVALUABLE nothing to review: 0 topic(s) in {cfg.home}; "
              "an empty home has no reviews due, which is not the same as none being due")
        return NOT_EVALUABLE
    for t in ([slug] if slug else topics(cfg)):
        rows = due_list(cfg, t)
        shown = rows[:limit] if limit else rows
        print(f"{t}: {len(rows)} due" + (f" (~{2 * len(rows)} min)" if rows else ""))
        for cid, c in shown:
            print(f"  {cid}  due {c.get('due') or 'unscheduled'}  [{badge(c)}]")
        if len(rows) > len(shown):
            print(f"  … {len(rows) - len(shown)} more held back by --limit {limit}")
        code = max(code, log_verdict(cfg, t))
    return code


def breadth_ok(c) -> bool:
    bt = c.get("by_type") or {}
    if not bt:
        return False            # no typed attempts: breadth was never tested, so it has not passed
    return sum(1 for v in bt.values() if v["attempts"] and v["correct"] / v["attempts"] >= BREADTH_RATE) >= BREADTH_TYPES


def interference_ok(rows, cid) -> bool:
    """A first-look unaided correct on a day when >= 3 other concepts were also studied."""
    rows = sorted(rows, key=lambda r: r["date"])
    by_day: dict = {}
    for r in rows:
        by_day.setdefault(r["date"], set()).add(r["concept"])
    return any(r["concept"] == cid and not rep and facets(r)["unaided_ok"]
               and len(by_day[r["date"]] - {cid}) >= INTERFERENCE_OTHERS for r, rep in zip(rows, repeats(rows)))


def graduation_evidence(cfg, slug) -> dict:
    """Which mastered concepts passed every evidence gate (retention, breadth, interference),
    from a VALIDATED view only: it refuses (never answers for a subset) when the log was not
    read in full or the cached mastery disagrees with a full replay. What the evidence may be
    used for (a facts.md line) is the career sidecar's business."""
    state = load_state(cfg, slug)
    rows, _p = read_log(cfg, slug)
    drifted, problems = audit(cfg, slug, state)
    if problems:
        raise NotEvaluable(f"{slug}: {len(problems)} log problem(s) (first: {problems[0]}); the record was not read "
                           f"in full, so no graduation is offered; fix the log, then `{H.PROG} rebuild {slug}`")
    if drifted:
        raise Drifted(f"{slug}: {len(drifted)} concept(s) disagree with the log ({', '.join(drifted[:5])}); "
                      f"mastery is stale, so no graduation is offered; run `{H.PROG} rebuild {slug}`")
    out = {"passed": [], "not retained": [], "not breadth-tested": [], "drilled solo": []}
    for cid, c in state["concepts"].items():
        if badge(c) != "mastered":
            continue
        if len(c.get("correct_days", [])) < RETENTION_DAYS:
            out["not retained"].append(cid)
        elif not breadth_ok(c):
            out["not breadth-tested"].append(cid)
        elif not interference_ok(rows, cid):
            out["drilled solo"].append(cid)
        else:
            out["passed"].append(cid)
    return out


WHY = {"not retained": f"correct on fewer than {RETENTION_DAYS} separate days",
       "not breadth-tested": f"fewer than {BREADTH_TYPES} question types at {int(BREADTH_RATE * 100)}%+ "
                             "(record --qtype)",
       "drilled solo": f"never answered unaided on a day when {INTERFERENCE_OTHERS}+ other concepts were also studied"}


# --- misconceptions, calibration ---------------------------------------------

def misconceptions(cfg, slug) -> int:
    state = load_state(cfg, slug)
    typed = Counter()
    for cid, c in state["concepts"].items():
        sigs = Counter(signature(e) for _i, e in open_errors(c))
        for s, k in sigs.items():
            if k >= 2:
                print(f"ACTIVE  {cid}: {s!r} x{k}")
        et = dominant_etype(c)
        if et:
            print(f"RECURRING {cid}: {et}; {REASK[et]}")
        typed.update(etype_of(e) for _i, e in open_errors(c) if etype_of(e))
    total = sum(typed.values())
    if total >= 3:
        top = max(typed.values())
        tied = sorted(k for k, v in typed.items() if v == top)
        if top / total >= 0.5 and len(tied) == 1:
            print(f"VERDICT {tied[0]} dominates ({top}/{total} open typed errors): {REASK[tied[0]]}")
        elif top / total >= 0.5:
            print(f"VERDICT split between {' and '.join(tied)} ({top}/{total} each):")
            for t in tied:
                print(f"  {t}: {REASK[t]}")
        else:
            print(f"no dominant error class ({total} open typed errors spread across {len(typed)} classes)")
    else:
        print(f"{total} open typed error(s): too few for a verdict (needs 3)")
    return log_verdict(cfg, slug)


def calibration(cfg, slug) -> int:
    need_topic(cfg, slug)
    rows, _p = read_log(cfg, slug)
    code = log_verdict(cfg, slug)
    acc: dict = {}
    days: Counter = Counter()
    rows = sorted(rows, key=lambda r: r["date"])
    for r, rep in zip(rows, repeats(rows)):
        f = facets(r)
        if not f["conf"] or f["assisted"] or f["massed"] or f["dialogue"] or rep:
            continue
        days[r["date"]] += 1
        a = acc.setdefault(f["conf"], [0, 0])
        a[0] += 1
        a[1] += f["ok"]
    if not acc:
        print(f"{slug}: no confidence-rated unaided attempts yet: calibration NOT EVALUABLE")
        return NOT_EVALUABLE
    total = sum(days.values())
    print(f"{slug}: {total} rated answer(s), first looks only, on {len(days)} day(s)")
    for lvl in CONFIDENCE:
        if lvl in acc:
            n, k = acc[lvl]
            print(f"  {lvl:5} {k}/{n} correct ({100 * k / n:.0f}%)")
    day, most = days.most_common(1)[0]
    if total >= 4 and most / total >= 0.5:
        print(f"note: {most} of {total} came from one day ({day}): the figure says as much about that session "
              "as about you")
    if "high" in acc and acc["high"][1] / acc["high"][0] < 0.8:
        print("OVERCONFIDENT: high-confidence answers are right less than 80% of the time")
    if "low" in acc and acc["low"][1] / acc["low"][0] > 0.8:
        print("UNDERCONFIDENT: low-confidence answers are right more than 80% of the time")
    return code


# --- integrity --------------------------------------------------------------------

def rebuild(cfg, slug, check=False, skip_damaged=False) -> int:
    """--check: 0 matches, 3 drift, 2 when the log could not be read in full.
    Without --check: rewrite concepts.json from syllabus + log. A log with
    unreadable rows is refused unless --skip-damaged, which rebuilds from the
    readable rows and says how many it skipped. A damaged concepts.json is
    kept beside the new one, never overwritten."""
    need_topic(cfg, slug)
    p = tdir(cfg, slug) / "concepts.json"
    try:
        state = load_state(cfg, slug)
    except NotEvaluable:
        if check:
            raise
        keep = p.with_name(f"concepts.json.damaged-{H.today().isoformat()}")
        n = 1
        while keep.exists():
            n += 1
            keep = p.with_name(f"concepts.json.damaged-{H.today().isoformat()}-{n}")
        p.rename(keep)
        H.warn(f"{slug}: damaged concepts.json kept as {keep.name}; rebuilding from syllabus + log")
        state = {"concepts": {}}
    new, problems = replay(cfg, slug, state)
    for pr in problems:
        H.warn(pr)
    if check:
        d, _ = audit(cfg, slug, state)
        if problems:
            print(f"NOT EVALUABLE {slug}: {len(problems)} log problem(s); the record was not read in full"
                  + (f" ({len(d)} concept(s) also differ)" if d else ""))
            return NOT_EVALUABLE
        if d:
            print(f"DRIFT {slug}: {len(d)} concept(s) disagree with the log: {', '.join(d[:8])}{', ...' if len(d) > 8 else ''}")
            return DRIFT
        print(f"{slug}: state matches the log ({len(state['concepts'])} concept(s))")
        return OK
    if problems and not skip_damaged:
        print(f"REFUSED {slug}: {len(problems)} log problem(s); fix the log, or pass --skip-damaged "
              "to rebuild from the readable rows only")
        return NOT_EVALUABLE
    save_state(cfg, slug, new)
    print(f"{slug}: rebuilt {len(new['concepts'])} concept(s) from the log"
          + (f"; skipped {len(problems)} damaged row(s)" if problems else ""))
    return OK


def _placeholder(text: str) -> bool:
    """An angle-bracket placeholder left from the brief's example block: "<the one checkable
    answer>". A short tag ("<div>") is a real answer, not a placeholder."""
    t = (text or "").strip()
    return bool(re.fullmatch(r"<[^<>]{10,}>", t)) and " " in t


def problems(cfg, slug) -> tuple:
    """(hard failures, warnings) for one topic."""
    hard, warn = [], []
    syl = tdir(cfg, slug) / "syllabus.md"
    if syl.exists():
        try:
            parse_syllabus(H.read_text(syl, "syllabus"))
        except UsageError as e:
            hard.append(f"{slug}: {e}")
    state = load_state(cfg, slug)
    load_config(cfg, slug)          # a damaged topic.json is reported, not skipped
    cons = state["concepts"]
    for r in read_log(cfg, slug)[0]:
        t = r.get("transcript")
        if not t:
            if r.get("mode") == "dialogue":
                warn.append(f"{slug}/{r['concept']}: the {r['date']} dialogue grade has no transcript: nothing shows "
                            "what it was graded on (keep one at the path `talk` prints, before recording)")
            continue
        p = tdir(cfg, slug) / t
        # The transcript is the evidence behind a grade: evidence gone or changed is a failure, not a note.
        g = graded_copy(cfg, slug, t)
        intact = g.is_file() and hashlib.sha256(g.read_bytes()).hexdigest() == r.get("transcript_sha256")
        how = (f"; the graded copy is {g.relative_to(tdir(cfg, slug)).as_posix()}: compare them, or copy it back"
               if intact else "; no intact graded copy is kept, so what changed cannot be shown")
        if not p.is_file():
            hard.append(f"{slug}/{r['concept']}: the transcript behind the {r['date']} dialogue grade is missing ({t}){how}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != r.get("transcript_sha256"):
            hard.append(f"{slug}/{r['concept']}: the transcript behind the {r['date']} dialogue grade "
                        f"changed after it was graded ({t}){how}")
    for cid, c in cons.items():
        if not c.get("name"):
            hard.append(f"{slug}/{cid}: no name")
        if c.get("correct", 0) > c.get("attempts", 0):
            hard.append(f"{slug}/{cid}: more correct than attempts")
        if c.get("streak", 0) < 0:
            hard.append(f"{slug}/{cid}: negative streak")
    for cid, qs in load_bank(cfg, slug).items():
        if cid not in cons:
            hard.append(f"{slug}: bank section for unknown concept {cid!r}")
        for q in qs:
            if not q["ref"]:
                hard.append(f"{slug}/{cid}: question without a Ref: {q['q'][:60]!r}")
            for field, what in (("q", "question"), ("a", "answer")):
                if _placeholder(q[field]):
                    hard.append(f"{slug}/{cid}: the {what} is still the brief's placeholder "
                                f"(edit it): {q[field][:60]!r}")
            if not q["a"]:
                hard.append(f"{slug}/{cid}: question without an answer (an `- **A:**` line): {q['q'][:60]!r}")
            if not q["type"]:
                warn.append(f"{slug}/{cid}: question without a Type: {q['q'][:60]!r}")
            if q["type"] and q["type"] not in QTYPES:
                warn.append(f"{slug}/{cid}: unknown question type {q['type']!r}")
    return hard, warn


BANK_EXAMPLE = """## <concept id>

### Q: <one question, asked with no hint in it>
- **A:** <the one checkable answer>
- **Why:** <one sentence: why that is the answer>
- **Ref:** <where the learner can check it: notes.md#section, or a URL>
- **Type:** recall
- **D:** <a wrong option> :: <the misconception that picks it>
- **D:** <another wrong option> :: <its misconception>
- **Provenance:** unverified
"""


def brief(cfg, slug) -> int:
    """A Markdown bundle for whoever writes questions for a topic: its concepts with their
    question counts, the bank format `validate` accepts, and the rules."""
    need_topic(cfg, slug)
    conf = load_config(cfg, slug)
    state = load_state(cfg, slug)
    bank = load_bank(cfg, slug)
    title = conf.get("title") or slug
    out = [f"# Study brief: {title} ({slug})", "",
           f"{H.NAME} wrote this from the topic's syllabus, its question bank and its log. It holds "
           "no model output.", "",
           "## Rules for whoever writes the questions", "",
           "- Ask with no hint: the question must not contain or point at its answer.",
           "- One checkable answer per question; say why in one sentence.",
           "- Give a Ref the learner can open (notes.md#section, or a URL). No Ref, no question.",
           "- Write your own questions; never copy an exam's or a course's questions.",
           f"- Type is one of: {', '.join(QTYPES)}. Mix them; recall alone does not test use.",
           "- Distractors (`D:`) name the misconception that would pick them.",
           "- Provenance stays `unverified` until the learner checks the answer against the Ref.",
           "", "## Concepts", "", "Each with the questions it has now (write for the thinnest first):", ""]
    cons = state.get("concepts", {})
    for cid in sorted(cons, key=lambda c: (len(bank.get(c, [])), c)):
        c = cons[cid]
        line = f"- {cid}  {len(bank.get(cid, []))} question(s)"
        if c.get("name") and c["name"] != cid:
            line += f"  ({c['name']})"
        out.append(line)
    if not cons:
        out.append(f"- (no concepts yet: add them to syllabus.md and run `{H.PROG} sync`)")
    if conf.get("origin"):
        out += ["", f"Seeded from {conf['origin']!r}."]
    out += ["", "## Format (exactly this; `##` is the concept id from the list above)", "",
            "```markdown", BANK_EXAMPLE.rstrip("\n"), "```", "",
            "## Wanted from you", "",
            "1. Three questions for each concept with fewer than three, of at least two types.",
            "2. Append them to the topic's questions.md under the concept's `##` heading.",
            f"3. Check: `{H.PROG} validate {slug}` must report 0 failure(s).", ""]
    print("\n".join(out))
    return OK


def validate(cfg, slug=None) -> int:
    hard, warn, damaged = [], [], []
    if not slug and not topics(cfg):
        print(f"NOT EVALUABLE nothing to validate: 0 topic(s) in {cfg.home}; "
              "an empty home has no failures, which is not the same as none being found")
        return NOT_EVALUABLE
    for t in ([slug] if slug else topics(cfg)):
        h, w = problems(cfg, t)
        hard += h
        warn += w
        damaged += [f"{t}: {d}" for d in read_log(cfg, t)[1]]
    if not slug:
        from . import questions as Q
        damaged += Q.read(cfg)[1]
    for w in warn:
        H.warn(f"warn: {w}")
    for h in hard:
        print(f"FAIL {h}")
    for d in damaged:
        print(f"DAMAGED {d}")
    print(f"validate: {len(hard)} failure(s), {len(warn)} warning(s), {len(damaged)} damaged log row(s)"
          + ("; the log cannot be read in full, so the topic is not evaluable (see `rebuild --check`)"
             if damaged else ""))
    return NOT_EVALUABLE if damaged else FINDINGS if hard else OK
