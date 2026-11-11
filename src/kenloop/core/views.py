"""Read-only views over a topic: what to go over, a concept from the ground up, mastery, and
every topic at once. None of them writes the record; teaching is not retrieval.

- dive: the reverse of a quiz. With no concept, what is most worth going over; with one, the
  material for going over it together, answers open: your misses, the banked questions with
  their answers and sources, and the look-alikes to contrast. A check afterwards is
  `record ... --mode learn`, which earns no credit: the evidence is a spaced quiz later.
- foundations: a layered note per concept (from the ground up), scaffolded on request.
- mastery: badges per concept, beside calibration, reasoning per move and question types.
- board: every topic, its mastery and what is due.
"""
from __future__ import annotations

from collections import Counter

from . import home as H
from . import learn as L
from .errors import NOT_EVALUABLE, OK, NotEvaluable

ORDER = ("mastered", "good", "fair", "weak", "new")

FOUNDATIONS = """# Foundations: {name} ({cid})

A from-the-ground-up note for understanding, not for recall. Write it BEFORE teaching, from
sources read that day: it is the lesson's preparation. Mark what humanity knows (settled, frontier,
open) where it matters. After teaching, add what the learner said back.

## In one line
{desc}

## Foundation
- (the primitives: what it is, from zero)

## Mechanism
- (how it works, step by step)

## Where it stops
- (what is settled, what is still open, and the cases the idea does not cover)

## Connections
- (what it builds on, what builds on it, what it is often confused with)

## Their say-back
- (after teaching: what they said in their own words, and what it missed)

## Sources
- Read on (date): (each page or paper, and the claims it carries)
- From memory, not checked: (anything above that was not read that day; none is the goal)
"""


def _active(c) -> list:
    """Misconceptions seen twice or more: [(signature, count)], most frequent first."""
    sigs = Counter(L.signature(e) for _i, e in L.open_errors(c))
    return sorted(((s, k) for s, k in sigs.items() if k >= 2), key=lambda x: (-x[1], x[0]))


def _concepts(cfg, slug) -> dict:
    cons = L.load_state(cfg, slug)["concepts"]
    if not cons:
        raise NotEvaluable(f"{slug} has no concepts yet: add them to syllabus.md and run `{H.PROG} sync {slug}`")
    return cons


def dive(cfg, slug, concept=None, n=8) -> int:
    cons = _concepts(cfg, slug)
    if not concept:
        rows = []
        for cid, c in cons.items():
            cm, active = L.confident_misses(c), _active(c)
            no_floor = c.get("attempts", 0) > 0 and not c.get("correct_days")
            if cm > 0 or active or no_floor:
                rows.append((-cm, -bool(active), -no_floor, cid, c, active))
        print(f"dive: {slug}, worth going over (highest payoff first)")
        if not rows:
            print(f"  nothing flagged; pick any concept: `{H.PROG} dive {slug} CONCEPT`")
            return L.log_verdict(cfg, slug)
        for ncm, _a, nf, cid, c, active in sorted(rows)[:n]:
            print(f"  {L.badge(c):<8} {cid}: {c.get('name', cid)}")
            if ncm:
                print(f"           {-ncm} confident miss(es): you were sure and wrong; go over it first")
            if active:
                print(f"           recurring: {active[0][0]} (x{active[0][1]})")
            if nf:
                print("           never right unaided yet")
        print(f"  `{H.PROG} dive {slug} CONCEPT` for the material")
        return L.log_verdict(cfg, slug)
    cid = L.resolve_concept({"concepts": cons}, concept)
    c = cons[cid]
    print(f"dive: {slug} / {cid}: {c.get('name', cid)}  [{L.badge(c)}]")
    print(f"  {c.get('correct', 0)}/{c.get('attempts', 0)} correct, streak {c.get('streak', 0)}, "
          f"next review {c.get('due') or 'not scheduled'}")
    if c.get("status"):
        print(f"  what humanity knows: {c['status']}: {L.STATUSES[c['status']]}")
    if c.get("desc"):
        print(f"  {c['desc']}")
    if _note(cfg, slug, cid).exists():
        print(f"  foundations note: `{H.PROG} foundations {slug} {cid}`")
    print("\n  What to fix (go over these first):")
    active, et, errs = _active(c), L.dominant_etype(c), L.open_errors(c)
    for sig, k in active[:3]:
        print(f"    recurring misconception (x{k}): {sig}")
    if et:
        print(f"    error class {et}: {L.REASK[et]}")
    if errs and not active:
        print(f"    open miss(es): {'; '.join(e[:70] for _i, e in errs[:3])}")
    if L.confident_misses(c):
        print("    a confident miss is on record: lead with the correction, then work it out again together")
    if not (active or et or errs or L.confident_misses(c)):
        print("    no recorded errors: one worked example, then contrast the look-alikes below")
    qs = L.load_bank(cfg, slug).get(cid, [])
    if qs:
        print(f"\n  Banked questions, answers open ({len(qs)}); go over them from the source:")
        for q in qs:
            print(f"    Q: {q['q']}")
            for key, label in (("a", "A"), ("why", "why"), ("ref", "ref")):
                if q.get(key):
                    print(f"       {label}: {q[key]}")
    else:
        print(f"\n  No banked questions: work from the syllabus resources, then `{H.PROG} bank {slug} {cid} ...`")
    cl = c.get("cluster")
    sibs = sorted(k for k, x in cons.items() if cl and x.get("cluster") == cl and k != cid)
    if sibs:
        print(f"\n  Look-alikes (cluster {cl}): draw the contrast")
        for s in sibs[:6]:
            print(f"    {s}: {cons[s].get('desc', '')[:80]}")
    print(f"\n  When it lands: `{H.PROG} record {slug} {cid} ok|partial|miss --mode learn` "
          "(no credit: the evidence is a spaced quiz next session)")
    return L.log_verdict(cfg, slug)


def _note(cfg, slug, cid):
    return L.tdir(cfg, slug) / "foundations" / (cid.replace(":", "--") + ".md")


def foundations(cfg, slug, concept=None, scaffold=False) -> int:
    cons = _concepts(cfg, slug)
    if not concept:
        have = [cid for cid in sorted(cons) if _note(cfg, slug, cid).exists()]
        lack = [cid for cid in sorted(cons) if cid not in have]
        print(f"foundations: {slug}, {len(have)}/{len(cons)} concept(s) have a note")
        for cid in have:
            print(f"  have  {cid}")
        for cid in lack[:12]:
            print(f"  none  {cid}")
        if len(lack) > 12:
            print(f"  ... and {len(lack) - 12} more")
        if lack:
            print(f"  scaffold one: `{H.PROG} foundations {slug} CONCEPT --scaffold`")
        return OK
    cid = L.resolve_concept({"concepts": cons}, concept)
    p = _note(cfg, slug, cid)
    if p.exists():
        print(f"{p.relative_to(cfg.home).as_posix()}\n")
        print(H.read_text(p, "foundations note"), end="")
        return OK
    if not scaffold:
        print(f"no foundations note for {cid} yet; `{H.PROG} foundations {slug} {cid} --scaffold` writes one")
        return OK
    c = cons[cid]
    H.write_text(p, FOUNDATIONS.format(name=c.get("name", cid), cid=cid, desc=c.get("desc") or "(one line)"))
    print(f"wrote {p.relative_to(cfg.home).as_posix()}")
    return OK


def _counts(cons) -> Counter:
    return Counter(L.badge(c) for c in cons.values())


def mastery(cfg, slug) -> int:
    cons = _concepts(cfg, slug)
    counts = _counts(cons)
    title = L.load_config(cfg, slug).get("title", slug)
    print(f"{title}: {counts['mastered']}/{len(cons)} mastered   "
          + "  ".join(f"{k} {counts[k]}" for k in ORDER))
    for cid, c in sorted(cons.items(), key=lambda kv: (ORDER.index(L.badge(kv[1])), kv[0])):
        line = f"  {L.badge(c):<8} {cid:<40} {c.get('correct', 0)}/{c.get('attempts', 0)}"
        active = _active(c)
        if active:
            line += f"  recurring x{active[0][1]}: {active[0][0][:44]}"
        elif c.get("errors"):
            line += f"  last miss: {c['errors'][-1][:44]}"
        if L.badge(c) == "mastered" and not L.breadth_ok(c):
            line += "  (breadth not tested)"
        if c.get("repeats"):
            line += f"  ({c['repeats']} same-day repeat(s): counted, no credit)"
        print(line)

    def total(field, a="attempts", b="correct"):
        agg: dict = {}
        for c in cons.values():
            for k, v in (c.get(field) or {}).items():
                x = agg.setdefault(k, [0, 0])
                x[0] += v.get(b, 0)
                x[1] += v.get(a, 0)
        return agg

    cal = total("by_conf")
    if cal:
        print("\n  calibration (stated vs right): "
              + "  ".join(f"{k} {cal[k][0]}/{cal[k][1]}" for k in L.CONFIDENCE if k in cal)
              + f"; detail: `{H.PROG} calibration {slug}`")
    rsn = total("by_reasoning", "probed", "points")
    if rsn:
        means = {k: v[0] / v[1] for k, v in rsn.items() if v[1]}
        weak = min(means, key=lambda k: (means[k], k))
        print("  reasoning (dialogues, mean of 2): "
              + "  ".join(f"{k} {means[k]:.1f} (n={rsn[k][1]})" for k in L.REASONING_MOVES if k in means)
              + f"; weakest: {weak}")
    qt = total("by_type")
    if qt:
        rates = {k: v[0] / v[1] for k, v in qt.items() if v[1]}
        print("  by question type: " + "  ".join(f"{k} {qt[k][0]}/{qt[k][1]}" for k in L.QTYPES if k in qt)
              + (f"; blind spot: {min(rates, key=rates.get)}" if len(rates) > 1 else ""))
    return L.log_verdict(cfg, slug)


def board(cfg) -> int:
    tops = L.topics(cfg)
    if not tops:
        print(f"no topics yet; `{H.PROG} plan SLUG` starts one")
        return OK
    print(f"{'TOPIC':<24}{'OUTLETS':<14}{'MASTERED':<14}{'DUE':<6}BADGES")
    damaged, due, pct, code = [], {}, {}, OK
    for t in tops:
        try:
            state = L.load_state(cfg, t)
            cons = state["concepts"]
            conf = L.load_config(cfg, t)
            due[t] = len(L.due_list(cfg, t))
        except NotEvaluable as e:
            damaged.append(f"{t}: {e}")
            continue
        code = max(code, L.log_verdict(cfg, t, state))
        counts = _counts(cons)
        pct[t] = round(100 * counts["mastered"] / len(cons)) if cons else 0
        kind = ",".join(conf.get("outlets", [])) or "curiosity"
        # graded dialogues never move the badges (quiz credit only), so a strong first day and a
        # struggling one read the same there; their reasoning is what tells them apart
        rm = [sum(m.values()) / len(m) for m in (L.reasoning_means(c) for c in cons.values()) if m]
        print(f"{t:<24}{kind:<14}{counts['mastered']}/{len(cons)} ({pct[t]}%)".ljust(52)
              + f"{due[t]:<6}" + " ".join(f"{k} {counts[k]}" for k in ORDER)
              + (f"  reasoning {sum(rm) / len(rm):.1f}/2 on {len(rm)}" if rm else ""))
    for d in damaged:
        print(f"NOT EVALUABLE {d}")
    return max(code, NOT_EVALUABLE) if damaged else code
