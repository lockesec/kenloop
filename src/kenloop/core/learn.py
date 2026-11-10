"""The learn arm: topics, concepts, a question bank, and a record of every attempt.

A topic lives in ``HOME/topics/<slug>/``:

    topic.json     settings you set (title, goal, origin, outlets, exam_date, passed)
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
import os
import re

from . import fsrs
from . import home as H
from .errors import (
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
MODES = ("practice", "exam", "diagnose", "learn", "dialogue", "teach", "predict")
# teach: the concept was TAUGHT this day (freeform, bottom-up). It is not an attempt: no credit, no
# streak, no schedule. It makes the concept "touched" for the on-ramp, and a quiz on it the same day
# counts as a repeat (seen today), never as a credited first look.
# predict: the learner's guess BEFORE the explanation ("what do you think happens when ..."). A wrong
# guess still helps memory once the answer follows (pretesting), so it is recorded with its result,
# but it is never credited, and like teach it makes a later answer that day a repeat.
QTYPES = ("recall", "applied", "edge", "comparison", "debugging")
ETYPES = ("term-confusion", "concept-conflation", "wrong-scope", "detail-slip", "misapplication", "other")
TESTED_BY = {"term-confusion": {"recall"}, "detail-slip": {"recall"},
             "concept-conflation": {"comparison"}, "wrong-scope": {"comparison"},
             "misapplication": {"applied"}}
RESOLVES_ALL = {"edge", "debugging"}
MAX_SLUG = 64
CONFIG_KEYS = ("title", "goal", "origin", "deadline", "complete", "exam_date", "passed")      # text
# Lens settings: `deadline` and `complete` are the names; `exam_date` and
# `passed` are their old names, read for one release. A topic.json is written in whichever names
# it already uses, so nothing is renamed behind the learner's back: `ken settings SLUG --migrate`
# renames on purpose. One file holding both names is refused as ambiguous.
KEY_ALIASES = {"deadline": "exam_date", "complete": "passed"}
# How you want to study a topic, or one syllabus line of it (`:: intent:` / `:: depth:`). A line's
# setting overrides its topic's. intent: understand it, or learn what the exam needs to pass.
# depth: where teaching starts and how far it goes (what it is / how it works / why it works).
INTENTS = ("understand", "pass")
DEPTHS = ("exam", "mechanism", "first-principles")    # ordered: shallow to deep
CHOICES = {"intent": INTENTS, "depth": DEPTHS}
# Where what you learn in a topic may go besides your own head. None is the normal case:
# studied for its own sake. "career": it may graduate into facts.md. "cert": toward an exam.
OUTLETS = ("career", "cert")
# kind "interest": a topic studied for its own sake (math, history, a science). Same quizzes,
# schedule and record as any topic; it is never tied to job demand and never graduates into
# facts.md. A topic with no kind is a career topic.
IDENTITY = ("name", "domain", "desc", "cluster", "scope", "status", "part_of", "before", "intent", "depth", "rung",
            "same")
EDGES = {"part-of": "part_of", "before": "before"}   # syllabus marker -> concept field
MASTERY_FIELDS = ("attempts", "correct", "streak", "partials", "guesses", "hints", "correct_days",
                  "errors", "resolved_idx", "by_type", "by_conf", "last_seen", "stability",
                  "difficulty", "interval", "due", "exam_clamp", "dialogues", "by_reasoning", "repeats",
                  "taught", "last_taught", "predictions", "last_predicted")
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
    """A topic's directory. A slug is one name under topics/, never a path: '..', 'a/b' and an absolute
    path would send every write of the record outside the data directory."""
    if not isinstance(slug, str) or not slug or slug in (".", "..") or "/" in slug or "\\" in slug or "\0" in slug:
        raise UsageError(f"topic slug {slug!r} is not a topic name (one name, no path separators)")
    return cfg.topics / slug


def topics(cfg) -> list:
    if not cfg.topics.is_dir():
        return []
    return sorted(d.name for d in cfg.topics.iterdir() if (d / "syllabus.md").exists()
                  or (d / "topic.json").exists())


def get_key(conf: dict, key: str) -> str:
    """A lens setting by its name, or by its old name."""
    return conf.get(key) or conf.get(KEY_ALIASES[key]) or ""


def set_key(conf: dict, key: str, value) -> None:
    """Set (or, with None, clear) a lens setting in the name the file already uses."""
    name = KEY_ALIASES[key] if KEY_ALIASES[key] in conf else key
    if value is None:
        conf.pop(key, None)
        conf.pop(KEY_ALIASES[key], None)
    else:
        conf[name] = value


def migrate_keys(conf: dict) -> list:
    """Rename old setting names in place; [(old, new)] renamed."""
    done = []
    for new, old in KEY_ALIASES.items():
        if old in conf:
            conf[new] = conf.pop(old)
            done.append((old, new))
    return done


def passed_on(cfg, slug) -> str:
    """The day a cert topic's exam was passed ("" if not): a passed topic is COMPLETE and off the
    schedule. Its record stays whole and it can still be studied by name. A damaged topic.json
    reads as not passed, so it stays where the integrity rule can see it."""
    try:
        return get_key(load_config(cfg, slug), "complete")
    except NotEvaluable:
        return ""


def keeps_studying(cfg, slug) -> bool:
    """A passed topic set to stay on the schedule: the exam is done, the material is not
    (`settings SLUG --keep-studying on`)."""
    try:
        return load_config(cfg, slug).get("keep_studying") is True
    except NotEvaluable:
        return False


def off_schedule(cfg, slug) -> str:
    """The pass date of a topic that is off the schedule ("" if it is on it)."""
    p = passed_on(cfg, slug)
    return "" if not p or keeps_studying(cfg, slug) else p


def scheduled_topics(cfg, lane=None) -> list:
    """The topics `next` and an unnamed `due` work on: every topic but the completed ones (unless
    set to keep studying), optionally one lane only."""
    return [t for t in topics(cfg) if not off_schedule(cfg, t) and (lane is None or lane_of(cfg, t) == lane)]


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
    for new, old in KEY_ALIASES.items():
        if new in data and old in data:
            raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'} holds both `{new}` and its old name `{old}`; "
                               "keep one by hand")
    for k in CONFIG_KEYS:
        if k in data and not isinstance(data[k], str):
            raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'}: `{k}` must be text, not "
                               f"{type(data[k]).__name__}; fix it by hand")
    for k, allowed in CHOICES.items():
        if k in data and data[k] not in allowed:
            raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'}: `{k}` must be one of {', '.join(allowed)}, "
                               f"not {data[k]!r}; fix it with `{H.PROG} settings {slug} --{k} ...`")
    if "start" in data and (not isinstance(data["start"], int) or isinstance(data["start"], bool)
                            or data["start"] < 0):
        raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'}: `start` must be a rung number; "
                           f"fix it with `{H.PROG} place {slug} --start N`")
    o = data.get("outlets", [])
    if not isinstance(o, list) or not all(x in OUTLETS for x in o):
        raise NotEvaluable(f"{tdir(cfg, slug) / 'topic.json'}: `outlets` must be a list of "
                           f"{', '.join(OUTLETS)}; fix it by hand")
    return data


def save_config(cfg, slug, conf: dict) -> None:
    load_config(cfg, slug)          # refuses over a damaged file
    # Keys this module does not know are KEPT: a setting another part of the tool (or a newer
    # version) wrote must not vanish on the next save. Dropping them is how a learner's intent
    # ended up as prose in a syllabus.
    out = {k: conf[k] for k in CONFIG_KEYS if k in conf}
    out.update({k: v for k, v in conf.items() if k not in CONFIG_KEYS and k != "outlets"})
    if conf.get("outlets"):
        out["outlets"] = [o for o in OUTLETS if o in conf["outlets"]]
    H.write_json(tdir(cfg, slug) / "topic.json", out)


def setting(conf: dict, concept: dict | None, key: str) -> str:
    """A concept's intent or depth: its own syllabus marker, else its topic's, else "" (unset)."""
    return ((concept or {}).get(key) or conf.get(key) or "")


def twins(cfg, slug, cid) -> list:
    """[(topic, concept id, name, badge)] for the same idea in OTHER topics (a shared `:: same:` key).
    A mapping, never a mastery transfer: each topic keeps its own evidence."""
    key = load_state(cfg, slug)["concepts"].get(cid, {}).get("same")
    if not key:
        return []
    out = []
    for t in topics(cfg):
        if t == slug:
            continue
        try:
            cons = load_state(cfg, t)["concepts"]
        except NotEvaluable:
            continue                      # a damaged topic is reported by validate, not here
        out += [(t, k, c.get("name", k), badge(c)) for k, c in cons.items() if c.get("same") == key]
    return out


def idea_key(slug, cid, c: dict) -> str:
    """The one-home identity of a concept: its shared `same:` key, else `topic/concept`."""
    return c.get("same") or f"{slug}/{cid}"


def twin_seen(cfg, slug, cid, day) -> list:
    """Topics where the same idea (a twin) already has a row on `day`: one idea, one held set, so an
    answer here after that is a repeat."""
    out = []
    for t, k, _n, _b in twins(cfg, slug, cid):
        try:
            if any(r["date"] == day and r["concept"] == k for r in read_log(cfg, t)[0]):
                out.append(t)
        except NotEvaluable:
            continue
    return out


def has_outlet(conf: dict, name: str) -> bool:
    """A cert is always a career item: studying toward an exam implies the career outlet."""
    o = conf.get("outlets", [])
    return name in o or (name == "career" and "cert" in o)


LANES = ("career", "interest")


def lane_of(cfg, slug) -> str:
    """career: may feed facts.md (a career or cert outlet); interest: studied for its own sake.
    A damaged topic.json reads as interest here; the integrity rule reports the damage."""
    try:
        return "career" if has_outlet(load_config(cfg, slug), "career") else "interest"
    except NotEvaluable:
        return "interest"


def exam_date(conf: dict):
    try:
        return _dt.date.fromisoformat(get_key(conf, "deadline"))
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
             "cluster": "", "scope": "exam", "status": "", "part_of": "", "before": "",
             "intent": "", "depth": "", "rung": "", "same": ""}
        desc = []
        for p in parts[2:]:
            key, _, val = p.partition(":")
            if key in EDGES and val and " " not in val.strip():
                c[EDGES[key]] = val.strip().lower()     # a concept id: this line is a piece of it, or comes before it
            elif key in CHOICES and val:
                v = val.strip().lower()
                if v not in CHOICES[key]:
                    raise UsageError(f"syllabus line {n}: unknown {key} {val!r} ({', '.join(CHOICES[key])})")
                c[key] = v
            elif key == "same" and val and " " not in val.strip():
                c["same"] = slugify(val)           # a key shared with the same idea in other topics (a mapping, no credit moves)
            elif key == "rung" and val and " " not in val.strip():
                c["rung"] = slugify(val)           # the Path rung this line sits on, when not its domain's
            elif key in ("cluster", "scope", "status") and val and " " not in key:
                val = val.strip().lower() if key == "scope" else val
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


# --- the `## Path` grammar and the settings rule (line > rung > topic) ----------------------

_RUNG = re.compile(r"^\s*\d+\.\s+\*\*([^*]+)\*\*")


def parse_path(text: str) -> list:
    """The rungs, in order: the bold domain of each numbered line under `## Path`."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "path"
            continue
        m = _RUNG.match(line) if inside else None
        if m:
            d = slugify(m.group(1))
            if d in out:
                raise UsageError(f"## Path lists the rung {d!r} twice")
            out.append(d)
    return out


_MARK = re.compile(r"::\s*(intent|depth):\s*([\w-]+)")


def path_settings(text: str) -> dict:
    """{domain: {intent/depth: value}} from markers on `## Path` lines (`:: intent:pass`): a whole rung
    set at once, so ingested concept lines need no marker of their own."""
    out, inside = {}, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == "path"
            continue
        m = _RUNG.match(line) if inside else None
        if not m:
            continue
        for key, val in _MARK.findall(line):
            v = val.lower()
            if v not in CHOICES[key]:
                raise UsageError(f"## Path rung {m.group(1)!r}: unknown {key} {val!r} ({', '.join(CHOICES[key])})")
            out.setdefault(slugify(m.group(1)), {})[key] = v
    return out


def concept_setting(cfg, slug, c: dict, key: str, _cache: dict | None = None) -> str:
    """A concept's intent or depth: its own line, else its rung's (`## Path` marker), else the topic's."""
    if c.get(key):
        return c[key]
    p = tdir(cfg, slug) / "syllabus.md"
    ps = path_settings(H.read_text(p, "syllabus")) if p.exists() else {}
    rung = slugify(c.get("rung") or c.get("domain", ""))
    return ps.get(rung, {}).get(key) or load_config(cfg, slug).get(key, "")



def load_bank(cfg, slug) -> dict:
    p = tdir(cfg, slug) / "questions.md"
    return parse_questions(H.read_text(p, "question bank")) if p.exists() else {}


# --- the log and the credit rules ---------------------------------------------

def read_log(cfg, slug) -> tuple:
    """(rows, problems). An undecodable line or a row with no valid date is
    reported and skipped; it is never replayed at today's date."""
    from . import ledger as LG
    return LG.read(tdir(cfg, slug) / "log.jsonl", _check_row)


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
    if r.get("depth", "") not in ("",) + DEPTHS:
        raise ValueError(f"depth {r.get('depth')!r}")
    if not isinstance(r.get("due", False), bool):
        raise ValueError(f"due {r.get('due')!r}")
    si = r.get("seen_in", [])
    if not (isinstance(si, list) and all(isinstance(t, str) and t for t in si)):
        raise ValueError(f"seen_in {si!r}")
    if r.get("mode") == "dialogue":
        rubric = check_rubric(r.get("rubric"))
        # rows recorded before the told-answer cap (2026-10-26) carry the uncapped verdict: both read
        if r.get("result") not in (rubric_result(rubric, int(r.get("hint_depth", 0) or 0)), rubric_result(rubric)):
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
    elif r.get("mode") == "teach" and (r.get("result") != "ok" or "rubric" in r):
        raise ValueError("a teach row records that a concept was taught: result ok, no rubric")
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


TOLD = 4        # hint depth 4: the tutor told the answer


def rubric_result(rubric: dict, hint_depth: int = 0) -> str:
    """The one rule from scores to verdict: the grader gives the scores, this gives the result.
    ok: mean >= 1.5 and no move at 0. partial: mean >= 0.75. Otherwise miss. A dialogue in which
    the tutor told the answer (hint depth 4) is at most partial: reasoning you were handed is not
    reasoning you reached."""
    mean = sum(rubric.values()) / len(rubric)
    if mean >= 1.5 and min(rubric.values()) > 0:
        return "partial" if hint_depth >= TOLD else "ok"
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


def row_depth(row: dict) -> str:
    """The depth of the question a row answers. Rows from before depth was recorded read a declared
    default: exam for quiz-like modes, mechanism for teaching, read-throughs and dialogues."""
    d = row.get("depth")
    if d:
        return d
    return "mechanism" if row.get("mode") in ("teach", "learn", "dialogue") else "exam"


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
    taught = row.get("mode") == "teach"
    predicted = row.get("mode") == "predict"
    return {"ok": ok, "taught": taught, "predicted": predicted, "guess": guess, "conf": conf, "depth": depth,
            "assisted": depth > 0, "massed": massed, "dialogue": dialogue, "qdepth": row_depth(row),
            "unaided_ok": ok and not guess and depth == 0 and not massed and not dialogue and not taught
                          and not predicted,
            "effortful": ok and conf == "low" and not guess}


def repeats(rows) -> list:
    """For each row (in the order given), whether an earlier row that day was on the same concept.
    Only the first look at a concept on a day can be a fresh retrieval: after a quiz, a miss, a
    hint, a dialogue or a read-through, the learner has seen it."""
    seen, out = set(), []
    for r in rows:
        key = (r["date"], r["concept"])
        out.append(key in seen or bool(r.get("seen_in")))      # seen_in: a twin was seen that day
        seen.add(key)
    return out


def apply_row(c: dict, row: dict, exam, repeat=False) -> None:
    """The one code path from an attempt to state: `record` and `rebuild` both call it."""
    f = facets(row)
    day = row["date"]
    if f["taught"]:
        c["taught"] = c.get("taught", 0) + 1
        c["last_taught"] = day
        if not c.get("due"):
            # no credit, but the first cold recall is scheduled: tomorrow, with no interval (edge
            # #22). Unscheduled, a taught concept fell out of every list and was never recalled.
            c["due"] = (_dt.date.fromisoformat(day) + _dt.timedelta(days=1)).isoformat()
        return
    if f["predicted"]:
        c["predictions"] = c.get("predictions", 0) + 1
        c["last_predicted"] = day
        return
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
        if not c.get("due"):
            # Never scheduled yet (it was predicted or taught first, then answered right the same
            # day): give it tomorrow, with no interval or stability, so no credit. Left without a
            # due date it reads as due NOW and comes straight back as another uncredited repeat.
            c["due"] = (_dt.date.fromisoformat(day) + _dt.timedelta(days=1)).isoformat()
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
    return ("weak", "fair", "good")[c.get("streak", 0)] if c.get("streak", 0) < 3 else "mastered"


def mastery_view(c: dict) -> dict:
    return {k: c[k] for k in MASTERY_FIELDS if c.get(k) not in (None, "", 0, [], {})}


def _check_rename(r) -> None:
    if not (isinstance(r.get("from"), str) and isinstance(r.get("to"), str)):
        raise ValueError("a rename row needs from and to")


def renames(cfg, slug) -> dict:
    """{old concept id: new}, from the topic's append-only renames.jsonl (written by `rename`).
    A STRICT ledger: a mapping read in part would silently split a concept's history."""
    from . import ledger as LG
    return {r["from"]: r["to"] for r in LG.read(tdir(cfg, slug) / "renames.jsonl", _check_rename)[0]}


def canonical(cid: str, mapping: dict) -> str:
    """A logged concept id under its current name: renames followed in order, a loop stopped."""
    seen = set()
    while cid in mapping and cid not in seen:
        seen.add(cid)
        cid = mapping[cid]
    return cid


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
    names = renames(cfg, slug)
    if names:
        rows = [dict(r, concept=canonical(r["concept"], names)) for r in rows]
        for old in names:
            new["concepts"].pop(old, None)
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
    """Where the next dialogue's transcript is kept: the evidence behind its grade. A path an
    earlier grade already rests on is never reused, so a second dialogue on the same concept the
    same day gets its own file (-2, -3, ...) and the first grade's evidence stays intact."""
    used = {r.get("transcript") for r in read_log(cfg, slug)[0] if r.get("transcript")}
    base = f"{day}-{slugify(cid)}"
    n = 1
    while True:
        p = tdir(cfg, slug) / "dialogues" / (f"{base}.md" if n == 1 else f"{base}-{n}.md")
        if p.relative_to(tdir(cfg, slug)).as_posix() not in used:
            return p
        n += 1


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


def _dialogue_fields(cfg, slug, cid, result, mode, qtype, rubric, grader, belief, open_questions, state=None,
                     hint_depth=0) -> dict:
    """The extra row fields of a dialogue, checked; {} for a quiz attempt (which may carry none)."""
    belief = {k: str(v).strip() for k, v in (belief or {}).items() if v and str(v).strip()}
    open_questions = [q.strip() for q in open_questions or () if q and q.strip()]
    if state is not None:
        open_questions = [_open_entry(state, q) for q in open_questions]
    unknown = set(belief) - set(BELIEF_FIELDS)
    if unknown:
        raise UsageError(f"unknown belief field(s): {', '.join(sorted(unknown))}")
    if mode == "predict" and set(belief) <= {"before"} and not (rubric or grader or open_questions):
        # the guess itself, kept so `beliefs` can show it beside what happened;
        # still never credited: apply_row returns at the prediction before any scoring
        return {"before": belief["before"]} if belief else {}
    if mode != "dialogue":
        if rubric or grader or belief or open_questions:
            raise UsageError("--rubric, --grader, the belief options and --open are for --mode dialogue only")
        return {}
    if not rubric:
        raise UsageError("a dialogue is graded by its rubric: give --rubric move=score,...")
    if qtype:
        raise UsageError("--qtype is for quiz attempts; a dialogue is graded by its rubric")
    want = rubric_result(rubric, hint_depth)
    if result != want:
        told = (" (the tutor told the answer: --hint-depth 4 caps a dialogue at partial)"
                if hint_depth >= TOLD and rubric_result(rubric) == "ok" else "")
        raise UsageError(f"the rubric grades this {want!r}, not {result!r}{told}: the verdict is the rubric's rule; "
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
           belief=None, open_questions=(), depth="", due=None) -> dict:
    qdepth = depth           # the question's depth; `depth` below is reused for the hint depth
    if result not in RESULTS:
        raise UsageError(f"result must be one of {', '.join(RESULTS)}")
    for val, allowed, what in ((confidence, CONFIDENCE, "--confidence"), (mode, MODES, "--mode"), (qdepth, DEPTHS, "--depth"),
                               (qtype, QTYPES, "--qtype"), (etype, ETYPES, "--etype")):
        if val and val not in allowed:
            raise UsageError(f"{what} {val!r} is not one of {', '.join(allowed)}")
    hint_depth = 0 if hint_depth is None else hint_depth
    if isinstance(hint_depth, bool) or not isinstance(hint_depth, int) or not 0 <= hint_depth <= 4:
        raise UsageError(f"--hint-depth {hint_depth!r} is outside 0-4 (0 = no hint, 4 = read the answer)")
    state = load_state(cfg, slug)
    cid = resolve_concept(state, concept)
    extra = _dialogue_fields(cfg, slug, cid, result, mode, qtype, rubric, grader, belief, open_questions, state,
                             4 if lookup else hint_depth)
    ok = result == "ok"
    depth = 4 if lookup else hint_depth
    row = {"date": H.today().isoformat(), "concept": cid, "correct": ok, "result": result,
           "guess": bool(guess) and ok, "qtype": qtype or "", "etype": etype or "",
           "confidence": confidence or ("low" if guess else ""), "hint_depth": depth,
           "mode": mode or "practice", "note": note or "", **extra}
    c = state["concepts"][cid]
    row["depth"] = qdepth or question_depth(cfg, slug, c, row["mode"])
    row["due"] = bool(c.get("due") and c["due"] <= row["date"]) if due is None else bool(due)
    earlier, damaged = read_log(cfg, slug)
    if damaged:     # a row appended now would be replayed against a record that cannot be read in full
        raise NotEvaluable(f"{slug}: {len(damaged)} damaged log row(s) (first: {damaged[0]}); nothing recorded. "
                           f"Fix the line, or `{H.PROG} rebuild {slug} --skip-damaged`, then record again")
    repeat = any(r["date"] == row["date"] and r["concept"] == cid for r in earlier)
    seen_in = twin_seen(cfg, slug, cid, row["date"])
    if seen_in:          # decided now and kept on the row, so replay never has to read another topic
        row["seen_in"] = seen_in
        repeat = True
    if not repeat and not extra and mode not in ("learn", "predict"):
        qs = load_bank(cfg, slug).get(cid, [])
        if ok and not qs and facets(row)["unaided_ok"]:
            H.warn(f"warn: {cid} has no banked question, so this credit rests on a question asked off the record; "
                   f"bank it (`{H.PROG} bank {slug} {cid} ...`) so the evidence can be read back")
        types = {q.get("type") for q in qs if q.get("type")}
        if qtype and types and qtype not in types:
            H.warn(f"warn: --qtype {qtype} matches none of {cid}'s banked questions ({', '.join(sorted(types))}); "
                   "record the type of the question you actually asked")
    apply_row(c, row, exam_date(load_config(cfg, slug)), repeat)
    from . import ledger as LG
    LG.append(tdir(cfg, slug) / "log.jsonl", row, _check_row, verified=True)   # the log first; damage refused above
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
    if mode == "dialogue":          # not `extra`: a prediction carries its text too
        means = reasoning_means(c)
        weak = min(means, key=lambda k: (means[k], k))
        print(f"{cid}: dialogue {result}, graded by {extra['grader']}; reasoning "
              + "  ".join(f"{k} {v:.1f}/2" for k, v in sorted(means.items()))
              + f"; push on: {weak} (reasoning is kept apart from quiz credit)")
    elif mode == "predict":
        print(f"{cid}: your guess before the explanation ({result}) is recorded; no credit, and any answer "
              "on it later today is a repeat")
    elif repeat:
        print(f"{cid}: {result}, counted; seen already today"
              + (f" (the same idea, under {', '.join(row['seen_in'])})" if row.get("seen_in") else "")
              + f", so no credit → {badge(c)} "
              f"(streak {c.get('streak', 0)}), next review {c.get('due') or 'not scheduled'}")
    else:
        print(f"{cid}: {result} → {badge(c)} (streak {c.get('streak', 0)}), next review {c['due']}"
              + (f" [{c['exam_clamp']}]" if c.get("exam_clamp") else ""))
    return row


# --- plan / sync / bank ----------------------------------------------------------


def rederive(cfg, slug) -> list:
    """Replay the log into state after a setting the schedule reads (a deadline) changed. Returns
    the log's problems; when there are any, nothing is saved: a replay that skipped rows must never
    become the stored state (that is what `rebuild --skip-damaged` is for)."""
    state, probs = replay(cfg, slug, load_state(cfg, slug))
    if not probs:
        save_state(cfg, slug, state)
    return probs


def question_depth(cfg, slug, c: dict, mode: str) -> str:
    """The depth a question on this concept is asked at when none is given: the line's, rung's or
    topic's depth setting, else the mode's default (row_depth)."""
    return concept_setting(cfg, slug, c, "depth") or row_depth({"mode": mode})


def taught(cfg, slug, concept, note="", quiet=False, depth="") -> dict:
    """Record that a concept was taught today (mode teach). No credit, streak or schedule."""
    state = load_state(cfg, slug)
    cid = resolve_concept(state, concept)
    earlier, damaged = read_log(cfg, slug)
    if damaged:
        raise NotEvaluable(f"{slug}: {len(damaged)} damaged log row(s) (first: {damaged[0]}); nothing recorded. "
                           f"Fix the line, or `{H.PROG} rebuild {slug} --skip-damaged`, then record again")
    if depth and depth not in DEPTHS:
        raise UsageError(f"--depth {depth!r} is not one of {', '.join(DEPTHS)}")
    row = {"date": H.today().isoformat(), "concept": cid, "result": "ok", "mode": "teach", "note": note or "",
           "depth": depth or question_depth(cfg, slug, state["concepts"][cid], "teach")}
    apply_row(state["concepts"][cid], row, exam_date(load_config(cfg, slug)))
    from . import ledger as LG
    LG.append(tdir(cfg, slug) / "log.jsonl", row, _check_row, verified=True)   # the log first; damage refused above
    save_state(cfg, slug, state)
    if not quiet:
        print(f"taught: {cid} ({state['concepts'][cid].get('taught', 1)} time(s)); no credit - "
              f"a quiz on it today counts as a repeat; cold recall due {state['concepts'][cid].get('due', '?')}")
    return row


# --- selection and quizzing ---------------------------------------------------


# --- reviews, dates, graduation ---------------------------------------------------


# --- misconceptions, calibration ---------------------------------------------


# --- integrity --------------------------------------------------------------------


# --- the facade -------------------------------------------------------------------
# Split modules: their names still read as `learn.<name>`, resolved on first use.
_SPLIT = ("plan", "quiz", "reviews", "integrity")


def __getattr__(name):
    import importlib
    for m in _SPLIT:
        mod = importlib.import_module(f"{__package__}.{m}")
        if name in vars(mod) and not name.startswith("__"):
            return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

