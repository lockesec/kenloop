"""Where your data lives, and the settings that shape the loop.

All state lives in ONE directory you own, never inside the package:

    --home DIR  >  $CAREERLOOP_HOME  >  $XDG_DATA_HOME/careerloop  >  ~/.local/share/careerloop

Layout (created by ``careerloop init``)::

    config.toml        settings (below)
    facts.md           what you actually hold — the only source of truth for claims
    roles/<slug>/      one job posting each: meta.json, jd.txt, coverage.json
    topics/<slug>/     one study topic each: topic.json, syllabus.md,
                       questions.md, log.jsonl (the record), concepts.json (derived)
    lexicons/          your own keyword packs (the package ships some too)
    upskill.json       demand for skills you lack, across your roles (derived)

``CAREERLOOP_TODAY=YYYY-MM-DD`` fixes the date (tests and the demo use it).
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import NotEvaluable, UsageError

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

PACKAGE_LEXICONS = Path(__file__).resolve().parent / "lexicons"

DEFAULT_STATUS_WEIGHTS = {
    "found": 1.0, "scored": 1.0, "tailoring": 1.0, "applied": 1.0,
    "interviewing": 1.0, "offer": 0.5, "on-hold": 0.5,
    "rejected": 0.25, "rejected-after-interview": 0.5, "passed": 0.0, "closed": 0.0,
}


SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")


def safe_name(name: str, what: str, exc=None) -> str:
    """A single path component we are willing to build a path from: lower-case
    letters, digits, dot, dash, underscore; no leading dot; never '..'."""
    if not isinstance(name, str) or not SAFE_NAME.match(name) or ".." in name:
        raise (exc or UsageError)(f"{what} {name!r} is not a safe name (a-z, 0-9, '.', '-', '_')")
    return name


_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def iso_date(s) -> _dt.date:
    """A date written exactly YYYY-MM-DD. `date.fromisoformat` alone also takes 20300401 and
    2030-W14-1; a typed date is held to the one form the docs show."""
    if not isinstance(s, str):
        raise TypeError(f"a date is text, not {type(s).__name__}")
    if not _ISO_DATE.fullmatch(s):
        raise ValueError(f"{s!r} is not YYYY-MM-DD")
    return _dt.date.fromisoformat(s)


def today() -> _dt.date:
    v = os.environ.get("CAREERLOOP_TODAY", "").strip()
    if v:
        try:
            return iso_date(v)
        except ValueError as e:
            raise UsageError(f"CAREERLOOP_TODAY={v!r} is not YYYY-MM-DD") from e
    return _dt.date.today()


def resolve_home(flag: str | None = None) -> tuple[Path, str]:
    if flag:
        return Path(flag).expanduser(), "--home"
    env = os.environ.get("CAREERLOOP_HOME", "").strip()
    if env:
        return Path(env).expanduser(), "$CAREERLOOP_HOME"
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "careerloop", "$XDG_DATA_HOME"
    return Path.home() / ".local" / "share" / "careerloop", "default"


@dataclass
class Bucket:
    name: str
    match: list
    action: str = ""
    held_ref: str = ""


@dataclass
class Config:
    home: Path
    packs: list = field(default_factory=list)
    user_lexicon: str = ""
    do_not_claim: set = field(default_factory=set)
    equivalence: dict = field(default_factory=dict)
    ignore: set = field(default_factory=set)
    buckets: list = field(default_factory=list)
    half_life_days: float = 60.0
    probe_bonus: float = 2.0
    status_weights: dict = field(default_factory=lambda: dict(DEFAULT_STATUS_WEIGHTS))
    bar: float = 4.0
    deadline_days: int = 3
    min_bucket_demand: float = 2.0
    targets: list = field(default_factory=list)
    profile: dict = field(default_factory=dict)
    wants: dict = field(default_factory=dict)
    headings: dict = field(default_factory=dict)
    org_aliases: dict = field(default_factory=dict)

    @property
    def facts(self) -> Path:
        return self.home / "facts.md"

    @property
    def roles(self) -> Path:
        return self.home / "roles"

    @property
    def topics(self) -> Path:
        return self.home / "topics"

    @property
    def upskill(self) -> Path:
        return self.home / "upskill.json"


def _num(v, key, lo=0.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < lo:
        raise NotEvaluable(f"config: `{key}` must be a number >= {lo}")
    return float(v)


def _int(v, key, lo=0):
    if isinstance(v, bool) or not isinstance(v, int) or v < lo:
        raise NotEvaluable(f"config: `{key}` must be a whole number >= {lo}")
    return v


def _strs(v, key):
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise NotEvaluable(f"config: `{key}` must be a list of strings")
    return v


def _table(raw, key):
    v = raw.get(key, {})
    if v is None:
        return {}
    if not isinstance(v, dict):
        raise NotEvaluable(f"config: `{key}` must be a table ([{key}])")
    return v


def _list(v, key):
    if v is None:
        return []
    if not isinstance(v, list):
        raise NotEvaluable(f"config: `{key}` must be a list")
    return v


def load_config(home: Path, how: str = "") -> Config:
    """The config of an initialised home. A missing home is NOT EVALUABLE,
    naming the path and how it was resolved; a malformed config names the key."""
    if not home.is_dir():
        raise NotEvaluable(f"no careerloop home at {home} (resolved from {how or 'the given path'}); "
                           f"run `careerloop init`")
    cfg = Config(home=home)
    p = home / "config.toml"
    if not p.exists():
        return cfg
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as e:
        raise NotEvaluable(f"{p} does not parse: {e}") from e
    ats = _table(raw, "ats")
    cfg.packs = [safe_name(n, "config: ats.packs entry", NotEvaluable) for n in _strs(ats.get("packs"), "ats.packs")]
    ul = ats.get("user_lexicon", "") or ""
    if not isinstance(ul, str):
        raise NotEvaluable("config: `ats.user_lexicon` must be a path string")
    cfg.user_lexicon = ul
    cfg.do_not_claim = {s.lower() for s in _strs(ats.get("do_not_claim"), "ats.do_not_claim")}
    eq = _table(ats, "equivalence")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in eq.items()):
        raise NotEvaluable("config: `ats.equivalence` must map strings to strings")
    cfg.equivalence = {k.lower(): v.lower() for k, v in eq.items()}
    gap = _table(raw, "gap")
    cfg.ignore = {s.lower() for s in _strs(gap.get("ignore"), "gap.ignore")}
    for i, b in enumerate(_list(gap.get("bucket"), "gap.bucket")):
        if not isinstance(b, dict) or not isinstance(b.get("name"), str) or not b.get("name"):
            raise NotEvaluable(f"config: `gap.bucket[{i}]` needs a `name`")
        cfg.buckets.append(Bucket(name=b["name"], match=[m.lower() for m in _strs(b.get("match"), f"gap.bucket[{i}].match")],
                                  action=str(b.get("action", "") or ""), held_ref=str(b.get("held_ref", "") or "")))
    dm = _table(raw, "demand")
    if "half_life_days" in dm:
        cfg.half_life_days = _num(dm["half_life_days"], "demand.half_life_days", 1.0)
    if "probe_bonus" in dm:
        cfg.probe_bonus = _num(dm["probe_bonus"], "demand.probe_bonus")
    for k, v in _table(dm, "status_weights").items():
        cfg.status_weights[str(k)] = _num(v, f"demand.status_weights.{k}")
    nx = _table(raw, "next")
    if "bar" in nx:
        cfg.bar = _num(nx["bar"], "next.bar")
    if "deadline_days" in nx:
        cfg.deadline_days = _int(nx["deadline_days"], "next.deadline_days")
    if "min_bucket_demand" in nx:
        cfg.min_bucket_demand = _num(nx["min_bucket_demand"], "next.min_bucket_demand")
    src = _table(raw, "sources")
    for i, t in enumerate(_list(src.get("targets"), "sources.targets")):
        if not isinstance(t, dict) or not isinstance(t.get("board"), str) or not isinstance(t.get("org"), str):
            raise NotEvaluable(f"config: `sources.targets[{i}]` needs string `board` and `org`")
        cfg.targets.append({"board": t["board"], "org": safe_name(t["org"], f"config: sources.targets[{i}].org", NotEvaluable),
                            "note": str(t.get("note", ""))})
    al = src.get("aliases", {}) or {}
    if not isinstance(al, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in al.items()):
        raise NotEvaluable("config: `sources.aliases` must map a board org name to the company it is")
    cfg.org_aliases = {k.strip().lower(): v.strip().lower() for k, v in al.items()}
    prof = _table(raw, "profile")
    cfg.profile = {k: str(v) for k, v in prof.items()}
    from . import wants as _wants
    cfg.wants = _wants.parse(_table(raw, "wants"), NotEvaluable)
    from . import sections as _sections
    allowed = [k for k in _sections.KINDS if k != "none"]
    for k, v in _table(raw, "headings").items():
        if v not in allowed:
            raise NotEvaluable(f"config: [headings] {k!r} = {v!r}: the type must be one of {', '.join(allowed)}")
        cfg.headings[_sections.norm_key(str(k))] = v
    return cfg


def write_text(path: Path, text: str) -> None:
    """Write-then-rename through a unique temp file in the same directory, so a
    crash leaves the old file or the new one, never half of either."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def write_json(path: Path, data) -> None:
    write_text(path, json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def read_text(path: Path, what: str) -> str:
    """The text of a UTF-8 file. One that cannot be read or decoded is NOT EVALUABLE and names
    the file, the byte and the offset; it is never read with replacement characters."""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        raise NotEvaluable(f"{what} {path} is not valid UTF-8 (byte 0x{e.object[e.start]:02x} at offset "
                           f"{e.start}); re-save it as UTF-8") from e
    except OSError as e:
        raise NotEvaluable(f"{what} {path} is unreadable: {e}") from e


def read_json(path: Path, what: str):
    """A missing file is None; a damaged one is NOT EVALUABLE, never {}."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeDecodeError) as e:
        raise NotEvaluable(f"{what} {path} is damaged ({e}); fix or restore it") from e


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)
