"""`next` and `doctor`: the loop as one decision, and the loop's health.

``next`` answers "what is the single most useful thing to do now?" by evaluating fixed rules
in order over the state study and the sidecars already keep. The first rule that fires wins.
``--all`` prints every rule's evaluation so the choice can be audited; a rule that cannot be
evaluated says so and why. Learning comes first; a closing deadline still outranks it.

    empty       nothing to work on                          -> plan a topic       (exit 2)
    integrity   a topic disagrees with its log, or fails validation -> rebuild / validate
    deadline    a strong role closes within deadline_days   -> tailor it, or mark it applied
    reviews     reviews are due (an exam soon first, then job demand) -> due
    continue    (off unless [next] continue_last) the topic you studied last -> session
    question    a dialogue left a question open, or a question has no rungs -> talk / ask
    graduation  a career topic's concept passed every gate  -> graduate --emit, paste under ## Held
    role        strong roles are waiting                    -> tailor the best
    fresh       a topic has banked, unstudied concepts      -> quiz --weak
    study       the study graph has a ready concept (its pieces, what comes before it and its
                ladder rungs below are climbed)              -> quiz it, or talk it through
    seed        the top unplanned demand bucket is big enough -> plan --from-gap
    score       roles are waiting to be scored              -> score the oldest
    fallback    nothing is ripe                             -> ask a question (discover, with targets)
"""
from __future__ import annotations

import json
import re

from .career import ats
from .career import demand as DM
from .career import facts as F
from .career import graduate as G
from .career import jobs as J
from .career import promote as PR
from .career import roles as R
from .career import seed as SD
from .core import home as H
from .core import ledger as LG
from .core import branches as B
from .core import graph as SG
from .core import learn as L
from .core import marks as MK
from .core import onramp as O
from .core import questions as Q
from .core.errors import DRIFT, FINDINGS, NOT_EVALUABLE, OK, Drifted, NotEvaluable, UsageError

EXAM_SOON_DAYS = 14

_ITEM = re.compile(r"^\s*([-*+]|\d+\.)\s")


def _cl(*args) -> list:
    return [H.PROG, *args]


_KEYWORD_NOTE = ("; replace … with a word from the titles you want (`discover --intake` takes in every "
                 "posting that matches it, so it never runs without one)")


def _take_in(cfg) -> list:
    """A command that takes roles IN (a bare `discover --all` only lists them)."""
    if cfg.targets:
        return _cl("jobs", "discover", "--all", "--intake", "--keyword", "…")
    return _cl("jobs", "intake", "--company", "…", "--role", "…")


def _advance(cfg, slug, meta) -> list:
    """What moves a strong role forward: check it first if its coverage is
    missing or stale (tailor would refuse), else tailor, else mark applied."""
    try:
        cov = J.load_coverage(cfg, slug)
    except NotEvaluable:
        cov = None
    if cov is None or J.coverage_stale(cfg, slug, cov):
        return _cl("jobs", "check", slug)
    if meta.get("status") == "tailoring":
        return _cl("jobs", "status", slug, "applied")
    return _cl("jobs", "tailor", slug)


def _mastered_pct(cfg, t) -> float:
    cons = L.load_state(cfg, t)["concepts"]
    return sum(L.badge(c) == "mastered" for c in cons.values()) / len(cons) if cons else 0.0


#: rules about the job search; the interest lane switches them off
JOB_RULES = ("deadline", "graduation", "role", "seed", "score")


class _Ctx:
    """What every rule reads: the home, the filters, the day, the roles and the topics. The
    integrity rule narrows `tops` to the topics that load cleanly and sets `active` (the study
    rules' topics); the question rule reads the asks ledger once for the study rule."""

    def __init__(self, cfg, lane, topic):
        self.cfg, self.lane, self.topic = cfg, lane, topic
        self.today = H.today()
        self.roles, self.damaged = R.scan(cfg)
        self.tops = L.topics(cfg)
        self.active = []
        self.events, self.ask_probs = [], []
        self.out = []
        try:
            self.upskill, self.stale = DM.load(cfg)
            self.up_err = ""
        except NotEvaluable as e:
            self.upskill, self.stale, self.up_err = None, False, str(e)
        self.bucket_demand = {b["name"]: b["demand"] for b in (self.upskill or {}).get("buckets", [])}

    def add(self, rule, status, detail, argv=None, reason="", complete=True):
        self.out.append({"rule": rule, "status": status, "detail": detail, "argv": argv or [], "reason": reason,
                         "argv_complete": complete})


def _rule_empty(c) -> None:
    cfg = c.cfg
    roles = c.roles
    tops = c.tops
    add = c.add
    # empty
    if not roles and not tops and cfg.targets:
        add("empty", "fired", "no topics and no roles", _take_in(cfg),
            "NOT EVALUABLE: nothing to work on yet (0 topic(s), 0 role(s))" + _KEYWORD_NOTE, complete=False)
    elif not roles and not tops:
        add("empty", "fired", "no topics and no roles", _cl("plan", "…"),
            "NOT EVALUABLE: nothing to work on yet (0 topic(s), 0 role(s)); plan a topic you want to understand, "
            "or take roles in with `jobs intake`", complete=False)
    else:
        add("empty", "not fired", f"{len(tops)} topic(s), {len(roles)} role(s)")


def _rule_integrity(c) -> None:
    cfg = c.cfg
    lane = c.lane
    topic = c.topic
    damaged = c.damaged
    add = c.add
    tops = c.tops
    # integrity
    bad = []
    for t in tops:
        try:
            d, probs = L.audit(cfg, t)
            h, _w = L.problems(cfg, t)
        except (NotEvaluable, UsageError) as e:
            bad.append((t, str(e), _cl("rebuild", t)))
            continue
        if probs:
            bad.append((t, f"{len(probs)} unreadable log row(s)", _cl("rebuild", t, "--check")))
        elif d:
            bad.append((t, f"{len(d)} concept(s) drifted from the log", _cl("rebuild", t)))
        elif h:
            bad.append((t, f"{len(h)} validation failure(s)", _cl("validate", t)))
    broken = {t for t, _w, _a in bad}
    tops = [t for t in tops if t not in broken]      # later rules read only topics that load cleanly
    # a passed cert topic is complete: no reviews, on-ramp, questions or study are suggested for it
    # (graduation still reads it: what it proved may still go to facts.md). Named commands still work.
    # One set to keep studying stays: the exam is done, the material is not.
    active = [t for t in tops if not L.off_schedule(cfg, t) and (lane is None or L.lane_of(cfg, t) == lane)
              and (topic is None or t == topic)]
    if damaged:
        bad.append(("roles", f"{len(damaged)} damaged role file(s): {damaged[0]}", _cl("doctor")))
    if bad:
        t, why, argv = bad[0]
        add("integrity", "fired", f"{len(bad)} integrity problem(s)", argv, f"{t}: {why}")
    else:
        add("integrity", "not fired", "every topic matches its log and validates")
    c.tops = tops
    c.active = active


def _rule_deadline(c) -> None:
    cfg = c.cfg
    today = c.today
    roles = c.roles
    add = c.add
    # deadline
    hot = []
    for s, m in J.shortlist(cfg, roles):
        dl = J._days_to(m.get("deadline"), today)
        if dl is not None and 0 <= dl <= cfg.deadline_days:
            hot.append((dl, -(m.get("fit_score") or 0), s, m))
    if hot:
        dl, _nf, s, m = sorted(hot)[0]
        argv = _advance(cfg, s, m)
        add("deadline", "fired", f"{len(hot)} strong role(s) closing within {cfg.deadline_days}d", argv,
            f"{s}: deadline in {dl} day(s), fit {m.get('fit_score')}")
    else:
        add("deadline", "not fired", f"no role at fit >= {cfg.bar} closes within {cfg.deadline_days} day(s)")


def _rule_reviews(c) -> None:
    cfg = c.cfg
    today = c.today
    active = c.active
    stale = c.stale
    bucket_demand = c.bucket_demand
    add = c.add
    # reviews
    wanted = []
    for t in active:
        conf = L.load_config(cfg, t)
        n_due = len(L.due_list(cfg, t, today))
        if not n_due:
            continue
        ex = L.exam_date(conf)
        demand = bucket_demand.get(conf.get("origin", ""), 0) if L.has_outlet(conf, "career") else 0
        if ex and 0 < (ex - today).days <= EXAM_SOON_DAYS:
            rank, why = 0, f"; exam in {(ex - today).days} day(s)"
        elif demand > 0:
            rank, why = 1, f"; bucket demand {demand}" + (" (upskill.json is stale; re-run jobs upskill)" if stale else "")
        else:
            rank, why = 2, ""
        wanted.append((rank, -n_due, _mastered_pct(cfg, t), t, why))
    if wanted:
        _r, nd, _p, t, why = sorted(wanted)[0]
        add("reviews", "fired", f"{len(wanted)} topic(s) with reviews due", _cl("due", t),
            f"{-nd} review(s) due in {t} (~{-2 * nd} min){why}")
    else:
        add("reviews", "not fired", "no reviews are due")


def _rule_onramp(c) -> None:
    cfg = c.cfg
    active = c.active
    add = c.add
    # onramp: a fresh topic is placed before anything is graded; then the rung you are climbing is taught
    ramp = []
    for t in active:
        try:
            got = O.next_step(cfg, t)
        except (NotEvaluable, UsageError) as e:
            ramp.append(("", t, ["place", t], f"not evaluable: {e}"))
            continue
        if got:
            ramp.append((got[0][0], t, got[0], got[1]))
    if ramp:
        _k, t, argv, why = sorted(ramp, key=lambda x: (x[0] != "place", x[1]))[0]
        add("onramp", "fired", f"{len(ramp)} topic(s) on the on-ramp", _cl(*argv), why)
    else:
        add("onramp", "not fired", "no fresh scale waits for placement, and no climbing rung is untaught")


def _rule_question(c) -> None:
    cfg = c.cfg
    lane = c.lane
    topic = c.topic
    active = c.active
    add = c.add
    # an open question nothing has followed up: a dialogue's, else a question with no rungs yet
    opened = []
    for t in active:
        rows = [r for r in L.read_log(cfg, t)[0] if r.get("mode") == "dialogue"]
        cons = L.load_state(cfg, t)["concepts"]
        for i, r in enumerate(rows):
            for text in r.get("open", []):
                cid, q = L.open_target(cons, text, r["concept"])
                if not any(x["concept"] == cid and x["date"] > r["date"] for x in rows[i + 1:]):
                    opened.append((r["date"], t, cid, q))
    events, ask_probs = Q.read(cfg)
    rung_of = {e["ask"] for e in events if e["event"] == "rung"}
    bare = [e for e in events if e["event"] == "ask" and e["id"] not in rung_of
            and lane != "career" and topic is None]   # a question with no ladder yet is curiosity: the interest lane's
    if opened:
        day, t, cid, q = sorted(opened)[0]
        add("question", "fired", f"{len(opened)} open question(s) from dialogues", _cl("talk", t, cid),
            f"left open on {day}: {q}")
    elif bare:
        e = bare[0]
        add("question", "fired", f"{len(bare)} question(s) with no rungs yet", _cl("ask"),
            f"{e['id']} has no ladder yet: {e['question']}")
    elif ask_probs:
        add("question", "not evaluable", f"asks.jsonl cannot be read in full: {ask_probs[0]}")
    else:
        add("question", "not fired", "every open question has been followed up")
    c.events = events
    c.ask_probs = ask_probs


def _rule_graduation(c) -> None:
    cfg = c.cfg
    tops = c.tops
    add = c.add
    # graduation
    grads, n_held, n_unwritable = [], 0, 0
    try:
        F.read(cfg)
        facts_err = ""
    except NotEvaluable as e:
        facts_err = str(e)
    for t in ([] if facts_err else tops):
        try:
            if not L.has_outlet(L.load_config(cfg, t), "career") and not PR.promoted(cfg, t):
                continue                    # a career topic, or an interest topic's promoted concepts
        except NotEvaluable:
            continue                        # a damaged promotions ledger is reported by graduate
        try:
            g = G.graduation(cfg, t)
        except (NotEvaluable, Drifted):
            continue
        n_held += len(g["held"])
        n_unwritable += len(g["unwritable"])
        if g["candidates"]:
            grads.append((-len(g["candidates"]), t))
    if facts_err:
        add("graduation", "not evaluable", f"what you hold is unknown: {facts_err}")
    elif grads:
        n, t = sorted(grads)[0]
        add("graduation", "fired", f"{sum(-g for g, _t in grads)} concept(s) ready", _cl("jobs", "graduate", t, "--emit"),
            f"{-n} concept(s) in {t} passed every graduation gate; paste them under ## Held in facts.md, then re-run jobs check")
    else:
        add("graduation", "not fired", (f"{n_held} concept(s) passed every gate, all already in facts.md" if n_held
                             else "no concept has passed all four graduation gates")
            + (f"; {n_unwritable} mastered concept(s) cannot be written as a facts line (rename them; "
               "see `jobs graduate`)" if n_unwritable else ""))


def _rule_role(c) -> None:
    cfg = c.cfg
    roles = c.roles
    add = c.add
    # role
    sl = J.shortlist(cfg, roles)
    if sl:
        s, m = sl[0]
        argv = _advance(cfg, s, m)
        add("role", "fired", f"{len(sl)} role(s) at or above the bar", argv,
            f"{s}: fit {m.get('fit_score')}, coverage {m.get('coverage_pct', '-')}%")
    else:
        add("role", "not fired", f"no live role in the work queue at fit >= {cfg.bar}")


def _rule_fresh(c) -> None:
    cfg = c.cfg
    active = c.active
    add = c.add
    # fresh
    fresh = []
    for t in active:
        bank = L.load_bank(cfg, t)
        cons = L.load_state(cfg, t)["concepts"]
        n = sum(1 for cid, c in cons.items() if not c.get("attempts") and bank.get(cid))
        if n:
            fresh.append((-n, t))
    if fresh:
        n, t = sorted(fresh)[0]
        add("fresh", "fired", f"{sum(-f for f, _t in fresh)} banked concept(s) never studied",
            _cl("quiz", t, "--weak", "--interactive"), f"{-n} unstudied concept(s) with questions in {t}")
    else:
        add("fresh", "not fired", "no topic has banked, unstudied concepts")


def _rule_study(c) -> None:
    cfg = c.cfg
    active = c.active
    events = c.events
    add = c.add
    # study: the frontier of the study graph (core/graph.py); a ladder rung you asked for first,
    # then a piece of a concept, then by rung. It never moves credit, only what is asked next.
    # [next] intent_rank (default off): at the same kind, an `understand` idea before a `pass` one.
    by_intent = bool((cfg.raw.get("next") or {}).get("intent_rank", False))
    ready, offers = [], 0
    for t in active:
        try:
            cons = L.load_state(cfg, t)["concepts"]
            g = SG.build(cfg, t, events)
            bank = L.load_bank(cfg, t)
            offers += len(B.candidates(cfg, t))
        except (NotEvaluable, UsageError):
            continue
        for i, n in enumerate(SG.frontier(g)):
            kind = 0 if n.ladders else 1 if n.recall_missed else 2 if n.part_of in g.nodes else 3
            passing = by_intent and O.concept_setting(cfg, t, cons.get(n.cid, {}), "intent") == "pass"
            ready.append((kind, MK.RANK.get(n.mark, 2), passing, n.rung if n.rung is not None else 99, t, i, n,
                          bool(bank.get(n.cid))))
    if ready:
        kind, _m, _p, _r, t, _i, n, banked = sorted(ready, key=lambda x: x[:6])[0]
        how = (f"rung {n.ladders[0][1]} of {n.ladders[0][0]}, a question you asked" if kind == 0
               else f"a piece of {n.part_of} you missed when recalling it" if kind == 1
               else f"a piece of {n.part_of}" if kind == 2 else "ready: everything it rests on is climbed")
        if n.mark in ("problem", "fuzzy"):
            how += f"; you marked it {n.mark}"
        argv = _cl("quiz", t, "--concept", n.cid, "--interactive") if banked else _cl("talk", t, n.cid)
        add("study", "fired", f"{len(ready)} concept(s) ready to study" + (f"; {offers} branch offer(s) waiting "
                                                                           "(`ken branch SLUG`)" if offers else ""),
            argv, f"{n.cid} in {t}: {how}" + ("" if banked else " (no banked question: a dialogue first)"))
    else:
        add("study", "not fired", "nothing on the study graph is ready and unclimbed"
            + (f"; {offers} branch offer(s) waiting (`ken branch SLUG`)" if offers else ""))


def _rule_seed(c) -> None:
    cfg = c.cfg
    upskill = c.upskill
    stale = c.stale
    up_err = c.up_err
    add = c.add
    # seed
    if upskill is None:
        add("seed", "not evaluable", up_err)
    else:
        planned = SD.planned_buckets(cfg)
        cands = [b for b in upskill["buckets"] if not SD.is_planned(b["name"], planned)
                 and b["name"] != DM.ACRONYM_BUCKET and b["demand"] >= cfg.min_bucket_demand]
        if cands:
            b = cands[0]
            add("seed", "fired", f"{len(cands)} unplanned bucket(s) at demand >= {cfg.min_bucket_demand}",
                _cl("plan", R.slugify(b["name"]), "--from-gap", b["name"]),
                f"demand {b['demand']}: " + ", ".join(i["term"] for i in b["items"][:4])
                + (" (upskill.json is stale; re-run jobs upskill)" if stale else ""))
        else:
            add("seed", "not fired", f"no unplanned bucket reaches demand {cfg.min_bucket_demand}")


def _rule_score(c) -> None:
    cfg = c.cfg
    roles = c.roles
    add = c.add
    # score
    q = J.needs_scoring(cfg, roles)
    if q:
        add("score", "fired", f"{len(q)} role(s) unscored", _cl("jobs", "score", q[0][0], "--fit", "N"),
            f"oldest found {q[0][1].get('found')}; fill scorecard.md first, then replace N", complete=False)
    else:
        add("score", "not fired", "every role is scored")


def _rule_fallback(c) -> None:
    cfg = c.cfg
    lane = c.lane
    topic = c.topic
    out = c.out
    add = c.add
    # fallback
    if topic is not None:
        for e in out:
            if e["rule"] in JOB_RULES:
                e.update(status="off", detail=f"focused on {topic}: job-search rules are off", argv=[], reason="")
        add("fallback", "fired", "fallback", _cl("talk", topic),
            f"nothing else is ripe in {topic}; go over a concept together", complete=False)
    elif lane == "interest":
        for e in out:
            if e["rule"] in JOB_RULES:
                e.update(status="off", detail="interest lane: job-search rules are off", argv=[], reason="")
        add("fallback", "fired", "fallback", _cl("ask", "…"),
            "nothing is ripe in the interest lane; ask a question you want answered, and build its ladder",
            complete=False)
    elif cfg.targets:
        add("fallback", "fired", "fallback", _take_in(cfg), "nothing is ripe; look for roles" + _KEYWORD_NOTE, complete=False)
    else:
        add("fallback", "fired", "fallback", _cl("ask", "…"),
            "nothing is ripe; ask a question you want answered, and build its ladder", complete=False)


def _rule_continue(c) -> None:
    """Continuity (behind `[next] continue_last`, default off): with no focus and no
    filter, stay in the topic you studied last instead of letting the rules jump you elsewhere;
    switching topics has a real cost, and following your own interest keeps you studying."""
    on = bool((c.cfg.raw.get("next") or {}).get("continue_last", False))
    if not on:
        c.add("continue", "off", "[next] continue_last is off (set it in config.toml to try it)")
        return
    if c.lane is not None or c.topic is not None:
        c.add("continue", "off", "a lane or topic is already chosen")
        return
    last = []
    for t in c.active:
        rows = L.read_log(c.cfg, t)[0]
        if rows:
            last.append((max(r["date"] for r in rows), t))
    if not last:
        c.add("continue", "not fired", "no topic has a study row yet")
        return
    day, t = max(last)
    c.add("continue", "fired", f"you last studied {t} on {day}", _cl("session", t),
          f"pick up {t} where you left off ({day}); `{H.PROG} focus TOPIC` to pin somewhere else")


#: The rules seam: (name, function) in the order `next` evaluates them; the first that fires wins.
#: A module adds a rule by declaring `rules() -> [(name, fn, after)]` (kenloop/modules.py); its
#: function takes the same context and reports through `c.add`, and it never writes state.
RULES = tuple((n, globals()[f"_rule_{n}"]) for n in ("empty", "integrity", "deadline", "reviews", "continue", "onramp",
                                                     "question", "graduation", "role", "fresh", "study",
                                                     "seed", "score", "fallback"))


def ordered_rules() -> list:
    from . import modules
    rules = list(RULES)
    for name, fn, after in modules.rules():
        at = next((i for i, (n, _f) in enumerate(rules) if n == after), None)
        if at is None or name in {n for n, _f in rules}:
            raise ValueError(f"module rule {name!r}: no rule {after!r} to follow, or the name is taken")
        rules.insert(at + 1, (name, fn))
    return rules


def evaluate(cfg, lane=None, topic=None) -> list:
    """[{rule, status: fired|not fired|not evaluable|off, detail, argv, reason}] for every rule. "off" is a
    rule a lane or topic filter switched off: it was not evaluated, which is not the same as not firing.
    `lane` (career | interest) limits the study rules to that lane's topics; the interest lane
    also switches the job-search rules off."""
    c = _Ctx(cfg, lane, topic)
    for _name, fn in ordered_rules():
        fn(c)
    return c.out


def next_action(cfg, show_all=False, as_json=False, lane=None, topic=None, focus_label="", candidates=False) -> int:
    if topic is not None:
        L.need_topic(cfg, topic)
    evals = evaluate(cfg, lane, topic)
    pick = next(e for e in evals if e["status"] == "fired")
    code = NOT_EVALUABLE if pick["rule"] == "empty" else OK
    for e in evals:
        if e["rule"] in ("graduation", "question") and e["status"] == "not evaluable":
            H.warn(f"NOT EVALUABLE {e['detail']}")
            code = NOT_EVALUABLE
    if as_json:
        print(json.dumps({"rule": pick["rule"], "argv": pick["argv"], "argv_complete": pick["argv_complete"],
                          "reason": pick["reason"], "focus": focus_label or None, "evaluations": evals}, indent=1, ensure_ascii=False))
        return code
    if show_all:
        for e in evals:
            mark = {"fired": "*", "not fired": " ", "not evaluable": "?", "off": "-"}[e["status"]]
            print(f"{mark} {e['rule']:<11} {e['status']:13} {e['detail']}")
    print(f"NEXT{' ' + lane if lane else ''}{' ' + topic if topic else ''}: "
          f"{' '.join(_q(a) for a in pick['argv'])}  — {pick['reason']}")
    if focus_label:
        print(f"  ({focus_label})")
    if candidates:      # two to four choices beat one or fifteen: the next rules that also fired
        alt = [e for e in evals if e["status"] == "fired" and e is not pick and e["rule"] != "fallback"][:2]
        for e in alt:
            print(f"  or: {' '.join(_q(a) for a in e['argv'])}  — {e['reason']}")
        if not alt:
            print("  or: nothing else is ripe")
    return code


def _q(a: str) -> str:
    return f'"{a}"' if (" " in a or ":" in a) else a


def doctor(cfg, fix=False) -> int:
    """Worst wins: 3 drift > 2 not evaluable > 1 findings > 0 clean. `fix` adds the .gitattributes
    lines a declared ledger is missing (the one repair doctor makes; it never removes a line)."""
    code = OK
    ga = cfg.home / ".gitattributes"
    if ga.exists():                  # a home kept in git: every declared ledger must merge line by line
        text = H.read_text(ga, ".gitattributes")
        have = set(text.splitlines())
        missing = [ln for ln in LG.gitattributes().splitlines() if ln not in have]
        if missing and fix:
            H.write_text(ga, text.rstrip("\n") + "\n" + "\n".join(missing) + "\n")
            print(f"fixed: added {len(missing)} ledger line(s) to .gitattributes: {', '.join(missing)}")
            missing = []
        if missing:
            print(f"FINDING .gitattributes lacks {len(missing)} ledger line(s): {', '.join(missing)}; two "
                  f"machines appending to those ledgers would conflict instead of merging. `{H.PROG} doctor --fix` adds them")
            code = max(code, FINDINGS)
    try:
        for s in MK.stack(cfg):
            if s["topic"] not in L.topics(cfg):
                print(f"FINDING the trail goes through {s['topic']}, a topic that no longer exists; "
                      f"`{H.PROG} trail --back` steps past it")
                code = max(code, FINDINGS)
    except NotEvaluable as e:
        print(f"NOT EVALUABLE {e}")
        code = max(code, NOT_EVALUABLE)
    n_roles = 0
    roles, damaged = R.scan(cfg)
    for p in damaged:
        print(f"NOT EVALUABLE damaged role file: {p}")
        code = max(code, NOT_EVALUABLE)
    for s, m in roles:
        d = cfg.roles / s
        jd = d / "jd.txt"
        try:
            if not jd.exists() or not H.read_text(jd, "posting").strip():
                continue
        except NotEvaluable as e:
            print(f"NOT EVALUABLE {e}")
            code = max(code, NOT_EVALUABLE)
            continue
        n_roles += 1
        try:
            cov = J.load_coverage(cfg, s)
        except NotEvaluable as e:
            print(f"NOT EVALUABLE {e}")
            code = max(code, NOT_EVALUABLE)
            continue
        if cov is None:
            print(f"FINDING {s}: posting never checked (`{H.PROG} jobs check {s}`)")
            code = max(code, FINDINGS)
        elif m.get("coverage_pct") != int(f"{cov['pct']:.0f}"):
            print(f"FINDING {s}: meta coverage {m.get('coverage_pct')} != coverage.json {cov['pct']}")
            code = max(code, FINDINGS)
        elif J.coverage_stale(cfg, s, cov):
            print(f"FINDING {s}: coverage is stale (posting, resume, facts or lexicon changed); "
                  f"`{H.PROG} jobs check {s}`")
            code = max(code, FINDINGS)
    facts, facts_err = "", ""
    try:
        facts = F.read(cfg)
    except NotEvaluable as e:
        facts_err = str(e)
    else:
        if not facts.strip():
            facts_err = (f"facts sheet {cfg.facts} is missing or empty: held-or-not cannot be judged, so no "
                         "resume claim can be checked (write facts.md with a ## Held section)")
    if facts_err:
        print(f"NOT EVALUABLE {facts_err}")
        code = max(code, NOT_EVALUABLE)
    scanned = set()
    for s, m in roles:
        if not (cfg.roles / s / "jd.txt").exists():
            continue
        why = ""
        try:
            rp = J.resolve_resume(cfg, m, None)
        except NotEvaluable as e:
            rp, why = None, str(e)
        if rp is None:
            print(f"NOT EVALUABLE role {s}: " + (why + ", so its claims cannot be checked" if why else
                  "no resume found (the role's own resume, [profile] resume, "
                  "resumes/resume.md, .txt or .tex), so its claims cannot be checked"))
            code = max(code, NOT_EVALUABLE)
            continue
        if rp in scanned:
            continue
        scanned.add(rp)
        try:
            if facts_err:                # without facts only the disguised-word half can be judged
                found = [(sp.shown, "suspicious-characters", J._suspicion(sp, t)) for sp, t in J.resume_findings(cfg, rp)]
            else:                        # exactly what `jobs check-claims RESUME` would exit 1 on
                found = J.claim_report(cfg, ats.resume_text(rp), facts, ats.load_lexicon(cfg))[0]
        except (OSError, NotEvaluable) as e:
            print(f"NOT EVALUABLE resume {rp.name}: cannot be checked: {e}")
            code = max(code, NOT_EVALUABLE)
            continue
        for term, kind, ev in found:
            print(f"FINDING resume {rp.name}: {kind} {term}: {ev}")
            code = max(code, FINDINGS)
    if not facts_err:
        sheet = F.analyse(facts)
        for b in F.contradiction_blocks(facts):
            print(f"FINDING facts.md line {b.line}: under ## Held but qualified (not held): {b.text[:80]}; {b.why}")
            code = max(code, FINDINGS)
        for no, t in sheet.struck:
            print(f"FINDING facts.md line {no}: struck through under ## Held (ignored, so not held): {t[:80]}; "
                  "delete the line if you meant it")
            code = max(code, FINDINGS)
        seen_c = set()
        for hd in sheet.hidden:
            key = (hd.kind, hd.opened)
            if not hd.in_held or not hd.closed or key in seen_c:
                continue
            body = re.sub(r"^<!--\s*", "", hd.text)
            if hd.kind == "comment" and F.hidden_qualifier(body):
                seen_c.add(key)
                print(f"FINDING facts.md line {hd.line}: a comment under ## Held hides a qualifier "
                      f"({F.hidden_qualifier(body)!r}), so the line counts as held: {hd.text[:60]}; "
                      "put it in the visible text if it is true")
                code = max(code, FINDINGS)
                continue
            if _ITEM.match(body):                  # a commented-out or fenced list item, not a note
                seen_c.add(key)
                print(f"FINDING facts.md line {hd.line}: a {hd.kind} (opened line {hd.opened}) hides text under "
                      f"## Held, so it counts as not held: {hd.text[:60]}; delete the {hd.kind} markers if you "
                      "meant it to count")
                code = max(code, FINDINGS)
        for what, no in sheet.unclosed:
            print(f"FINDING facts.md line {no}: the {what} opened here never closes, so everything after it "
                  "is hidden and counts as not held")
            code = max(code, FINDINGS)
    n_topics = 0
    for t in L.topics(cfg):
        n_topics += 1
        try:
            h, _w = L.problems(cfg, t)
            dr, probs = L.audit(cfg, t)
        except (NotEvaluable, UsageError) as e:
            print(f"NOT EVALUABLE {t}: {e}")
            code = max(code, NOT_EVALUABLE)
            continue
        if probs:
            print(f"NOT EVALUABLE {t}: {len(probs)} log problem(s): {probs[0]}")
            code = max(code, NOT_EVALUABLE)
        for x in h:
            print(f"FINDING {x}")
            code = max(code, FINDINGS)
        if dr:
            print(f"DRIFT {t}: {len(dr)} concept(s); `{H.PROG} rebuild {t} --check`")
            code = max(code, DRIFT)
    for p in Q.read(cfg)[1]:
        print(f"NOT EVALUABLE {p}")
        code = max(code, NOT_EVALUABLE)
    if facts and not facts_err:
        for w in G.held_vs_study(cfg, facts):
            H.warn(f"warn: {w}")
    try:
        _d, stale = DM.load(cfg)
        if stale:
            H.warn(f"warn: {cfg.upskill.name} is stale; re-run `{H.PROG} jobs upskill`")
    except NotEvaluable as e:
        H.warn(f"warn: {e}")
    from . import modules
    levels = {"FINDING": FINDINGS, "NOT EVALUABLE": NOT_EVALUABLE, "DRIFT": DRIFT}
    for _name, check in modules.doctors():          # the doctor seam: each module checks its own data
        for level, text in check(cfg):
            print(f"{level} {text}")
            code = max(code, levels[level])
    if not n_roles and not n_topics and code == OK:
        what = (f"{len(roles)} role(s), none with a posting, and no topics" if roles else "0 topic(s), 0 role(s)")
        print(f"NOT EVALUABLE nothing to check: {what} in {cfg.home}; "
              "a home with nothing in it is not a clean one")
        return NOT_EVALUABLE
    print(f"checked {n_roles} role(s) with a posting, {n_topics} topic(s)")
    print({OK: "CLEAN", FINDINGS: "FINDINGS", NOT_EVALUABLE: "NOT EVALUABLE", DRIFT: "DRIFT"}[code])
    return code
