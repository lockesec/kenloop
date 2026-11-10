"""Planning a topic: create it, read new concepts from the syllabus, bank questions.

Split out of core/learn.py; `learn` re-exports every name, so `L.<name>` still
works for callers. Kernel names are reached through `L.` so the kernel stays the one home of the
record and its rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import home as H
from . import learn as L
from .errors import (
    OK,
    UsageError,
)
from .names import slugify


SYLLABUS = """# {title}

Goal: {goal}

One concept per line under the Concepts heading:
- <domain> :: <name> :: <what it covers> [:: cluster:<id>] [:: scope:exam|depth] [:: status:settled|frontier|open]
  [:: part-of:<concept-id>] [:: before:<concept-id>|<topic>/<concept-id>]   (a piece of it / learned before it)

The scale (optional, but a new field wants one): list the domains as rungs, ground first, each
leaning only on the rungs below it, as `0. **domain** — what it covers`; then `{prog} place {slug}`
finds the rung you start on:

## Path


## Concepts

"""


def sync(cfg, slug, quiet=False) -> int:
    L.need_topic(cfg, slug)
    p = L.tdir(cfg, slug) / "syllabus.md"
    parsed = L.parse_syllabus(H.read_text(p, "syllabus") if p.exists() else "")
    state = L.load_state(cfg, slug)
    added = 0
    for c in parsed:
        cur = state["concepts"].get(c["cid"])
        if cur is None:
            added += 1
            cur = state["concepts"][c["cid"]] = {}
        for k in L.IDENTITY:
            if c.get(k) or k in ("desc", "scope", "status", "part_of", "before", "intent", "depth", "rung", "same"):
                cur[k] = c.get(k, "")
    L.save_state(cfg, slug, state)
    if not quiet:
        print(f"{slug}: {len(parsed)} concept(s) in the syllabus, {added} new")
    return L.log_verdict(cfg, slug, state)


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
    if len(slug) > L.MAX_SLUG:
        raise UsageError(f"topic slug is {len(slug)} characters; the limit is {L.MAX_SLUG}")


def plan(cfg, slug, title=None, goal=None, origin=None, seed=None, force=False, outlets=(),
         is_known=lambda term: False) -> int:
    """Create or update a topic. With no outlet it is studied for its own sake. `origin` says
    where it came from (a sidecar's own name for it); `seed` adds concepts to its syllabus,
    skipping any `is_known` or already present; `outlets` are added, never removed."""
    check_slug(slug)
    d = L.tdir(cfg, slug)
    exists = d.is_dir()
    if exists and not (force or origin):
        raise UsageError(f"topic {slug} exists; pass --force to update its title/goal (the syllabus is never overwritten)")
    d.mkdir(parents=True, exist_ok=True)
    conf = L.load_config(cfg, slug)
    conf.setdefault("title", title or slug.replace("-", " "))
    if title:
        conf["title"] = title
    if goal:
        conf["goal"] = goal
    for o in outlets:
        if o not in L.OUTLETS:
            raise UsageError(f"unknown outlet {o!r} ({', '.join(L.OUTLETS)})")
        conf.setdefault("outlets", [])
        if o not in conf["outlets"]:
            conf["outlets"].append(o)
    syl = d / "syllabus.md"
    if not syl.exists():
        H.write_text(syl, SYLLABUS.format(title=conf["title"], goal=conf.get("goal", ""), prog=H.PROG, slug=slug))
    if not (d / "questions.md").exists():
        H.write_text(d / "questions.md",
                     f"# Question bank — {conf['title']}\n\nAdd with `{H.PROG} bank {slug} <concept> --q --a --ref`.\n\n")
    (d / "log.jsonl").touch()
    added = skipped = 0
    if seed is not None:
        text = H.read_text(syl, "syllabus")
        have = {c["name"].lower() for c in L.parse_syllabus(text)}
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
    if origin and not conf.get("origin"):    # a topic many branches grow into keeps where it began;
        conf["origin"] = origin               # branches.jsonl records where each later concept came from
    L.save_config(cfg, slug, conf)
    if not (d / "concepts.json").exists():
        L.save_state(cfg, slug, {"concepts": {}})
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
    state = L.load_state(cfg, slug)
    cid = L.resolve_concept(state, concept)
    if not ref:
        raise UsageError("--ref is required: every question names where its answer comes from")
    if qtype and qtype not in L.QTYPES:
        raise UsageError(f"--qtype must be one of {', '.join(L.QTYPES)}")
    if len(distractors) > 7:
        raise UsageError("at most 7 distractors per question (8 options in all)")
    ds = []
    for d in distractors:
        opt, sep, mis = d.partition("::")
        if not sep or not opt.strip():
            raise UsageError(f"--d {d!r} must be 'option :: the misconception it encodes'")
        ds.append((opt.strip(), mis.strip()))
    p = L.tdir(cfg, slug) / "questions.md"
    text = H.read_text(p, "question bank") if p.exists() else ""
    if any(x["q"].lower() == q.strip().lower() for x in L.parse_questions(text).get(cid, [])):
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
