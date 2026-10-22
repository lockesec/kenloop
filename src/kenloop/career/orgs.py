"""A company's template, learned from its own postings.

Employers reuse text across their postings: the about-us paragraph, the benefits list, the
equal-opportunity statement. A line that appears in most of one company's postings is that
company's template. It is labelled, never deleted: `jobs check` keeps it out of the "not
looked at" list (it is not this role's requirement) while still reading it for skills, and the
company profile keeps its about, benefits and legal text for tailoring a resume and a cover
letter to that company.

Fewer than MIN_POSTINGS postings give nothing to compare: the template is NOT EVALUABLE, never
an empty one.
"""
from __future__ import annotations

import math
import re

from ..core import home as H
from . import roles as R
from . import sections as S

MIN_POSTINGS = 3
SHARE = 0.6


def key(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _postings(cfg, org: str) -> list:
    """Every posting of the company, its `[sources] aliases` names pooled with it."""
    alias = getattr(cfg, "org_aliases", None) or {}
    canon = lambda n: alias.get(n.strip().lower(), n.strip().lower())   # noqa: E731
    want = canon(org)
    out = []
    roles, _damaged = R.scan(cfg)
    for slug, meta in roles:
        names = {canon(str(meta.get("org") or "")), canon(str(meta.get("company") or ""))}
        p = R.role_dir(cfg, slug) / "jd.txt"
        if want in names and p.exists():
            out.append((slug, H.read_text(p, "posting")))
    return out


def _kind(counts: dict) -> str:
    """The kind a line most often takes (ties go to the earlier in sections.KINDS): the same
    answer whichever order the postings were read in."""
    return min(counts, key=lambda k: (-counts[k], S.KINDS.index(k)))


def profile(cfg, org: str) -> dict:
    posts = _postings(cfg, org)
    n = len(posts)
    count, first, kinds, sec_kinds, pos = {}, {}, {}, {}, {}
    for _slug, text in posts:
        lines = S.split(text, getattr(cfg, "headings", None))
        sectioned = any(ln.heading for ln in lines)       # a posting with no headings types every line `none`
        seen = set()
        for i, ln in enumerate(lines):
            if not ln.text or ln.heading:
                continue
            k = key(ln.text)
            if k in seen:
                continue
            seen.add(k)
            count[k] = count.get(k, 0) + 1
            pos[k] = min(pos.get(k, i), i)
            first[k] = min(first.get(k, ln.text.strip()), ln.text.strip())   # not order-dependent
            kinds.setdefault(k, set()).add(ln.kind)
            if sectioned:
                c = sec_kinds.setdefault(k, {})
                c[ln.kind] = c.get(ln.kind, 0) + 1
    # the kind a line takes where the posting has sections; `none` only when no posting typed it
    kind = {k: _kind(sec_kinds[k]) if k in sec_kinds else "none" for k in count}
    out = {"org": org, "postings": n, "generated": H.today().isoformat(), "template": None, "why": "",
           "threshold": None}
    if n < MIN_POSTINGS:
        out["why"] = (f"{n} posting(s) from {org}: a template needs at least {MIN_POSTINGS} to compare "
                      f"(NOT EVALUABLE)")
        shared = []
    else:
        need = max(MIN_POSTINGS, math.ceil(SHARE * n))
        out["threshold"] = need
        shared = sorted((k for k in count if count[k] >= need), key=lambda k: (pos[k], k))
        out["template"] = [{"text": first[k], "count": count[k], "kind": kind[k],
                            "kinds": sorted(kinds[k], key=S.KINDS.index)} for k in shared]
    # tailoring text: the template's lines when there is a template, else every posting's own
    pool = shared if shared else sorted(count, key=lambda k: (pos[k], k))
    for k_, field in (("company", "about"), ("benefits", "benefits"), ("legal", "legal")):
        out[field] = [first[k] for k in pool if kind[k] == k_]
    return out


JOB_KINDS = ("required", "preferred", "responsibilities")


def template_keys(cfg, org: str) -> set:
    """The template lines `jobs check` may set aside: never one in a required, preferred or
    responsibilities section in ANY posting (a line one posting leaves unheaded and three others
    list under Requirements is a requirement). A company that posts many similar roles repeats
    its requirements too, and a repeated requirement is still a requirement."""
    prof = profile(cfg, org) if org else None
    return {key(t["text"]) for t in (prof or {}).get("template") or []
            if not set(t.get("kinds") or [t["kind"]]) & set(JOB_KINDS)}
