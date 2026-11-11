"""Interview prep, company research and the application email, each a Markdown file in the role's folder.

Like `jobs brief`, these hold no model output: every line is the posting, facts.md, the coverage
report, your story bank, research.md or your [profile], put in order. What only you (or a web read)
can supply is marked [FILL]. All three need a fresh `jobs check`, and none overwrites a file you may
have filled in unless you pass --force.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..core import home as H
from ..core.errors import OK, NotEvaluable, Refused
from . import ats
from . import jobs as J
from . import roles as R

FILL = "[FILL]"


def _write(cfg, slug, name, text, force) -> int:
    p = R.role_dir(cfg, slug) / name
    if p.exists() and not force:
        raise Refused(f"{slug}: {name} already exists (you may have filled it in); pass --force to rewrite it")
    H.write_text(p, text)
    print(f"wrote roles/{slug}/{name}")
    return OK


def _typed(v, kind) -> list:
    return [t for t in v["terms"] if v["where"].get(t.lower()) == kind]


def _proof(v, term) -> str:
    ev = J._evidence(term.lower(), v["facts"], v["lex"])
    return " / ".join('"' + re.sub(r"^[-*+]\s+", "", e) + '"' for e in ev) if ev else "(held)"


def _years(v) -> list:
    out = []
    for y in v["cov"].get("years") or []:
        ask = f"{y['min']}-{y['max']}" if y["max"] else f"{y['min']}+"
        out.append(f"- {ask} years ({y['kind']}): \"{y['text']}\"")
    return out


# --- stories --------------------------------------------------------------------------------------

def stories(cfg) -> tuple:
    """([(title, body)], why-none). The story bank is `[profile] stories`, a Markdown file with one
    `### Title` heading per story; [TAGS] after a title are dropped."""
    rel = cfg.profile.get("stories", "")
    if not rel:
        return [], "no story bank: set `[profile] stories` to a Markdown file with one `### Title` per story"
    p = Path(rel).expanduser()
    p = p if p.is_absolute() else cfg.home / p
    if not p.is_file():
        raise NotEvaluable(f"[profile] stories = {rel!r}: no such file")
    out, title, body = [], None, []
    for ln in H.read_text(p, "story bank").splitlines():
        if ln.startswith("### "):
            if title:
                out.append((title, "\n".join(body)))
            title, body = re.sub(r"\s*\[.*", "", ln[4:]).strip(" —-"), []
        elif ln.startswith("## ") or ln.startswith("# "):
            if title:
                out.append((title, "\n".join(body)))
            title, body = None, []
        elif title:
            body.append(ln)
    if title:
        out.append((title, "\n".join(body)))
    return out, "" if out else f"the story bank {rel} has no `### Title` stories"


def matched_stories(cfg, v) -> tuple:
    """([(title, [posting terms the story names])] best first, stories that name none, why-none)."""
    bank, why = stories(cfg)
    wanted = {t.lower() for t in v["terms"]}
    hits, rest = [], []
    for title, body in bank:
        named = [t for t in ats.extract(f"{title}\n{body}", v["lex"], acronyms=False) if t.lower() in wanted]
        (hits if named else rest).append((title, sorted({t.lower() for t in named})))
    hits.sort(key=lambda h: (-len(h[1]), h[0]))
    return hits, [t for t, _ in rest], why


# --- research -------------------------------------------------------------------------------------

def research_section(cfg, slug) -> list:
    """The prep pack's company section, from research.md; an absent or unfilled one says so."""
    p = R.role_dir(cfg, slug) / "research.md"
    if not p.exists():
        return [f"## Company research {FILL}", "", f"No research.md yet: `{H.PROG} jobs research {slug}`, then fill it."]
    text = H.read_text(p, "research")
    unfilled = re.findall(r"(?m)^## (.+?)\s+\[FILL\]\s*$", text)
    body = text.split("\n## ", 1)
    head = "## Company research" + (f" {FILL} still open: {', '.join(unfilled)}" if unfilled else "")
    if len(body) < 2:
        return [head, "", "research.md has no sections yet."]
    return [head, "", "From research.md:", "", "### " + body[1].replace("\n## ", "\n### ").rstrip()]


def research(cfg, slug, force=False) -> int:
    from . import orgs as O
    v = J.role_view(cfg, slug)
    meta, parts, company = v["meta"], v["parts"], v["company"]
    prof = O.profile(cfg, meta.get("org") or company)
    about = prof["about"] if prof.get("template") else parts.get("company", [])
    where = (f"{company}'s template across {prof['postings']} posting(s)" if prof.get("template")
             else "this posting only")
    out = [f"# Company research: {company} — {v['role']}", "",
           f"What {H.NAME} already knows, from the posting and your records; the {FILL} sections need a read "
           "of the company's own site and recent news. Keep only what you can point to.", "",
           "| | |", "|---|---|"]
    for k in ("source_url", "board", "job_id", "location", "salary"):
        out.append(f"| {k.replace('_', ' ')} | {meta.get(k) or '-'} |")
    out += ["", "## What they do", "", f"In its own words ({where}):", ""]
    out += [f"> {ln}" for ln in about] or [f"> (the posting says nothing about the company) {FILL}"]
    others = [(s, m) for s, m in R.scan(cfg)[0] if s != slug and str(m.get("company", "")).strip().lower()
              == company.lower()]
    out += ["", "## Your other roles here", ""]
    out += [f"- {s}: {m.get('role')} ({m.get('status')}{', fit ' + str(m['fit_score']) if m.get('fit_score') else ''})"
            for s, m in others] or ["- (none tracked)"]
    if parts.get("benefits"):
        out += ["", "## Benefits it states", ""] + [f"- {ln}" for ln in parts["benefits"]]
    angle = []
    for ln in parts.get("responsibilities", []):
        named = [t for t in ats.extract(ln, v["lex"], acronyms=False) if t.lower() in v["held"]]
        if named:
            angle.append(f"- They need: \"{ln}\". You hold {', '.join(sorted({t.lower() for t in named}))}.")
    out += ["", "## Your angle", "", "The responsibilities you hold a skill for, in the posting's words:", ""]
    out += angle or ["- (no responsibility names a skill you hold)"]
    out += ["", f"Sharpened for this company {FILL}: the one story that fits what they need now.", ""]
    for sec, hint in (("Size, stage and ownership", "headcount, public or private, funding or contracts"),
                      ("Recent news", "announcements, contracts, hiring, tools adopted in the last six months"),
                      ("Who interviews", "the hiring manager and team, if you can find them"),
                      ("Culture and tone", "how they write about themselves: sets the letter's and the interview's tone")):
        out += [f"## {sec} {FILL}", "", f"- {hint}", ""]
    return _write(cfg, slug, "research.md", "\n".join(out), force)


# --- prep -----------------------------------------------------------------------------------------

def prep(cfg, slug, force=False) -> int:
    v = J.role_view(cfg, slug)
    meta, parts = v["meta"], v["parts"]
    out = [f"# Interview prep: {v['company']} — {v['role']}", "",
           f"{H.NAME} put this together from the posting, your facts.md, `jobs check` and your story bank. "
           "Claim only what facts.md holds. For a term NOT HELD, bridge honestly: what you have done nearest to it, "
           "and what you are doing about it.", "",
           f"Fit {meta.get('fit_score') or '-'} · status {meta.get('status')} · job id {meta.get('job_id') or '-'}", "",
           "## What the job does (expect questions on each)", ""]
    out += [f"- {ln}" for ln in parts.get("responsibilities", [])] or ["- (the posting lists no responsibilities)"]
    groups = [(_typed(v, k), f"{k.capitalize()}: what to say") for k in ("required", "preferred")]
    if not any(ts for ts, _ in groups):           # sections not recognised: every term, untyped, never none
        groups = [(list(v["terms"]), "What the posting asks for (its sections were not recognised, so "
                                     "required and preferred are not told apart): what to say")]
    for ts, title in groups:
        out += ["", f"## {title}", ""]
        for t in ts:
            if t.lower() in v["held"]:
                out.append(f"- {t.lower()}: say {_proof(v, t)}")
            else:
                out.append(f"- {t.lower()}: NOT HELD (bridge, never claim)")
        if not ts:
            out.append("- (no term found here)")
    yrs = _years(v)
    if yrs:
        out += ["", "## Experience asked", ""] + yrs
    unread = (v["cov"].get("unread") or {}).get("unread") or []
    if unread:
        out += ["", "## Lines no known skill was found in (read them; worth a question back)", ""]
        out += [f"- {ln}" for ln in unread]
    hits, rest, why = matched_stories(cfg, v)
    out += ["", "## Stories to lead with", ""]
    if why:
        out.append(f"- {why}")
    else:
        out += [f"- {t}: names {', '.join(n)}" for t, n in hits] or ["- (no story names a term this posting asks for)"]
        if rest:
            out.append(f"- {len(rest)} other stor{'y' if len(rest) == 1 else 'ies'} name nothing this posting asks for")
    out += [""] + research_section(cfg, slug) + [""]
    return _write(cfg, slug, "prep.md", "\n".join(out), force)


# --- email ----------------------------------------------------------------------------------------

def email(cfg, slug, force=False) -> int:
    p = cfg.profile
    if not p.get("name"):
        raise NotEvaluable("the email is signed from [profile] name, which is not set (also read: email, phone, location)")
    v = J.role_view(cfg, slug)
    meta = v["meta"]
    ref = v["role"] + (f" ({meta['job_id']})" if meta.get("job_id") else "")
    contact = " · ".join(p.get(k) or f"{FILL} {k}" for k in ("phone", "email", "location"))
    req = [t for t in _typed(v, "required") if t.lower() in v["held"]] or \
          [t for t in v["terms"] if t.lower() in v["held"]]
    pdfs = []
    if meta.get("pdf_dir"):
        d = Path(meta["pdf_dir"]).expanduser()
        d = d if d.is_absolute() else cfg.home / d
        pdfs = sorted(x.name for x in d.glob("*.pdf")) if d.is_dir() else []
    attach = [f"[ ] {n}" for n in pdfs] or [f"[ ] no PDFs yet: `{H.PROG} jobs build {slug}`"]
    out = [f"# Application email: {v['company']} — {v['role']}", "",
           f"A DRAFT: {H.NAME} never sends. Write the {FILL}s from the material below; claim only what it holds.", "",
           "## Email", "", f"**To:** {FILL} the recruiter or hiring address", f"**Subject:** {ref} - {p['name']}", "",
           f"Dear {v['company']} hiring team,", "",
           f"I am applying for the {ref} role. {FILL} one or two sentences: what in the posting you have done, "
           "from the material below.", "",
           "My resume and cover letter are attached. Thank you for your consideration.", "",
           p["name"], contact, "", "**Attach:** " + "  ".join(attach), "",
           "## Short note to a recruiter or the hiring manager", "",
           f"Hi {FILL} name, I have applied for the {v['role']} role at {v['company']}. {FILL} one sentence from the "
           "material below. Happy to share more if useful.", "",
           "## Material (the posting's asks you hold, with your proof)", ""]
    out += [f"- {t.lower()}: {_proof(v, t)}" for t in req[:6]] or ["- (you hold nothing this posting names: is this the right role?)"]
    return _write(cfg, slug, "email.md", "\n".join(out) + "\n", force)
