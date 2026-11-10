"""Integrity: rename a concept, rebuild state from the log, validate a topic, the brief.

Split out of core/learn.py; `learn` re-exports every name, so `L.<name>` still
works for callers. Kernel names are reached through `L.` so the kernel stays the one home of the
record and its rules."""
from __future__ import annotations

import hashlib
import re

from . import home as H
from . import learn as L
from .errors import (
    DRIFT,
    FINDINGS,
    NOT_EVALUABLE,
    OK,
    NotEvaluable,
    UsageError,
)


def rename(cfg, slug, old: str, new: str) -> int:
    """Carry a concept's history to its new name after you renamed its syllabus line. The log is
    never rewritten: a renames.jsonl row maps the old id, and replay reads history under the new
    one. The files you edit by hand follow: links (`part-of:` / `before:`) in syllabus.md, the
    bank's `## <id>` heading, the foundations note. Then the state is rebuilt from the log."""
    L.need_topic(cfg, slug)
    d = L.tdir(cfg, slug)
    syl = d / "syllabus.md"
    ids = {c["cid"] for c in L.parse_syllabus(H.read_text(syl, "syllabus"))} if syl.exists() else set()
    if old == new:
        raise UsageError("the old and new ids are the same")
    if new not in ids:
        raise UsageError(f"{new!r} is not in syllabus.md: rename the concept's line there first "
                         f"(its id is domain:name), then run this to carry its history")
    if old in ids:
        raise UsageError(f"{old!r} is still in syllabus.md: rename or remove its line first")
    state = L.load_state(cfg, slug)
    cons = state["concepts"]
    if old not in cons:
        raise UsageError(f"{old!r} has no record in this topic: nothing to carry")
    if cons.get(new, {}).get("attempts", 0):
        raise UsageError(f"{new!r} already has a history of its own: merging two histories is not done here")
    from . import ledger as LG
    LG.append(d / "renames.jsonl", {"date": H.today().isoformat(), "from": old, "to": new}, L._check_rename)
    text = H.read_text(syl, "syllabus")
    linked = re.sub(rf"(?<=part-of:){re.escape(old)}(?![\w:.-])|(?<=before:){re.escape(old)}(?![\w:.-])", new, text)
    if linked != text:
        H.write_text(syl, linked)
    bank = d / "questions.md"
    if bank.exists():
        b = H.read_text(bank, "question bank")
        nb = re.sub(rf"^## {re.escape(old)}[ \t]*$", f"## {new}", b, flags=re.M)
        if nb != b:
            H.write_text(bank, nb)
    note_old, note_new = (d / "foundations" / (x.replace(":", "--") + ".md") for x in (old, new))
    if note_old.is_file() and not note_new.exists():
        note_old.rename(note_new)
    cons.pop(old, None)
    L.save_state(cfg, slug, state)
    L.sync(cfg, slug, quiet=True)
    code = rebuild(cfg, slug)
    links = "links updated in syllabus.md; " if linked != text else ""
    print(f"{slug}: {old} -> {new}: its history now reads under the new id; {links}recorded in renames.jsonl")
    return code


def rebuild(cfg, slug, check=False, skip_damaged=False) -> int:
    """--check: 0 matches, 3 drift, 2 when the log could not be read in full.
    Without --check: rewrite concepts.json from syllabus + log. A log with
    unreadable rows is refused unless --skip-damaged, which rebuilds from the
    readable rows and says how many it skipped. A damaged concepts.json is
    kept beside the new one, never overwritten."""
    L.need_topic(cfg, slug)
    p = L.tdir(cfg, slug) / "concepts.json"
    try:
        state = L.load_state(cfg, slug)
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
    new, problems = L.replay(cfg, slug, state)
    for pr in problems:
        H.warn(pr)
    if check:
        d, _ = L.audit(cfg, slug, state)
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
    L.save_state(cfg, slug, new)
    print(f"{slug}: rebuilt {len(new['concepts'])} concept(s) from the log"
          + (f"; skipped {len(problems)} damaged row(s)" if problems else ""))
    return OK


def _placeholder(text: str) -> bool:
    """An angle-bracket placeholder left from the brief's example block: "<the one checkable
    answer>". A short tag ("<div>") is a real answer, not a placeholder."""
    t = (text or "").strip()
    return bool(re.fullmatch(r"<[^<>]{10,}>", t)) and " " in t


def edge_problems(concepts: list) -> list:
    """What is wrong with the syllabus's `part-of` / `before` links: a concept linked to itself, a
    link to a concept the syllabus does not have, and a cycle. A piece comes before its whole and
    a `before` concept before its target, so a cycle through either is an order no one can follow."""
    ids = {c["cid"] for c in concepts}
    out, nxt = [], {}
    for c in concepts:
        for field, marker in (("part_of", "part-of"), ("before", "before")):
            t = c.get(field)
            if not t:
                continue
            if t == c["cid"]:
                out.append(f"{c['cid']}: `{marker}:{t}` links the concept to itself")
            elif field == "before" and "/" in t:
                continue                  # another topic's concept: checked by cross_topic_problems
            elif t not in ids:
                out.append(f"{c['cid']}: `{marker}:{t}` names a concept this syllabus does not have")
            else:
                nxt.setdefault(c["cid"], []).append(t)
    state, reported = {}, set()           # 1 = on the current path, 2 = done; iterative, no recursion
    for root in sorted(nxt):
        if state.get(root):
            continue
        stack, path = [(root, iter(nxt.get(root, ())))], [root]
        state[root] = 1
        while stack:
            node, it = stack[-1]
            t = next(it, None)
            if t is None:
                state[node] = 2
                stack.pop()
                path.pop()
            elif state.get(t) == 1:
                loop = path[path.index(t):] + [t]
                key = frozenset(loop)
                if key not in reported:
                    reported.add(key)
                    out.append("a cycle of part-of / before links: " + " -> ".join(loop))
            elif not state.get(t):
                state[t] = 1
                stack.append((t, iter(nxt.get(t, ()))))
                path.append(t)
    return out


def cross_topic_problems(cfg, slug, concepts: list) -> tuple:
    """(hard, warnings) for `before:<topic>/<cid>`: it must name another topic that exists and a
    concept it has, and the chain of `before` links it starts must not come back to where it began
    (two topics each waiting on the other would hold both forever). A damaged other topic is a
    warning here, so this topic's own checks still run."""
    hard, warn = [], []
    for c in concepts:
        t = c.get("before") or ""
        if "/" not in t:
            continue
        topic, _, cid = t.partition("/")
        if topic == slug:
            hard.append(f"{c['cid']}: `before:{t}` names this topic; write `before:{cid}` for a link inside one topic")
            continue
        if topic not in L.topics(cfg):
            hard.append(f"{c['cid']}: `before:{t}` names a topic this home does not have")
            continue
        try:
            if cid not in L.load_state(cfg, topic)["concepts"]:
                hard.append(f"{c['cid']}: `before:{t}` names a concept {topic} does not have")
                continue
        except NotEvaluable:
            warn.append(f"{c['cid']}: `before:{t}` cannot be checked: {topic} is damaged (`{H.PROG} validate {topic}`)")
            continue
        loop = _before_chain_loop(cfg, slug, c["cid"], concepts)
        if loop:
            hard.append("a cycle of before links across topics: " + " -> ".join(loop))
    return hard, warn


def _before_chain_loop(cfg, slug, cid, concepts) -> list:
    """The chain of `before` links from slug/cid, as topic/cid steps, if it returns to its start."""
    mine = {c["cid"]: c.get("before") or "" for c in concepts}
    start, at, path, seen = f"{slug}/{cid}", (slug, cid), [], set()
    while at and f"{at[0]}/{at[1]}" not in seen:
        here = f"{at[0]}/{at[1]}"
        seen.add(here)
        path.append(here)
        try:
            ref = mine.get(at[1], "") if at[0] == slug else \
                (L.load_state(cfg, at[0])["concepts"].get(at[1]) or {}).get("before") or ""
        except NotEvaluable:
            return []
        if not ref:
            return []
        at = tuple(ref.split("/", 1)) if "/" in ref else (at[0], ref)
    return path + [start] if at and f"{at[0]}/{at[1]}" == start else []


def problems(cfg, slug) -> tuple:
    """(hard failures, warnings) for one topic."""
    hard, warn = [], []
    syl = L.tdir(cfg, slug) / "syllabus.md"
    on_syllabus = None
    if syl.exists():
        try:
            parsed = L.parse_syllabus(H.read_text(syl, "syllabus"))
            on_syllabus = {c["cid"] for c in parsed}
            cross_hard, cross_warn = cross_topic_problems(cfg, slug, parsed)
            hard += [f"{slug}/{p}" for p in edge_problems(parsed) + cross_hard]
            warn += [f"{slug}/{p}" for p in cross_warn]
        except UsageError as e:
            hard.append(f"{slug}: {e}")
    from . import marks as M
    from . import recall as RC          # recall reads learn: imported here, not at module load
    hard += [f"{slug}: damaged {p}" for p in RC.read(cfg, slug)[1]]
    hard += [f"{slug}: damaged {p}" for p in M.read_marks(cfg, slug)[1]]
    state = L.load_state(cfg, slug)
    L.load_config(cfg, slug)          # a damaged topic.json is reported, not skipped
    cons = state["concepts"]
    for r in L.read_log(cfg, slug)[0]:
        t = r.get("transcript")
        if not t:
            if r.get("mode") == "dialogue":
                warn.append(f"{slug}/{r['concept']}: the {r['date']} dialogue grade has no transcript: nothing shows "
                            "what it was graded on (keep one at the path `talk` prints, before recording)")
            continue
        p = L.tdir(cfg, slug) / t
        # The transcript is the evidence behind a grade: evidence gone or changed is a failure, not a note.
        g = L.graded_copy(cfg, slug, t)
        intact = g.is_file() and hashlib.sha256(g.read_bytes()).hexdigest() == r.get("transcript_sha256")
        how = (f"; the graded copy is {g.relative_to(L.tdir(cfg, slug)).as_posix()}: compare them, or copy it back"
               if intact else "; no intact graded copy is kept, so what changed cannot be shown")
        if not p.is_file():
            hard.append(f"{slug}/{r['concept']}: the transcript behind the {r['date']} dialogue grade is missing ({t}){how}")
        elif hashlib.sha256(p.read_bytes()).hexdigest() != r.get("transcript_sha256"):
            hard.append(f"{slug}/{r['concept']}: the transcript behind the {r['date']} dialogue grade "
                        f"changed after it was graded ({t}){how}")
    for cid, c in cons.items():
        if on_syllabus is not None and cid not in on_syllabus and c.get("attempts", 0):
            warn.append(f"{slug}/{cid}: has a history in the log but is no longer in syllabus.md (renamed or "
                        f"removed?); its record still counts in mastery and links. To carry the history to a new "
                        f"name: `{H.PROG} rename {slug} {cid} NEW-ID`")
        if not c.get("name"):
            hard.append(f"{slug}/{cid}: no name")
        if c.get("correct", 0) > c.get("attempts", 0):
            hard.append(f"{slug}/{cid}: more correct than attempts")
        if c.get("streak", 0) < 0:
            hard.append(f"{slug}/{cid}: negative streak")
    for cid, qs in L.load_bank(cfg, slug).items():
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
            if q["type"] and q["type"] not in L.QTYPES:
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
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    state = L.load_state(cfg, slug)
    bank = L.load_bank(cfg, slug)
    title = conf.get("title") or slug
    out = [f"# Study brief: {title} ({slug})", "",
           f"{H.NAME} wrote this from the topic's syllabus, its question bank and its log. It holds "
           "no model output.", "",
           "## Rules for whoever writes the questions", "",
           "- Ask with no hint: the question must not contain or point at its answer.",
           "- One checkable answer per question; say why in one sentence.",
           "- Give a Ref the learner can open (notes.md#section, or a URL). No Ref, no question.",
           "- Write your own questions; never copy an exam's or a course's questions.",
           f"- Type is one of: {', '.join(L.QTYPES)}. Mix them; recall alone does not test use.",
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
    if not slug and not L.topics(cfg):
        print(f"NOT EVALUABLE nothing to validate: 0 topic(s) in {cfg.home}; "
              "an empty home has no failures, which is not the same as none being found")
        return NOT_EVALUABLE
    for t in ([slug] if slug else L.topics(cfg)):
        h, w = problems(cfg, t)
        hard += h
        warn += w
        damaged += [f"{t}: {d}" for d in L.read_log(cfg, t)[1]]
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
