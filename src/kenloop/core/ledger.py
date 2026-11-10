"""Ledgers: the append-only JSON-lines records, read and written one way.

Every record kenloop keeps as history (the topic log, placements, recalls, renames, promotions,
questions asked, branch decisions, scouted branches) is a ledger. One reader and one writer give them
the same rules, which seven hand-written copies had drifted apart on (recall appended past a damaged
line; promotions refused while branches skipped):

- **read** returns (rows, problems). A line that cannot be decoded, parsed or checked is a PROBLEM,
  reported with its file and line number, never skipped in silence and never replayed half-read.
  A STRICT ledger raises instead: reading it in part changes meaning (a skipped revoke turns a
  withdrawn claim back on; a skipped rename splits a concept's history).
- **append** refuses past damage: a row appended to a ledger that cannot be read in full would be
  read against a record nobody can check.
- **order is position**: a reader that needs "since X" uses the row's index in the file, never its
  date (two rows can share a day).
- Every ledger is DECLARED in `LEDGERS`; the declaration writes `.gitattributes` (`merge=union`, so
  two machines appending to one ledger merge line by line) and the docs' list of your data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .errors import NotEvaluable


@dataclass(frozen=True)
class Ledger:
    file: str           # file name
    scope: str          # "home" (one per study home) or "topic" (one per topic directory)
    what: str           # one line for the docs
    strict: bool = False


LEDGERS = (
    Ledger("log.jsonl", "topic", "every answer, dialogue and taught concept: the study record"),
    Ledger("placement.jsonl", "topic", "placement answers on the topic's scale"),
    Ledger("recall.jsonl", "topic", "what you listed when recalling a concept's pieces"),
    Ledger("renames.jsonl", "topic", "concept renames, so history follows a renamed concept", strict=True),
    Ledger("promotions.jsonl", "topic", "interest concepts promoted to job skills, and revoked", strict=True),
    Ledger("marks.jsonl", "topic", "how an idea feels to you: problem, fuzzy, solid (last row wins; never evidence)"),
    Ledger("asks.jsonl", "home", "questions you asked and the rungs built under them"),
    Ledger("branches.jsonl", "home", "every branch decision: piece, before, topic, note, declined"),
    Ledger("scouts.jsonl", "home", "scouted (predicted) branches, decided through branches.jsonl"),
    Ledger("sessions.jsonl", "home", "the session journal: one closed study session per row (never evidence)"),
    Ledger("tutor_gaps.jsonl", "home", "misses the teaching caused, counted against the tutor (never evidence)"),
    Ledger("focus.jsonl", "home", "where `next` points: every pivot, its day and why (last row wins)", strict=True),
    Ledger("trail.jsonl", "home", "the path from what started a study thread: each step down and back", strict=True),
)


def declared(name: str) -> Ledger:
    for d in LEDGERS:
        if d.file == name:
            return d
    raise KeyError(f"{name} is not a declared ledger (core/ledger.py LEDGERS)")


def gitattributes() -> str:
    """One merge=union line per declared ledger."""
    return "".join(f"{'topics/*/' if d.scope == 'topic' else ''}{d.file} merge=union\n" for d in LEDGERS)


def _lines(p: Path) -> tuple:
    """[(n, text)] and problems: a line that is not UTF-8 is a problem; the others still read."""
    raw = p.read_bytes()
    try:
        return [(n, t.rstrip("\r")) for n, t in enumerate(raw.decode("utf-8").split("\n"), 1)], []
    except UnicodeDecodeError:
        out, problems = [], []
        for n, b in enumerate(raw.split(b"\n"), 1):
            try:
                out.append((n, b.decode("utf-8").rstrip("\r")))
            except UnicodeDecodeError as e:
                problems.append(f"{p.name} line {n}: not UTF-8 (byte 0x{e.object[e.start]:02x} at offset {e.start})")
        return out, problems


def read(p: Path, check=None) -> tuple:
    """(rows, problems) from one ledger file; `check(row)` raises ValueError/KeyError/TypeError on a
    row it cannot accept. A missing file is ([], []): nothing recorded yet."""
    p = Path(p)
    if not p.exists():
        return [], []
    lines, problems = _lines(p)
    rows = []
    for n, line in lines:
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if not isinstance(r, dict):
                raise TypeError("not a JSON object")
            if check:
                check(r)
        except (ValueError, KeyError, TypeError) as err:
            problems.append(f"{p.name} line {n}: {err}")
            continue
        rows.append(r)
    if problems and declared_strict(p.name):
        raise NotEvaluable(f"{p} is damaged ({problems[0]}); it cannot be read in part, because a skipped "
                           "row would change what the rest means. Fix the line by hand")
    return rows, problems


def declared_strict(name: str) -> bool:
    return any(d.file == name and d.strict for d in LEDGERS)


def append(p: Path, row: dict, check=None, verified: bool = False) -> dict:
    """Append one row; refused (NotEvaluable) when the ledger is already damaged. `verified`: the
    caller has just read the whole ledger and refused on damage itself (the study log's writers do),
    so it is not read twice."""
    p = Path(p)
    _rows, problems = ([], []) if verified else read(p, check)
    if problems:
        raise NotEvaluable(f"{len(problems)} damaged line(s) in {p.name} (first: {problems[0]}); nothing appended "
                           "past the damage. Fix the line, then try again")
    if check:
        check(row)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:            # an append is the record's own unit
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row
