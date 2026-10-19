"""Job boards. Each adapter returns a FetchResult whose status says what
happened: ``ok`` (the board listed postings; a keyword filter may keep none of them),
``empty`` (the board answered with no postings at all) or
``error`` (it did not answer). An error is never an empty board, and an empty
board is never evidence that a posting closed.

Adapters: the public posting APIs of Greenhouse, Lever and Ashby, plus
``fixture`` (a local JSON file, ``HOME/fixtures/<org>.json``, for tests,
demos and boards you copy by hand). Postings are normalised to
``{board, org, ext_id, title, location, url, jd}``; a fixture may add
``deadline``.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import __version__
from . import home as H
from .ats import strip_html

USER_AGENT = f"careerloop/{__version__}"
TIMEOUT = 20
MAX_BYTES = 20_000_000      # a board response larger than this is an error, not a board
MIN_INTERVAL = 1.0          # seconds between requests to one host
_last_hit: dict = {}

SENIOR_RE = re.compile(
    r"\b(senior|sr\.?|staff|principal|lead|director|manager|mgr|vp|vice president|chief|"
    r"head of|distinguished|architect|iii|iv)\b", re.IGNORECASE)


def is_senior(title: str) -> bool:
    """Senior, lead and management titles. "II" is mid-level and kept."""
    return bool(SENIOR_RE.search(title or ""))


@dataclass
class FetchResult:
    status: str                       # ok | empty | error
    postings: list = field(default_factory=list)
    error: str = ""
    total: int = 0                    # postings the board listed, before any keyword filter


def _get_json(url: str):
    host = urllib.parse.urlsplit(url).netloc
    wait = MIN_INTERVAL - (time.monotonic() - _last_hit.get(host, -1e9))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        body = r.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError(f"response larger than {MAX_BYTES} bytes")
    return json.loads(body.decode("utf-8"))


def clean_text(s):
    """Text with each lone surrogate (not encodable as UTF-8) replaced by U+FFFD."""
    if not isinstance(s, str):
        return s
    try:
        s.encode("utf-8")
        return s
    except UnicodeEncodeError:
        return "".join("\ufffd" if "\ud800" <= c <= "\udfff" else c for c in s)


def _norm(board, org, ext_id, title, location, url, jd, **extra) -> dict:
    p = {"board": board, "org": org, "ext_id": "" if ext_id is None else str(ext_id),
         "title": title or "", "location": location or "", "url": url or "", "jd": jd or ""}
    p.update({k: v for k, v in extra.items() if v})
    p["sanitised"] = [k for k, v in p.items() if isinstance(v, str) and clean_text(v) != v]
    for k in p["sanitised"]:
        p[k] = clean_text(p[k])
    if not p["sanitised"]:
        del p["sanitised"]
    return p


_WORKPLACE = {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite", "on-site": "onsite",
              "in-office": "onsite"}


def _workplace(v):
    return _WORKPLACE.get(str(v or "").strip().lower())


def _ashby_pay(j):
    for tier in ((j.get("compensation") or {}).get("compensationTiers") or []):
        for c in tier.get("components") or []:
            if c.get("compensationType") == "Salary" and isinstance(c.get("maxValue"), (int, float)):
                iv = str(c.get("interval") or "").upper()
                interval = "hour" if "HOUR" in iv else "year" if "YEAR" in iv else None
                if interval and c.get("currencyCode"):
                    lo = c.get("minValue") if isinstance(c.get("minValue"), (int, float)) else c["maxValue"]
                    return {"min": lo, "max": c["maxValue"], "currency": c["currencyCode"],
                            "interval": interval, "source": "board field"}
    return None


def _ashby_benefits(j):
    """Benefits the board states as fields: equity, from a compensation component."""
    for tier in ((j.get("compensation") or {}).get("compensationTiers") or []):
        for c in tier.get("components") or []:
            if "equity" in str(c.get("compensationType") or "").lower():
                return ["equity"]
    return None


def _lever_pay(j):
    r = j.get("salaryRange") or {}
    if isinstance(r.get("max"), (int, float)) and r.get("currency"):
        iv = str(r.get("interval") or "").lower()
        interval = "hour" if "hour" in iv else "year" if "year" in iv else None
        if interval:
            return {"min": r.get("min") if isinstance(r.get("min"), (int, float)) else r["max"],
                    "max": r["max"], "currency": r["currency"], "interval": interval,
                    "source": "board field"}
    return None


def _greenhouse(org):
    data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(org)}/jobs?content=true")
    return [_norm("greenhouse", org, j.get("id"), j.get("title"), (j.get("location") or {}).get("name"),
                  j.get("absolute_url"), strip_html(html.unescape(j.get("content") or ""), structure=True))
            for j in data.get("jobs", [])]


def _lever_text(j) -> str:
    """A Lever posting's whole text: the description, then each of `lists` (where Lever keeps
    the requirements) as a `##` heading and its items, then the closing `additional` text."""
    parts = [j.get("descriptionPlain") or strip_html(j.get("description"), structure=True) or ""]
    for item in j.get("lists") or []:
        if isinstance(item, dict):
            head = clean_text(str(item.get("text") or "")).strip()
            body = strip_html(f"<ul>{item.get('content') or ''}</ul>", structure=True).strip()
            parts.append((f"## {head}\n" if head else "") + body)
    extra = j.get("additionalPlain") or strip_html(j.get("additional"), structure=True)
    if extra:
        parts.append(extra)
    return "\n\n".join(p for p in parts if p and p.strip())


def _lever(org):
    data = _get_json(f"https://api.lever.co/v0/postings/{urllib.parse.quote(org)}?mode=json")
    return [_norm("lever", org, j.get("id"), j.get("text"), (j.get("categories") or {}).get("location"),
                  j.get("hostedUrl"), _lever_text(j), workplace=_workplace(j.get("workplaceType")),
                  pay=_lever_pay(j))
            for j in data]


def _ashby(org):
    data = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(org)}"
                     "?includeCompensation=true")
    return [_norm("ashby", org, j.get("id"), j.get("title"), j.get("location"),
                  j.get("jobUrl") or j.get("applyUrl"),
                  j.get("descriptionPlain") or strip_html(j.get("descriptionHtml"), structure=True),
                  workplace=_workplace(j.get("workplaceType")), pay=_ashby_pay(j),
                  board_benefits=_ashby_benefits(j))
            for j in data.get("jobs", [])]


def _fixture(org, cfg):
    p = cfg.home / "fixtures" / f"{org}.json"
    if not p.is_file():
        raise FileNotFoundError(f"no fixture board at {p}")
    if p.stat().st_size > MAX_BYTES:
        raise ValueError(f"{p} is larger than {MAX_BYTES} bytes")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{p} must hold a JSON list of postings")
    for n, j in enumerate(data, 1):
        _check_fixture_entry(p.name, n, j)
    return [_norm("fixture", org, j.get("ext_id"), j.get("title"), j.get("location"), j.get("url"),
                  strip_html(j.get("jd"), structure=True), deadline=j.get("deadline"),
                  workplace=_workplace(j.get("workplace"))) for j in data]


def _check_fixture_entry(name: str, n: int, j) -> None:
    """A fixture posting is an object with a non-empty text title; the other fields are text
    (ext_id may also be a number) or null. Anything else is named, never read as an empty field."""
    if not isinstance(j, dict):
        raise ValueError(f"{name}: entry {n} is not an object (a posting is {{\"title\": ..., ...}})")
    if not isinstance(j.get("title"), str) or not j["title"].strip():
        raise ValueError(f"{name}: entry {n} has no title (a non-empty text field)")
    for k in ("location", "url", "jd", "deadline", "workplace"):
        if j.get(k) is not None and not isinstance(j[k], str):
            raise ValueError(f"{name}: entry {n}: {k} must be text or null, not {type(j[k]).__name__}")
    if j.get("ext_id") is not None and (isinstance(j["ext_id"], bool) or not isinstance(j["ext_id"], (str, int))):
        raise ValueError(f"{name}: entry {n}: ext_id must be text or a whole number or null, "
                         f"not {type(j['ext_id']).__name__}")


BOARDS = {"greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby, "fixture": _fixture}


def fetch(board: str, org: str, cfg, keyword: str | None = None) -> FetchResult:
    fn = BOARDS.get(board)
    if not isinstance(org, str) or not H.SAFE_NAME.match(org or "") or ".." in org:
        return FetchResult("error", error=f"org {org!r} is not a safe name (a-z, 0-9, '.', '-', '_')")
    if fn is None:
        return FetchResult("error", error=f"unknown board {board!r} (known: {', '.join(BOARDS)})")
    try:
        postings = fn(org, cfg) if board == "fixture" else fn(org)
    except (urllib.error.URLError, OSError, ValueError, AttributeError, TypeError, UnicodeDecodeError) as e:
        return FetchResult("error", error=f"{board}:{org}: {e}")
    total = len(postings)
    if not total:
        return FetchResult("empty")                  # the board itself listed nothing
    if keyword:
        postings = [p for p in postings if keyword.lower() in p["title"].lower()]
    return FetchResult("ok", postings, total=total)  # a keyword that matches none is still "ok"
