"""The learn arm: topics, concepts, a question bank, and a record of every attempt.

A topic lives in ``HOME/topics/<slug>/``:

    topic.json     settings you set (title, goal, from_gap, exam_date)
    syllabus.md    the concepts, one line each, under a "## Concepts" heading:
                   - <domain> :: <name> :: <description> [:: cluster:<id>] [:: scope:exam|depth]
    questions.md   the bank, a "## <concept id>" section per concept
    log.jsonl      one line per attempt, append-only: THE RECORD
    concepts.json  mastery and schedule, DERIVED from the log (``learn rebuild``)

Credit is strict on purpose. A correct answer earns streak, retention and
breadth credit only when it was UNAIDED: not a guess, no hint, not read off
the page, not in a massed "learn" pass. A correct you were unsure of
(``--confidence low``) still earns credit but is reviewed sooner.
"""
from __future__ import annotations

import datetime as _dt
import json
import random
import re
import sys
from collections import Counter

from . import demand as DM
from . import facts as F
from . import fsrs
from . import home as H
from .errors import DRIFT, FINDINGS, NOT_EVALUABLE, OK, Drifted, NotEvaluable, UsageError
from .roles import slugify

RESULTS = ("ok", "partial", "miss")
CONFIDENCE = ("low", "med", "high")
MODES = ("practice", "exam", "diagnose", "learn")
QTYPES = ("recall", "applied", "edge", "comparison", "debugging")
ETYPES = ("term-confusion", "concept-conflation", "wrong-scope", "detail-slip", "misapplication", "other")
TESTED_BY = {"term-confusion": {"recall"}, "detail-slip": {"recall"},
             "concept-conflation": {"comparison"}, "wrong-scope": {"comparison"},
             "misapplication": {"applied"}}
RESOLVES_ALL = {"edge", "debugging"}
MAX_SLUG = 64
CONFIG_KEYS = ("title", "goal", "from_gap", "exam_date")
IDENTITY = ("name", "domain", "desc", "cluster", "scope")
MASTERY_FIELDS = ("attempts", "correct", "streak", "partials", "guesses", "hints", "correct_days",
                  "errors", "resolved_idx", "by_type", "by_conf", "last_seen", "stability",
                  "difficulty", "interval", "due", "exam_clamp")
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
        raise UsageError(f"no topic {slug!r} (topics: {known}); create it with `careerloop learn plan`")


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
    return data


def save_config(cfg, slug, conf: dict) -> None:
    load_config(cfg, slug)          # refuses over a damaged file
    H.write_json(tdir(cfg, slug) / "topic.json", {k: conf[k] for k in CONFIG_KEYS if k in conf})


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
        raise NotEvaluable(f"{tdir(cfg, slug) / 'concepts.json'} is damaged; `careerloop learn rebuild {slug}`")
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
             "cluster": "", "scope": "exam"}
        desc = []
        for p in parts[2:]:
            key, _, val = p.partition(":")
            if key in ("cluster", "scope") and val and " " not in key:
                if key == "scope" and val not in ("exam", "depth"):
                    raise UsageError(f"syllabus line {n}: unknown scope {val!r} (exam or depth)")
                c[key] = slugify(val) if key == "cluster" else val
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
    return {"ok": ok, "guess": guess, "conf": conf, "depth": depth, "assisted": depth > 0,
            "massed": massed, "unaided_ok": ok and not guess and depth == 0 and not massed,
            "effortful": ok and conf == "low" and not guess}


def apply_row(c: dict, row: dict, exam) -> None:
    """The one code path from an attempt to state: `record` and `rebuild` both call it."""
    f = facets(row)
    day = row["date"]
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
    if f["conf"] and not f["assisted"] and not f["massed"]:
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
    for r in sorted(rows, key=lambda r: r["date"]):
        c = new["concepts"].get(r["concept"])
        if c is None:
            problems.append(f"log row for unknown concept {r['concept']!r} ({r['date']}) skipped")
            continue
        apply_row(c, r, exam)
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


def record(cfg, slug, concept, result, note="", guess=False, confidence="", hint_depth=0,
           lookup=False, mode="practice", qtype="", etype="", quiet=False) -> dict:
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
    ok = result == "ok"
    depth = 4 if lookup else hint_depth
    row = {"date": H.today().isoformat(), "concept": cid, "correct": ok, "result": result,
           "guess": bool(guess) and ok, "qtype": qtype or "", "etype": etype or "",
           "confidence": confidence or ("low" if guess else ""), "hint_depth": depth,
           "mode": mode or "practice", "note": note or ""}
    c = state["concepts"][cid]
    earlier, _ = read_log(cfg, slug)
    apply_row(c, row, exam_date(load_config(cfg, slug)))
    with open(tdir(cfg, slug) / "log.jsonl", "a", encoding="utf-8") as fh:   # the log first
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if any(r["date"] > row["date"] for r in earlier):
        # back-dated (clock skew between machines): state must be the date-ordered replay
        state, _p = replay(cfg, slug, state)
        c = state["concepts"][cid]
    save_state(cfg, slug, state)
    d, probs = audit(cfg, slug, state)
    if d or probs:
        H.warn(f"DRIFT: {len(d)} concept(s) disagree with the log, {len(probs)} log problem(s); "
               f"`careerloop learn rebuild {slug} --check`")
    if not quiet:
        print(f"{cid}: {result} → {badge(c)} (streak {c.get('streak', 0)}), next review {c['due']}"
              + (f" [{c['exam_clamp']}]" if c.get("exam_clamp") else ""))
    return row


# --- plan / sync / bank ----------------------------------------------------------

SYLLABUS = """# {title}

Goal: {goal}

One concept per line under the Concepts heading:
- <domain> :: <name> :: <what it covers> [:: cluster:<id>] [:: scope:exam|depth]

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
            if c.get(k) or k in ("desc", "scope"):
                cur[k] = c.get(k, "")
    save_state(cfg, slug, state)
    d = drift(cfg, slug, state)
    if d:
        H.warn(f"DRIFT: {len(d)} concept(s) disagree with the log; `careerloop learn rebuild {slug} --check`")
    if not quiet:
        print(f"{slug}: {len(parsed)} concept(s) in the syllabus, {added} new")
    return _log_verdict(cfg, slug)       # the drift check above read a log that may be damaged


def plan(cfg, slug, title=None, goal=None, from_gap=None, top=None, force=False) -> int:
    if not slug or slug != slugify(slug):
        raise UsageError(f"topic slug {slug!r} should be {slugify(slug)!r}" if slug
                         else "the topic slug must not be empty")
    if len(slug) > MAX_SLUG:
        raise UsageError(f"topic slug is {len(slug)} characters; the limit is {MAX_SLUG}")
    d = tdir(cfg, slug)
    exists = d.is_dir()
    bucket = None
    if from_gap and from_gap != "none":        # validate before creating anything
        data, stale = DM.load(cfg)
        names = [b["name"] for b in data["buckets"]]
        if from_gap not in names:
            raise UsageError(f"no bucket {from_gap!r} in {cfg.upskill.name} (buckets: {'; '.join(names) or 'none'}; "
                             "or --from-gap none)")
        bucket = next(b for b in data["buckets"] if b["name"] == from_gap)
        if stale:
            H.warn(f"{cfg.upskill.name} is stale; re-run `careerloop jobs upskill`")
    if exists and not (force or from_gap):
        raise UsageError(f"topic {slug} exists; pass --force to update its title/goal (the syllabus is never overwritten)")
    d.mkdir(parents=True, exist_ok=True)
    conf = load_config(cfg, slug)
    conf.setdefault("title", title or slug.replace("-", " "))
    if title:
        conf["title"] = title
    if goal:
        conf["goal"] = goal
    syl = d / "syllabus.md"
    if not syl.exists():
        syl.write_text(SYLLABUS.format(title=conf["title"], goal=conf.get("goal", "")), encoding="utf-8")
    if not (d / "questions.md").exists():
        (d / "questions.md").write_text(
            f"# Question bank — {conf['title']}\n\nAdd with `careerloop learn bank {slug} <concept> --q --a --ref`.\n\n",
            encoding="utf-8")
    (d / "log.jsonl").touch()
    added = skipped = 0
    if bucket is not None:
        facts = F.read(cfg)
        text = H.read_text(syl, "syllabus")
        have = {c["name"].lower() for c in parse_syllabus(text)}
        new_lines = []
        for it in [i for i in bucket["items"] if not i["noise"]][: top or None]:
            if F.holds(it["term"], facts) or it["term"].lower() in have:
                skipped += 1
                continue
            have.add(it["term"].lower())
            new_lines.append(f"- {slugify(from_gap)} :: {it['term']} :: wanted by {it['count']} role(s)")
            added += 1
        if new_lines:
            if not re.search(r"(?m)^## Concepts\s*$", text):
                text = text.rstrip("\n") + "\n\n## Concepts\n\n"
            syl.write_text(_insert_concepts(text, new_lines), encoding="utf-8")
    if from_gap:
        conf["from_gap"] = from_gap
    save_config(cfg, slug, conf)
    if not (d / "concepts.json").exists():
        save_state(cfg, slug, {"concepts": {}})
    code = sync(cfg, slug, quiet=True)
    msg = f"{slug}: {'updated' if exists else 'created'} {d.relative_to(cfg.home)}"
    if bucket is not None:
        msg += f"; from {from_gap!r}: {added} concept(s) added, {skipped} skipped (held or present)"
    print(msg)
    return code


def _insert_concepts(text: str, new_lines: list) -> str:
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
    p.write_text("\n".join(lines).strip("\n") + "\n", encoding="utf-8")
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


def _log_verdict(cfg, slug) -> int:
    """OK when the log reads in full; otherwise warn and NOT_EVALUABLE. `due` and
    `quiz` read the derived concepts.json, so a damaged log row means what they
    printed may not match the record: they still print, then exit 2."""
    bad = len(read_log(cfg, slug)[1])
    if not bad:
        return OK
    H.warn(f"{slug}: {bad} damaged log row(s): what was shown was derived without them and may not match "
           f"the record; run `careerloop learn validate {slug}` or `learn rebuild {slug} --check`")
    return NOT_EVALUABLE


def quiz(cfg, slug, n=5, weak=False, concept=None) -> int:
    state = load_state(cfg, slug)
    if not state["concepts"]:
        raise NotEvaluable(f"{slug} has no concepts yet: add them to syllabus.md and run `careerloop learn sync {slug}`")
    bank_ = load_bank(cfg, slug)
    for cid in select(state, n, weak, concept):
        c = state["concepts"][cid]
        q, _i = pick_question(bank_, cid, c)
        print(f"- {cid} [{badge(c)}]" + (f"  Q: {q['q']}" if q else "  (no banked question)"))
        et = dominant_etype(c)
        if et:
            last = open_errors(c)[-1][1]
            print(f"    recurring {et}: {REASK[et]}  (last: {last})")
    print(f"record each: careerloop learn record {slug} <concept> ok|partial|miss [--confidence L] [--qtype T]")
    return _log_verdict(cfg, slug)


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
    record through the same path as `learn record`. EOF or `q` ends the
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
                out.write(f"\n{cid}: no banked question; skipped (bank one with `careerloop learn bank`)\n")
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
    return _log_verdict(cfg, slug)


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
        code = max(code, _log_verdict(cfg, t))
    return code


def set_exam_date(cfg, slug, set_=None, clear=False) -> int:
    need_topic(cfg, slug)
    conf = load_config(cfg, slug)
    if set_:
        try:
            d = H.iso_date(set_)
        except ValueError as e:
            raise UsageError(f"--set {set_!r} is not YYYY-MM-DD") from e
        if d <= H.today():
            raise UsageError(f"--set {set_} is not in the future")
        conf["exam_date"] = d.isoformat()
    elif clear:
        conf.pop("exam_date", None)
    else:
        return show_exam(cfg, slug)
    save_config(cfg, slug, conf)
    label = f"exam date {conf['exam_date']}" if conf.get("exam_date") else "exam date cleared"
    state, probs = replay(cfg, slug, load_state(cfg, slug))
    if probs:
        # a replay that skipped rows must not become the stored state (that is what `rebuild --skip-damaged` is for)
        print(f"{slug}: {label}{' and' if clear else ''} saved; schedules NOT re-derived: "
              f"{len(probs)} log problem(s), so the record cannot be read in full")
        return _log_verdict(cfg, slug)
    save_state(cfg, slug, state)
    print(f"{slug}: {label}; schedules re-derived from the log")
    return OK


def show_exam(cfg, slug) -> int:
    conf = load_config(cfg, slug)
    ex = exam_date(conf)
    if ex is None:
        print(f"{slug}: no exam date (set one with --set YYYY-MM-DD)")
        return _log_verdict(cfg, slug)
    state = load_state(cfg, slug)
    cons = [(cid, c) for cid, c in state["concepts"].items() if c.get("scope", "exam") == "exam"]
    if not cons:
        raise NotEvaluable(f"{slug} has no exam-scope concepts: exam readiness cannot be judged")
    print(f"{slug}: exam {ex} ({(ex - H.today()).days} days)")
    for cid, c in cons:
        if not c.get("stability"):
            print(f"  {cid}: not studied")
            continue
        prev = _dt.date.fromisoformat(c["due"]) - _dt.timedelta(days=c["interval"])
        r = fsrs.retrievability(c["stability"], (ex - prev).days)
        flag = "  STRANDED (due after the exam)" if c["due"] >= ex.isoformat() else ""
        print(f"  {cid}: predicted recall at the exam {r:.2f}" + ("  LOW" if r < 0.7 else "") + flag)
    return _log_verdict(cfg, slug)


def breadth_ok(c) -> bool:
    bt = c.get("by_type") or {}
    if not bt:
        return False            # no typed attempts: breadth was never tested, so it has not passed
    return sum(1 for v in bt.values() if v["attempts"] and v["correct"] / v["attempts"] >= BREADTH_RATE) >= BREADTH_TYPES


def interference_ok(rows, cid) -> bool:
    """An unaided correct on a day when >= 3 other concepts were also studied."""
    by_day: dict = {}
    for r in rows:
        by_day.setdefault(r["date"], set()).add(r["concept"])
    return any(r["concept"] == cid and facets(r)["unaided_ok"]
               and len(by_day[r["date"]] - {cid}) >= INTERFERENCE_OTHERS for r in rows)


EMIT_SUFFIX = " (held knowledge from study; a knowledge claim, separate from work claims)"


def emit_line(name) -> str:
    return f"- {name}{EMIT_SUFFIX}"


def emit_problem(name) -> str:
    """Why the line `--emit` would print for `name` could not pass the claim gate
    ("" when it can): it must read back as held, with no qualifier, from a
    sheet that holds nothing else."""
    sheet = F.analyse("## Held\n" + emit_line(name))
    bad = [b for b in sheet.blocks if b.held and not b.heading and b.qualified]
    if bad:
        return f"it would read as qualified ({bad[0].why})"
    if not F.holds(name, "## Held\n" + emit_line(name)):
        return "it would not read back as held (markup such as ~~ or <!-- in the name)"
    return ""


def _comment_safe(text) -> str:
    """Text for inside an HTML comment: no `--`, so no early `-->` and no nested `<!--`."""
    return re.sub(r"-{2,}", "-", re.sub(r"\s+", " ", str(text))).replace("<!-", "<!").strip()


def graduation(cfg, slug) -> dict:
    """Candidates from a VALIDATED view only. Graduation says what may be copied
    into the facts sheet, so it refuses (never emits a subset) when the log was
    not read in full or the cached mastery disagrees with a full replay."""
    state = load_state(cfg, slug)
    rows, _p = read_log(cfg, slug)
    drifted, problems = audit(cfg, slug, state)
    if problems:
        raise NotEvaluable(f"{slug}: {len(problems)} log problem(s) (first: {problems[0]}); the record was not read "
                           f"in full, so no graduation is offered; fix the log, then `careerloop learn rebuild {slug}`")
    if drifted:
        raise Drifted(f"{slug}: {len(drifted)} concept(s) disagree with the log ({', '.join(drifted[:5])}); "
                      f"mastery is stale, so no graduation is offered; run `careerloop learn rebuild {slug}`")
    facts = F.read(cfg)
    out = {"candidates": [], "held": [], "not retained": [], "not breadth-tested": [], "drilled solo": [],
           "unwritable": []}
    for cid, c in state["concepts"].items():
        if badge(c) != "mastered":
            continue
        if len(c.get("correct_days", [])) < RETENTION_DAYS:
            out["not retained"].append(cid)
        elif not breadth_ok(c):
            out["not breadth-tested"].append(cid)
        elif not interference_ok(rows, cid):
            out["drilled solo"].append(cid)
        elif F.holds(c.get("name", ""), facts):
            out["held"].append(cid)
        elif emit_problem(c.get("name", cid)):
            out["unwritable"].append(cid)        # would fail the claim gate once pasted: never a candidate
        else:
            out["candidates"].append(cid)
    return out


WHY = {"not retained": f"correct on fewer than {RETENTION_DAYS} separate days",
       "not breadth-tested": f"fewer than {BREADTH_TYPES} question types at {int(BREADTH_RATE * 100)}%+ "
                             "(record --qtype)",
       "drilled solo": f"never answered unaided on a day when {INTERFERENCE_OTHERS}+ other concepts were also studied"}


def graduate(cfg, slug, emit=False) -> int:
    g = graduation(cfg, slug)
    state = load_state(cfg, slug)
    conf = load_config(cfg, slug)
    if emit:
        # Lines only, no heading of their own: the owner pastes them under `## Held`,
        # and the topic title goes in a comment so its words never become held claims.
        for cid in g["unwritable"]:
            name = state["concepts"][cid].get("name", cid)
            H.warn(f"not emitted: {name!r} is mastered but {emit_problem(name)}; rename the concept in "
                   f"{slug}/syllabus.md, then run graduate again")
        if not g["candidates"]:
            print(f"<!-- {slug}: no graduation candidates -->")
            return OK
        names = [state["concepts"][c].get("name", c) for c in g["candidates"]]
        names.sort()
        lines = [emit_line(n) for n in names]
        head = (f"<!-- paste the lines below under `## Held` in facts.md: "
                f"`careerloop learn graduate {slug} --emit` @ {H.today()}: "
                f"{_comment_safe(conf.get('title', slug))}; {len(lines)} retained-mastered -->")
        block = "\n".join([head, *lines])
        # the block must pass its own gate, or nothing is printed
        sheet = "## Held\n" + block
        got = F.analyse(sheet)
        if (got.unclosed or F.contradiction_blocks(sheet) or not all(F.holds(n, sheet) for n in names)
                or len([b for b in got.blocks if b.held and not b.heading]) != len(lines)):
            raise NotEvaluable(f"{slug}: the emitted block would not read back as held; refusing to print it")
        print(block)
        return OK
    print(f"## Ready for facts.md ({len(g['candidates'])})")
    for cid in g["candidates"]:
        print(f"  {cid}")
    if g["held"]:
        print(f"## Already held in facts.md ({len(g['held'])})")
        for cid in g["held"]:
            print(f"  {cid}")
    if g["unwritable"]:
        print(f"## Mastered but cannot be written to facts.md ({len(g['unwritable'])}): rename the concept in the syllabus")
        for cid in g["unwritable"]:
            print(f"  {cid}: {emit_problem(state['concepts'][cid].get('name', cid))}")
    for k in ("not retained", "not breadth-tested", "drilled solo"):
        if g[k]:
            print(f"## Mastered but held back: {k} ({len(g[k])}): {WHY[k]}")
            for cid in g[k]:
                print(f"  {cid}")
    if g["candidates"]:
        print(f"paste `careerloop learn graduate {slug} --emit` under ## Held in facts.md yourself; nothing writes it for you")
    return OK


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
    return _log_verdict(cfg, slug)


def calibration(cfg, slug) -> int:
    need_topic(cfg, slug)
    rows, _p = read_log(cfg, slug)
    code = _log_verdict(cfg, slug)
    acc: dict = {}
    for r in rows:
        f = facets(r)
        if not f["conf"] or f["assisted"] or f["massed"]:
            continue
        a = acc.setdefault(f["conf"], [0, 0])
        a[0] += 1
        a[1] += f["ok"]
    if not acc:
        print(f"{slug}: no confidence-rated unaided attempts yet: calibration NOT EVALUABLE")
        return NOT_EVALUABLE
    for lvl in CONFIDENCE:
        if lvl in acc:
            n, k = acc[lvl]
            print(f"  {lvl:5} {k}/{n} correct ({100 * k / n:.0f}%)")
    if "high" in acc and acc["high"][1] / acc["high"][0] < 0.8:
        print("OVERCONFIDENT: high-confidence answers are right less than 80% of the time")
    if "low" in acc and acc["low"][1] / acc["low"][0] > 0.8:
        print("UNDERCONFIDENT: low-confidence answers are right more than 80% of the time")
    return code


# --- the learn side of the seam ----------------------------------------------

def planned_buckets(cfg) -> set:
    """Buckets a topic was planned from (topic.json from_gap). A topic's slug
    alone never claims a bucket. Damaged topics are skipped here; rule 1 and
    doctor report them."""
    out = set()
    for t in topics(cfg):
        try:
            conf = load_config(cfg, t)
        except NotEvaluable:
            continue
        if conf.get("from_gap"):
            out.add(conf["from_gap"])
    return out


def is_planned(bucket_name, planned) -> bool:
    return bucket_name in planned


def gaps(cfg) -> int:
    try:
        data, stale = DM.load(cfg)
    except NotEvaluable as e:
        if cfg.upskill.exists():
            raise
        raise NotEvaluable(f"{e} (0 role(s) analysed, 0 demand bucket(s) measured)") from e
    if stale:
        H.warn(f"{cfg.upskill.name} is older than your roles or facts; re-run `careerloop jobs upskill`")
    planned = planned_buckets(cfg)
    n_roles = data.get("roles_analyzed", 0)
    if not n_roles:
        print(f"NOT EVALUABLE gaps: 0 role(s) analysed in {cfg.upskill.name}, so no demand has been measured; "
              "check a role (`careerloop jobs check SLUG`) and re-run `careerloop jobs upskill`")
        return NOT_EVALUABLE
    print(f"gaps: {len(data['buckets'])} demand bucket(s) from {n_roles} role(s)")
    for b in data["buckets"]:
        mark = "planned" if is_planned(b["name"], planned) else ""
        print(f"{b['demand']:7.2f}  {b['name']}  {mark}")
        for it in b["items"][:6]:
            print(f"           {it['term']} ({it['demand']}, {it['count']} role(s))" + (" ignored" if it["noise"] else ""))
    top = next((b for b in data["buckets"] if b["demand"] > 0 and not is_planned(b["name"], planned)
                and b["name"] != "Unmapped: acronym"), None)
    if top:
        print(f"suggest: careerloop learn plan {slugify(top['name'])} --from-gap \"{top['name']}\"")
    return OK


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
    conf = load_config(cfg, slug)
    cons = state["concepts"]
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
    if not conf.get("from_gap"):
        warn.append(f"{slug}: not linked to a demand bucket (set from_gap, or \"none\" to opt out)")
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
    question counts, the bank format `learn validate` accepts, and the rules."""
    need_topic(cfg, slug)
    conf = load_config(cfg, slug)
    state = load_state(cfg, slug)
    bank = load_bank(cfg, slug)
    title = conf.get("title") or slug
    out = [f"# Study brief: {title} ({slug})", "",
           "careerloop wrote this from the topic's syllabus, its question bank and its log. It holds "
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
        out.append("- (no concepts yet: add them to syllabus.md and run `careerloop learn sync`)")
    if conf.get("from_gap") and conf["from_gap"] != "none":
        out += ["", f"Seeded from the demand bucket {conf['from_gap']!r}: the jobs you track ask for it."]
    out += ["", "## Format (exactly this; `##` is the concept id from the list above)", "",
            "```markdown", BANK_EXAMPLE.rstrip("\n"), "```", "",
            "## Wanted from you", "",
            "1. Three questions for each concept with fewer than three, of at least two types.",
            "2. Append them to the topic's questions.md under the concept's `##` heading.",
            f"3. Check: `careerloop learn validate {slug}` must report 0 failure(s).", ""]
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
    for w in warn:
        H.warn(f"warn: {w}")
    for h in hard:
        print(f"FAIL {h}")
    for d in damaged:
        print(f"DAMAGED {d}")
    print(f"validate: {len(hard)} failure(s), {len(warn)} warning(s), {len(damaged)} damaged log row(s)"
          + ("; the log cannot be read in full, so the topic is not evaluable (see `learn rebuild --check`)"
             if damaged else ""))
    return NOT_EVALUABLE if damaged else FINDINGS if hard else OK
