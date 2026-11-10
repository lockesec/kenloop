"""The job-search verbs (`ken jobs ...`): the career sidecar's commands, registered through the
commands seam (kenloop/modules.py)."""
from __future__ import annotations

import sys

from ..core.errors import OK, NotEvaluable, UsageError
from . import graduate as G
from . import jobs as J
from . import seed as SD
from . import sources as S


def _graduate(cfg, ns) -> int:
    return G.graduate(cfg, ns.slug, ns.emit)


def _gaps(cfg, ns) -> int:
    return SD.gaps(cfg)


def _read_jd(arg):
    if arg is None:
        return None
    try:
        data = sys.stdin.buffer.read() if arg == "-" else open(arg, "rb").read()
    except OSError as e:
        raise UsageError(f"--jd {arg}: {e}") from e
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise NotEvaluable(f"--jd {'stdin' if arg == '-' else arg} is not valid UTF-8 (byte 0x{data[e.start]:02x} "
                           f"at offset {e.start}); re-save the posting as UTF-8") from e
    if not text.strip():
        raise NotEvaluable(f"--jd {'stdin' if arg == '-' else arg} is an empty posting (only white space); "
                           "nothing was taken in")
    from . import ats as _ats
    if not _ats.has_visible_text(text):
        raise NotEvaluable(f"--jd {'stdin' if arg == '-' else arg} is an empty posting (markup with no visible "
                           "text); nothing was taken in")
    return text


def _intake(cfg, ns) -> int:
    slug, created = J.intake(cfg, ns.company, ns.role, _read_jd(ns.jd), ns.url, ns.job_id,
                             ns.location, ns.salary, ns.status, ns.applied, ns.deadline,
                             ns.slug or None, ns.force)
    print(f"{slug}: {'taken in' if created else 'exists (pass --force to refresh)'}")
    return OK


def _discover(cfg, ns) -> int:
    return J.discover(cfg, ns.board, ns.company, ns.all, ns.keyword, ns.intake,
                      ns.exclude_senior, ns.reconcile)


def _reconcile(cfg, ns) -> int:
    if bool(ns.board) != bool(ns.company):
        raise UsageError("reconcile: pass --board and --company together (or neither, for every [sources] target)")
    if ns.board and ns.board not in S.BOARDS:
        raise UsageError(f"unknown board {ns.board!r} (known: {', '.join(S.BOARDS)})")
    return J.reconcile(cfg, ns.board, ns.company, all_targets=not (ns.board and ns.company))


def _score(cfg, ns) -> int:
    return J.score(cfg, ns.slug, ns.fit, ns.note)


def _check(cfg, ns) -> int:
    return J.check(cfg, ns.slug, ns.resume)


def _tailor(cfg, ns) -> int:
    return J.tailor(cfg, ns.slug)


def _status(cfg, ns) -> int:
    return J.status(cfg, ns.slug, ns.state, ns.date, ns.note, ns.stage, ns.reason, ns.probed)


def _rank(cfg, ns) -> int:
    return J.rank(cfg)


def _board(cfg, ns) -> int:
    return J.board(cfg, ns.status, ns.min_fit)


def _show(cfg, ns) -> int:
    return J.show(cfg, ns.slug)


def _brief(cfg, ns) -> int:
    return J.brief(cfg, ns.slug)


def _org(cfg, ns) -> int:
    return J.org_report(cfg, ns.name)


def _headings(cfg, ns) -> int:
    return J.headings_report(cfg, ns.show_all)


def _wants(cfg, ns) -> int:
    return J.wants_report(cfg)


def _digest(cfg, ns) -> int:
    return J.digest(cfg, ns.dry_run)


def _upskill(cfg, ns) -> int:
    return J.upskill(cfg)


def _check_claims(cfg, ns) -> int:
    return J.check_claims(cfg, ns.resume, ns.acronyms)


HANDLERS = {
        "graduate": _graduate,
        "gaps": _gaps,
        "intake": _intake,
        "discover": _discover,
        "reconcile": _reconcile,
        "score": _score,
        "check": _check,
        "tailor": _tailor,
        "status": _status,
        "rank": _rank,
        "board": _board,
        "show": _show,
        "brief": _brief,
        "org": _org,
        "headings": _headings,
        "wants": _wants,
        "digest": _digest,
        "upskill": _upskill,
        "check-claims": _check_claims,
}


def commands(groups) -> None:
    js = groups["jobs"]
    a = js.add_parser("intake", help="add a role by hand")
    a.add_argument("--company", required=True)
    a.add_argument("--role", required=True)
    a.add_argument("--jd", help="file with the posting text, or - for stdin")
    for f in ("--url", "--job-id", "--location", "--salary", "--applied", "--deadline", "--slug"):
        a.add_argument(f, default="")
    a.add_argument("--status", default="found")
    a.add_argument("--force", action="store_true", help="refresh posting fields; keeps your state")
    a = js.add_parser("discover", help="list (and optionally take in) postings from job boards")
    a.add_argument("--board")
    a.add_argument("--company", help="the board's org slug")
    a.add_argument("--all", action="store_true", help="every [sources] target")
    a.add_argument("--keyword")
    a.add_argument("--intake", action="store_true")
    a.add_argument("--exclude-senior", action="store_true")
    a.add_argument("--reconcile", action="store_true", help="then mark vanished postings")
    a = js.add_parser("reconcile", help="mark roles whose posting vanished from a reachable board")
    a.add_argument("--board")
    a.add_argument("--company")
    a = js.add_parser("score", help="record your fit score (1-5)")
    a.add_argument("slug")
    a.add_argument("--fit", help="1-5, or `suggested` (see `jobs score SLUG` for the working)")
    a.add_argument("--note", default="")
    a = js.add_parser("check", help="coverage of a posting by your resume and facts")
    a.add_argument("slug")
    a.add_argument("--resume")
    a = js.add_parser("tailor", help="a checklist for tailoring your resume to one posting")
    a.add_argument("slug")
    a = js.add_parser("status", help="move a role and record the outcome")
    a.add_argument("slug")
    a.add_argument("state")
    a.add_argument("--date")
    a.add_argument("--note", default="")
    a.add_argument("--stage", help="how far you got: none, screen, interview, final, offer")
    a.add_argument("--reason", help="why it closed: rejected, withdrew, filled, posting_gone, no_response, other")
    a.add_argument("--probed", help="comma-separated skills an interviewer asked about")
    js.add_parser("rank", help="what to score, what to apply to, what is in flight")
    a = js.add_parser("board", help="every role in one table")
    a.add_argument("--status")
    a.add_argument("--min-fit", type=float)
    a = js.add_parser("show", help="one role's record")
    a.add_argument("slug")
    js.add_parser("upskill", help="which missing skills your tracked roles ask for most (writes upskill.json)")
    br = js.add_parser("brief", help="a bundle for writing the tailored resume and cover letter")
    br.add_argument("slug")
    og = js.add_parser("org", help="a company's template and profile, learned from its postings")
    og.add_argument("name", help="the company or board org name")
    hd = js.add_parser("headings", help="headings the section reader did not type, counted across postings")
    hd.add_argument("--all", action="store_true", dest="show_all", help="list typed headings too")
    js.add_parser("wants", help="check every role against your [wants] filters (remote, pay floor ...): pass, fail or unknown for each")
    a = js.add_parser("digest", help="read every [sources] board and sort postings into buckets by your [digest] "
                                     "and [wants]: apply first, stretch, worth a look, set aside (writes digests/<date>.md)")
    a.add_argument("--dry-run", action="store_true", help="print the digest; write nothing (seen.json unchanged)")
    a = js.add_parser("check-claims", help="every term a resume states must be held in facts.md")
    a.add_argument("resume")
    a.add_argument("--acronyms", action="store_true", help="also check acronyms outside the lexicon packs")
    a = js.add_parser("graduate", help="skills you have proved, as a line for facts.md")
    a.add_argument("slug")
    a.add_argument("--emit", action="store_true", help="print a block to paste into facts.md")
    js.add_parser("gaps", help="demand buckets and which are planned")
    for verb, run in HANDLERS.items():
        js.choices[verb].set_defaults(run=run)
