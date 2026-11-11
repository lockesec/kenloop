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

The digest knows the roles you already track (HOME/roles/). A posting that is a tracked role
shows that role's status: one you applied to, are interviewing for, passed on or closed leaves
the tables for one line under "Already tracked"; one still in your work queue stays, marked
"tracked". The top of the digest is the few best NEW postings to apply to first, and a
follow-ups section lists the roles you applied to 7, 14 and 30 days ago.

The digest is a file (HOME/digests/<date>.md); `digests/seen.json` records the day each
posting was first listed, which is what "new" means.
"""
from __future__ import annotations

import datetime as _dt
import json
import re

from ..core import home as H
from ..core.errors import NOT_EVALUABLE, OK, NotEvaluable
from . import roles as R
from . import sources as S
from . import wants as W

BUCKETS = ("apply first", "stretch", "worth a look", "set aside")
TOP_PICKS = 5                    # new apply-first rows shown at the top; the rest are counted
FOLLOW_UP_DAYS = (7, 14, 30)     # portal check, short note, suggest closing as no_response


def parse(table: dict, error) -> dict:
    """The [digest] table, checked."""
    known = {"families", "near", "search", "exclude", "fresh_days", "place_order"}
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
    for key in ("near", "search", "exclude", "place_order"):
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


def place_rank(where: str, location, order: list) -> int:
    """Where the posting sits in your `place_order` (0 is best); len(order) when it names none.
    The word "remote" stands for a remote posting; any other word is looked for in the location
    of a posting that is not remote."""
    remote = (where or "").startswith("remote")
    low = (location or "").lower()
    for i, w in enumerate(order):
        if (w == "remote" and remote) or (w != "remote" and not remote and w in low):
            return i
    return len(order)


def _norm_url(u) -> str:
    """A posting URL reduced to what names the posting: no scheme, www, query, fragment,
    Workday locale segment or trailing slash."""
    u = re.sub(r"[?#].*$", "", (u or "").strip().lower())
    u = re.sub(r"^https?://(?:www\.)?", "", u)
    return re.sub(r"/[a-z]{2}-[a-z]{2}(?=/)", "", u).rstrip("/")


def _squash(s) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _same_org(meta: dict, row: dict) -> bool:
    """A job id is only unique inside one company, so an id match also needs the company to agree."""
    org = (row.get("org") or "").lower()
    if meta.get("org"):
        return meta["org"].lower() == org
    a, b = _squash(org), _squash(meta.get("company"))
    return bool(a) and ((bool(b) and (a in b or b in a)) or org in (meta.get("source_url") or "").lower())


def _id_match(job_id: str, ext_id: str) -> bool:
    """The record's job_id is the posting's id, or (Workday) the requisition its /job/ path ends with."""
    return bool(job_id) and bool(ext_id) and (
        job_id == ext_id or (ext_id.startswith("/job/") and ext_id.endswith("_" + job_id)))


_STATUS_RANK = {s: i for i, s in enumerate(
    ("offer", "interviewing", "applied", "rejected", "closed", "passed", "on-hold", "tailoring", "scored", "found"))}


def tracked_role(row: dict, roles: list):
    """(slug, meta) of the tracked role this posting is, or None. Matched on the normalised
    posting URL, or on the job id inside the same company. When several records match (the
    same posting tracked twice), the one furthest along wins."""
    url = _norm_url(row.get("url"))
    hits = [(slug, m) for slug, m in roles
            if (url and _norm_url(m.get("source_url")) == url)
            or (_id_match(m.get("job_id") or "", row.get("ext_id") or "") and _same_org(m, row))]
    return min(hits, key=lambda sm: _STATUS_RANK.get(sm[1].get("status"), 99)) if hits else None


def _tracked_label(t: dict) -> str:
    day = f" {t['applied'][5:]}" if t.get("applied") else ""
    if t["status"] == "applied":
        return f"already applied{day}"
    if t["status"] in ("interviewing", "offer"):
        return f"{t['status']} (applied{day})" if day else t["status"]
    if t["status"] == "closed" and t.get("reason"):
        return f"closed ({t['reason']})"
    return t["status"]


def _left_tables(r: dict) -> bool:
    """A posting you already acted on (in flight, or closed out) is not offered again."""
    return bool(r.get("tracked")) and r["tracked"]["status"] in R.IN_FLIGHT | set(R.TERMINAL)


def follow_ups(roles: list, today, listed: set) -> list:
    """Every role with status applied: days since, and whether its posting was in today's listing
    (True, or None when it was not seen: a board not read today cannot say the posting is gone)."""
    out = []
    for slug, m in roles:
        if m.get("status") != "applied":
            continue
        when = m.get("applied") or ""
        out.append({"slug": slug, "company": m.get("company") or "", "role": m.get("role") or "",
                    "applied": when, "days": (today - _dt.date.fromisoformat(when)).days if when else None,
                    "listed": True if slug in listed else None})
    return sorted(out, key=lambda f: (f["days"] is None, -(f["days"] or 0), f["slug"]))


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
            "place_rank": place_rank(where, p.get("location"), settings.get("place_order", [])),
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
    if report.get("roles_damaged"):
        out += [f"TRACKED ROLES NOT FULLY READ: {report['roles_damaged']} role record(s) are damaged, so a posting "
                "below may be one you already track (`ken jobs list` names them).", ""]
    moved = [r for r in rows if _left_tables(r) and r["bucket"] != "set aside"]
    picks = [r for r in rows if r["bucket"] == "apply first" and r["new"] and not r.get("tracked")]
    picks.sort(key=lambda r: (r.get("place_rank", 0), bool(r["flag"]), r["posted"] is None,
                              -_dt.date.fromisoformat(r["posted"]).toordinal() if r["posted"] else 0,
                              r["pay"] == "not stated", r["org"] or "", r["title"]))
    out.append(f"## Start here ({len(picks)} new to apply to first)")
    out.append("")
    if not picks:
        out += ["Nothing new to apply to first today.", ""]
    else:
        out.append("| Posted | Company | Role | Where | Pay |")
        out.append("|---|---|---|---|---|")
        for r in picks[:TOP_PICKS]:
            out.append(_line(r, today, new_col=False))
        if len(picks) > TOP_PICKS:
            out += ["", f"{len(picks) - TOP_PICKS} more new under Apply first."]
        out.append("")
    for b in BUCKETS[:-1]:
        mine = [r for r in rows if r["bucket"] == b and not _left_tables(r)]
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
            out.append(_line(r, today))
        if hidden:
            out.append("")
            out.append(f"{hidden} more, older than {fresh} days and not new.")
        out.append("")
    if moved:
        out.append(f"## Already tracked ({len(moved)})")
        out.append("")
        for r in sorted(moved, key=lambda r: (_STATUS_RANK.get(r["tracked"]["status"], 99), r["org"] or "", r["title"])):
            out.append(f"- {r['org']}: {r['title']}: {_tracked_label(r['tracked'])} (`{r['tracked']['slug']}`)")
        out.append("")
    out += _follow_up_lines(report.get("followups") or [])
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


def _line(r: dict, today, new_col: bool = True) -> str:
    role = f"[{r['title']}]({r['url']})" if r["url"] else r["title"]
    if r.get("tracked"):
        role += f" (tracked: {r['tracked']['status']})"
    note = f" ({r['reason']})" if r["reason"] else ""
    flag = f" FLAG: {r['flag']}" if r["flag"] else ""
    first = f"| {'NEW' if r['new'] else ''} " if new_col else ""
    return (f"{first}| {_age(r['posted'], today)} | {r['org']} | {role} | "
            f"{r['where']}{note} | {r['pay']}{flag} |").replace("\n", " ")


def _follow_up_lines(ups: list) -> list:
    """The follow-ups section: nothing when no role is in status applied."""
    if not ups:
        return []
    week, note, close = FOLLOW_UP_DAYS
    out = [f"## Follow-ups ({len(ups)} applied)", ""]
    quiet = 0
    for f in ups:
        name = f"{f['company']}: {f['role']} (`{f['slug']}`)"
        up = " It was in today's listing." if f["listed"] else ""
        if f["days"] is None:
            out.append(f"- {name}: the applied date is not recorded, so there is no day count.")
        elif f["days"] >= close:
            out.append(f"- {name}: day {f['days']}. If no reply has come: "
                       f"`ken jobs status {f['slug']} closed --reason no_response`.{up}")
        elif f["days"] >= note:
            out.append(f"- {name}: day {f['days']}. Send a short note if you have a recruiter contact.{up}")
        elif f["days"] >= week:
            out.append(f"- {name}: day {f['days']}. Check the portal, and that the posting is still up.{up}")
        else:
            quiet += 1
    if quiet:
        out.append(f"- {quiet} applied in the last {week} days: nothing due yet.")
    out.append("")
    return out


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
    roles, damaged = R.scan(cfg)
    report["roles_damaged"] = len(damaged)
    listed: set = set()
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
                hit = tracked_role(row, roles)
                if hit:
                    listed.add(hit[0])
                    row["tracked"] = {"slug": hit[0], "status": hit[1].get("status"),
                                      "applied": hit[1].get("applied") or "",
                                      "reason": (hit[1].get("outcome") or {}).get("closed_reason") or ""}
                rows.append(row)
        report["reached"] += reached
    report["followups"] = follow_ups(roles, today, listed)
    if write:
        for r in rows:
            seen.setdefault(r["key"], today.isoformat())
        d = cfg.home / "digests"
        d.mkdir(parents=True, exist_ok=True)
        H.write_text(d / f"{today.isoformat()}.md", render(rows, report, today, settings))
        H.write_text(seen_path, json.dumps(seen, indent=1, sort_keys=True) + "\n")
    code = OK if not report["errors"] else NOT_EVALUABLE
    return rows, report, code
