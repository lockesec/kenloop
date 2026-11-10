"""Focus: what `next` points at, set by you or left to the rules.

`ken focus black-holes` pins `next` to one topic until you pivot (`ken focus blockchain`), point it
at a lane (`ken focus interest`), or hand it back to the rules (`ken focus auto`). `ken next` with
no arguments then answers inside your focus; `ken next career` or `ken next --topic X` still asks
about somewhere else for one call without moving the focus.

Every change is a row in focus.jsonl, so the record shows when you pivoted and why. The last row
wins; no rows means auto. A focus on a topic that no longer exists is said out loud and read as
auto, never silently followed.
"""
from __future__ import annotations

from . import home as H
from . import learn as L
from . import ledger as LG
from .errors import OK

LEDGER = "focus.jsonl"
LANES = ("career", "interest")
AUTO = "auto"


def _path(cfg):
    return cfg.home / LEDGER


def _check(row) -> None:
    if not isinstance(row.get("focus"), str) or not row["focus"]:
        raise ValueError("a focus row needs a focus")


def history(cfg) -> list:
    return LG.read(_path(cfg), _check)[0]


def current(cfg) -> dict:
    """{"focus": auto|career|interest|<slug>, "since": date or None, "why": str, "gone": bool}."""
    rows = history(cfg)
    if not rows:
        return {"focus": AUTO, "since": None, "why": "", "gone": False}
    last = rows[-1]
    f = last["focus"]
    gone = f not in (AUTO, *LANES) and f not in L.topics(cfg)
    return {"focus": f, "since": last.get("date"), "why": last.get("why", ""), "gone": gone}


def resolve(cfg, lane=None, topic=None) -> tuple:
    """(lane, topic, label) for `next`: explicit arguments win; otherwise the focus. label is the
    line `next` prints about the focus, or "" when the arguments overrode it or it is auto."""
    if lane is not None or topic is not None:
        return lane, topic, ""
    cur = current(cfg)
    f = cur["focus"]
    if cur["gone"]:
        H.warn(f"focus {f!r} names no topic any more; reading it as auto (`{H.PROG} focus auto` to clear)")
        return None, None, ""
    if f == AUTO:
        return None, None, ""
    label = f"focus: {f}" + (f" since {cur['since']}" if cur["since"] else "") + \
            f"; `{H.PROG} focus auto` hands next back to the rules"
    return (f, None, label) if f in LANES else (None, f, label)


def focus(cfg, target=None, why="") -> int:
    if target is None:
        cur = current(cfg)
        if cur["focus"] == AUTO:
            print(f"focus: auto (the rules pick across every topic); `{H.PROG} focus TOPIC|career|interest` to pin it")
        else:
            print(f"focus: {cur['focus']}" + (f" since {cur['since']}" if cur["since"] else "")
                  + (f" ({cur['why']})" if cur["why"] else "")
                  + (" — that topic no longer exists, so next reads auto" if cur["gone"] else ""))
        return OK
    if target not in (AUTO, *LANES):
        L.need_topic(cfg, target)
    if current(cfg)["focus"] == target:
        print(f"focus is already {target}")
        return OK
    LG.append(_path(cfg), {"date": H.today().isoformat(), "focus": target, "why": why.strip()}, _check)
    print(f"focus: {target}" + ("; next picks across every topic again" if target == AUTO
                                 else f"; `{H.PROG} next` now answers inside it"))
    return OK


def doctor(cfg) -> list:
    """A focus on a topic that no longer exists reads as auto; say so until it is cleared."""
    cur = current(cfg)
    if cur["gone"]:
        return [("FINDING", f"focus {cur['focus']!r} names no topic any more, so next reads auto; "
                            f"`{H.PROG} focus auto` or pin another topic")]
    return []


def commands(groups) -> None:
    a = groups[""].add_parser("focus", help="pin what `next` points at: a topic, a lane (career|interest), "
                                            "or auto; alone, shows it")
    a.add_argument("target", nargs="?", help="a topic slug, career, interest, or auto")
    a.add_argument("--why", default="", help="why you are pivoting (kept in focus.jsonl)")
    a.set_defaults(run=lambda cfg, ns: focus(cfg, ns.target, ns.why))
