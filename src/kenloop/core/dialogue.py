"""Dialogue: understanding shown by reasoning, not recall.

`talk` sets up a graded back-and-forth on one concept for your assistant to run; the grade
lands with `record ... --mode dialogue --rubric ...`. `beliefs` reads the log back: what
you believed before and after each dialogue, where your reasoning held and where it broke,
the questions left open, and the errors of the tutor that you caught.

Both are read-only. A dialogue grade is kept apart from quiz credit (learn.apply_row).
"""
from __future__ import annotations

from . import graph as SG
from . import home as H
from . import learn as L
from . import onramp as O
from .errors import NotEvaluable

PROTOCOL = """\
  How to run it (your assistant asks; you reason):
  0. Before the first question: what do you believe about this now, and how sure are you
     (low / med / high)? In your own words. Ask again at the end: that pair is --before/--after.
  1. Open with a why or a what-if, never "define X". No formulas needed; the logic is graded.
  2. One question at a time. Follow the answer, not a script.
  3. Probe at least 3 of the moves below. Push back with a case that breaks a weak claim, and
     sometimes push back on a correct one: holding a sound position is half of pushback.
  4. No explaining before you have tried. Teaching mid-dialogue is help: record it with
     --hint-depth (1 reframe, 2 narrow, 3 give the fact, 4 tell).
  5. Settle a disputed fact from the topic's sources, not from either side's say-so.
  6. At the end: which step of the reasoning held, which first broke, what to learn to get
     past it, and the questions left open. Those open questions start the next session.
  Keep the transcript at {transcript} (your words verbatim)."""


def _probes(c) -> int:
    return sum(m.get("probed", 0) for m in (c.get("by_reasoning") or {}).values())


def talk(cfg, slug, concept=None, protocol=False) -> int:
    state = L.load_state(cfg, slug)
    cons = state["concepts"]
    if not cons:
        raise NotEvaluable(f"{slug} has no concepts yet: add them to syllabus.md and run `{H.PROG} sync {slug}`")
    if concept:
        cid = L.resolve_concept(state, concept)
    else:   # ready before waiting (the study graph), then least talked about, then weakest, then
            # the syllabus's own order (it is a learning path)
        g = SG.build(cfg, slug)
        order = {k: i for i, k in enumerate(cons)}
        waiting = {k for k, n in g.nodes.items() if not n.climbed and SG.waits(g, n)}
        cid = min(cons, key=lambda k: (k in waiting, _probes(cons[k]), cons[k].get("streak", 0), order[k]))
    c = cons[cid]
    print(f"talk: {c.get('name', cid)} ({cid})")
    if c.get("desc"):
        print(f"  {c['desc']}")
    for line in O.advice(cfg, slug, cid):
        print(f"  on-ramp: {line}")
    g = SG.build(cfg, slug)
    for line in SG.waits(g, g.nodes[cid]) if cid in g.nodes else []:
        if line.startswith("rung ") and " of q" in line:     # ladders: advice covers pieces, before and the scale
            print(f"  ladder: {line}")
    from . import branches as B                    # plugged-in offers (e.g. scouting) ride along to the conversation
    for x in B.provider_offers(cfg, slug, reached_only=False):
        if x["concept"] == cid:
            print(f"  predicted branch {x['source']}: {x['gap']}  -- offer it when the gap shows; "
                  f"decide with --source {x['source']}")
    for t, k, name, b in L.twins(cfg, slug, cid):
        print(f"  the same idea in {t}: {name} ({k}) [{b}] - a mapping; each topic keeps its own evidence")
    status = c.get("status", "")
    print(f"  what humanity knows: {status}: {L.STATUSES[status]}" if status
          else "  what humanity knows: not marked in the syllabus (`:: status:settled|frontier|open`)")
    means = L.reasoning_means(c)
    if means:
        print("  your reasoning so far: " + "  ".join(f"{k} {v:.1f}/2" for k, v in sorted(means.items())))
        weak = min(means, key=lambda k: (means[k], k))
        unprobed = [k for k in L.REASONING_MOVES if k not in means]
        print(f"  push on: {weak}" + (f"; never probed: {', '.join(unprobed)}" if unprobed else ""))
    else:
        print("  your reasoning so far: none recorded; this is the first dialogue on it")
    if c.get("errors"):
        print(f"  last miss on record: {c['errors'][-1][:90]}")
    transcript = L.dialogue_path(cfg, slug, cid, H.today().isoformat()).relative_to(cfg.home).as_posix()
    print()
    if protocol:          # the graded-dialogue method, only when a graded dialogue is what is happening
        print(PROTOCOL.format(transcript=transcript))
    else:
        print(f"  teaching it? `{H.PROG} taught {slug} {cid}` records that (no credit). Grading a dialogue? "
              f"`{H.PROG} talk {slug} {cid} --protocol` prints the method; transcript: {transcript}")
    print()
    print("  Moves (score 0-2, only those probed; an unprobed move is left out, never 0):")
    for k, desc in L.REASONING_MOVES.items():
        print(f"    {k:<9} {desc}")
    print()
    print("  The verdict is the rubric's rule: ok = mean >= 1.5 with no 0; partial = mean >= 0.75;\n"
          "  if you told the answer (--hint-depth 4), at most partial.")
    print(f"  Record: {H.PROG} record {slug} {cid} ok|partial|miss --mode dialogue \\\n"
          "            --rubric chain=_,predict=_,limits=_ --grader MODEL \\\n"
          "            --before \"...\" --confidence low|med|high --after \"...\" --after-confidence low|med|high \\\n"
          "            --held \"...\" --broke \"...\" --next \"...\" [--open \"...\" ...] [--claude-wrong \"...\"]")
    return L.log_verdict(cfg, slug)


def _predictions(log, want="") -> None:
    """Each guess made before an explanation, beside the next answer on the same concept: what you
    expected, and then what you could do. A guess with no text says so rather than hiding."""
    preds = [(i, r) for i, r in enumerate(log) if r.get("mode") == "predict" and (not want or r["concept"] == want)]
    if not preds:
        return
    print(f"\n  predictions ({len(preds)}), each beside the next answer on it:")
    for i, r in preds:
        then = next((x for x in log[i + 1:] if x["concept"] == r["concept"]
                     and x.get("mode") not in ("predict", "teach")), None)
        said = f"({r.get('confidence') or '?'}): {r['before']}" if r.get("before") else "(no prediction text)"
        print(f"    {r['date']}  {r['concept']}  guessed [{r.get('result', '?')}] {said}")
        print(f"      then: {then.get('result', '?')} ({then.get('mode') or 'practice'}, {then['date']})" if then
              else "      then: nothing recorded on it yet")


def beliefs(cfg, slug, concept=None) -> int:
    """How your beliefs moved, dialogue by dialogue. What was believed, how sure, what changed
    and what was left open: behaviour, never a curiosity score."""
    state = L.load_state(cfg, slug)
    want = L.resolve_concept(state, concept) if concept else ""
    log = L.read_log(cfg, slug)[0]
    rows = [r for r in log if r.get("mode") == "dialogue" and (not want or r["concept"] == want)]
    title = L.load_config(cfg, slug).get("title", slug)
    print(f"beliefs: {title}" + (f" ({want})" if want else ""))
    if not rows and not any(r.get("mode") == "predict" for r in log):
        print(f"  no dialogues recorded yet; `{H.PROG} talk {slug}` starts one")
        return L.log_verdict(cfg, slug)
    _predictions(log, want)
    if not rows:
        print(f"\n  no dialogues recorded yet; `{H.PROG} talk {slug}` starts one")
        return L.log_verdict(cfg, slug)
    moved = with_belief = caught = 0
    open_all = []
    for r in rows:
        print(f"\n  {r['date']}  {r['concept']}  [{r['result']}]  graded by {r.get('grader', '?')}")
        if r.get("before"):
            with_belief += 1
            changed = r["before"].strip().lower() != r["after"].strip().lower()
            moved += changed
            print(f"    before ({r.get('confidence') or '?'}): {r['before']}")
            print(f"    after  ({r.get('after_confidence') or '?'}): {r['after']}" + ("" if changed else "   (held)"))
        for key, label in (("held", "right up to"), ("broke", "broke at   "), ("next", "learn next ")):
            if r.get(key):
                print(f"    {label}: {r[key]}")
        if r.get("claude_wrong"):
            caught += 1
            print(f"    you caught the tutor: {r['claude_wrong']}")
        open_all += [(r["date"], *L.open_target(state["concepts"], q, r["concept"])) for q in r.get("open", [])]
    print(f"\n  {len(rows)} dialogue(s); {with_belief} with a before/after belief, {moved} of those changed; "
          f"you caught the tutor wrong {caught} time(s)")
    if open_all:
        print(f"\n  open questions ({len(open_all)}), where the next session starts:")
        for day, cid, q in open_all:
            print(f"    {day}  {cid}: {q}")
    return L.log_verdict(cfg, slug)
