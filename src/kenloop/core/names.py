"""Names: turning text into slugs, and checking a name is safe to build a path from.

Shared by study and the job search, so it depends on neither.
"""
from __future__ import annotations

import re

from .errors import UsageError

_TRANSLIT = str.maketrans({"ß": "ss", "ẞ": "SS", "æ": "ae", "Æ": "AE", "œ": "oe",
                           "Œ": "OE", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L",
                           "đ": "d", "Đ": "D", "ð": "d", "Ð": "D", "þ": "th",
                           "Þ": "TH", "ı": "i"})


def slugify(s: str) -> str:
    """Lower-case ASCII words joined by hyphens. Accents are removed first (NFKD), so "Café Ünï"
    gives "cafe-uni" rather than losing the letters."""
    import unicodedata
    t = (s or "").translate(_TRANSLIT)
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")


def safe_name(name: str, what: str, exc=None) -> str:
    """A single path component we are willing to build a path from: lower-case
    letters, digits, dot, dash, underscore; no leading dot; never '..'."""
    if not isinstance(name, str) or not SAFE_NAME.match(name) or ".." in name:
        raise (exc or UsageError)(f"{what} {name!r} is not a safe name (a-z, 0-9, '.', '-', '_')")
    return name
