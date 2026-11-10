"""Scouting: predicted branches, stored ahead of study and scored when decided (scouts.jsonl).

A tutor reads the sources and says "this concept will want this branch": `ken scout TOPIC CONCEPT
"DOMAIN :: NAME :: DESC" --why "..."`. A scout stays dormant until you study the concept it hangs
off; then it is offered like the tool's own offers (`ken branch`, `ken session`, `ken talk`), and
deciding it cites `--source scout:N`. That makes scouting scoreable: precision (scouts you took, of
the scouts you decided) and recall (branches you kept that a scout had predicted, of every branch
kept since scouting began).

A plug-in module: it reaches the core only through the offers seam (`branches.register_provider`),
the commands seam and the doctor seam. Removing it from MODULES removes its verb, offers, keys and
report lines; nothing else changes.
"""
from __future__ import annotations

from .core import branches as B
from .core import home as H
from .core import learn as L
from .core import ledger as LG
from .core.errors import OK, NotEvaluable, UsageError

LEDGER = "scouts.jsonl"

SCOUT_KINDS = ("piece", "before", "topic")


def scouts_path(cfg):
    return cfg.home / LEDGER


def _check_scout(r) -> None:
    H.iso_date(r["date"])
    if not (isinstance(r.get("id"), int) and r.get("kind") in SCOUT_KINDS
            and all(isinstance(r.get(k), str) and r[k].strip() for k in ("topic", "concept", "line", "why"))):
        raise ValueError("a scout needs id, topic, concept, line, kind and why")


def read_scouts(cfg) -> tuple:
    """(scouts, problems): every scouted offer, decided or not."""
    return LG.read(scouts_path(cfg), _check_scout)


def scout(cfg, topic, concept, line, kind, why, url="") -> dict:
    """Store an undecided, predicted branch. Nothing reaches the syllabus or `next` until it is
    offered (when the concept is studied) and decided."""
    H.one_line(line, "the scout line")
    H.one_line(why, "--why")
    have, problems = read_scouts(cfg)
    if problems:
        raise NotEvaluable(f"{len(problems)} unreadable line(s) in scouts.jsonl (first: {problems[0]}); "
                           "nothing appended past the damage")
    if not why.strip():
        raise UsageError("--why is required: what the scout predicts the learner will need, and why")
    if any(x["topic"] == topic and x["concept"] == concept and x["line"].strip() == line.strip() for x in have):
        raise UsageError("that branch is already scouted on this concept")
    rows, _p = B.read(cfg)
    row = {"id": max((x["id"] for x in have), default=0) + 1, "date": H.today().isoformat(), "topic": topic,
           "concept": concept, "line": line.strip(), "kind": kind, "why": why.strip(), "url": url,
           "after": len(rows)}      # branches.jsonl rows before this scout: recall counts only later ones
    return LG.append(scouts_path(cfg), row, _check_scout)


def _reached(c: dict) -> bool:
    return bool(c.get("attempts") or c.get("dialogues") or c.get("taught"))


def open_scouts(cfg, slug, reached_only=True) -> list:
    """Undecided scouts for one topic; by default only those whose concept you have studied."""
    decided = {r["source"] for r in B.read(cfg)[0] if r["source"].startswith("scout:")}
    cons = L.load_state(cfg, slug)["concepts"]
    return [x for x in read_scouts(cfg)[0] if x["topic"] == slug and f"scout:{x['id']}" not in decided
            and (not reached_only or _reached(cons.get(x["concept"], {})))]


def scout_score(cfg, rows, slug=None) -> dict:
    """Precision: of the scouts decided, how many were taken (declined = passed up).
    Recall: of the branches kept since scouting began (in topics with scouts), how many a scout had predicted."""
    scouts = [x for x in read_scouts(cfg)[0] if slug is None or x["topic"] == slug]
    if not scouts:
        return {"scouts": 0}
    topics = {x["topic"] for x in scouts}
    # recall counts branches made AFTER scouting began: by ledger position when the scout recorded
    # it (a date alone would count branches made earlier the same day as misses), else by date
    if all(isinstance(x.get("after"), int) for x in scouts):
        rows_after = B.read(cfg)[0][min(x["after"] for x in scouts):]
    else:
        rows_after = [r for r in B.read(cfg)[0] if r["date"] >= min(x["date"] for x in scouts)]
    decided = [r for r in rows if r["source"].startswith("scout:")]
    kept = [r for r in rows_after if r["topic"] in topics and r["as"] != "declined"]
    return {"scouts": len(scouts), "decided": len(decided),
            "taken": sum(r["as"] != "declined" for r in decided),
            "passed_up": sum(r["as"] == "declined" for r in decided),
            "kept": len(kept), "predicted": sum(r["source"].startswith("scout:") for r in kept),
            "unscouted": [r["gap"][:60] for r in kept if not r["source"].startswith("scout:")]}


class _Scouts:
    """The offer provider for `scout:N` keys."""
    prefix = "scout"

    def offers(self, cfg, slug, reached_only=True) -> list:
        return [{"source": f"scout:{x['id']}", "concept": x["concept"], "gap": x["line"],
                 "why": f"scouted {x['date']} ({x['kind']}): {x['why']}" + (f" [{x['url']}]" if x.get("url") else "")}
                for x in open_scouts(cfg, slug, reached_only)]

    def check_source(self, cfg, source, rows) -> None:
        if source not in {f"scout:{x['id']}" for x in read_scouts(cfg)[0]}:
            raise UsageError(f"{source} is not a scouted offer (`{H.PROG} branch SLUG` lists them)")
        if any(r["source"] == source for r in rows):
            raise UsageError(f"{source} is already decided")

    def report(self, cfg, rows, slug) -> list:
        sc = scout_score(cfg, rows, slug)
        if not sc["scouts"]:
            return []
        dormant = len(open_scouts(cfg, slug, reached_only=False)) - len(open_scouts(cfg, slug)) if slug else None
        out = [f"  scouting: {sc['scouts']} scouted" + (f", {dormant} dormant (concept not studied yet)" if dormant else "")
               + (f"; precision {sc['taken']}/{sc['decided']} scouts taken" if sc["decided"]
                  else "; precision: no scout decided yet")
               + (f" ({sc['passed_up']} passed up)" if sc["passed_up"] else "")
               + (f"; recall {sc['predicted']}/{sc['kept']} kept branches predicted" if sc["kept"]
                  else "; recall: no branch kept since scouting began")]
        out += [f"    missed by scouting: {g}" for g in sc["unscouted"][:5]]
        return out


B.register_provider(_Scouts())


def scout_cmd(cfg, slug, frm, line, why, url="", before=False, topic=False) -> int:
    state = L.load_state(cfg, slug)
    fid = L.resolve_concept(state, frm)
    if not line or line.count("::") < 2:
        raise UsageError('a scout is one syllabus line: "DOMAIN :: CONCEPT :: DESCRIPTION"')
    kind = "topic" if topic else "before" if before else "piece"
    x = scout(cfg, slug, fid, line, kind, why, url)
    print(f"scouted: scout:{x['id']} on {slug}/{fid} ({kind}); offered once you study {fid}")
    return OK


def doctor(cfg) -> list:
    return [("NOT EVALUABLE", f"{LEDGER}: {p}") for p in read_scouts(cfg)[1]]


def commands(groups) -> None:
    a = groups[""].add_parser("scout", help="store a predicted branch, undecided: offered once the concept is "
                                            "studied, scored when decided (--source scout:N)")
    a.add_argument("slug")
    a.add_argument("concept", help="the concept the branch hangs off")
    a.add_argument("line", help='"DOMAIN :: CONCEPT :: DESCRIPTION"')
    a.add_argument("--why", default="", help="why the learner will need it (required)")
    a.add_argument("--url", default="", help="the source the prediction rests on")
    a.add_argument("--before", action="store_true", help="learned before the concept rather than a piece of it")
    a.add_argument("--topic", action="store_true", help="a topic of its own")
    a.set_defaults(run=lambda cfg, ns: scout_cmd(cfg, ns.slug, ns.concept, ns.line, ns.why, ns.url, ns.before, ns.topic))
