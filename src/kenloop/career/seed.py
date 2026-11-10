"""Seeds from job demand: a study topic planned from a demand bucket (`plan --from-gap`),
and the study queue of buckets (`jobs gaps`). The core plans the topic; this picks what to
offer it and checks what you already hold.
"""
from __future__ import annotations

from ..core import home as H
from ..core import learn as L
from ..core.errors import NOT_EVALUABLE, OK, NotEvaluable, UsageError
from ..core.names import slugify
from . import demand as DM
from . import facts as F


def plan(cfg, slug, title=None, goal=None, from_gap=None, top=None, force=False, career=False) -> int:
    """`plan`: a topic studied for its own sake; with --career one that may graduate into
    facts.md; with --from-gap one seeded from a demand bucket (which implies --career)."""
    outlets = ("career",) if career or from_gap else ()
    if not from_gap:
        return L.plan(cfg, slug, title, goal, force=force, outlets=outlets)
    L.check_slug(slug)
    data, stale = DM.load(cfg)                 # validate before creating anything
    names = [b["name"] for b in data["buckets"]]
    if from_gap not in names:
        raise UsageError(f"no bucket {from_gap!r} in {cfg.upskill.name} (buckets: {'; '.join(names) or 'none'})")
    bucket = next(b for b in data["buckets"] if b["name"] == from_gap)
    if stale:
        H.warn(f"{cfg.upskill.name} is stale; re-run `{H.PROG} jobs upskill`")
    items = [(it["term"], f"wanted by {it['count']} role(s)")
             for it in [i for i in bucket["items"] if not i["noise"]][: top or None]]
    facts = F.read(cfg)
    return L.plan(cfg, slug, title, goal, origin=from_gap, seed=L.Seed(slugify(from_gap), items),
                  force=force, outlets=outlets, is_known=lambda term: F.holds(term, facts))


def planned_buckets(cfg) -> set:
    """Buckets a career topic was seeded from (topic.json `origin`). A topic's slug alone never
    claims a bucket. Damaged topics are skipped here; next and doctor report them."""
    out = set()
    for t in L.topics(cfg):
        try:
            conf = L.load_config(cfg, t)
        except NotEvaluable:
            continue
        if L.has_outlet(conf, "career") and conf.get("origin"):
            out.add(conf["origin"])
    return out


def is_planned(bucket_name, planned) -> bool:
    return bucket_name in planned


def gaps(cfg) -> int:
    try:
        data, stale = DM.load(cfg)
    except NotEvaluable as e:
        if cfg.upskill.exists():
            raise
        raise NotEvaluable(f"{e} (0 role(s) analysed, 0 demand bucket(s) measured)") from e
    if stale:
        H.warn(f"{cfg.upskill.name} is older than your roles or facts; re-run `{H.PROG} jobs upskill`")
    planned = planned_buckets(cfg)
    n_roles = data.get("roles_analyzed", 0)
    if not n_roles:
        print(f"NOT EVALUABLE gaps: 0 role(s) analysed in {cfg.upskill.name}, so no demand has been measured; "
              f"check a role (`{H.PROG} jobs check SLUG`) and re-run `{H.PROG} jobs upskill`")
        return NOT_EVALUABLE
    print(f"gaps: {len(data['buckets'])} demand bucket(s) from {n_roles} role(s)")
    for b in data["buckets"]:
        mark = "planned" if is_planned(b["name"], planned) else ""
        print(f"{b['demand']:7.2f}  {b['name']}  {mark}")
        for it in b["items"][:6]:
            print(f"           {it['term']} ({it['demand']}, {it['count']} role(s))" + (" ignored" if it["noise"] else ""))
    top = next((b for b in data["buckets"] if b["demand"] > 0 and not is_planned(b["name"], planned)
                and b["name"] != DM.ACRONYM_BUCKET), None)
    if top:
        print(f"suggest: {H.PROG} plan {slugify(top['name'])} --from-gap \"{top['name']}\"")
    return OK
