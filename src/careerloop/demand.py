"""Demand: how much the roles you are pursuing want each skill you lack.

This is the seam from the job arm to the learn arm. ``jobs upskill`` reads
every role's ``coverage.json`` and writes ``upskill.json``; ``learn gaps``,
``learn plan --from-gap`` and ``next`` read it.

A term's demand is not a raw count of postings. Each role that lacks the term
(and whose facts do not hold it) contributes

    status weight x recency

where recency halves every ``half_life_days`` (60 by default) since the role
was found, a closed or passed role weighs nothing, an offer or on-hold role
half, and a rejection a quarter (half if you reached an interview). A skill an
interviewer actually probed adds ``probe_bonus`` x recency on top.

Held-ness is re-read from the facts sheet at every run, so a term you
graduate into ``facts.md`` stops being a gap without re-checking any role.
"""
from __future__ import annotations

import hashlib
import json

from . import facts as F
from . import home as H
from . import roles as R


def role_weight(meta: dict, cfg, today) -> float:
    st = meta.get("status", "found")
    stage = (meta.get("outcome") or {}).get("stage_reached", "")
    if st == "rejected" and stage in ("interview", "final"):
        w = cfg.status_weights.get("rejected-after-interview", 0.5)
    else:
        w = cfg.status_weights.get(st, 0.0)
    if meta.get("posting_gone") and st not in ("applied", "interviewing"):
        return 0.0
    return w * recency(meta, cfg, today)


def recency(meta: dict, cfg, today) -> float:
    try:
        found = H._dt.date.fromisoformat(meta.get("found") or "")
    except (ValueError, TypeError):
        return 1.0
    return 0.5 ** (max(0, (today - found).days) / cfg.half_life_days)


def inputs_digest(cfg) -> str:
    """A hash of everything demand is computed from. A stored digest that no
    longer matches means upskill.json is stale (same-day edits included)."""
    h = hashlib.sha256()
    for p in [cfg.facts, cfg.home / "config.toml"] + sorted(cfg.roles.glob("*/meta.json")) \
            + sorted(cfg.roles.glob("*/coverage.json")):
        h.update(str(p.relative_to(cfg.home)).encode())
        try:
            h.update(p.read_bytes())
        except OSError:
            h.update(b"<absent>")
    return h.hexdigest()[:16]


def _bucket_of(key: str, cfg):
    for b in cfg.buckets:
        for m in b.match:
            if (m.startswith("substr:") and m[7:] in key) or m == key:
                return b
    return None


def compute(cfg) -> dict:
    today = H.today()
    facts = F.read(cfg)
    roles, damaged = R.scan(cfg)
    from . import ats
    from .errors import NotEvaluable
    try:
        holds = ats.load_lexicon(cfg).holds          # a term held under an alias is held
    except NotEvaluable:
        holds = F.holds                                # a missing pack: literal spellings only
    items: dict = {}
    quick: dict = {}
    analyzed, unchecked = 0, []
    unread = {"roles": 0, "lines": 0, "unread": 0, "unmeasured": 0}

    def item(key, term, category):
        return items.setdefault(key, {"term": term, "count": 0, "demand": 0.0,
                                      "roles": [], "category": category})

    for slug, meta in roles:
        from .jobs import load_coverage
        cov = load_coverage(cfg, slug)
        w = role_weight(meta, cfg, today)
        if cov is None:
            if (cfg.roles / slug / "jd.txt").exists():
                unchecked.append(slug)
        else:
            analyzed += 1
            u = cov.get("unread") if isinstance(cov.get("unread"), dict) else None
            if u is None:
                unread["unmeasured"] += 1     # checked before the count existed: not "no lines"
            elif isinstance(u.get("lines"), int) and u["lines"] > 0:
                unread["roles"] += 1
                unread["lines"] += u["lines"]
                unread["unread"] += len(u.get("unread") or [])
            if w > 0:
                for m in cov.get("missing", []):
                    key = m["term"].lower()
                    held = holds(key, facts) and key not in cfg.do_not_claim
                    if held:
                        q = quick.setdefault(key, {"term": key, "count": 0, "roles": []})
                        q["count"] += 1
                        q["roles"].append(slug)
                        continue
                    it = item(key, m["term"], m.get("category", "acronym"))
                    it["count"] += 1
                    it["demand"] += w
                    it["roles"].append(slug)
        probed = {t.lower(): t for t in (meta.get("outcome") or {}).get("probed_terms", []) or []
                  if isinstance(t, str) and t.strip()}
        for key, t in probed.items():                     # once per role, weighted like the role
            if w <= 0 or (holds(key, facts) and key not in cfg.do_not_claim):
                continue
            it = item(key, t, "probed")
            it["demand"] += cfg.probe_bonus * w
            if slug not in it["roles"]:
                it["roles"].append(slug)

    buckets: dict = {}
    for key, it in items.items():
        b = _bucket_of(key, cfg)
        name = b.name if b else f"Unmapped: {it['category']}"
        bk = buckets.setdefault(name, {"name": name, "demand": 0.0, "action": b.action if b else "",
                                       "items": []})
        if b and b.held_ref and not F.holds(b.held_ref, facts):
            bk["action"] = (bk["action"] + f" [STALE? anchor '{b.held_ref}' no longer reads "
                            "held in facts.md; re-verify]").strip()
        it["noise"] = key in cfg.ignore
        it["demand"] = round(it["demand"], 2)
        bk["items"].append(it)
        if not it["noise"]:
            bk["demand"] += it["demand"]
    out = []
    for bk in buckets.values():
        bk["demand"] = round(bk["demand"], 2)
        bk["items"].sort(key=lambda i: (-i["demand"], i["term"].lower()))
        out.append(bk)
    out.sort(key=lambda b: (-b["demand"], b["name"]))
    return {"schema": 2, "generated": today.isoformat(), "inputs": inputs_digest(cfg),
            "roles_analyzed": analyzed, "roles_unchecked": unchecked, "roles_damaged": damaged,
            "unread": unread,
            "quick_wins": sorted(quick.values(), key=lambda q: (-q["count"], q["term"])),
            "buckets": out}


def load(cfg) -> tuple:
    """(upskill, stale). Absent is NOT EVALUABLE: no demand has been measured."""
    from .errors import NotEvaluable
    data = H.read_json(cfg.upskill, "upskill")
    if data is None:
        raise NotEvaluable(f"no {cfg.upskill.name} yet: run `careerloop jobs upskill` first")
    if not isinstance(data, dict) or data.get("schema") != 2:
        raise NotEvaluable(f"{cfg.upskill} is not a schema-2 demand file; re-run `careerloop jobs upskill`")
    bs = data.get("buckets")
    if not (isinstance(bs, list) and all(
            isinstance(b, dict) and isinstance(b.get("name"), str) and isinstance(b.get("items"), list)
            and isinstance(b.get("demand"), (int, float)) and all(isinstance(i, dict) for i in b["items"])
            for b in bs)):
        raise NotEvaluable(f"{cfg.upskill} is damaged (`buckets` must be a list of buckets with a name, a demand "
                           "and items); re-run `careerloop jobs upskill`")
    stale = data.get("inputs") != inputs_digest(cfg) or data.get("generated") != H.today().isoformat()
    return data, stale   # recency weights move every day even when no file does


def dumps(data) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False)
