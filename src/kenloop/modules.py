"""The modules that plug commands into `ken`, in one list (the commands seam).

A module exposes `commands(groups)`: `groups` maps "" to the top-level subparsers and "jobs" to the
job-search group. It adds its verbs there (or its own group, as `cert` does) and gives each one
`set_defaults(run=handler)`, where `handler(cfg, ns) -> exit code`. `cli.dispatch` runs whichever
handler argparse chose; it holds no list of these verbs. Adding a command is one function in its
module and, for a new module, one line here.

The rest of the verbs still live in `cli.py`; they move onto this seam as their modules are split
The module standard (docs/modules.md) is written from what this turns out to be.
"""
from __future__ import annotations

import importlib

MODULES = (
    "kenloop.study",               # the study verbs: plan, bank, quiz, record, talk, place, branch, views, integrity
    "kenloop.career.commands",     # ken jobs ...: the job-search sidecar
    "kenloop.core.settings",       # ken settings
    "kenloop.core.focus",          # ken focus
    "kenloop.core.marks",          # ken mark, ken trail
    "kenloop.session",             # ken session, ken note, ken taught
    "kenloop.journal",             # ken close, ken sessions
    "kenloop.printout",            # ken print: reference sheet and session printouts as pages
    "kenloop.gaps",                # ken gap, ken gaps: misses the teaching caused (tutor_gaps.jsonl)
    "kenloop.scouts",              # ken scout: predicted branches, offered and scored (scouts.jsonl)
    "kenloop.certs",               # ken cert exam | passed | exam-date
    "kenloop.career.promote",      # ken jobs promote
)


def register(groups: dict) -> None:
    for name in MODULES:
        importlib.import_module(name).commands(groups)


def rules() -> list:
    """[(name, fn, after)] from every module that declares `rules()`: the rules seam (loop.RULES)."""
    out = []
    for name in MODULES:
        m = importlib.import_module(name)
        if hasattr(m, "rules"):
            out += m.rules()
    return out


def doctors() -> list:
    """[(module, fn)] for every module that declares `doctor(cfg) -> [(level, text)]`, level one of
    FINDING, NOT EVALUABLE or DRIFT: the doctor seam (loop.doctor prints them, worst wins)."""
    out = []
    for name in MODULES:
        m = importlib.import_module(name)
        if hasattr(m, "doctor"):
            out.append((name, m.doctor))
    return out
