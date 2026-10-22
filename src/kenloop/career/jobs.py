"""The job arm: find roles, measure your coverage of each, track outcomes.

Every verb takes the loaded Config and returns an exit code (see errors.py).
Output goes to stdout; warnings to stderr.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import tempfile

from ..core import home as H
from ..core.errors import (
    FINDINGS,
    NOT_EVALUABLE,
    OK,
    KenloopError,
    NotEvaluable,
    UsageError,
)
from . import ats
from . import demand as DM
from . import facts as F
from . import roles as R
from . import sources as S
from . import wants as W

SCORECARD = """# {company} — {role}

Score each 1-5, then record the average with `{prog} jobs score {slug} --fit N`.

| Dimension | Score | Notes |
|---|---|---|
| Role fit (the work itself) | | |
| Skill match (see coverage) | | |
| Level (not above or below you) | | |
| Pay and logistics | | |
| Legitimacy (real, funded, reachable) | | |
| Growth (moves you toward your stated goal) | | |

## Deal-breakers

## Requirements you lack (credentials, clearances, years)

## Verdict

## Angle for cover letter
"""


_write_text = H.write_text


def _date(s: str, what: str) -> str:
    if not s:
        return ""
    try:
        return H.iso_date(s).isoformat()
    except ValueError as e:
        raise UsageError(f"{what} {s!r} is not YYYY-MM-DD") from e


# --- intake / discover ------------------------------------------------------

def intake(cfg, company, role, jd=None, url="", job_id="", location="", salary="",
           status="found", applied="", deadline="", slug=None, force=False,
           board="manual", org="", workplace=None, pay=None, board_benefits=None,
           reposted_from=None) -> tuple:
    """(slug, created). Re-intake without --force changes nothing. With
    --force the posting fields are refreshed and everything else survives:
    your status, fit, history, outcome, a filled scorecard, and the stored
    posting text when no new text is given."""
    if status not in R.STATUSES:
        raise UsageError(f"unknown status {status!r} (one of {', '.join(R.STATUSES)})")
    if not (company or "").strip() or not (role or "").strip():
        raise UsageError("--company and --role must not be empty")
    if jd is not None and not ats.has_visible_text(jd):
        raise NotEvaluable("the posting is empty (no visible text once markup and invisible characters "
                           "are removed); nothing was taken in")
    slug = slug or R.role_slug(company, role)
    if not slug:
        raise UsageError("company and role give an empty slug; pass --slug")
    d = R.role_dir(cfg, slug)
    old = R.read_meta(d / "meta.json")
    if old is not None and (old.get("company"), old.get("role")) != (company, role):
        raise UsageError(f"slug {slug!r} already holds {old.get('company')!r} / {old.get('role')!r}; "
                         f"pass --slug to name this one")
    if old is not None and not force:
        return slug, False
    posting = {"company": company, "role": role, "board": board, "org": org or "",
               "job_id": job_id or "", "source_url": url or "", "location": location or "",
               "salary": salary or ""}
    if workplace:
        posting.update(workplace=workplace, workplace_source="board field")
    if pay:
        posting["pay"] = pay
    if board_benefits:
        posting["board_benefits"] = board_benefits
    if reposted_from:
        posting["reposted_from"] = reposted_from
    if jd is not None and jd.strip():
        posting["jd_sha"] = jd_sha(ats.strip_html(jd, structure=True).strip() + "\n")
    if old is None:
        meta = dict(posting, status=status, fit_score=None, found=H.today().isoformat(),
                    applied=_date(applied, "--applied"), deadline=_date(deadline, "--deadline"),
                    history=[], outcome={})
        R.history(meta, f"intake ({status})")
    else:
        meta = dict(old)
        meta.update(posting)
        if deadline:
            meta["deadline"] = _date(deadline, "--deadline")
        R.history(meta, "refreshed (--force)")
    card = SCORECARD.format(company=company, role=role, slug=slug, prog=H.PROG)
    if old is None:
        _create_role(cfg, d, ats.strip_html(jd, structure=True).strip() + "\n" if jd is not None and jd.strip() else "", card, meta)
        return slug, True
    if jd is not None and jd.strip():
        _write_text(d / "jd.txt", ats.strip_html(jd, structure=True).strip() + "\n")
    if not (d / "scorecard.md").exists():
        _write_text(d / "scorecard.md", card)
    R.save(cfg, slug, meta)
    return slug, True


def jd_sha(text: str) -> str:
    """A hash of the text with whitespace normalised (runs collapsed, lines stripped, blank lines
    and CRLF differences gone), so re-spacing a posting is not a change to it."""
    import hashlib
    lines = (re.sub(r"[ \t\u00a0\u2007\u202f]+", " ", ln).strip() for ln in (text or "").splitlines())
    return hashlib.sha256("\n".join(ln for ln in lines if ln).encode("utf-8")).hexdigest()[:16]


def _dupe_key(cfg, org: str, title: str, location: str) -> tuple:
    """The same job: one company (board org names mapped by [sources] aliases), one title, one
    location, whatever the board or the posting id."""
    o = (org or "").strip().lower()
    o = cfg.org_aliases.get(o, o)
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()  # noqa: E731
    return (o, norm(title), norm(location))


def _active(meta: dict) -> bool:
    """A role that is still live for duplicate purposes: any status but the terminal ones
    (rejected, passed, closed), and not gone from the board. `offer` and `on-hold` count."""
    return meta.get("status") not in R.TERMINAL and not meta.get("posting_gone")


def _remember(cfg, by_job: dict, org, title, location, slug, meta) -> None:
    """Index a role by its job key, keeping an active role over a closed one for the same key."""
    k = _dupe_key(cfg, org, title, location)
    if k not in by_job or (_active(meta) and not _active(by_job[k][1])):
        by_job[k] = (slug, meta)


def _create_role(cfg, d, jd_text, card, meta) -> None:
    """A new role's files are built in a temporary directory beside roles/ and renamed into place, so a
    failure part-way leaves no role directory (an empty one, or one without a meta.json). A directory
    already there without a meta.json (a leftover) is filled, meta.json last."""
    cfg.roles.mkdir(parents=True, exist_ok=True)
    tmp = H.Path(tempfile.mkdtemp(prefix=f".{d.name}.", suffix=".new", dir=cfg.roles))
    try:
        _write_text(tmp / "jd.txt", jd_text)
        _write_text(tmp / "scorecard.md", card)
        H.write_json(tmp / "meta.json", meta)
        if not d.exists():
            os.rename(tmp, d)
            return
        for name in ("jd.txt", "scorecard.md", "meta.json"):
            if name == "scorecard.md" and (d / name).exists():
                continue
            os.replace(tmp / name, d / name)
    finally:
        for f in tmp.glob("*"):                    # whatever was not moved: the directory holds files only
            f.unlink()
        if tmp.exists():
            tmp.rmdir()


def discover(cfg, board=None, org=None, all_targets=False, keyword=None, do_intake=False,
             exclude_senior=False, reconcile_after=False) -> int:
    if all_targets:
        targets = cfg.targets
        if not targets:
            raise NotEvaluable("no [sources] targets in config.toml; add one or pass --board/--company")
        if do_intake and not keyword:
            raise UsageError("--all --intake needs --keyword (it would intake every posting on every board)")
    elif board and org:
        targets = [{"board": board, "org": org}]
    else:
        raise UsageError("pass --board and --company, or --all")
    for t in targets:
        if t["board"] not in S.BOARDS:
            raise UsageError(f"unknown board {t['board']!r} (known: {', '.join(S.BOARDS)})")
    errors, empties, n_new, n_seen, n_senior, n_untitled, n_failed = [], [], 0, 0, 0, 0, 0
    n_wants = 0
    scanned, damaged = R.scan(cfg)
    existing = {(m.get("board"), m.get("org"), m.get("job_id")) for _s, m in scanned if m.get("job_id")}
    by_id = {(m.get("board"), m.get("org"), m.get("job_id")): (s, m) for s, m in scanned if m.get("job_id")}
    by_job = {}
    for s, m in scanned:
        _remember(cfg, by_job, m.get("org") or m.get("company"), m.get("role"), m.get("location"), s, m)
    n_dup, taken_here = 0, {}
    for p in damaged:
        print(f"DAMAGED {p}: not read, so a posting it holds may be listed as new")
    for t in targets:
        res = S.fetch(t["board"], t["org"], cfg, keyword)
        if res.status == "error":
            errors.append(res.error)
            print(f"ERROR   {res.error}")
            continue
        if res.status == "empty":
            empties.append(f"{t['board']}:{t['org']}")
            print(f"EMPTY   {t['board']}:{t['org']}  (the board returned no postings at all; "
                  "that is not a measurement, so nothing is concluded from it)")
            continue
        if keyword:
            print(f"        {t['board']}:{t['org']}  {len(res.postings)} of {res.total} posting(s) "
                  f"matched {keyword!r}")
        for p in res.postings:
            if not (p["title"] or "").strip():
                n_untitled += 1
                print(f"SKIPPED {p['board']}:{p['org']}  {p['ext_id'] or '-'}  the posting has no title, "
                      "so it is neither listed nor taken in")
                continue
            if exclude_senior and S.is_senior(p["title"]):
                n_senior += 1
                continue
            n_seen += 1
            known = (p["board"], p["org"], p["ext_id"]) in existing and p["ext_id"]
            mark = "known" if known else "new"
            print(f"{mark:7} {p['board']}:{p['org']}  {p['ext_id'] or '-':10} {p['title']}  [{p['location']}]")
            if known:
                _note_change(cfg, p, *by_id[(p["board"], p["org"], p["ext_id"])])
            dup = None if known else by_job.get(_dupe_key(cfg, p["org"], p["title"], p["location"]))
            if dup is not None and taken_here.get(dup[0]) == (p["board"], p["org"]):
                dup = None                  # the same listing offers two openings of one title: both are real
            reposted_from = None
            if dup is not None:
                dslug, dmeta = dup
                if _active(dmeta):
                    n_dup += 1
                    print(f"DUPLICATE {p['board']}:{p['org']}  {p['ext_id'] or '-'} {p['title']}: same company, "
                          f"title and location as {dslug}; not taken in again")
                    continue
                why = "gone from the board" if dmeta.get("posting_gone") else dmeta.get("status")
                reposted_from = dslug
                print(f"REPOSTED {p['board']}:{p['org']}  {p['ext_id'] or '-'} {p['title']}: was {dslug} ({why})")
            if p.get("sanitised"):
                print(f"NOTE    {p['board']}:{p['org']}  {p['ext_id'] or '-'}  {p['title']}: a lone surrogate in "
                      f"{', '.join(p['sanitised'])} was replaced with U+FFFD")
            if do_intake and not known and cfg.wants:
                probe = {"role": p["title"], "location": p["location"], "workplace": p.get("workplace"),
                         "pay": p.get("pay"), "board_benefits": p.get("board_benefits")}
                verdict, why = W.decide(cfg, W.evaluate(cfg, probe, p["jd"]))
                if verdict == "exclude":
                    n_wants += 1
                    print(f"EXCLUDED {p['board']}:{p['org']}  {p['ext_id'] or '-'} {p['title']}: {why} [wants]")
                    continue
                if verdict == "flag":
                    print(f"FLAG    {p['board']}:{p['org']}  {p['ext_id'] or '-'} {p['title']}: {why} [wants]")
            if do_intake and not known:
                slug = R.role_slug(p["org"], p["title"])
                if (cfg.roles / slug / "meta.json").exists() and p["ext_id"]:
                    slug = R.slugify(f"{slug}-{p['ext_id']}")   # same title, different posting
                try:
                    _date(p.get("deadline", ""), "the posting's deadline field")
                    slug, created = intake(cfg, p["org"], p["title"], slug=slug, jd=p["jd"], url=p["url"],
                                           job_id=p["ext_id"], location=p["location"],
                                           deadline=p.get("deadline", ""), board=p["board"], org=p["org"],
                                           workplace=p.get("workplace"), pay=p.get("pay"),
                                           board_benefits=p.get("board_benefits"),
                                           reposted_from=reposted_from)
                except (KenloopError, UnicodeError, OSError) as e:
                    n_failed += 1
                    print(f"SKIPPED {p['board']}:{p['org']}  {p['ext_id'] or '-'}  {p['title']}: not taken in ({e})")
                    continue
                if created:
                    n_new += 1
                    existing.add((p["board"], p["org"], p["ext_id"]))
                    _remember(cfg, by_job, p["org"], p["title"], p["location"], slug, R.load(cfg, slug))
                    taken_here[slug] = (p["board"], p["org"])
    print(f"{n_seen} posting(s) listed" + (f", {n_new} new role(s) taken in" if do_intake else "")
          + (f", {n_senior} excluded as senior (--exclude-senior)" if exclude_senior else "")
          + (f", {n_untitled} without a title skipped" if n_untitled else "")
          + (f", {n_failed} not taken in" if n_failed else "")
          + (f", {n_wants} excluded by [wants]" if n_wants else "")
          + (f", {n_dup} duplicate(s) not taken in" if n_dup else ""))
    code = OK
    if reconcile_after:
        code = reconcile(cfg, board, org, all_targets)
    if errors or empties:
        why = ", ".join(x for x in (f"{len(errors)} unreachable" if errors else "",
                                    f"{len(empties)} returned no postings" if empties else "") if x)
        H.warn(f"NOT EVALUABLE for {len(errors) + len(empties)} of {len(targets)} board(s) ({why}): "
               "the listing is incomplete")
        code = NOT_EVALUABLE
    if damaged or n_failed:
        H.warn(f"NOT EVALUABLE: {len(damaged)} damaged role file(s) and {n_failed} posting(s) not taken in; "
               "the rest was done")
        code = NOT_EVALUABLE
    return code


def _note_change(cfg, p, slug, meta) -> None:
    """A known posting whose text differs from the stored one: say so every time, record it
    once per new text, and keep the stored text until the user re-intakes it."""
    now = jd_sha(ats.strip_html(p["jd"], structure=True).strip() + "\n") if (p.get("jd") or "").strip() else None
    # the stored text, hashed by today's rule: a hash an older version wrote of the raw text would
    # report a re-spaced posting as changed
    jd_file = R.role_dir(cfg, slug) / "jd.txt"
    stored = jd_sha(H.read_text(jd_file, "posting")) if jd_file.exists() else meta.get("jd_sha")
    if now is None or stored is None or now == stored:
        return
    print(f"CHANGED {p['board']}:{p['org']}  {p['ext_id'] or '-'} {p['title']}: the posting text changed on the "
          f"board; the stored text is kept (to take the new text, `{H.PROG} jobs intake --company "
          f"{p['org']} --role {p['title']!r} --jd FILE --force` keeps your status and history)")
    if meta.get("board_changed_sha") != now:
        meta["board_changed"] = H.today().isoformat()
        meta["board_changed_sha"] = now
        R.history(meta, "posting changed on the board (stored text kept)")
        R.save(cfg, slug, meta)


def reconcile(cfg, board=None, org=None, all_targets=True) -> int:
    """Mark roles whose posting has vanished from a board that answered.
    Absence proves nothing unless the board was reachable AND non-empty; a
    role from an untracked board or a manual intake is skipped. Status never
    changes: what a vanished posting means is your call."""
    targets = cfg.targets if (all_targets or not (board and org)) else [{"board": board, "org": org}]
    if not targets:
        raise NotEvaluable("no targets to reconcile against: nothing was checked")
    live: dict = {}
    inconclusive = []
    for t in targets:
        res = S.fetch(t["board"], t["org"], cfg)       # never keyword-filtered
        if res.status == "ok":
            live[(t["board"], t["org"])] = {p["ext_id"] for p in res.postings if p["ext_id"]}
        else:
            inconclusive.append(f"{t['board']}:{t['org']} ({res.status}{': ' + res.error if res.error else ''})")
    gone, checked = [], 0
    scanned, damaged = R.scan(cfg)
    for p in damaged:
        print(f"DAMAGED {p}: not checked")
    for slug, meta in scanned:
        key = (meta.get("board"), meta.get("org"))
        if (meta.get("status") not in R.RECONCILE_ACTIVE or not meta.get("job_id")
                or meta.get("posting_gone") or key not in live):
            continue
        checked += 1
        if meta["job_id"] not in live[key]:
            meta["posting_gone"] = H.today().isoformat()
            R.history(meta, f"posting no longer listed on {key[0]}:{key[1]}")
            R.save(cfg, slug, meta)
            gone.append(slug)
    for s in gone:
        print(f"GONE    {s}  (status unchanged; decide with `{H.PROG} jobs status`)")
    if not gone and live:
        print(f"checked {checked} tracked active role(s) on {len(live)} reachable board(s): none vanished"
              + (f"; {len(damaged)} damaged role file(s) not checked" if damaged else ""))
    for i in inconclusive:
        print(f"INCONCLUSIVE {i}: marks nothing")
    return NOT_EVALUABLE if inconclusive or damaged else OK      # a partial check is not a clean one


# --- score / check / tailor / status ----------------------------------------

FIT_REQUIRED_WEIGHT = 0.7
FIT_YEARS_PENALTY = 0.5


def suggest_fit(cfg, cov) -> tuple:
    """(suggested fit, working). From what facts.md holds of what the posting asks: required
    and preferred shares weighted 0.7 / 0.3 (without sections, every term), minus 0.5 when the
    experience asked is above [profile] years; clamped to 1-5, rounded to the half point."""
    facts, lex = F.read(cfg), ats.load_lexicon(cfg)
    terms = [t.lower() for t in cov["present"]] + [e["term"].lower() for e in cov["equiv"]] + \
            [m["term"].lower() for m in cov["missing"]]
    held = {t for t in terms if ats.claimable(t, facts, cfg, lex)}
    where = cov.get("term_sections") or {}

    def share(kind):
        ts = [t for t in terms if where.get(t) == kind]
        return (sum(1 for t in ts if t in held), len(ts))
    if (cov.get("sections") or {}).get("found"):
        (rh, rn), (ph, pn) = share("required"), share("preferred")
        if rn and pn:
            base = FIT_REQUIRED_WEIGHT * rh / rn + (1 - FIT_REQUIRED_WEIGHT) * ph / pn
            why = (f"1 + 4 x (0.7 x required {rh}/{rn} held + 0.3 x preferred {ph}/{pn} held)")
        elif rn:
            base, why = rh / rn, f"1 + 4 x required {rh}/{rn} held"
        elif pn:
            base, why = ph / pn, f"1 + 4 x preferred {ph}/{pn} held (no required term found)"
        else:
            base, why = None, ""
    else:
        base = None
    if base is None:
        h, n = len(held), len(terms)
        base, why = h / n, f"1 + 4 x {h}/{n} terms held (no required/preferred split)"
    fit = 1 + 4 * base
    try:
        mine = float(cfg.profile.get("years", ""))
    except (TypeError, ValueError):
        mine = None
    asks = [y["min"] for y in cov.get("years") or [] if y.get("kind") == "required"]
    if mine is not None and asks and max(asks) > mine:
        fit -= FIT_YEARS_PENALTY
        why += f" -0.5 (asks {max(asks)}+ years, [profile] years = {cfg.profile['years']})"
    fit = min(5.0, max(1.0, round(fit * 2) / 2))
    return fit, f"{why} = {fit}"


def _fresh_coverage(cfg, slug, verb):
    cov = load_coverage(cfg, slug)
    if cov is None:
        raise NotEvaluable(f"{slug} has no coverage yet, so no fit can be suggested: run "
                           f"`{H.PROG} jobs check {slug}` first")
    if coverage_stale(cfg, slug, cov):
        raise NotEvaluable(f"{slug}: coverage is stale, so a suggested fit would be from old inputs: run "
                           f"`{H.PROG} jobs check {slug}` first")
    return cov


def score(cfg, slug, fit=None, note="") -> int:
    meta = R.load(cfg, slug)
    source = "you"
    if fit is None:
        sug, why = suggest_fit(cfg, _fresh_coverage(cfg, slug, "score"))
        print(f"{slug}: suggested fit {sug}: {why}")
        print(f"  accept it: {H.PROG} jobs score {slug} --fit suggested   (or --fit N, your own 1-5)")
        return OK
    if isinstance(fit, str):
        if fit.strip().lower() != "suggested":
            try:
                fit = float(fit)
            except ValueError:
                raise UsageError(f"--fit {fit!r}: a number from 1 to 5, or `suggested`") from None
        else:
            fit, _why = suggest_fit(cfg, _fresh_coverage(cfg, slug, "score"))
            source = "suggested"
    if fit != fit or not 1.0 <= fit <= 5.0:
        raise UsageError(f"--fit {fit} is outside 1-5")
    meta["fit_score"] = round(float(fit), 2)
    meta["fit_source"] = source
    if meta.get("status") in ("found", "", None):
        meta["status"] = "scored"
    R.history(meta, f"scored {meta['fit_score']}/5" + (f" — {note}" if note else ""))
    R.save(cfg, slug, meta)
    side = "at or above" if fit >= cfg.bar else "below"
    print(f"{slug}: fit {meta['fit_score']} ({side} the bar {cfg.bar})")
    return OK


def user_path(cfg, arg):
    """A path the user typed: absolute as is; relative to the current directory when a file is
    there, else relative to the home. `jobs check --resume` and `jobs check-claims` both use it."""
    p = H.Path(arg).expanduser()
    if p.is_absolute() or p.exists():
        return p
    return cfg.home / p


def resolve_resume(cfg, meta, explicit=None):
    """An explicit --resume is used or refused, never swapped for another file."""
    if explicit:
        p = user_path(cfg, explicit)
        if p.exists() and not p.is_file():
            raise NotEvaluable(f"resume {explicit} is not a regular file (a directory or device); pass the resume file")
        if not p.is_file():
            raise NotEvaluable(f"resume {explicit} not found")
        return p.resolve()
    named = []
    if meta and meta.get("resume"):
        named.append(("the role's resume", meta["resume"]))
    if cfg.profile.get("resume"):
        named.append(("[profile] resume", cfg.profile["resume"]))
    for what, c in named + [("", x) for x in ("resumes/resume.md", "resumes/resume.txt", "resumes/resume.tex")]:
        p = H.Path(c).expanduser()
        p = p if p.is_absolute() else cfg.home / p
        if p.is_file():
            return p
        if what:                  # a pointer that was written down is never skipped for another file
            raise NotEvaluable(f"{what} {c!r} is not a file ({p}); fix the pointer or remove it")
    return None


def load_coverage(cfg, slug):
    """coverage.json, None if absent; NOT EVALUABLE if its fields have the wrong types."""
    p = R.role_dir(cfg, slug) / "coverage.json"
    cov = H.read_json(p, "coverage")
    if cov is None:
        return None
    ok = (isinstance(cov, dict) and isinstance(cov.get("pct"), (int, float)) and not isinstance(cov.get("pct"), bool)
          and all(isinstance(cov.get(k), int) for k in ("covered", "denom"))
          and isinstance(cov.get("present"), list) and isinstance(cov.get("equiv"), list)
          and isinstance(cov.get("missing"), list)
          and all(isinstance(m, dict) and isinstance(m.get("term"), str) and isinstance(m.get("held"), bool)
                  for m in cov["missing"]))
    if not ok:
        raise NotEvaluable(f"{p} is damaged (wrong field types); re-run `{H.PROG} jobs check {slug}`")
    return cov


def coverage_inputs(cfg, slug, resume_path) -> str:
    """A digest of everything a coverage report was computed from: the posting,
    the resume, the facts sheet, the config and the lexicon packs."""
    import hashlib
    h = hashlib.sha256()
    paths = [R.role_dir(cfg, slug) / "jd.txt", resume_path, cfg.facts, cfg.home / "config.toml"]
    try:
        paths += [ats.pack_path(cfg, n) for n in cfg.packs]
    except NotEvaluable:
        h.update(b"<pack missing>")
    if cfg.user_lexicon:
        paths.append(cfg.home / cfg.user_lexicon)
    for p in paths:
        h.update(str(H.Path(p).resolve()).encode())
        try:
            h.update(H.Path(p).read_bytes())
        except OSError:
            h.update(b"<absent>")
    return h.hexdigest()[:16]


def coverage_stale(cfg, slug, cov) -> bool:
    rp = H.Path(cov.get("resume", ""))
    rp = rp if rp.is_absolute() else cfg.home / rp
    return cov.get("inputs") != coverage_inputs(cfg, slug, rp)


def check(cfg, slug, resume=None) -> int:
    meta = R.load(cfg, slug)
    d = R.role_dir(cfg, slug)
    jd = H.read_text(d / "jd.txt", "posting") if (d / "jd.txt").exists() else ""
    if not jd.strip():
        raise NotEvaluable(f"{slug} has no posting text (jd.txt); re-intake with --jd --force")
    rp = resolve_resume(cfg, meta, resume)
    if rp is None:
        raise NotEvaluable("no resume found: put one at resumes/resume.md, set [profile] resume, "
                           "or pass --resume")
    rp = rp.resolve()
    lex = ats.load_lexicon(cfg)
    facts = F.read(cfg)
    if not facts.strip():
        raise NotEvaluable(f"facts sheet {cfg.facts} is missing or empty: held-or-not cannot be judged, so "
                           "coverage would read every term as a gap (write facts.md with a ## Held section)")
    jd_text, resume_body = ats.strip_html(jd, structure=True), ats.resume_text(rp)
    lw = lex.words()
    if not ats.extract(resume_body, lex) and not F.disguised(resume_body, lw):
        raise NotEvaluable(f"no lexicon terms found in the resume {rp.name} ({len(resume_body.split())} word(s)): "
                           "coverage of 0 would read as a measurement, so none was written; check that this is "
                           "the right file, or add a lexicon pack that fits your field")
    from . import orgs as O
    org = meta.get("org") or meta.get("company") or ""
    tmpl = O.template_keys(cfg, org)
    rep = ats.coverage(jd_text, resume_body, facts, cfg, lex,
                       excluded={meta.get("company", ""), meta.get("org", "")}, template=tmpl)
    try:
        rel = str(rp.relative_to(cfg.home.resolve()))
    except ValueError:
        rel = str(rp)
    rep = dict(rep, generated=H.today().isoformat(), resume=rel, inputs=coverage_inputs(cfg, slug, rp))
    H.write_json(d / "coverage.json", rep)
    meta["coverage_pct"] = int(f"{rep['pct']:.0f}")
    meta["coverage_resume"] = rel
    R.save(cfg, slug, meta)
    held = [m["term"] for m in rep["missing"] if m["held"]]
    gaps = [m["term"] for m in rep["missing"] if not m["held"]]
    print(f"{slug}: coverage {rep['covered']}/{rep['denom']} = {rep['pct']}%  (resume {rel})")
    for line in placement_lines(cfg, rep):
        print(line)
    try:
        sug, _why = suggest_fit(cfg, rep)
        print(f"  suggested fit {sug} (`{H.PROG} jobs score {slug}` shows the working)")
    except ZeroDivisionError:
        pass
    n_t = len((rep.get("parts") or {}).get("template") or [])
    if n_t:
        n_org = O.profile(cfg, org)["postings"]
        print(f"  company template: {n_t} line(s) seen in most of {meta.get('company') or org}'s {n_org} "
              f"posting(s), set aside from not looked at (still read for skills)")
    if rep["equiv"]:
        print("  covered by a held equivalent: " + ", ".join(f"{e['term']} via {e['via']}" for e in rep["equiv"]))
    if held:
        print("  held but not stated (add the literal term): " + ", ".join(held))
    if gaps:
        print("  not held (study it, or leave it off): " + ", ".join(gaps))
    odd = [("resume", sp, t) for sp, t in F.disguised(resume_body, lw)]
    posting_odd = [("posting", sp, t) for sp, t in F.disguised(jd_text, lw)]
    unheld = [(t, "listed under [ats] do_not_claim" if ats.on_do_not_claim(t, cfg, lex)
               else F.explain(t.lower(), facts)) for t in rep["present"]
              if not ats.claimable(t, facts, cfg, lex)]
    if unheld:
        print("  stated on the resume but not held (counted as covered, but not a claim you can make): "
              + "; ".join(f"{t} ({why})" for t, why in unheld) + f"; run `{H.PROG} jobs check-claims {rel}`")
    for where, sp, t in odd:
        print(f"  VIOLATION suspicious-characters ({where}) {sp.shown}: {_suspicion(sp, t)}")
    for where, sp, t in posting_odd:
        # third-party text: you cannot retype it, so it is a warning and does not change the exit code
        print(f"  WARNING suspicious-characters ({where}) {sp.shown}: {_posting_suspicion(sp, t)}")
    return FINDINGS if odd else OK


UNREAD_SHOWN = 10


def placement_lines(cfg, rep) -> list:
    """The required/preferred split, the experience asked for, and the requirement lines no
    lexicon term was found in. Absent sections read as such, never as 0 required."""
    out = []
    sec = rep.get("sections") or {}
    if sec.get("found"):
        covered = {t.lower() for t in rep["present"]} | {e["term"].lower() for e in rep["equiv"]}
        asked = ("required", "preferred", "responsibilities")
        rest = [t for t, w in (rep.get("term_sections") or {}).items() if w not in asked]
        resp = sec.get("responsibilities") or {"covered": 0, "denom": 0}
        out.append(f"  required {sec['required']['covered']}/{sec['required']['denom']} · "
                   f"preferred {sec['preferred']['covered']}/{sec['preferred']['denom']} · "
                   f"responsibilities {resp['covered']}/{resp['denom']} · "
                   f"elsewhere in the posting {sum(1 for t in rest if t in covered)}/{len(rest)}")
    elif "sections" in rep and not (rep.get("unread") or {}).get("lines"):
        out.append("  sections: no requirements heading or bullet list recognised, so the terms are "
                   "counted together (required vs preferred and unread lines NOT EVALUABLE)")
    elif "sections" in rep:
        out.append("  sections: no requirements or preferred heading recognised, so the terms "
                   "are counted together (required vs preferred NOT EVALUABLE)")
    mine, bad_years = None, None
    if "years" in cfg.profile:
        try:
            mine = float(cfg.profile["years"])
        except (TypeError, ValueError):
            bad_years = cfg.profile["years"]
    for y in rep.get("years") or []:
        ask = f"{y['min']}-{y['max']}" if y["max"] else f"{y['min']}+"
        line = f"  experience: asks {ask} years ({y['kind']})"
        if mine is not None:
            line += f"; [profile] years = {cfg.profile['years']}"
            if mine < y["min"]:
                line += ": below the ask"
        elif bad_years is not None:
            line += f"; [profile] years = {bad_years!r} is not a number, so the comparison is NOT EVALUABLE"
        out.append(line)
    u = rep.get("unread")
    if u is not None and u["lines"]:
        out.append(f"  not looked at: {len(u['unread'])} of {u['lines']} requirement line(s) mention "
                   f"no skill term it knows; listed so you can read them yourself")
        for t in u["unread"][:UNREAD_SHOWN]:
            out.append(f"    - {t}")
        if len(u["unread"]) > UNREAD_SHOWN:
            out.append(f"    ... and {len(u['unread']) - UNREAD_SHOWN} more (coverage.json)")
    return out


def tailor(cfg, slug, resume=None) -> int:
    """Scaffold review.md from coverage. Moves found/scored to tailoring; a
    role already applied or further along keeps its status."""
    meta = R.load(cfg, slug)
    d = R.role_dir(cfg, slug)
    cov = load_coverage(cfg, slug)
    if cov is None:
        raise NotEvaluable(f"{slug} has no coverage yet: run `{H.PROG} jobs check {slug}` first")
    if coverage_stale(cfg, slug, cov):
        raise NotEvaluable(f"{slug}: coverage is stale (the posting, resume, facts, config or a lexicon changed "
                           f"since it was computed): run `{H.PROG} jobs check {slug}` first")
    if meta.get("status") in ("found", "scored"):
        meta["status"] = "tailoring"
        R.history(meta, "→ tailoring")
    R.save(cfg, slug, meta)
    held = [m["term"] for m in cov["missing"] if m["held"]]
    gaps = [m["term"] for m in cov["missing"] if not m["held"]]
    review = d / "review.md"
    if review.exists():
        print(f"{slug}: {review.relative_to(cfg.home)} already exists; left as is")
    else:
        lines = [f"# Tailoring review — {meta.get('company')} / {meta.get('role')}", "",
                 f"Coverage {cov['covered']}/{cov['denom']} ({cov['pct']}%).", "",
                 "## State these (you hold them; the resume does not say so)", ""]
        lines += [f"- [ ] {t}" for t in held] or ["- (none)"]
        lines += ["", "## Do not claim these (not held; bridge honestly or leave off)", ""]
        lines += [f"- {t}" for t in gaps] or ["- (none)"]
        lines += ["", "## Before sending", "",
                  f"- [ ] `{H.PROG} jobs check-claims <tailored resume>` exits 0",
                  f"- [ ] `{H.PROG} jobs status {slug} applied`", ""]
        _write_text(review, "\n".join(lines))
        print(f"{slug}: wrote {review.relative_to(cfg.home)} "
              f"({len(held)} term(s) to state, {len(gaps)} to leave off)")
    return OK


BRIEF_RULES = f"""## Rules for whoever writes from this brief

- Only claim what "You hold" lists, and trace each claim to the facts.md line quoted there.
- Never claim anything under "Do not claim". Say you are learning it only if facts.md says so.
- Say which requirement each resume bullet answers.
- Use the company's own words for what it does (under "About the company"); invent nothing about it.
- When done, run `{H.PROG} jobs check-claims <the tailored resume>`: it must exit 0.
"""


def _evidence(term: str, facts: str, lex) -> list:
    """The unqualified `## Held` lines of facts.md that hold `term` (under any spelling)."""
    out = []
    for b in F.analyse(facts).blocks:
        if b.held and not b.qualified and not b.heading and any(F.token_in(f, b.norm) for f in lex.forms(term)):
            out.append(b.text.strip())
    return out


def brief(cfg, slug) -> int:
    """A Markdown bundle for writing the tailored resume and cover letter: the posting typed,
    what you hold (with the facts.md line that proves each), what not to claim, and the
    company's own text. Needs a fresh `jobs check`."""
    from . import orgs as O
    meta = R.load(cfg, slug)
    cov = load_coverage(cfg, slug)
    if cov is None:
        raise NotEvaluable(f"{slug} has no coverage yet: run `{H.PROG} jobs check {slug}` first")
    if coverage_stale(cfg, slug, cov):
        raise NotEvaluable(f"{slug}: coverage is stale (the posting, resume, facts, config or a lexicon changed "
                           f"since it was computed): run `{H.PROG} jobs check {slug}` first")
    facts, lex = F.read(cfg), ats.load_lexicon(cfg)
    where = cov.get("term_sections") or {}
    terms = list(cov["present"]) + [e["term"] for e in cov["equiv"]] + [m["term"] for m in cov["missing"]]
    held = {t.lower() for t in terms if ats.claimable(t, facts, cfg, lex)}
    parts = cov.get("parts") or {}
    company, role = str(meta.get("company", "")).strip(), str(meta.get("role", "")).strip()
    out = [f"# Brief: {company} — {role}", "",
           f"{H.NAME} wrote this from the posting, your facts.md and `jobs check` "
           f"(coverage {cov['covered']}/{cov['denom']}). It holds no model output.", "", BRIEF_RULES,
           "## The role", ""]
    for kind, title in (("required", "Required"), ("preferred", "Preferred"),
                        ("responsibilities", "Responsibilities")):
        out.append(f"### {title}")
        out.append("")
        ts = [t for t in terms if where.get(t.lower()) == kind]
        out += [f"- [{'held' if t.lower() in held else 'not held'}] {t.lower()}" for t in ts]
        if kind == "responsibilities":
            out += ["", "What the job does, in the posting's words:", ""]
            out += [f"- {ln}" for ln in parts.get("responsibilities", [])]
        if not ts and kind != "responsibilities":
            out.append("- (no term found here)")
        out.append("")
    for y in cov.get("years") or []:
        ask = f"{y['min']}-{y['max']}" if y["max"] else f"{y['min']}+"
        out.append(f"Experience asked: {ask} years ({y['kind']}): \"{y['text']}\"")
    prof = O.profile(cfg, meta.get("org") or company)
    about = prof["about"] if prof.get("template") else parts.get("company", [])
    src = (f"from {company}'s template across {prof['postings']} posting(s)" if prof.get("template")
           else "this posting only (fewer than 3 postings from the company)")
    out += ["", "## About the company", "", f"In its own words, {src}:", ""]
    out += [f"> {ln}" for ln in about] or ["> (the posting says nothing about the company)"]
    benefits = parts.get("benefits", [])
    standing = [ln for ln in prof["benefits"] if ln not in benefits] if prof.get("template") else []
    if benefits or standing:
        out += ["", "## Benefits it states (for your judgement, not for the letter)", ""]
        out += [f"- {ln}" for ln in benefits]
        if standing:
            out += ["", f"{company}'s standing benefits (in most of its postings, so set aside from this "
                        "posting's own lines):", ""]
            out += [f"- {ln}" for ln in standing]
    out += ["", "## You hold", "", "Each with the facts.md line that holds it:", ""]
    for t in terms:
        if t.lower() in held:
            ev = _evidence(t.lower(), facts, lex)
            out.append(f"- {t.lower()}: " + (" / ".join(f'"{e}"' for e in ev) if ev else "(held)"))
    if not held:
        out.append("- (nothing this posting asks for)")
    out += ["", "## Do not claim", "", "Not held by facts.md (bridge honestly, or leave off):", ""]
    nots = [t.lower() for t in terms if t.lower() not in held]
    out += [f"- {t}" for t in nots] or ["- (none)"]
    unread = (cov.get("unread") or {}).get("unread") or []
    if unread:
        out += ["", "## Not looked at", "",
                f"Requirement lines {H.NAME} found no known skill in; read them yourself:", ""]
        out += [f"- {ln}" for ln in unread]
    out += ["", "## Wanted from you", "",
            "1. Four to six resume bullets, each naming the requirement it answers.",
            "2. A cover letter of at most 250 words, using the company's own words for what it does.",
            "3. A list of anything you left out because it is under \"Do not claim\".", ""]
    print("\n".join(out))
    return OK


def status(cfg, slug, state, date=None, note="", stage=None, reason=None, probed=None) -> int:
    if state not in R.STATUSES:
        raise UsageError(f"unknown status {state!r} (one of {', '.join(R.STATUSES)})")
    if stage is not None and stage not in R.STAGES:
        raise UsageError(f"unknown --stage {stage!r} (one of {', '.join(R.STAGES)})")
    if reason is not None and reason not in R.CLOSED_REASONS:
        raise UsageError(f"unknown --reason {reason!r} (one of {', '.join(R.CLOSED_REASONS)})")
    meta = R.load(cfg, slug)
    when = _date(date, "--date") if date else H.today().isoformat()
    old = meta.get("status", "")
    back = R.is_backward(old, state)
    if back:
        H.warn(f"{slug}: backward move {old} → {state} (recorded)")
    meta["status"] = state
    if state == "applied" and not meta.get("applied"):
        meta["applied"] = when
    out = dict(meta.get("outcome") or {})
    if stage is not None:
        out["stage_reached"] = stage
    if reason is not None:
        out["closed_reason"] = reason
    if probed:
        merged: dict = {}
        for t in list(out.get("probed_terms", [])) + [t.strip() for t in probed.split(",")]:
            if t and t.lower() not in merged:
                merged[t.lower()] = t                      # one entry per term, first spelling kept
        out["probed_terms"] = sorted(merged.values(), key=str.lower)
    if out != (meta.get("outcome") or {}):
        out["updated"] = when
        meta["outcome"] = out
    extra = [x for x in (stage and f"stage {stage}", reason and f"reason {reason}",
                         probed and f"probed {probed}", note) if x]
    meta.setdefault("history", []).append(
        f"{when} → {state}" + (" (backward)" if back else "") + (" — " + "; ".join(extra) if extra else ""))
    R.save(cfg, slug, meta)
    print(f"{slug}: {old or '-'} → {state}")
    return OK


# --- views --------------------------------------------------------------------

def _days_to(deadline: str, today):
    try:
        return (_dt.date.fromisoformat(deadline) - today).days
    except (TypeError, ValueError):
        return None


def shortlist(cfg, roles=None) -> list:
    """Apply-now: in the work queue, fit at or above the bar, posting live.
    Highest fit, then highest coverage, then oldest."""
    roles = roles if roles is not None else R.scan(cfg)[0]
    rows = [(s, m) for s, m in roles if m.get("status") in R.WORK_QUEUE
            and (m.get("fit_score") or 0) >= cfg.bar and not m.get("posting_gone")]
    rows.sort(key=lambda sm: (-(sm[1].get("fit_score") or 0), -(sm[1].get("coverage_pct") or 0),
                              sm[1].get("found", ""), sm[0]))
    return rows


def needs_scoring(cfg, roles=None) -> list:
    roles = roles if roles is not None else R.scan(cfg)[0]
    rows = [(s, m) for s, m in roles if m.get("status") == "found" and m.get("fit_score") is None
            and not m.get("posting_gone")]
    rows.sort(key=lambda sm: (sm[1].get("found", ""), sm[0]))
    return rows


def rank(cfg) -> int:
    roles, damaged = R.scan(cfg)
    today = H.today()
    q = needs_scoring(cfg, roles)
    print(f"## Needs scoring ({len(q)})")
    for s, m in q:
        print(f"  {s}  found {m.get('found')}")
    sl = shortlist(cfg, roles)
    print(f"## Apply now: fit >= {cfg.bar} ({len(sl)})")
    for s, m in sl:
        dl = _days_to(m.get("deadline"), today)
        soon = f"  DEADLINE in {dl}d" if dl is not None and 0 <= dl <= cfg.deadline_days else ""
        print(f"  {s}  fit {m.get('fit_score')}  cov {m.get('coverage_pct', '-')}%{soon}")
    below = [(s, m) for s, m in roles if m.get("status") in R.WORK_QUEUE
             and m.get("fit_score") is not None and m["fit_score"] < cfg.bar]
    print(f"## Below the bar ({len(below)})")
    for s, m in below:
        print(f"  {s}  fit {m.get('fit_score')}")
    inflight = [(s, m) for s, m in roles if m.get("status") in R.IN_FLIGHT]
    print(f"## In flight ({len(inflight)})")
    for s, m in inflight:
        print(f"  {s}  {m.get('status')} since {m.get('applied') or '-'}")
    for p in damaged:
        H.warn(f"damaged role file skipped: {p}")
    return NOT_EVALUABLE if damaged else OK


def board(cfg, status_filter=None, min_fit=None) -> int:
    if status_filter and status_filter not in R.STATUSES:
        raise UsageError(f"--status {status_filter!r} is not a status (one of: {', '.join(R.STATUSES)})")
    if min_fit is not None and not 0 <= min_fit <= 5:
        raise UsageError(f"--min-fit {min_fit} is not a number from 0 to 5")
    roles, damaged = R.scan(cfg)
    order = {s: i for i, s in enumerate(R.STATUSES)}
    rows = [(s, m) for s, m in roles if (not status_filter or m.get("status") == status_filter)
            and (min_fit is None or (m.get("fit_score") or 0) >= min_fit)]
    rows.sort(key=lambda sm: (order.get(sm[1].get("status"), 99), -(sm[1].get("fit_score") or 0), sm[0]))
    print(f"{'':2}{'status':13}{'fit':>5} {'cov':>5}  role")
    for s, m in rows:
        gone = "✗ " if m.get("posting_gone") else "  "
        fit = "-" if m.get("fit_score") is None else m["fit_score"]
        cov = "-" if m.get("coverage_pct") is None else f"{m['coverage_pct']}%"
        print(f"{gone}{m.get('status', '?'):13}{fit!s:>5} {cov:>5}  {s}")
    print(f"{len(rows)} role(s)" + ("  (✗ = posting gone)" if any(m.get("posting_gone") for _s, m in rows) else ""))
    for p in damaged:
        H.warn(f"damaged role file skipped: {p}")
    return NOT_EVALUABLE if damaged else OK


def show(cfg, slug) -> int:
    meta = R.load(cfg, slug)
    for k in ("company", "role", "status", "fit_score", "coverage_pct", "found", "applied",
              "deadline", "posting_gone", "source_url"):
        if meta.get(k) not in (None, ""):
            print(f"{k:13} {meta[k]}")
    if meta.get("outcome"):
        print(f"{'outcome':13} {meta['outcome']}")
    for h in meta.get("history", []):
        print(f"  {h}")
    return OK


# --- the job -> learn seam ---------------------------------------------------

def org_report(cfg, org: str) -> int:
    """A company's profile from its postings: the template lines with their counts, and the
    about, benefits and legal text kept for tailoring. Written to HOME/orgs/<org>.json."""
    from . import orgs as O
    prof = O.profile(cfg, org)
    if not prof["postings"]:
        print(f"NOT EVALUABLE org: no posting from {org!r} has been taken in")
        return NOT_EVALUABLE
    if prof["template"] is None:
        print(f"{org}: {prof['postings']} posting(s); template: {prof['why']}")
    else:
        print(f"{org}: {prof['postings']} posting(s); template: {len(prof['template'])} line(s) in at least "
              f"{prof['threshold']} of them")
        for t in sorted(prof["template"], key=lambda t: -t["count"]):
            print(f"  {t['count']:>3}  {t['kind']:<16} {t['text'][:90]}")
    print(f"  kept for tailoring: {len(prof['about'])} about line(s), {len(prof['benefits'])} benefit "
          f"line(s), {len(prof['legal'])} legal line(s)")
    d = cfg.home / "orgs"
    d.mkdir(exist_ok=True)
    name = R.slugify(org)
    H.write_json(d / f"{name}.json", prof)
    print(f"  wrote orgs/{name}.json")
    if prof["template"] is None:
        H.warn(f"NOT EVALUABLE: {prof['postings']} posting(s) from {org} is too few for a template "
               f"(the profile above holds this company's own text only)")
        return NOT_EVALUABLE
    return OK


def headings_report(cfg, show_all=False) -> int:
    """Heading-shaped lines across every posting, counted by how many postings use each; by
    default only those nothing typed. Map one in config.toml [headings] to type it everywhere."""
    from . import sections as SEC
    roles, damaged = R.scan(cfg)
    count, kinds, n_postings = {}, {}, 0
    for slug, _meta in roles:
        p = R.role_dir(cfg, slug) / "jd.txt"
        if not p.exists():
            continue
        n_postings += 1
        seen = set()
        for text, kind in SEC.census(H.read_text(p, "posting"), cfg.headings):
            key = SEC.norm_key(text)
            if key in seen:
                continue
            seen.add(key)
            count[key] = count.get(key, 0) + 1
            kinds.setdefault(key, (text, kind))
    if not n_postings:
        print("NOT EVALUABLE headings: no posting text taken in yet (jobs discover --intake, or jobs intake --jd)")
        return NOT_EVALUABLE
    untyped = [k for k in count if kinds[k][1] is None]
    print(f"headings: {len(untyped)} not typed, over {n_postings} posting(s); map one in config.toml "
          f"[headings] (\"<heading>\" = \"required\" | \"preferred\" | \"responsibilities\" | \"company\" | "
          f"\"benefits\" | \"legal\" | \"logistics\" | \"other\")")
    for k in sorted(count, key=lambda k: (-count[k], k)):
        text, kind = kinds[k]
        if kind is None or show_all:
            print(f"  {count[k]}  {text}  {kind or 'NOT TYPED'}")
    for p in damaged:
        H.warn(f"damaged role file skipped: {p}")
    return NOT_EVALUABLE if damaged else OK


def wants_report(cfg) -> int:
    """Every stored role against [wants]: each filter's pass/fail/unknown with its denominator,
    and the roles it would set aside, with the reason. Reports only; changes nothing."""
    if not cfg.wants:
        print("NOT EVALUABLE wants: no [wants] in config.toml (e.g. workplace = [\"remote\"], pay_min = 120000)")
        return NOT_EVALUABLE
    roles, damaged = R.scan(cfg)
    tally, rows = {}, []
    for slug, meta in roles:
        d = R.role_dir(cfg, slug)
        jd = H.read_text(d / "jd.txt", "posting") if (d / "jd.txt").exists() else ""
        res = W.evaluate(cfg, meta, jd)
        for r in res:
            tally.setdefault(r["filter"], {"pass": 0, "fail": 0, "unknown": 0})[r["verdict"]] += 1
        verdict, why = W.decide(cfg, res)
        if verdict != "keep":
            rows.append((slug, verdict, why))
    for f, t in tally.items():
        print(f"{f}: {t['pass']} pass · {t['fail']} fail · {t['unknown']} unknown of {len(roles)} role(s)")
    for slug, verdict, why in rows:
        print(f"  {verdict.upper():8} {slug}: {why}")
    for p in damaged:
        H.warn(f"damaged role file skipped: {p}")
    return NOT_EVALUABLE if damaged else OK


def upskill(cfg) -> int:
    data = DM.compute(cfg)
    if not data["roles_analyzed"]:
        # nothing was measured: an upskill.json saying "no demand" would read as a result
        why = (f"{len(data['roles_unchecked'])} role(s) have a posting but no coverage.json "
               f"(run `{H.PROG} jobs check SLUG`)" if data["roles_unchecked"]
               else "no roles have been checked")
        print(f"NOT EVALUABLE upskill: 0 bucket(s) from 0 role(s): {why}; {cfg.upskill.name} was not written")
        for p in data["roles_damaged"]:
            H.warn(f"damaged role file skipped: {p}")
        return NOT_EVALUABLE
    H.write_json(cfg.upskill, data)
    lines = [f"# Upskill plan ({data['generated']})", "",
             f"Demand from {data['roles_analyzed']} checked role(s), weighted by status and age.", ""]
    if data["quick_wins"]:
        lines += ["## Quick wins: held but not stated on the resume", ""]
        lines += [f"- {q['term']} (wanted by {q['count']})" for q in data["quick_wins"]] + [""]
    for b in data["buckets"]:
        lines += [f"## {b['name']} — demand {b['demand']}", ""]
        if b["action"]:
            lines += [f"_{b['action']}_", ""]
        for it in b["items"]:
            tag = " (ignored)" if it["noise"] else ""
            lines.append(f"- {it['term']}: demand {it['demand']}, {it['count']} role(s){tag}")
        lines.append("")
    _write_text(cfg.home / "upskill.md", "\n".join(lines))
    print(f"wrote {cfg.upskill.name}: {len(data['buckets'])} bucket(s), "
          f"{len(data['quick_wins'])} quick win(s), from {data['roles_analyzed']} role(s)")
    for b in data["buckets"][:5]:
        print(f"  {b['demand']:6.2f}  {b['name']}  ({', '.join(i['term'] for i in b['items'][:4])})")
    u, n = data["unread"], data["roles_analyzed"]
    old = u.get("unmeasured", 0)
    none = n - u["roles"] - old
    if u["roles"]:
        rest = f"; the other {none} had no requirement lines to read" if none else ""
        print(f"  not looked at: {u['unread']} of {u['lines']} requirement line(s) in {u['roles']} of {n} "
              f"role(s) mention no skill term it knows, so the gaps they state are not measured above{rest}")
    elif not old:
        print(f"  not looked at: NOT EVALUABLE (none of the {n} role(s) had requirement lines to read)")
    if old:
        print(f"  not looked at: {old} role(s) checked before this count existed (re-run `jobs check`): "
              f"NOT EVALUABLE for those")
    for s in data["roles_unchecked"]:
        H.warn(f"{s} has a posting but no coverage.json; run `{H.PROG} jobs check {s}` (counted nothing)")
    for p in data["roles_damaged"]:
        H.warn(f"damaged role file skipped: {p}")
    return NOT_EVALUABLE if data["roles_damaged"] else OK


def _suspicion(sp, term) -> str:
    return (f"contains {F.describe(sp)}; without it the word reads like the skill {term!r}, so it cannot be "
            "checked: type it in plain ASCII letters")


def _posting_suspicion(sp, term) -> str:
    return (f"contains {F.describe(sp)}; without it the word reads as {term!r}, so the posting may ask for "
            "that skill in a spelling the matcher cannot read (the posting is not yours to change; "
            "the exit code is unaffected)")


def resume_findings(cfg, path) -> list:
    """[(Suspect, term)] for the disguised words of one resume file, with the lexicon of `cfg`."""
    lex = ats.load_lexicon(cfg)
    return F.disguised(ats.resume_text(path), lex.words())


def claim_report(cfg, text, facts, lex, acronyms=False) -> tuple:
    """([(term, kind, evidence)] violations, terms stated, [(Suspect, term)] disguised, shown lines):
    what `check-claims` and `doctor` both judge about one resume's text. NOT EVALUABLE
    when the resume states no term at all."""
    look = F.disguised(text, lex.words())
    terms = ats.extract(text, lex, acronyms=acronyms)
    if not terms and not look:
        raise NotEvaluable("no lexicon terms" + (" or acronyms" if acronyms else "")
                           + " found in the resume: nothing to check")
    bad, shown = [], set()
    for sp, t in look:
        bad.append((sp.shown, "suspicious-characters", _suspicion(sp, t)))
    for t in terms:
        k = t.lower()
        if ats.on_do_not_claim(k, cfg, lex):
            bad.append((t, "do-not-claim", "listed under [ats] do_not_claim"))
        elif lex.holds(k, facts):
            continue
        elif cfg.equivalence.get(k) and lex.holds(cfg.equivalence[k], facts):
            bad.append((t, "equivalent", f"you hold {cfg.equivalence[k]!r}, not {t!r}; say what you did"))
        else:
            c = F.qualified_blocks(k, facts)
            o = F.held_elsewhere(k, facts)
            dg = F.disguised_in_held(k, facts)
            if not c and dg:
                shown.add(dg[0].line)
                bad.append((t, "contradiction", f"facts.md line {dg[0].line} is under ## Held but spells it "
                            f"{dg[1].shown!r} with {F.describe(dg[1])}, so it is not held: {dg[0].text[:90]}"))
            elif c:
                shown.add(c[0].line)
                bad.append((t, "contradiction", f"facts.md line {c[0].line} is under ## Held but qualified "
                            f"({c[0].why}): {c[0].text[:90]}"))
            elif o:
                bad.append((t, "not held", f"not under ## Held: {o[0][:90]}"))
            elif F.hidden_for(k, facts):
                bad.append((t, "hidden", F.hidden_cause(F.hidden_for(k, facts))))
            else:
                bad.append((t, "unsupported", "not in facts.md"))
    return bad, terms, look, shown


def check_claims(cfg, resume, acronyms=False) -> int:
    """Every term the resume states must itself be held: listed under `## Held` in
    facts.md, in a line that carries no qualifier word. Holding an
    equivalent is not holding the term. Lexicon terms only unless --acronyms
    (names, employers and places are acronyms too). Exit 1 on any violation,
    2 if it cannot judge."""
    facts = F.read(cfg)
    if not facts.strip():
        raise NotEvaluable(f"facts sheet {cfg.facts} is missing or empty: nothing can be verified")
    p = user_path(cfg, resume)
    if p.exists() and not p.is_file():
        raise NotEvaluable(f"resume {resume} is not a regular file (a directory or device); pass the resume file")
    if not p.is_file():
        raise NotEvaluable(f"resume {resume} not found")
    text = ats.resume_text(p)
    lex = ats.load_lexicon(cfg)
    bad, terms, look, shown = claim_report(cfg, text, facts, lex, acronyms)
    # a Held line that blocks the gate on its own, apart from any resume term
    sheet = [b for b in F.contradiction_blocks(facts) if b.line not in shown]
    for t, kind, ev in bad:
        print(f"VIOLATION {kind:12} {t}: {ev}")
    for b in sheet:
        print(f"SHEET CONTRADICTION facts.md line {b.line}: {b.text[:90]} (under ## Held but {b.why}; not held)")
    for what, no in F.analyse(facts).unclosed:
        print(f"NOTE facts.md: the {what} opened on line {no} never closes, so everything after it is "
              "hidden and counts as not held")
    print(f"checked {len(terms) + len(look)} resume term(s): {len(bad)} violation(s); "
          f"{len(sheet)} sheet contradiction(s) elsewhere in facts.md")
    print("scope: " + (f"lexicon terms ({', '.join(cfg.packs) or 'no packs'}) plus acronyms and names"
                       if acronyms else f"lexicon terms only ({', '.join(cfg.packs) or 'no packs'}); "
                       "a skill outside the packs is not checked; --acronyms adds acronyms and names"))
    return FINDINGS if (bad or sheet) else OK
