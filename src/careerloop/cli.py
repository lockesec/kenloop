"""careerloop command line.

    careerloop [--home DIR] init
    careerloop [--home DIR] jobs  <verb> ...
    careerloop [--home DIR] learn <verb> ...
    careerloop [--home DIR] next [--all] [--json]
    careerloop [--home DIR] doctor

Exit codes: 0 ok · 1 findings · 2 NOT EVALUABLE · 3 drift · 64 usage.
"""
from __future__ import annotations

import argparse
import contextlib
import sys

from . import __version__
from . import home as H
from .errors import NOT_EVALUABLE, OK, USAGE, CareerloopError, NotEvaluable, UsageError

CONFIG_TEMPLATE = """# careerloop settings. Every key is optional.

[profile]
# name = "Your Name"
# resume = "resumes/resume.md"

[ats]
packs = ["web"]                 # keyword packs, in order (shipped: see the package's lexicons/)
# user_lexicon = "lexicons/mine.toml"
# do_not_claim = ["some-term"]  # never counted as held, flagged if a resume states it
# [ats.equivalence]             # posting term = a term you hold that covers it
# "openapi" = "rest"

[gap]
ignore = []                     # terms that are never gaps for you
# group gap terms into study plans; the rest land in "Unmapped: <category>"
bucket = [
  # {name = "Web security", match = ["oauth", "cors", "substr:tls"], action = "what to study"},
]

[demand]
half_life_days = 60
probe_bonus = 2.0

[next]
bar = 4.0
deadline_days = 3
min_bucket_demand = 2.0

[sources]
targets = []                    # e.g. {board = "greenhouse", org = "examplecorp"}
"""

FACTS_TEMPLATE = """# Facts

What you actually hold. Only you edit this file; `init` wrote this template once and
no careerloop command modifies it afterwards. A skill is held only when it is listed under `## Held`. Anything
elsewhere in this file is not held, whatever it says. Keep one skill per line,
and do not put planned, learning or "not yet" skills under Held.

Held is last on purpose: `careerloop learn graduate <topic> --emit >> facts.md`
then lands under it.

## Learning

## Held
"""


def init(home, how) -> int:
    new = not (home / "config.toml").exists()
    for d in ("roles", "topics", "lexicons", "resumes", "fixtures"):
        (home / d).mkdir(parents=True, exist_ok=True)
    made = []
    for name, text in (("config.toml", CONFIG_TEMPLATE), ("facts.md", FACTS_TEMPLATE),
                       (".gitattributes", "topics/*/log.jsonl merge=union\n")):
        p = home / name
        if not p.exists():
            p.write_text(text, encoding="utf-8")
            made.append(name)
    print(f"{'initialised' if new else 'already initialised'}: {home} (from {how})"
          + ("" if new or not made else f"; recreated {', '.join(made)} (the missing file was written "
                                           "from the template)"))
    if new:
        print("next: write facts.md, put a resume at resumes/resume.md, add a [sources] target, "
              "then `careerloop next`")
    return OK


def _count(text: str) -> int:
    """A whole number of at least 1 (a count of items to show or take)."""
    try:
        n = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a whole number") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"{text} must be 1 or more")
    return n


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sub = self.prog.removeprefix("careerloop").strip()   # main() prefixes "careerloop: "
        raise UsageError(f"{sub + ': ' if sub else ''}{message}")


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="careerloop", description="A job search and a study plan that feed each other.")
    p.add_argument("--home", help="data directory (default: $CAREERLOOP_HOME, then the XDG data dir)")
    p.add_argument("--version", action="version", version=f"careerloop {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    sub.add_parser("init", help="create the data directory")
    sub.add_parser("doctor", help="check jobs and study: 0 clean, 1 findings, 2 not evaluable, 3 drift")
    nx = sub.add_parser("next", help="the single most useful thing to do now")
    nx.add_argument("--all", action="store_true", help="print every rule's evaluation")
    nx.add_argument("--json", action="store_true", help="print the chosen action and every rule's evaluation as JSON, for scripts")

    j = sub.add_parser("jobs", help="find roles, measure coverage, track outcomes")
    js = j.add_subparsers(dest="verb", required=True, parser_class=_Parser)
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
    a = js.add_parser("check-claims", help="every term a resume states must be held in facts.md")
    a.add_argument("resume")
    a.add_argument("--acronyms", action="store_true", help="also check acronyms outside the lexicon packs")

    lp = sub.add_parser("learn", help="study what the market wants, with an honest record")
    ls = lp.add_subparsers(dest="verb", required=True, parser_class=_Parser)
    a = ls.add_parser("plan", help="create a topic, optionally seeded from a demand bucket")
    a.add_argument("slug")
    a.add_argument("--title")
    a.add_argument("--goal")
    a.add_argument("--from-gap", metavar="BUCKET")
    a.add_argument("--top", type=_count)
    a.add_argument("--force", action="store_true")
    a = ls.add_parser("sync", help="read new concepts from syllabus.md")
    a.add_argument("slug")
    a = ls.add_parser("bank", help="add a question")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("--q", required=True)
    a.add_argument("--a", required=True)
    a.add_argument("--ref", required=True)
    a.add_argument("--why", default="")
    a.add_argument("--qtype", default="")
    a.add_argument("--d", action="append", default=[], help="'wrong option :: the misconception it encodes'")
    a = ls.add_parser("quiz", help="pick what to practise (weakest first)")
    a.add_argument("slug")
    a.add_argument("--n", type=_count, default=5)
    a.add_argument("--weak", action="store_true")
    a.add_argument("--concept")
    a.add_argument("--interactive", action="store_true", help="ask, hint, reveal and record here")
    a = ls.add_parser("record", help="record one attempt")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("result", choices=["ok", "partial", "miss"])
    a.add_argument("--note", default="")
    a.add_argument("--guess", action="store_true", help="right, but a guess: no credit")
    a.add_argument("--confidence", default="", help="low, med or high, stated before seeing the answer")
    a.add_argument("--hint-depth", type=int, default=0, help="0-4, the highest hint used (0 = none, the default)")
    a.add_argument("--lookup", action="store_true", help="read the answer (hint depth 4)")
    a.add_argument("--mode", default="practice", help="practice, exam, diagnose or learn")
    a.add_argument("--qtype", default="")
    a.add_argument("--etype", default="")
    a = ls.add_parser("due", help="reviews due today")
    a.add_argument("slug", nargs="?")
    a.add_argument("--limit", type=_count, default=20)
    a = ls.add_parser("exam-date", help="show, set or clear a topic's exam date")
    a.add_argument("slug")
    g = a.add_mutually_exclusive_group()
    g.add_argument("--set")
    g.add_argument("--clear", action="store_true")
    a = ls.add_parser("graduate", help="skills you have proved, as a line for facts.md")
    a.add_argument("slug")
    a.add_argument("--emit", action="store_true", help="print a block to paste into facts.md")
    a = ls.add_parser("misconceptions", help="recurring errors and what to do about them")
    a.add_argument("slug")
    a = ls.add_parser("calibration", help="are your confidence ratings honest?")
    a.add_argument("slug")
    ls.add_parser("gaps", help="demand buckets and which are planned")
    a = ls.add_parser("rebuild", help="re-derive state from the log (--check: exit 3 on drift)")
    a.add_argument("slug")
    a.add_argument("--check", action="store_true")
    a.add_argument("--skip-damaged", action="store_true", help="rebuild from the readable log rows only")
    a = ls.add_parser("brief", help="a bundle for writing a topic's questions, in the bank's format")
    a.add_argument("slug")
    a = ls.add_parser("validate", help="integrity of topics and banks")
    a.add_argument("slug", nargs="?")
    return p


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
    from careerloop import ats as _ats
    from careerloop import facts as F_
    if not _ats.has_visible_text(text):
        raise NotEvaluable(f"--jd {'stdin' if arg == '-' else arg} is an empty posting (markup with no visible "
                           "text); nothing was taken in")
    return text


def dispatch(ns) -> int:
    from . import jobs as J
    from . import learn as L
    from . import loop
    from . import sources as S
    home, how = H.resolve_home(ns.home)
    if ns.cmd == "init":
        return init(home, how)
    cfg = H.load_config(home, how)
    if ns.cmd == "next":
        return loop.next_action(cfg, ns.all, ns.json)
    if ns.cmd == "doctor":
        return loop.doctor(cfg)
    v = ns.verb
    if ns.cmd == "jobs":
        if v == "intake":
            slug, created = J.intake(cfg, ns.company, ns.role, _read_jd(ns.jd), ns.url, ns.job_id,
                                     ns.location, ns.salary, ns.status, ns.applied, ns.deadline,
                                     ns.slug or None, ns.force)
            print(f"{slug}: {'taken in' if created else 'exists (pass --force to refresh)'}")
            return OK
        if v == "discover":
            return J.discover(cfg, ns.board, ns.company, ns.all, ns.keyword, ns.intake,
                              ns.exclude_senior, ns.reconcile)
        if v == "reconcile":
            if bool(ns.board) != bool(ns.company):
                raise UsageError("reconcile: pass --board and --company together (or neither, for every [sources] target)")
            if ns.board and ns.board not in S.BOARDS:
                raise UsageError(f"unknown board {ns.board!r} (known: {', '.join(S.BOARDS)})")
            return J.reconcile(cfg, ns.board, ns.company, all_targets=not (ns.board and ns.company))
        if v == "score":
            return J.score(cfg, ns.slug, ns.fit, ns.note)
        if v == "check":
            return J.check(cfg, ns.slug, ns.resume)
        if v == "tailor":
            return J.tailor(cfg, ns.slug)
        if v == "status":
            return J.status(cfg, ns.slug, ns.state, ns.date, ns.note, ns.stage, ns.reason, ns.probed)
        if v == "rank":
            return J.rank(cfg)
        if v == "board":
            return J.board(cfg, ns.status, ns.min_fit)
        if v == "show":
            return J.show(cfg, ns.slug)
        if v == "brief":
            return J.brief(cfg, ns.slug)
        if v == "org":
            return J.org_report(cfg, ns.name)
        if v == "headings":
            return J.headings_report(cfg, ns.show_all)
        if v == "wants":
            return J.wants_report(cfg)
        if v == "upskill":
            return J.upskill(cfg)
        if v == "check-claims":
            return J.check_claims(cfg, ns.resume, ns.acronyms)
    if ns.cmd == "learn":
        if v == "plan":
            return L.plan(cfg, ns.slug, ns.title, ns.goal, ns.from_gap, ns.top, ns.force)
        if v == "sync":
            return L.sync(cfg, ns.slug)
        if v == "bank":
            return L.bank(cfg, ns.slug, ns.concept, ns.q, ns.a, ns.ref, ns.why, ns.qtype, ns.d)
        if v == "quiz":
            if ns.interactive:
                return L.quiz_interactive(cfg, ns.slug, ns.n, ns.weak, ns.concept)
            return L.quiz(cfg, ns.slug, ns.n, ns.weak, ns.concept)
        if v == "record":
            L.record(cfg, ns.slug, ns.concept, ns.result, ns.note, ns.guess, ns.confidence,
                     ns.hint_depth, ns.lookup, ns.mode, ns.qtype, ns.etype)
            return OK
        if v == "due":
            return L.due(cfg, ns.slug, ns.limit)
        if v == "exam-date":
            return L.set_exam_date(cfg, ns.slug, ns.set, ns.clear)
        if v == "graduate":
            return L.graduate(cfg, ns.slug, ns.emit)
        if v == "misconceptions":
            return L.misconceptions(cfg, ns.slug)
        if v == "calibration":
            return L.calibration(cfg, ns.slug)
        if v == "gaps":
            return L.gaps(cfg)
        if v == "rebuild":
            return L.rebuild(cfg, ns.slug, ns.check, ns.skip_damaged)
        if v == "brief":
            return L.brief(cfg, ns.slug)
        if v == "validate":
            return L.validate(cfg, ns.slug)
    raise UsageError(f"unknown command {ns.cmd} {v}")


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):      # a legacy console must not crash after a write
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(errors="replace")
    try:
        ns = build_parser().parse_args(argv)
        return dispatch(ns)
    except CareerloopError as e:
        print(f"careerloop: {e}", file=sys.stderr)
        return e.code
    except UnicodeError as e:         # a lone surrogate or invalid byte in an argument or a posting
        print(f"careerloop: text that cannot be written as UTF-8, result NOT EVALUABLE: {e}", file=sys.stderr)
        return NOT_EVALUABLE
    except SystemExit as e:           # --help / --version
        return e.code if isinstance(e.code, int) else (OK if e.code is None else USAGE)
    except Exception as e:            # never let a crash read as exit 1 ("findings")
        print(f"careerloop: internal error, result NOT EVALUABLE: {type(e).__name__}: {e}", file=sys.stderr)
        return NOT_EVALUABLE
