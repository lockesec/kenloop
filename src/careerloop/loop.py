"""`next` and `doctor`: the loop as one decision, and the loop's health.

``next`` answers "what is the single most useful thing to do now?" by
evaluating fixed rules in order over state the two arms already keep. The
first rule that fires wins. ``--all`` prints every rule's evaluation so the
choice can be audited; a rule that cannot be evaluated says so and why.

    0  nothing to work on                 -> init / discover       (exit 2)
    1  a topic's state disagrees with its log, or fails validation -> rebuild / fix
    2  a strong role's deadline is close  -> tailor it, or mark it applied
    3  a concept has graduated            -> graduate --emit, paste under ## Held in facts.md
    4  reviews are due in a topic the market wants, or before an exam -> due
    5  strong roles are waiting           -> tailor the best
    6  a demand-linked topic has banked, unstudied concepts -> quiz --weak
    7  the top unplanned demand bucket is big enough -> plan --from-gap
    8  roles are waiting to be scored     -> score the oldest
    9  nothing is ripe                    -> discover
"""
from __future__ import annotations

import json
import re

from . import ats
from . import demand as DM
from . import facts as F
from . import home as H
from . import jobs as J
from . import learn as L
from . import roles as R
from .errors import DRIFT, FINDINGS, NOT_EVALUABLE, OK, Drifted, NotEvaluable

EXAM_SOON_DAYS = 14
ACRONYM_BUCKET = "Unmapped: acronym"   # unknown capitalised words: shown, never planned automatically

_ITEM = re.compile(r"^\s*([-*+]|\d+\.)\s")


def _cl(*args) -> list:
    return ["careerloop", *args]


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


def evaluate(cfg) -> list:
    """[{rule, status: fired|not fired|not evaluable, detail, argv, reason}] for every rule."""
    today = H.today()
    roles, damaged = R.scan(cfg)
    tops = L.topics(cfg)
    out = []

    def add(rule, status, detail, argv=None, reason="", complete=True):
        out.append({"rule": rule, "status": status, "detail": detail, "argv": argv or [], "reason": reason,
                    "argv_complete": complete})

    try:
        upskill, stale = DM.load(cfg)
        up_err = ""
    except NotEvaluable as e:
        upskill, stale, up_err = None, False, str(e)
    bucket_demand = {b["name"]: b["demand"] for b in (upskill or {}).get("buckets", [])}

    # 0
    if not roles and not tops:
        add(0, "fired", "no roles and no topics", _take_in(cfg),
            "NOT EVALUABLE: nothing to work on yet (0 role(s), 0 topic(s))" + (_KEYWORD_NOTE if cfg.targets else ""), complete=False)
    else:
        add(0, "not fired", f"{len(roles)} role(s), {len(tops)} topic(s)")

    # 1
    bad = []
    for t in tops:
        try:
            d, probs = L.audit(cfg, t)
            h, _w = L.problems(cfg, t)
        except NotEvaluable as e:
            bad.append((t, str(e), _cl("learn", "rebuild", t)))
            continue
        if probs:
            bad.append((t, f"{len(probs)} unreadable log row(s)", _cl("learn", "rebuild", t, "--check")))
        elif d:
            bad.append((t, f"{len(d)} concept(s) drifted from the log", _cl("learn", "rebuild", t)))
        elif h:
            bad.append((t, f"{len(h)} validation failure(s)", _cl("learn", "validate", t)))
    broken = {t for t, _w, _a in bad}
    tops = [t for t in tops if t not in broken]      # later rules read only topics that load cleanly
    if damaged:
        bad.append(("roles", f"{len(damaged)} damaged role file(s): {damaged[0]}", _cl("doctor")))
    if bad:
        t, why, argv = bad[0]
        add(1, "fired", f"{len(bad)} integrity problem(s)", argv, f"{t}: {why}")
    else:
        add(1, "not fired", "every topic matches its log and validates")

    # 2
    hot = []
    for s, m in J.shortlist(cfg, roles):
        dl = J._days_to(m.get("deadline"), today)
        if dl is not None and 0 <= dl <= cfg.deadline_days:
            hot.append((dl, -(m.get("fit_score") or 0), s, m))
    if hot:
        dl, _nf, s, m = sorted(hot)[0]
        argv = _advance(cfg, s, m)
        add(2, "fired", f"{len(hot)} strong role(s) closing within {cfg.deadline_days}d", argv,
            f"{s}: deadline in {dl} day(s), fit {m.get('fit_score')}")
    else:
        add(2, "not fired", f"no role at fit >= {cfg.bar} closes within {cfg.deadline_days} day(s)")

    # 3
    grads, n_held, n_unwritable = [], 0, 0
    try:
        F.read(cfg)
        facts_err = ""
    except NotEvaluable as e:
        facts_err = str(e)
    for t in ([] if facts_err else tops):
        try:
            g = L.graduation(cfg, t)
        except (NotEvaluable, Drifted):
            continue
        n_held += len(g["held"])
        n_unwritable += len(g["unwritable"])
        if g["candidates"]:
            grads.append((-len(g["candidates"]), t))
    if facts_err:
        add(3, "not evaluable", f"what you hold is unknown: {facts_err}")
    elif grads:
        n, t = sorted(grads)[0]
        add(3, "fired", f"{sum(-g for g, _t in grads)} concept(s) ready", _cl("learn", "graduate", t, "--emit"),
            f"{-n} concept(s) in {t} passed every graduation gate; paste them under ## Held in facts.md, then re-run jobs check")
    else:
        add(3, "not fired", (f"{n_held} concept(s) passed every gate, all already in facts.md" if n_held
                             else "no concept has passed all four graduation gates")
            + (f"; {n_unwritable} mastered concept(s) cannot be written as a facts line (rename them; "
               "see `learn graduate`)" if n_unwritable else ""))

    # 4
    wanted = []
    for t in tops:
        conf = L.load_config(cfg, t)
        n_due = len(L.due_list(cfg, t, today))
        if not n_due:
            continue
        ex = L.exam_date(conf)
        demand = bucket_demand.get(conf.get("from_gap", ""), 0)
        if demand > 0 or (ex and 0 < (ex - today).days <= EXAM_SOON_DAYS):
            why = f"bucket demand {demand}" if demand > 0 else f"exam in {(ex - today).days} day(s)"
            wanted.append((-n_due, _mastered_pct(cfg, t), t, why))
    if wanted:
        nd, _p, t, why = sorted(wanted)[0]
        add(4, "fired", f"{len(wanted)} topic(s) with wanted reviews due", _cl("learn", "due", t),
            f"{-nd} review(s) due in {t} (~{-2 * nd} min); {why}"
            + (" (upskill.json is stale; re-run jobs upskill)" if stale and why.startswith("bucket") else ""))
    elif upskill is None and any(L.due_list(cfg, t, today) for t in tops):
        add(4, "not evaluable", f"reviews are due but demand is unknown: {up_err}")
    else:
        add(4, "not fired", "no due reviews in a topic with demand or a near exam")

    # 5
    sl = J.shortlist(cfg, roles)
    if sl:
        s, m = sl[0]
        argv = _advance(cfg, s, m)
        add(5, "fired", f"{len(sl)} role(s) at or above the bar", argv,
            f"{s}: fit {m.get('fit_score')}, coverage {m.get('coverage_pct', '-')}%")
    else:
        add(5, "not fired", f"no live role in the work queue at fit >= {cfg.bar}")

    # 6
    fresh = []
    for t in tops:
        conf = L.load_config(cfg, t)
        if not conf.get("from_gap") or conf["from_gap"] == "none":
            continue
        bank = L.load_bank(cfg, t)
        cons = L.load_state(cfg, t)["concepts"]
        n = sum(1 for cid, c in cons.items() if not c.get("attempts") and bank.get(cid))
        if n:
            fresh.append((-n, t))
    if fresh:
        n, t = sorted(fresh)[0]
        add(6, "fired", f"{sum(-f for f, _t in fresh)} banked concept(s) never studied",
            _cl("learn", "quiz", t, "--weak", "--interactive"), f"{-n} unstudied concept(s) with questions in {t}")
    else:
        add(6, "not fired", "no demand-linked topic has banked, unstudied concepts")

    # 7
    if upskill is None:
        add(7, "not evaluable", up_err)
    else:
        planned = L.planned_buckets(cfg)
        cands = [b for b in upskill["buckets"] if not L.is_planned(b["name"], planned)
                 and b["name"] != ACRONYM_BUCKET and b["demand"] >= cfg.min_bucket_demand]
        if cands:
            b = cands[0]
            add(7, "fired", f"{len(cands)} unplanned bucket(s) at demand >= {cfg.min_bucket_demand}",
                _cl("learn", "plan", R.slugify(b["name"]), "--from-gap", b["name"]),
                f"demand {b['demand']}: " + ", ".join(i["term"] for i in b["items"][:4])
                + (" (upskill.json is stale; re-run jobs upskill)" if stale else ""))
        else:
            add(7, "not fired", f"no unplanned bucket reaches demand {cfg.min_bucket_demand}")

    # 8
    q = J.needs_scoring(cfg, roles)
    if q:
        add(8, "fired", f"{len(q)} role(s) unscored", _cl("jobs", "score", q[0][0], "--fit", "N"),
            f"oldest found {q[0][1].get('found')}; fill scorecard.md first, then replace N", complete=False)
    else:
        add(8, "not fired", "every role is scored")

    add(9, "fired", "fallback", _take_in(cfg),
        "nothing is ripe; look for roles" + (_KEYWORD_NOTE if cfg.targets else ""), complete=False)
    return out


def next_action(cfg, show_all=False, as_json=False) -> int:
    evals = evaluate(cfg)
    pick = next(e for e in evals if e["status"] == "fired")
    code = NOT_EVALUABLE if pick["rule"] == 0 else OK
    for e in evals:
        if e["rule"] == 3 and e["status"] == "not evaluable":
            H.warn(f"NOT EVALUABLE {e['detail']}")
            code = NOT_EVALUABLE
    if as_json:
        print(json.dumps({"rule": pick["rule"], "argv": pick["argv"], "argv_complete": pick["argv_complete"],
                          "reason": pick["reason"], "evaluations": evals}, indent=1, ensure_ascii=False))
        return code
    if show_all:
        for e in evals:
            mark = {"fired": "*", "not fired": " ", "not evaluable": "?"}[e["status"]]
            print(f"{mark} rule {e['rule']}: {e['status']:13} {e['detail']}")
    print(f"NEXT: {' '.join(_q(a) for a in pick['argv'])}  — {pick['reason']}")
    return code


def _q(a: str) -> str:
    return f'"{a}"' if (" " in a or ":" in a) else a


def doctor(cfg) -> int:
    """Worst wins: 3 drift > 2 not evaluable > 1 findings > 0 clean."""
    code = OK
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
            print(f"FINDING {s}: posting never checked (`careerloop jobs check {s}`)")
            code = max(code, FINDINGS)
        elif m.get("coverage_pct") != int(f"{cov['pct']:.0f}"):
            print(f"FINDING {s}: meta coverage {m.get('coverage_pct')} != coverage.json {cov['pct']}")
            code = max(code, FINDINGS)
        elif J.coverage_stale(cfg, s, cov):
            print(f"FINDING {s}: coverage is stale (posting, resume, facts or lexicon changed); "
                  f"`careerloop jobs check {s}`")
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
        except NotEvaluable as e:
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
            print(f"DRIFT {t}: {len(dr)} concept(s); `careerloop learn rebuild {t} --check`")
            code = max(code, DRIFT)
    try:
        _d, stale = DM.load(cfg)
        if stale:
            H.warn(f"warn: {cfg.upskill.name} is stale; re-run `careerloop jobs upskill`")
    except NotEvaluable as e:
        H.warn(f"warn: {e}")
    if not n_roles and not n_topics and code == OK:
        what = (f"{len(roles)} role(s), none with a posting, and no topics" if roles else "no roles and no topics")
        print(f"NOT EVALUABLE nothing to check: {what} in {cfg.home}; "
              "a home with nothing in it is not a clean one")
        return NOT_EVALUABLE
    print(f"checked {n_roles} role(s) with a posting, {n_topics} topic(s)")
    print({OK: "CLEAN", FINDINGS: "FINDINGS", NOT_EVALUABLE: "NOT EVALUABLE", DRIFT: "DRIFT"}[code])
    return code
