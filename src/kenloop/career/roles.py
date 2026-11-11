"""Roles: one job posting each, in ``HOME/roles/<slug>/``.

``meta.json`` is the role's record: posting fields, where it is in your
process (``status``), your fit score, dated history lines, and a structured
``outcome`` (how far you got, why it closed, which skills an interviewer
probed). Outcomes feed demand: a skill an interviewer asked about counts
extra, a role you passed on counts nothing.
"""
from __future__ import annotations

from ..core import home as H
from ..core.errors import NotEvaluable, UsageError
from ..core.names import slugify  # noqa: F401  (R.slugify, used by jobs and loop)

STATUSES = ("found", "scored", "tailoring", "applied", "interviewing", "offer",
            "rejected", "passed", "closed", "on-hold")
LADDER = ("found", "scored", "tailoring", "applied", "interviewing", "offer")
TERMINAL = ("rejected", "passed", "closed")
WORK_QUEUE = {"found", "scored", "tailoring"}
IN_FLIGHT = {"applied", "interviewing", "offer"}
RECONCILE_ACTIVE = WORK_QUEUE | {"applied", "interviewing"}
STAGES = ("none", "screen", "interview", "final", "offer")
CLOSED_REASONS = ("rejected", "withdrew", "filled", "posting_gone", "no_response", "other")
TEXT_KEYS = ("company", "role", "board", "org", "job_id", "source_url", "location", "salary", "resume",
             "coverage_resume", "pdf_dir")
POSTING_KEYS = ("company", "role", "board", "org", "job_id", "source_url", "location", "salary")


def role_slug(company: str, role: str) -> str:
    return slugify(f"{company}-{role}")


def role_dir(cfg, slug: str):
    return cfg.roles / H.safe_name(slug, "role slug")


def _read(path):
    """(meta, problem): the record, or "" and the cause when it cannot be used. Not called for an absent file."""
    try:
        m = H.read_json(path, "role")
    except NotEvaluable as e:
        return None, str(e)
    if not isinstance(m, dict):
        return None, f"it holds {'null' if m is None else type(m).__name__}, not a JSON object"
    return (m, "") if not (pr := meta_problem(m)) else (None, pr)


def read_meta(path):
    """The role record at `path`: None only when there is no file. A file that is not a JSON object, or
    whose fields are wrong, is NOT EVALUABLE and names the file and the field (never "no such role")."""
    if not path.exists():
        return None
    m, problem = _read(path)
    if m is None:
        raise NotEvaluable(f"role {path} is damaged ({problem}); fix it by hand")
    return m


def load(cfg, slug: str) -> dict:
    p = role_dir(cfg, slug) / "meta.json"
    meta = read_meta(p)
    if meta is None:
        known = ", ".join(s for s, _m in scan(cfg)[0][:8])
        raise UsageError(f"no role {slug!r}" + (f" (known: {known})" if known else ""))
    return meta


def save(cfg, slug: str, meta: dict) -> None:
    H.write_json(role_dir(cfg, slug) / "meta.json", meta)


def scan(cfg) -> tuple:
    """([(slug, meta)], [damaged paths with the cause]). A damaged role is reported and
    skipped, never allowed to abort a scan of the others."""
    good, bad = [], []
    if not cfg.roles.is_dir():
        return good, bad
    for d in sorted(cfg.roles.iterdir()):
        p = d / "meta.json"
        if not p.is_file():
            if d.is_dir() and not d.name.startswith("."):
                bad.append(f"{p} (missing: a role directory without a meta.json)")
            continue
        m, problem = _read(p)
        if m is None:
            bad.append(f"{p} ({problem})")
        else:
            good.append((d.name, m))
    return good, bad


REQUIRED_KEYS = ("company", "role", "status")


def meta_problem(m: dict) -> str:
    """"" when the fields every reader relies on are present with the types and values they rely on;
    otherwise a phrase naming the wrong one."""
    for k in REQUIRED_KEYS:
        if k not in m:
            return f"the required field {k!r} is missing"
    if m["status"] not in STATUSES:
        return f"field 'status' is {m['status']!r}, not one of {', '.join(STATUSES)}"
    fit = m.get("fit_score")
    if fit is not None and (isinstance(fit, bool) or not isinstance(fit, (int, float))):
        return f"field 'fit_score' is {fit!r}, not a number or null"
    if fit is not None and not 1.0 <= fit <= 5.0:          # also false for NaN
        return f"field 'fit_score' is {fit!r}, outside 1-5"
    cov = m.get("coverage_pct")
    if cov is not None and (isinstance(cov, bool) or not isinstance(cov, (int, float))
                            or not 0 <= cov <= 100):       # the comparison is also false for NaN
        return f"field 'coverage_pct' is {cov!r}, not a percentage from 0 to 100 or null"
    for k in ("company", "role"):
        if not isinstance(m[k], str):
            return f"field {k!r} is {m[k]!r}, not text"
    for k in ("found", "applied", "deadline", "posting_gone"):
        v = m.get(k, "")
        if not isinstance(v, str):
            return f"field {k!r} is {v!r}, not a date string"
        if v:
            try:
                H.iso_date(v)
            except ValueError:
                return f"field {k!r} is {v!r}, not a YYYY-MM-DD date"
    for k in ("slug",) + TEXT_KEYS:
        if m.get(k) is not None and not isinstance(m.get(k), str):
            return f"field {k!r} is {m.get(k)!r}, not text"
    out = m.get("outcome", {})
    if not isinstance(out, dict):
        return "field 'outcome' is not an object"
    if not isinstance(out.get("probed_terms", []), list):
        return "field 'outcome.probed_terms' is not a list"
    if not isinstance(m.get("history", []), list):
        return "field 'history' is not a list"
    return ""


def meta_ok(m: dict) -> bool:
    return not meta_problem(m)


def is_backward(old: str, new: str) -> bool:
    """A move down the ladder, or out of a closed state back onto it."""
    if old in LADDER and new in LADDER:
        return LADDER.index(new) < LADDER.index(old)
    return old in TERMINAL and new in LADDER


def history(meta: dict, line: str) -> None:
    meta.setdefault("history", []).append(f"{H.today().isoformat()} {line}")
