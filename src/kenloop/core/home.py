"""Where your data lives, and the settings that shape the loop.

All state lives in ONE directory you own, never inside the package:

    --home DIR  >  $KENLOOP_HOME  >  $XDG_DATA_HOME/kenloop  >  ~/.local/share/kenloop

Layout (created by ``ken init``)::

    config.toml        settings (below)
    facts.md           what you actually hold — the only source of truth for claims
    roles/<slug>/      one job posting each: meta.json, jd.txt, coverage.json
    topics/<slug>/     one study topic each: topic.json, syllabus.md,
                       questions.md, log.jsonl (the record), concepts.json (derived)
    lexicons/          your own keyword packs (the package ships some too)
    upskill.json       demand for skills you lack, across your roles (derived)

``KENLOOP_TODAY=YYYY-MM-DD`` fixes the date (tests and the demo use it).
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
from .names import SAFE_NAME, safe_name  # noqa: F401  (H.safe_name, H.SAFE_NAME)

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

NAME = "kenloop"   # the product: package, data directory, version, user agent, prose
PROG = "ken"       # the command, in every suggested command line

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
    v = os.environ.get("KENLOOP_TODAY", "").strip()
    if v:
        try:
            return iso_date(v)
        except ValueError as e:
            raise UsageError(f"KENLOOP_TODAY={v!r} is not YYYY-MM-DD") from e
    return _dt.date.today()


def resolve_home(flag: str | None = None) -> tuple[Path, str]:
    if flag:
        return Path(flag).expanduser(), "--home"
    env = os.environ.get("KENLOOP_HOME", "").strip()
    if env:
        return Path(env).expanduser(), "$KENLOOP_HOME"
    xdg = os.environ.get("XDG_DATA_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / NAME, "$XDG_DATA_HOME"
    return Path.home() / ".local" / "share" / NAME, "default"


@dataclass
class Config:
    home: Path
    raw: dict = field(default_factory=dict)   # config.toml, parsed; sidecars read their sections

    @property
    def topics(self) -> Path:
        return self.home / "topics"


def load_config(home: Path, how: str = "") -> Config:
    """The config of an initialised home: the path and the parsed config.toml. A missing home
    is NOT EVALUABLE, naming the path and how it was resolved; so is a file that does not parse.
    Each sidecar reads and checks its own sections (kenloop.career.config)."""
    if not home.is_dir():
        raise NotEvaluable(f"no {NAME} home at {home} (resolved from {how or 'the given path'}); "
                           f"run `{PROG} init`")
    p = home / "config.toml"
    if not p.exists():
        return Config(home=home)
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as e:
        raise NotEvaluable(f"{p} does not parse: {e}") from e
    return Config(home=home, raw=raw)


def write_text(path: Path, text: str) -> None:
    """Write-then-rename through a unique temp file in the same directory, so a
    crash leaves the old file or the new one, never half of either."""
    _write(path, "w", text)


def write_bytes(path: Path, data: bytes) -> None:
    """write_text for exact bytes (no encoding, no newline translation)."""
    _write(path, "wb", data)


def _write(path: Path, mode: str, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as fh:
            fh.write(data)
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


def one_line(value, what: str):
    """``value`` unchanged, or a UsageError when it holds a line break: it becomes one line of a
    Markdown file, where a newline would start a section or an entry of its own."""
    if isinstance(value, str) and re.search(r"[\r\n\v\f\x1c-\x1e\x85  ]", value):
        raise UsageError(f"{what} must be one line (it holds a line break)")
    return value


def warn(msg: str) -> None:
    print(msg, file=sys.stderr)
