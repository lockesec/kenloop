"""Career settings: the [ats], [gap], [demand], [next], [sources], [profile], [wants], [digest]
and [headings] sections of config.toml, on top of the core config.

`load` is what the shell calls: a CareerConfig is a core Config, so the core reads it
without knowing these fields exist.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core import home as H
from ..core.errors import NotEvaluable
from ..core.names import safe_name
from . import sections as _sections
from . import wants as _wants

DEFAULT_STATUS_WEIGHTS = {
    "found": 1.0, "scored": 1.0, "tailoring": 1.0, "applied": 1.0,
    "interviewing": 1.0, "offer": 0.5, "on-hold": 0.5,
    "rejected": 0.25, "rejected-after-interview": 0.5, "passed": 0.0, "closed": 0.0,
}


@dataclass
class Bucket:
    name: str
    match: list
    action: str = ""
    held_ref: str = ""


@dataclass
class CareerConfig(H.Config):
    packs: list = field(default_factory=list)
    user_lexicon: str = ""
    do_not_claim: set = field(default_factory=set)
    equivalence: dict = field(default_factory=dict)
    ignore: set = field(default_factory=set)
    buckets: list = field(default_factory=list)
    half_life_days: float = 60.0
    probe_bonus: float = 2.0
    status_weights: dict = field(default_factory=lambda: dict(DEFAULT_STATUS_WEIGHTS))
    bar: float = 4.0
    deadline_days: int = 3
    min_bucket_demand: float = 2.0
    targets: list = field(default_factory=list)
    profile: dict = field(default_factory=dict)
    wants: dict = field(default_factory=dict)
    headings: dict = field(default_factory=dict)
    org_aliases: dict = field(default_factory=dict)
    digest: dict = field(default_factory=lambda: {"families": [], "near": [], "search": [], "exclude": [],
                                                           "fresh_days": 14})

    @property
    def facts(self) -> Path:
        return self.home / "facts.md"

    @property
    def roles(self) -> Path:
        return self.home / "roles"

    @property
    def upskill(self) -> Path:
        return self.home / "upskill.json"


def _num(v, key, lo=0.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < lo:
        raise NotEvaluable(f"config: `{key}` must be a number >= {lo}")
    return float(v)


def _int(v, key, lo=0):
    if isinstance(v, bool) or not isinstance(v, int) or v < lo:
        raise NotEvaluable(f"config: `{key}` must be a whole number >= {lo}")
    return v


def _strs(v, key):
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise NotEvaluable(f"config: `{key}` must be a list of strings")
    return v


def _table(raw, key):
    v = raw.get(key, {})
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise NotEvaluable(f"config: `{key}` must be a table ([{key}])")
    return v


def _list(v, key):
    if v is None:
        return []
    if not isinstance(v, list):
        raise NotEvaluable(f"config: `{key}` must be a list")
    return v


def load(home: Path, how: str = "") -> CareerConfig:
    """The core config of an initialised home, with the career sections read and checked.
    A malformed section is NOT EVALUABLE and names the key."""
    base = H.load_config(home, how)
    cfg = CareerConfig(home=base.home, raw=base.raw)
    raw = base.raw
    ats = _table(raw, "ats")
    cfg.packs = [safe_name(n, "config: ats.packs entry", NotEvaluable) for n in _strs(ats.get("packs"), "ats.packs")]
    ul = ats.get("user_lexicon", "") or ""
    if not isinstance(ul, str):
        raise NotEvaluable("config: `ats.user_lexicon` must be a path string")
    cfg.user_lexicon = ul
    cfg.do_not_claim = {s.lower() for s in _strs(ats.get("do_not_claim"), "ats.do_not_claim")}
    eq = _table(ats, "equivalence")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in eq.items()):
        raise NotEvaluable("config: `ats.equivalence` must map strings to strings")
    cfg.equivalence = {k.lower(): v.lower() for k, v in eq.items()}
    gap = _table(raw, "gap")
    cfg.ignore = {s.lower() for s in _strs(gap.get("ignore"), "gap.ignore")}
    for i, b in enumerate(_list(gap.get("bucket"), "gap.bucket")):
        if not isinstance(b, dict) or not isinstance(b.get("name"), str) or not b.get("name"):
            raise NotEvaluable(f"config: `gap.bucket[{i}]` needs a `name`")
        cfg.buckets.append(Bucket(name=b["name"], match=[m.lower() for m in _strs(b.get("match"), f"gap.bucket[{i}].match")],
                                  action=str(b.get("action", "") or ""), held_ref=str(b.get("held_ref", "") or "")))
    dm = _table(raw, "demand")
    if "half_life_days" in dm:
        cfg.half_life_days = _num(dm["half_life_days"], "demand.half_life_days", 1.0)
    if "probe_bonus" in dm:
        cfg.probe_bonus = _num(dm["probe_bonus"], "demand.probe_bonus")
    for k, v in _table(dm, "status_weights").items():
        cfg.status_weights[str(k)] = _num(v, f"demand.status_weights.{k}")
    nx = _table(raw, "next")
    if "bar" in nx:
        cfg.bar = _num(nx["bar"], "next.bar")
    if "deadline_days" in nx:
        cfg.deadline_days = _int(nx["deadline_days"], "next.deadline_days")
    if "min_bucket_demand" in nx:
        cfg.min_bucket_demand = _num(nx["min_bucket_demand"], "next.min_bucket_demand")
    src = _table(raw, "sources")
    for i, t in enumerate(_list(src.get("targets"), "sources.targets")):
        if not isinstance(t, dict) or not isinstance(t.get("board"), str) or not isinstance(t.get("org"), str):
            raise NotEvaluable(f"config: `sources.targets[{i}]` needs string `board` and `org`")
        tgt = {"board": t["board"], "org": safe_name(t["org"], f"config: sources.targets[{i}].org", NotEvaluable),
               "note": str(t.get("note", ""))}
        if t["board"] == "workday":
            from .sources import WORKDAY_HOST, WORKDAY_SITE
            host, site = t.get("host"), t.get("site")
            if not isinstance(host, str) or not WORKDAY_HOST.match(host):
                raise NotEvaluable(f"config: `sources.targets[{i}]` (workday) needs `host` like "
                                   "\"acme.wd1.myworkdayjobs.com\"")
            if not isinstance(site, str) or not WORKDAY_SITE.match(site):
                raise NotEvaluable(f"config: `sources.targets[{i}]` (workday) needs `site`, the career site's "
                                   "name in its URL (e.g. \"External\")")
            tgt.update(host=host, site=site)
        cfg.targets.append(tgt)
    al = src.get("aliases", {}) or {}
    if not isinstance(al, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in al.items()):
        raise NotEvaluable("config: `sources.aliases` must map a board org name to the company it is")
    cfg.org_aliases = {k.strip().lower(): v.strip().lower() for k, v in al.items()}
    prof = _table(raw, "profile")
    cfg.profile = {k: str(v) for k, v in prof.items()}
    cfg.wants = _wants.parse(_table(raw, "wants"), NotEvaluable)
    from . import digest as _digest
    cfg.digest = _digest.parse(_table(raw, "digest"), NotEvaluable)
    allowed = [k for k in _sections.KINDS if k != "none"]
    for k, v in _table(raw, "headings").items():
        if v not in allowed:
            raise NotEvaluable(f"config: [headings] {k!r} = {v!r}: the type must be one of {', '.join(allowed)}")
        cfg.headings[_sections.norm_key(str(k))] = v
    return cfg
