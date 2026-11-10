"""The daily digest: every [sources] board read once, each posting sorted into a bucket by the
kind of role, its level, where it is and your [wants], newest first.

Applying early matters, so the digest leads with what is NEW since the last one and says how
old each posting is. Buckets, from your [digest] settings:

  apply first   a preferred family, not senior, in a place you said yes to, [wants] not failed
  stretch       a preferred family at a senior (not management) level, in a place you said yes to
  worth a look  any other family you listed, in a place you said yes to; or a preferred family
                elsewhere in the US, which you would have to move for
  set aside     a [wants] filter failed; a management title (director, manager, head of, VP,
                chief); a posting outside the US; or neither family nor place fits (counted by
                reason, never listed one by one)

A posting whose title matches no family, or holds one of your `exclude` words ("product
manager", "sales"), is outside your search and is only counted. A board
that did not answer, or answered with a partial listing, is named at the top: an unreachable
board is never "no new jobs".

The digest is a file (HOME/digests/<date>.md); `digests/seen.json` records the day each
posting was first listed, which is what "new" means.
"""
from __future__ import annotations

import datetime as _dt
import json
import re

from ..core import home as H
from ..core.errors import NOT_EVALUABLE, OK, NotEvaluable
from . import sources as S
from . import wants as W

BUCKETS = ("apply first", "stretch", "worth a look", "set aside")


def parse(table: dict, error) -> dict:
    """The [digest] table, checked."""
    known = {"families", "near", "search", "exclude", "fresh_days"}
    extra = set(table) - known
    if extra:
        raise error(f"config: unknown [digest] key(s) {', '.join(sorted(extra))} (known: {', '.join(sorted(known))})")
    fams = []
    for i, f in enumerate(table.get("families") or []):
        if not isinstance(f, dict) or not isinstance(f.get("name"), str) or not f["name"].strip():
            raise error(f"config: `digest.families[{i}]` needs a `name`")
        match = f.get("match")
        if not isinstance(match, list) or not match or not all(isinstance(m, str) and m.strip() for m in match):
            raise error(f"config: `digest.families[{i}]` needs `match`, a list of words a title contains")
        if not isinstance(f.get("prefer", False), bool):
            raise error(f"config: `digest.families[{i}].prefer` must be true or false")
        fams.append({"name": f["name"].strip(), "match": [m.strip().lower() for m in match],
                     "prefer": f.get("prefer", False)})
    out = {"families": fams}
    for key in ("near", "search", "exclude"):
        v = table.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x.strip() for x in v):
            raise error(f"config: `digest.{key}` must be a list of words")
        out[key] = [x.strip().lower() for x in v]
    fd = table.get("fresh_days", 14)
    if isinstance(fd, bool) or not isinstance(fd, int) or fd < 1:
        raise error("config: `digest.fresh_days` must be a whole number of days, at least 1")
    out["fresh_days"] = fd
    return out


def _has(low: str, words) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", low) for w in words)


def family(title: str, families: list, exclude=()):
    """The first family one of whose words the title contains (whole words), or None; None too
    when the title holds an `exclude` word."""
    low = (title or "").lower()
    if _has(low, exclude):
        return None
    for f in families:
        if _has(low, f["match"]):
            return f
    return None


MANAGEMENT_RE = re.compile(r"\b(?:director|manager|mgr|head of|vp|vice president|chief)\b", re.IGNORECASE)


_REMOTE_WORDS = re.compile(r"\b(?:remote|anywhere|work from home|wfh|virtual|telecommute)\b|[-–,/()|;]", re.I)


def place(p: dict, near: list) -> tuple:
    """(fits, label, in_us). A remote posting fits when its location says US or says nothing
    but remote; one naming somewhere else does not. A non-remote posting fits when its location
    holds one of your `near` words. in_us: True, False, or None when the location does not say."""
    meta = {"location": p.get("location"), "role": p.get("title")}
    wp = p.get("workplace") or W.workplace_from_text(meta)[0] or ""
    loc = (p.get("location") or "").strip()
    if "remote" in wp:
        if W._us_evidence(meta):
            return True, f"remote, US ({loc})" if loc else "remote, US", True
        if not _REMOTE_WORDS.sub(" ", loc).strip():
            return True, "remote (country not stated)", None
        return False, f"remote, outside the US? ({loc})", False
    low = loc.lower()
    if any(n in low for n in near):
        return True, f"{wp or 'on site or hybrid'}, near ({loc})", True
    if not loc:
        return False, "location not stated", None
    return False, loc, W._us_evidence(meta)


def pay_label(cfg, p: dict) -> tuple:
    """(verdict from [wants] 'keep'|'flag'|'exclude', why, pay shown)."""
    meta = {"role": p.get("title"), "location": p.get("location"), "workplace": p.get("workplace"),
            "pay": p.get("pay"), "board_benefits": p.get("board_benefits")}
    verdict, why = ("keep", "")
    if getattr(cfg, "wants", None):
        verdict, why = W.decide(cfg, W.evaluate(cfg, meta, p.get("jd") or ""))
    pay = p.get("pay") or W.pay_from_text(p.get("jd") or "", (cfg.wants or {}).get("pay_currency"))
    if not pay:
        return verdict, why, "not stated"
    per = W.PER_YEAR.get(pay["interval"], 1)
    lo, hi = pay["min"] * per, pay["max"] * per
    shown = f"{W._money(lo, pay['currency'])}-{W._money(hi, pay['currency'])}"
    return verdict, why, shown + (" (hourly)" if pay["interval"] == "hour" else "")


def bucket(cfg, p: dict, settings: dict) -> dict | None:
    """The posting's row, or None when its title is outside every family."""
    fam = family(p.get("title"), settings["families"], settings.get("exclude", ()))
    if fam is None:
        return None
    senior = S.is_senior(p.get("title"))
    fits, where, in_us = place(p, settings["near"])
    verdict, why, pay = pay_label(cfg, p)
    if verdict == "exclude":
        b, reason = "set aside", why
    elif MANAGEMENT_RE.search(p.get("title") or ""):
        b, reason = "set aside", "a management role"
    elif not fits and in_us is False:
        b, reason = "set aside", "outside the US"
    elif fam["prefer"] and fits and not senior:
        b, reason = "apply first", ""
    elif fam["prefer"] and fits:
        b, reason = "stretch", ""
    elif fits or fam["prefer"]:
        b, reason = "worth a look", "" if fits else "you would have to move"
    else:
        b, reason = "set aside", "not a preferred family, and not in a place you said yes to"
    return {"bucket": b, "reason": reason, "family": fam["name"], "senior": senior, "where": where,
            "pay": pay, "flag": why if verdict == "flag" else "", "title": p.get("title") or "",
            "org": p.get("org"), "board": p.get("board"), "ext_id": p.get("ext_id") or "",
            "url": p.get("url") or "", "posted": p.get("posted")}


def _age(posted, today) -> str:
    if not posted:
        return "date not stated"
    days = (today - _dt.date.fromisoformat(posted)).days
    return "today" if days <= 0 else f"{days}d"


def render(rows: list, report: dict, today, settings: dict) -> str:
    fresh = settings["fresh_days"]
    out = [f"# Job digest {today.isoformat()}", ""]
    reached = report["reached"]
    out.append(f"Boards: {reached} of {report['boards']} reached.")
    for e in report["errors"]:
        out.append(f"- NOT REACHED: {e} (its postings are missing from this digest)")
    for e in report["partial"]:
        out.append(f"- PARTIAL: {e}")
    new = sum(1 for r in rows if r["new"])
    out += ["", f"{len(rows)} posting(s) in your families, {new} new since the last digest; "
                f"{report['outside']} outside them (not listed).", ""]
    for b in BUCKETS[:-1]:
        mine = [r for r in rows if r["bucket"] == b]
        listed = mine if b == "apply first" else [r for r in mine if r["new"] or _fresh(r, today, fresh)]
        listed.sort(key=lambda r: (not r["new"], r["posted"] is None,
                                   -_dt.date.fromisoformat(r["posted"]).toordinal() if r["posted"] else 0,
                                   r["org"] or "", r["title"]))
        hidden = len(mine) - len(listed)
        out.append(f"## {b.capitalize()} ({len(mine)}, {sum(r['new'] for r in mine)} new)")
        out.append("")
        if not listed:
            out.append("None." if not mine else f"None new or posted in the last {fresh} days ({hidden} older).")
            out.append("")
            continue
        out.append("| | Posted | Company | Role | Where | Pay |")
        out.append("|---|---|---|---|---|---|")
        for r in listed:
            role = f"[{r['title']}]({r['url']})" if r["url"] else r["title"]
            note = f" ({r['reason']})" if r["reason"] else ""
            flag = f" FLAG: {r['flag']}" if r["flag"] else ""
            out.append(f"| {'NEW' if r['new'] else ''} | {_age(r['posted'], today)} | {r['org']} | {role} | "
                       f"{r['where']}{note} | {r['pay']}{flag} |".replace("\n", " "))
        if hidden:
            out.append("")
            out.append(f"{hidden} more, older than {fresh} days and not new.")
        out.append("")
    aside = [r for r in rows if r["bucket"] == "set aside"]
    out.append(f"## Set aside ({len(aside)})")
    out.append("")
    reasons: dict = {}
    for r in aside:
        why = re.sub(r"\s*\((?:posting text|board field)[^)]*\)", "", r["reason"])   # group across postings
        reasons[why] = reasons.get(why, 0) + 1
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        out.append(f"- {n}: {why}")
    if not aside:
        out.append("None.")
    return "\n".join(out) + "\n"


def _fresh(r, today, fresh_days) -> bool:
    return bool(r["posted"]) and (today - _dt.date.fromisoformat(r["posted"])).days <= fresh_days


def run(cfg, settings: dict, today=None, write: bool = True, progress: bool = False) -> tuple:
    """Read every target, bucket every posting. Returns (rows, report, exit code)."""
    if not settings.get("families"):
        raise NotEvaluable("no [digest] families in config.toml: the digest has nothing to sort by")
    if not cfg.targets:
        raise NotEvaluable("no [sources] targets in config.toml: no board to read")
    today = today or H.today()
    seen_path = cfg.home / "digests" / "seen.json"
    try:
        seen = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.is_file() else {}
    except (OSError, ValueError) as e:
        raise NotEvaluable(f"{seen_path} could not be read ({e}): 'new' cannot be told from 'seen'") from e
    report = {"boards": len(cfg.targets), "reached": 0, "errors": [], "partial": [], "outside": 0}
    rows, keys = [], set()
    for t in cfg.targets:
        # Workday is searched server side, once per search word; the others list everything
        words = (settings["search"] or [""]) if t["board"] == "workday" else [None]
        reached = False
        for w in words:
            label = f"{t['board']}:{t['org']}" + (f" ({w!r})" if w else "")
            if progress:
                H.warn(f"reading {label} ...")
            res = S.fetch(t["board"], t["org"], cfg, keyword=w or None, target=t,
                          detail_for=lambda title: family(title, settings["families"],
                                                          settings.get("exclude", ())) is not None)
            if res.status == "error":
                report["errors"].append(f"{label}: {res.error}")
                continue
            reached = True
            if not res.complete:
                report["partial"].append(f"{label}: {len(res.postings)} of {res.total} matches read")
            for p in res.postings:
                key = f"{p['board']}:{p['org']}:{p['ext_id'] or p['title']}"
                if key in keys:
                    continue
                keys.add(key)
                row = bucket(cfg, p, settings)
                if row is None:
                    report["outside"] += 1
                    continue
                row["key"] = key
                row["new"] = key not in seen
                rows.append(row)
        report["reached"] += reached
    if write:
        for r in rows:
            seen.setdefault(r["key"], today.isoformat())
        d = cfg.home / "digests"
        d.mkdir(parents=True, exist_ok=True)
        H.write_text(d / f"{today.isoformat()}.md", render(rows, report, today, settings))
        H.write_text(seen_path, json.dumps(seen, indent=1, sort_keys=True) + "\n")
    code = OK if not report["errors"] else NOT_EVALUABLE
    return rows, report, code
