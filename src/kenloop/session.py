"""Session: the one read-only view a tutor starts a study session from, and the tutor's notes.

`ken session SLUG` prints, in order: the topic's settings (intent, depth, chosen start), where you
are on the scale and what the on-ramp says, the tutor's last notes on this topic and on the learner,
the questions left open, the scouted branches now reached, and what `next` says for this topic. A
tutor reads this one output to pick its mode; nothing here is stored.

`ken note SLUG "..."` / `ken note --learner "..."` append a dated note to topics/<slug>/tutor.md or
learner.md in the home: how this learner learns (an analogy that landed, a framing that failed, what
to lead with next time). Notes are prose, never evidence: no credit or schedule reads them.

`ken profile` is the curated page on top of those notes (profile.md: who, goals, background by
field, how to teach them, what to watch for), rewritten by the tutor when a note changes a rule and
stamped with the day it was last brought up to date. `session` prints the profile and then only the
learner notes written since that day, so the notes stay the log and the profile stays short.
"""
from __future__ import annotations

import re

from . import loop
from .core import branches as B
from .core import focus as FO
from .core import graph as SG
from .core import height as HT
from .core import home as H
from .core import learn as L
from .core import marks as MK
from .core import onramp as O
from .core.errors import NotEvaluable, OK, UsageError

# what the tutor does at each height, by the line's intent; the router copies it
MOVES = {
    ("understand", 0): ("teach", "ask their guess first (record --mode predict), then explain in chunks around a concrete "
                                 "example; the learner interrupts; close every chunk with one act by them (say it back, predict "
                                 "the next step, or one 'why does that follow?')"),
    ("understand", 1): ("recall, then teach the gap", "open with cold recall, no hints; feedback; then shorter "
                                                      "explanations, hints before answers, confidence before each reveal"),
    ("understand", 2): ("they explain first", "they explain it; you fill the gaps and push on the weak step; weave in "
                                             "one old idea they could confuse with it"),
    ("understand", 3): ("they teach it", "roles flip: they teach you, you play a novice and ask follow-ups, then "
                                         "bring a new case (a graded dialogue)"),
    ("pass", 0): ("teach to the exam", "worked example first, at exam level; close each chunk with their act"),
    ("pass", 1): ("recall with hints", "cold recall, then the hint ladder (question, hint, partial, answer last)"),
    ("pass", 2): ("exam questions", "exam-format questions, untimed, feedback after"),
    ("pass", 3): ("exam questions cold", "exam-format questions cold, at the exam's pace"),
}
IN_PLAY = 6


PROFILE = """# Learner profile

Updated:

<!-- The curated page a tutor reads first. Fill it from the learner notes, then set Updated to the
     day (YYYY-MM-DD); until then session shows every note. Rewrite it (do not append) when a note
     changes a rule, then `ken profile --folded`: it sets Updated to today and counts the notes
     taken in, so session shows only the notes written after that. -->

## Who

## Goals

## Background by field

<!-- One line per field: where they stand and what that means for teaching (math, security, ...). -->

## How to teach them

## Watch for
"""


def _profile_path(cfg):
    return cfg.home / "profile.md"


def profile_updated(cfg) -> str:
    """The profile's `Updated:` day, "" when there is no profile or no readable day."""
    p = _profile_path(cfg)
    if not p.is_file():
        return ""
    m = re.search(r"^Updated:\s*(\d{4}-\d{2}-\d{2})\s*$", p.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else ""


def profile_folded(cfg):
    """How many learner notes the profile says it has taken in (its `Folded:` line), or None."""
    p = _profile_path(cfg)
    if not p.is_file():
        return None
    m = re.search(r"^Folded:\s*(\d+)\s*$", p.read_text(encoding="utf-8"), re.M)
    return int(m.group(1)) if m else None


def _stamp_folded(cfg) -> int:
    """Mark every learner note written so far as taken into the profile: Updated is today and
    Folded is their count, so a note folded in on the day it was written stops showing as new."""
    p = _profile_path(cfg)
    if not p.is_file():
        raise UsageError(f"no profile yet; `{H.PROG} profile --scaffold` writes one")
    n = len(last_notes(_notes_path(cfg), None))
    text = p.read_text(encoding="utf-8")
    text = re.sub(r"^Folded:.*\n", "", text, flags=re.M)
    stamp = f"Updated: {H.today().isoformat()}\nFolded: {n}\n"
    if re.search(r"^Updated:.*$", text, re.M):
        text = re.sub(r"^Updated:.*\n?", lambda _m: stamp, text, count=1, flags=re.M)
    else:
        head, _, rest = text.partition("\n")
        text = f"{head}\n\n{stamp}{rest}"
    H.write_text(p, text)
    print(f"profile: Updated {H.today().isoformat()}, {n} learner note(s) folded in; session shows only later ones")
    return OK


def profile(cfg, scaffold=False, folded=False) -> int:
    p = _profile_path(cfg)
    if folded:
        return _stamp_folded(cfg)
    if scaffold:
        if p.exists():                      # a file or anything else in the way: never overwritten
            print(f"{p.name} exists; nothing written")
            return OK
        H.write_text(p, PROFILE)
        print(f"wrote {p.name}: fill it from {_notes_path(cfg).name}, keep it short, then set its Updated day")
        return OK
    if not p.is_file():
        print(f"no profile yet; `{H.PROG} profile --scaffold` writes one to fill from the learner notes")
        return OK
    print(p.read_text(encoding="utf-8"), end="")
    return OK


def _notes_path(cfg, slug=None):
    return (L.tdir(cfg, slug) / "tutor.md") if slug else (cfg.home / "learner.md")


def note(cfg, slug=None, text="", learner=False) -> int:
    if not text.strip():
        raise UsageError("a note needs text")
    if learner and slug:
        raise UsageError("--learner notes are about you across topics: give no topic with it")
    if not learner:
        if not slug:
            raise UsageError("give a topic, or --learner for a note about you across topics")
        L.need_topic(cfg, slug)
    p = _notes_path(cfg, None if learner else slug)
    head = "# Notes on the learner\n" if learner else f"# Tutor notes: {slug}\n"
    body = p.read_text(encoding="utf-8") if p.exists() else head
    day = H.today().isoformat()
    if f"\n## {day}\n" not in body:
        body = body.rstrip("\n") + f"\n\n## {day}\n"
    text = re.sub(rf"^{day}\s*:\s*", "", text.strip())      # the heading already carries the day
    if not text:
        raise UsageError("a note needs text")
    body = body.rstrip("\n") + f"\n- {text}\n"
    H.write_text(p, body)
    print(f"note: added to {p.relative_to(cfg.home)}")
    return OK


def last_notes(path, n=3) -> list:
    """The last n bullet notes, each prefixed with its date heading."""
    if not path.exists():
        return []
    out, day = [], ""
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d{4}-\d{2}-\d{2})\s*$", line)
        if m:
            day = m.group(1)
        elif line.startswith("- "):
            out.append(f"{day}: {line[2:]}")
    return out if n is None else out[-n:]


def session(cfg, slug, brief=False) -> int:
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    cons = L.load_state(cfg, slug)["concepts"]
    print(f"session: {conf.get('title', slug)} ({slug}), {L.lane_of(cfg, slug)} lane"
          + (f", complete (passed {L.get_key(conf, 'complete')})" if L.get_key(conf, "complete") else "")
          + (", still studied" if L.get_key(conf, "complete") and conf.get("keep_studying") is True else ""))
    intent, depth = conf.get("intent", ""), conf.get("depth", "")
    over = sum(1 for c in cons.values() if O.concept_setting(cfg, slug, c, "intent") not in ("", intent))
    print(f"  intent: {intent or 'not set'}" + (f" ({over} concept(s) differ, by line or rung)" if over else "")
          + f"; depth: {depth or 'not set'}")
    fo = FO.current(cfg)
    if fo["focus"] != FO.AUTO:
        print(f"  focus: {fo['focus']}" + ("" if fo["focus"] in (slug, L.lane_of(cfg, slug)) else
                                         f" (this session is outside it; `{H.PROG} focus {slug}` to pivot here)"))
    path = O.rungs(cfg, slug)
    if path:
        rows, _p = O.read(cfg, slug)
        st = O.placed(cfg, slug, rows, len(path))
        on = O.climbing(cons, path, st["start"])
        how = "by choice" if st.get("chosen") else "from placement" if st["start"] is not None else "not placed"
        print(f"  scale: {len(path)} rungs; start {st['start'] if st['start'] is not None else '-'} ({how})"
              + (f"; climbing rung {on} ({path[on]})" if on is not None else ""))
        bare = O.empty_rungs(cons, path)
        if bare:
            print(f"  {O.empty_line(bare, path, slug)}")
    try:
        steps = MK.stack(cfg)
        if steps:
            print("  trail: " + " > ".join(f"{s['topic']}/{s['concept']}" for s in steps)
                  + f"; return with `{H.PROG} trail --back`")
    except NotEvaluable as e:             # a way back is an aid: losing it does not stop the session
        print(f"  DAMAGED {e}")
    for p in MK.read_marks(cfg, slug)[1]:
        print(f"  DAMAGED {p}; marks are ignored until it is fixed")
    marked = MK.current(cfg, slug)
    problems = [k for k, v in marked.items() if v == "problem"]
    if problems:
        print(f"  you marked as a problem: {', '.join(problems)}")
    step = O.next_step(cfg, slug)
    if step:
        print(f"  on-ramp: {H.PROG} {' '.join(step[0])}  ({step[1]})")
    _ideas_in_play(cfg, slug, cons, step)
    taught = sorted(((c.get("last_taught"), k) for k, c in cons.items() if c.get("taught")), reverse=True)
    if taught:
        print(f"  taught so far: {len(taught)} concept(s); last {taught[0][1]} on {taught[0][0]}")
    # tutor notes on this topic: the last few. On the learner: the profile, then the notes since it was
    # last brought up to date; with no profile, every learner note (they are standing facts)
    notes = last_notes(_notes_path(cfg, slug), 3)
    print("  tutor notes: " + ("none yet" if not notes else ""))
    for x in notes:
        print(f"    {x}")
    from . import gaps as GP              # the last misses of the teaching here: not to be repeated
    last, total, damaged = GP.latest(cfg, slug)
    if damaged:
        print(f"  tutor gaps: NOT EVALUABLE, {len(damaged)} damaged line(s) in {GP.LEDGER}; see `{H.PROG} doctor`")
    elif last:
        print(f"  tutor gaps here: {total}; the last {len(last)} (do not repeat them):")
        for g in last:
            print(f"    {g['date']} {GP.line(g)}")
    learner = last_notes(_notes_path(cfg), None)
    if _profile_path(cfg).is_file():
        day = profile_updated(cfg)
        future = bool(day) and day > H.today().isoformat()
        if future:
            print(f"  learner profile: Updated {day} is later than today; read as no day, so every note shows")
            day = ""
        body = [ln for ln in re.sub(r"<!--.*?-->", "", _profile_path(cfg).read_text(encoding="utf-8"), flags=re.S).splitlines()
                if ln.strip() and not ln.startswith(("# ", "Updated:", "Folded:"))]
        if brief:
            print(f"  learner profile (updated {day or 'on no stated day'}): {len(body)} line(s), "
                  f"not shown (--brief); `{H.PROG} profile` prints it")
        else:
            print(f"  learner profile (updated {day or 'on no stated day'}):")
            for ln in body:
                print(f"    {ln}")
        newer = [x for x in learner if x[:10] >= day] if day else learner     # a same-day note shows
        n = profile_folded(cfg)
        # a Folded count is exact where the day is not: notes are appended, so the first n are in.
        # More counted than exist means notes were removed: the count is not trusted, the day rule holds
        if day and n is not None and n <= len(learner):
            newer = learner[n:]
        print(f"  learner notes since the profile: " + ("none" if not newer else f"{len(newer)} (fold them in)")
              + (f"; {len(learner) - len(newer)} older one(s) are in the profile" if day and len(learner) > len(newer) else ""))
        for x in newer:
            print(f"    {x}")
    else:
        print("  learner notes: " + ("none yet" if not learner else f"(no profile yet: `{H.PROG} profile --scaffold`)"))
        for x in learner:
            print(f"    {x}")
    rows, _d = L.read_log(cfg, slug)
    opened = [q for r in rows if r.get("mode") == "dialogue" for q in r.get("open", [])]
    if opened:
        print(f"  open questions: {len(opened)}; latest: {opened[-1][:100]}")
    reached = B.provider_offers(cfg, slug)          # scouted branches and any other plugged-in offers
    if reached:
        print(f"  predicted branches reached ({len(reached)}): offer when the gap shows")
        for x in reached[:5]:
            print(f"    {x['source']} {x['gap'][:90]}")
    evals = loop.evaluate(cfg, topic=slug)
    pick = next(e for e in evals if e["status"] == "fired")
    print(f"  next here: {' '.join(pick['argv'])}  ({pick['reason']})")      # argv already starts with the program
    print(f"  record: taught -> `{H.PROG} taught {slug} CONCEPT`; a graded dialogue -> "
          f"`{H.PROG} talk {slug} CONCEPT --protocol`; a note on how this learner learns -> `{H.PROG} note {slug} \"...\"`")
    return OK


def _ideas_in_play(cfg, slug, cons, step) -> None:
    """Per idea in play (the on-ramp's, then due, then last taught): its height and the foundations
    under it; then the one mode line the router copies."""
    today = H.today().isoformat()
    picks = [a for a in (step[0] if step else []) if a in cons][:1]
    picks += sorted((k for k, c in cons.items() if c.get("due") and c["due"] <= today), key=lambda k: cons[k]["due"])
    picks += [k for _d, k in sorted(((c.get("last_taught"), k) for k, c in cons.items() if c.get("taught")), reverse=True)]
    seen, play = set(), []
    for k in picks:
        if k not in seen:
            seen.add(k)
            play.append(k)
    if not play:
        return
    g = SG.build(cfg, slug)
    print(f"  ideas in play (height: {', '.join(f'{i} {n}' for i, n in enumerate(HT.LEVELS))}):")
    first = None
    for k in play[:IN_PLAY]:
        n, label, why, d = HT.height(cfg, slug, k)
        under = [(u, HT.height(cfg, slug, u)) for u in (g.nodes[k].first + g.nodes[k].pieces if k in g.nodes else [])]
        under += [(ref, HT.height(cfg, *ref.split("/", 1))) for ref, _up in (g.nodes[k].elsewhere if k in g.nodes else [])]
        print(f"    {k}: {n} {label} at {d} ({why})"
              + (f"; rests on {', '.join(f'{u} ({h[0]} {h[1]})' for u, h in under)}" if under else ""))
        if first is None:
            first = (k, n, label, d, under)
    k, n, label, d, under = first
    intent = O.concept_setting(cfg, slug, cons[k], "intent") or "understand"
    name, how = MOVES[(intent, n)]
    pull = [u for u, h in under if h[0] >= 1]
    print(f"  mode: {name}, {k} at height {n} ({label}), depth {d}, intent {intent}"
          + (f"; foundations to pull up from them first: {', '.join(pull)}" if pull and n <= 1 else "")
          + f"\n    how: {how}")


def _taught(cfg, ns) -> int:
    L.taught(cfg, ns.slug, ns.concept, ns.note, depth=ns.depth)
    return L.log_verdict(cfg, ns.slug)


def commands(groups) -> None:
    g = groups[""]
    a = g.add_parser("session", help="start a study session: settings, where you are, tutor notes, open questions, "
                                     "reached scouts and what to do next in this topic")
    a.add_argument("slug")
    a.add_argument("--brief", action="store_true", help="leave the learner profile's text out (a second look "
                                                        "in the same sitting); new notes still show")
    a.set_defaults(run=lambda cfg, ns: session(cfg, ns.slug, ns.brief))
    a = g.add_parser("note", help="a dated tutor note on how you learn: per topic, or --learner across topics")
    a.add_argument("slug", nargs="?")
    a.add_argument("text")
    a.add_argument("--learner", action="store_true")
    a.set_defaults(run=lambda cfg, ns: note(cfg, None if ns.learner else ns.slug, ns.text, ns.learner))
    a = g.add_parser("profile", help="the curated learner profile the tutor reads first (profile.md); "
                                     "--scaffold writes the template")
    a.add_argument("--scaffold", action="store_true")
    a.add_argument("--folded", action="store_true", help="the profile now holds every learner note written "
                                                         "so far: set Updated to today and count them")
    a.set_defaults(run=lambda cfg, ns: profile(cfg, ns.scaffold, ns.folded))
    a = g.add_parser("taught", help="record that a concept was taught today (teach mode): no credit, no schedule")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("--note", default="", help="what was covered")
    a.add_argument("--depth", default="", choices=("",) + L.DEPTHS, help="how deep it was taught")
    a.set_defaults(run=_taught)
