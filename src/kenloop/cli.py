"""kenloop command line.

    ken [--home DIR] init | next [--all] [--json] | doctor
    ken [--home DIR] <study verb> ...     plan, place, quiz, record, due, talk, dive, branch, ask, ...
    ken [--home DIR] jobs <verb> ...      the job-search sidecar
    ken [--home DIR] cert <verb> ...      the exam sidecar

Exit codes: 0 ok · 1 findings · 2 NOT EVALUABLE · 3 drift · 64 usage.
"""
from __future__ import annotations

import argparse
import contextlib
import sys

from . import __version__
from .core import args as A
from .core import home as H
from .core import ledger as LG
from .core.errors import (
    NOT_EVALUABLE,
    OK,
    USAGE,
    KenloopError,
    UsageError,
)

CONFIG_TEMPLATE = "# " + H.NAME + """ settings. Every key is optional.

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
# Workday also needs the career site: {board = "workday", org = "acme",
#   host = "acme.wd1.myworkdayjobs.com", site = "External"}

[digest]                        # `jobs digest`: sort every board's postings into buckets
# families = [                  # a posting's title picks its family (first match wins)
#   {name = "Security operations", match = ["soc", "incident response", "detection"], prefer = true},
#   {name = "Security engineering", match = ["security engineer"], prefer = true},
#   {name = "Threat intelligence", match = ["threat intel", "threat research"]},
# ]
# near = ["austin", "texas"]    # a non-remote posting fits when its location holds one of these
# search = ["security"]         # Workday is searched server side, once per word
# fresh_days = 14               # older postings outside "apply first" are counted, not listed
"""

FACTS_TEMPLATE = f"""# Facts

What you actually hold. Only you edit this file; `init` wrote this template once and
no {H.NAME} command modifies it afterwards. A skill is held only when it is listed under `## Held`. Anything
elsewhere in this file is not held, whatever it says. Keep one skill per line,
and do not put planned, learning or "not yet" skills under Held.

Held is last on purpose: `{H.PROG} jobs graduate <topic> --emit >> facts.md`
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
                       (".gitattributes", LG.gitattributes())):
        p = home / name
        if not p.exists():
            H.write_text(p, text)
            made.append(name)
    print(f"{'initialised' if new else 'already initialised'}: {home} (from {how})"
          + ("" if new or not made else f"; recreated {', '.join(made)} (the missing file was written "
                                           "from the template)"))
    if new:
        print(f"next: plan a topic you want to understand (`{H.PROG} plan SLUG`) or ask a question "
              f"(`{H.PROG} ask \"...\"`); for the job search, list your skills under ## Held in facts.md, put a "
              f"resume at resumes/resume.md and add a [sources] target. Then `{H.PROG} next`")
    return OK


_count = A.count
_Parser = A.Parser


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog=H.PROG, description="Do you ken? Learn what you want to understand, with an honest record of what you know. "
                                         "Sidecars: a job search (jobs) and exam prep (cert).")
    p.add_argument("--home", help="data directory (default: $KENLOOP_HOME, then the XDG data dir)")
    p.add_argument("--version", action="version", version=f"{H.NAME} {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    sub.add_parser("init", help="create the data directory")
    dr = sub.add_parser("doctor", help="check study and the sidecars: 0 clean, 1 findings, 2 not evaluable, 3 drift")
    dr.add_argument("--fix", action="store_true", help="add the .gitattributes lines a declared ledger is missing")
    nx = sub.add_parser("next", help="the single most useful thing to do now")
    nx.add_argument("lane", nargs="?", choices=("career", "interest"),
                    help="career: what may feed facts.md (certs included); interest: studied for its own sake")
    nx.add_argument("--topic", help="only this topic: what to do next inside a study session")
    nx.add_argument("--all", action="store_true", help="print every rule's evaluation")
    nx.add_argument("--candidates", action="store_true", help="also print up to two other things that are ripe")
    nx.add_argument("--json", action="store_true", help="print the chosen action and every rule's evaluation as JSON, for scripts")


    from . import modules
    class _Groups(dict):          # the jobs group is made when its first module registers, so it lists in place
        def __missing__(self, key):
            if key != "jobs":
                raise KeyError(key)
            j = sub.add_parser("jobs", help="find roles, measure coverage, track outcomes")
            self[key] = j.add_subparsers(dest="verb", required=True, parser_class=_Parser)
            return self[key]

    modules.register(_Groups({"": sub}))         # the commands seam: modules add their own verbs
    return p


def dispatch(ns) -> int:
    from . import loop
    from .career import config as CC
    home, how = H.resolve_home(ns.home)
    if ns.cmd == "init":
        return init(home, how)
    cfg = CC.load(home, how)
    if ns.cmd == "next":
        from .core import focus as FO
        lane, topic, label = FO.resolve(cfg, ns.lane, ns.topic)
        return loop.next_action(cfg, ns.all, ns.json, lane, topic, focus_label=label, candidates=ns.candidates)
    if ns.cmd == "doctor":
        return loop.doctor(cfg, fix=ns.fix)
    if getattr(ns, "run", None):             # a verb a module registered (kenloop/modules.py)
        return ns.run(cfg, ns)
    v = getattr(ns, "verb", ns.cmd)
    raise UsageError(f"unknown command {ns.cmd}" + (f" {v}" if v != ns.cmd else ""))


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):      # a legacy console must not crash after a write
        with contextlib.suppress(AttributeError, ValueError):
            stream.reconfigure(errors="replace")
    try:
        ns = build_parser().parse_args(argv)
        return dispatch(ns)
    except KenloopError as e:
        print(f"{H.PROG}: {e}", file=sys.stderr)
        return e.code
    except UnicodeError as e:         # a lone surrogate or invalid byte in an argument or a posting
        print(f"{H.PROG}: text that cannot be written as UTF-8, result NOT EVALUABLE: {e}", file=sys.stderr)
        return NOT_EVALUABLE
    except SystemExit as e:           # --help / --version
        return e.code if isinstance(e.code, int) else (OK if e.code is None else USAGE)
    except Exception as e:            # never let a crash read as exit 1 ("findings")
        print(f"{H.PROG}: internal error, result NOT EVALUABLE: {type(e).__name__}: {e}", file=sys.stderr)
        return NOT_EVALUABLE
