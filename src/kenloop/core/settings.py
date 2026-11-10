"""Settings: how you study a topic, shown in one place and set through one verb.

A topic's `intent` (understand it, or learn what an exam needs to pass) and `depth` (where teaching
starts: exam, mechanism or first-principles) live in topic.json; one syllabus line may override
either with `:: intent:` / `:: depth:` (AI-901: understand the concepts, pass the Azure service
details). A chosen start rung is set with `place --start`. Nothing here is evidence: settings steer
what is taught and suggested, never what is credited.
"""
from __future__ import annotations

from . import home as H
from . import learn as L
from .errors import OK, UsageError


def migrate(cfg, slug, check=False) -> int:
    """Rename a topic.json's old setting names (exam_date -> deadline, passed -> complete)."""
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    done = L.migrate_keys(conf)
    if not done:
        print(f"{slug}: settings already use the current names")
        return OK
    what = ", ".join(f"{o} -> {n}" for o, n in done)
    if check:
        print(f"{slug}: would rename {what} (nothing written; run without --check to rename)")
        return OK
    L.save_config(cfg, slug, conf)
    print(f"{slug}: renamed {what}")
    return OK


def settings(cfg, slug, intent=None, depth=None, clear=(), keep_studying=None) -> int:
    L.need_topic(cfg, slug)
    conf = L.load_config(cfg, slug)
    if keep_studying is not None:
        if keep_studying == "on":
            conf["keep_studying"] = True
            if not L.get_key(conf, "complete"):
                print(f"{slug}: keep studying is set; it takes effect once the exam is passed "
                      "(until then the topic is on the schedule anyway)")
        else:
            conf.pop("keep_studying", None)
    for k in clear:
        if k not in L.CHOICES:
            raise UsageError(f"--clear takes {' or '.join(L.CHOICES)}")
        conf.pop(k, None)
    for k, v in (("intent", intent), ("depth", depth)):
        if v is not None:
            if v not in L.CHOICES[k]:
                raise UsageError(f"--{k} must be one of {', '.join(L.CHOICES[k])}")
            conf[k] = v
    if intent is not None or depth is not None or clear or keep_studying is not None:
        L.save_config(cfg, slug, conf)
    cons = L.load_state(cfg, slug)["concepts"]
    print(f"settings: {conf.get('title', slug)} ({slug})")
    print(f"  lane: {L.lane_of(cfg, slug)}"
          + (f"; complete (exam passed {L.get_key(conf, 'complete')})" if L.get_key(conf, "complete") else "")
          + ((", still studied (--keep-studying on)" if conf.get("keep_studying") is True
              else ", off the schedule (`--keep-studying on` keeps it)") if L.get_key(conf, "complete") else "")
          + (f"; deadline {L.get_key(conf, 'deadline')}" if L.get_key(conf, "deadline") and not L.get_key(conf, "complete") else ""))
    from . import onramp as O
    for k in L.CHOICES:
        eff = [{**c, k: O.concept_setting(cfg, slug, c, k)} for c in cons.values()]
        over = [c for c in eff if c.get(k) and c.get(k) != conf.get(k)]
        print(f"  {k}: {conf.get(k) or 'not set'}"
              + (f"; {len(over)} concept(s) differ by their line or rung ({_summary(over, k)})" if over else ""))
    start = conf.get("start")
    print(f"  start: rung {start} by choice (no placement probes)" if isinstance(start, int)
          else "  start: from placement (`place SLUG --start N` to choose)")
    if not (intent or depth or clear) and not any(conf.get(k) for k in L.CHOICES):
        print(f"  set with `{H.PROG} settings {slug} --intent understand|pass --depth exam|mechanism|first-principles`;"
              " one syllabus line overrides with `:: intent:pass` / `:: depth:exam`")
    return OK


def doctor(cfg) -> list:
    """A keep_studying that is not true or false is reported: it would silently read as off."""
    out = []
    for t in L.topics(cfg):
        try:
            v = L.load_config(cfg, t).get("keep_studying")
        except Exception:                 # a damaged topic.json is the integrity rule's finding, not this one
            continue
        if v is not None and not isinstance(v, bool):
            out.append(("FINDING", f"{t}/topic.json: keep_studying is {v!r}, read as off; "
                                   f"`{H.PROG} settings {t} --keep-studying on|off` writes it"))
    return out


def _summary(cons: list, key: str) -> str:
    vals: dict = {}
    for c in cons:
        vals[c[key]] = vals.get(c[key], 0) + 1
    return ", ".join(f"{n} {v}" for v, n in sorted(vals.items()))


def commands(groups) -> None:
    a = groups[""].add_parser("settings", help="how you study a topic: intent (understand|pass) and depth "
                                               "(exam|mechanism|first-principles); alone, shows every setting")
    a.add_argument("slug")
    a.add_argument("--intent", choices=L.INTENTS)
    a.add_argument("--depth", choices=L.DEPTHS)
    a.add_argument("--clear", choices=tuple(L.CHOICES), action="append", default=[], help="unset one")
    a.add_argument("--migrate", action="store_true", help="rename old setting names (exam_date -> deadline, "
                                                          "passed -> complete) in this topic.json")
    a.add_argument("--check", action="store_true", help="with --migrate: say what would change, write nothing")
    a.add_argument("--keep-studying", choices=("on", "off"), help="a passed topic stays on the schedule: the exam "
                                                                    "is done, the material is not")
    a.set_defaults(run=lambda cfg, ns: migrate(cfg, ns.slug, ns.check) if ns.migrate
                   else settings(cfg, ns.slug, ns.intent, ns.depth, ns.clear, ns.keep_studying))
