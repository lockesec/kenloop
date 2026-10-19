"""Where in a posting a line sits: required, preferred, other, or none.

Postings mark what they insist on with headings ("Requirements", "Minimum
qualifications", "What you'll need") and what they would merely like with
others ("Nice to have", "Preferred qualifications", "Bonus"). A line inside a
required section that says "a plus", "preferred" or "ideally" reads preferred.
Headings like "Responsibilities", "About" or "Benefits" close a section: terms
there are what the job does or offers, not what it asks of you.

A posting with no recognised heading has no sections: callers must report the
split as NOT EVALUABLE, never as "0 required".
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A heading is a line that LOOKS like one (a Markdown `#` heading, a line wholly in bold,
# a line ending in a colon, or a line in capitals) and starts with a cue; or a line that is
# nothing but a cue ("Requirements", "Nice to have", "Experience"). "Experience with Splunk",
# "Annual bonus" or "health insurance through our preferred provider" are not headings.
_Q = r"(?:qualifications|skills|experience|requirements|points|knowledge|attributes|education)"
PREFERRED_CUES = (
    rf"(?:preferred|desired|desirable|bonus|additional preferred|optional) {_Q}",
    r"preferred|desired|desirable|bonus|bonus points|pluses|extra credit|ideally",
    r"nice to haves?(?: skills| experience)?|good to haves?|it'?s a plus|would be a plus|"
    r"(?:even )?better if you have|nice if you have|what we value|we'?d love(?: to see)?|"
    r"(?:it'?s )?a bonus if you have|bonus if you have",
)
REQUIRED_CUES = (
    rf"(?:minimum|basic|required|key|core|essential|technical|relevant|must have|your) {_Q}",
    rf"{_Q}(?: (?:and|&) {_Q})?|required|requirements",
    r"what (?:you'?ll|you will|you) (?:need|bring)(?: to (?:the|this|our) \w+)?",
    r"what (?:we'?re|we are) looking for|you have|you'?ll have|who you are|about you|your profile|"
    r"must haves?|you might be a (?:good )?fit if|you may be a (?:good )?fit if|is this you|"
    r"what we require|what (?:we|you) (?:need|require)(?: from you)?|who we'?re looking for",
)
RESPONSIBILITY_CUES = (
    r"(?:(?:key|core|main|primary|your) )?responsibilities|what (?:you'?ll|you will) do|the role|role|"
    r"(?:roles?|duties|tasks)(?: (?:and|&) responsibilities)?|job description|"
    r"what (?:you'?ll|you will) be (?:doing|working on)|what success looks like|"
    r"about this (?:role|job|position)|"
    r"the job|about the (?:role|job|position|opportunity)|the opportunity|day to day|your impact|"
    r"in this role|how you'?ll make an impact|what you'?ll work on|your mission",
)
COMPANY_CUES = (
    r"about(?: [a-z&.'-]+){0,3}|who we are|life at \w+|our culture|why (?:join|work).*|"
    r"why you'?ll love.*|the \w+ experience|our team|the team|our mission|our values|our story|"
    r"what we do|what we'?re building|who we serve",
)
BENEFIT_CUES = (
    r"(?:perks|benefits)(?: (?:and|&) (?:perks|benefits))?(?: (?:at|with|from) [\w&.'-]+(?: [\w&.'-]+){0,3})?|"
    r"\w+ benefits|(?:compensation|salary|total rewards)(?: (?:and|&) (?:benefits|perks|equity|bonus))?|"
    r"pay(?: range| transparency)?|what we offer(?: you)?|we offer(?: you)?|our offer|what'?s in it for you|"
    r"what you'?ll get|what you will get|what you can look forward to.*",
)
LEGAL_CUES = (
    r"equal (?:employment )?opportunity.*|eeo.*|our commitment.*|accommodations?.*|"
    r"(?:applicant |candidate )?privacy.*|e verify.*|pay equity.*|other notices|legal notices?|fair chance.*",
)
LOGISTICS_CUES = (
    r"how to apply|location|work location|travel(?: requirements)?|hiring process|interview process|what to expect|next steps|referral instructions|referrals?",
)
_KINDS = [(k, re.compile("|".join(f"(?:{c})" for c in cues)))
          for k, cues in (("preferred", PREFERRED_CUES), ("required", REQUIRED_CUES),
                          ("responsibilities", RESPONSIBILITY_CUES), ("company", COMPANY_CUES),
                          ("benefits", BENEFIT_CUES), ("legal", LEGAL_CUES),
                          ("logistics", LOGISTICS_CUES))]
# what a line can be: the first two are what the posting asks of you
KINDS = ("required", "preferred", "responsibilities", "company", "benefits", "legal", "logistics",
         "other", "none")
PREFERRED_LINE = re.compile(r"\b(?:a plus|is a plus|preferred|nice to have|nice-to-have|ideally|"
                            r"bonus|desirable)\b", re.IGNORECASE)
BULLET = re.compile(r"^\s*(?:[-*+•·▪–]|\d{1,2}[.)])\s+")
YEARS = re.compile(r"(?<![\d.])(\d{1,2})\s*\+?\s*(?:(?:-|–|to)\s*(\d{1,2})\s*\+?\s*)?"
                   r"(?:years?|yrs?)\b", re.IGNORECASE)


@dataclass
class Line:
    text: str        # the line without its bullet marker
    kind: str        # one of KINDS
    heading: bool
    bullet: bool


def _norm_heading(raw: str) -> tuple:
    """(visible heading text, normalised text for matching, heading-shaped?)."""
    t = raw.strip()
    shaped = t.startswith("#") or t.endswith(":") or (t.startswith("**") and t.endswith("**"))
    text = re.sub(r"^#+\s*", "", t).strip().strip("*_").strip().rstrip(":").strip().strip("*_").strip()
    letters = [c for c in text if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        shaped = True
    n = text.lower().replace("’", "'").replace("-", " ").replace("&", "&")
    n = re.sub(r"\s+", " ", n).strip()
    return text, n, shaped


def norm_key(text: str) -> str:
    """The form a heading is looked up by in `[headings]`: lower case, no `#`, `*`, trailing colon."""
    return _norm_heading(text)[1]


def _heading_kind(raw: str, headings=None):
    """(kind, visible text, typed) when the line opens a section, else None. `typed` is False
    for a heading nobody recognised (kept, as `other`)."""
    text, n, shaped = _norm_heading(raw)
    if headings and n in headings:                 # the user's own mapping wins
        return headings[n], text, True
    # a line that looks like a heading may run longer ("BENEFITS AVAILABLE TO ALL FULL-TIME
    # EMPLOYEES (GLOBAL)"); a bare cue line is short
    if not n or len(n.split()) > (12 if shaped else 8) or n.endswith((".", ",", ";")):
        return None
    md = raw.lstrip().startswith("#")
    for kind, rx in _KINDS:                 # preferred first: "Preferred qualifications"
        if rx.fullmatch(n) or (shaped and rx.match(n) and _ends_on_word(rx, n)
                               and (md or not _requirement_clause(rx, n))):
            return kind, text, True
    if raw.lstrip().startswith("#"):
        # a real heading (Markdown, or an HTML <h1>-<h6>) with no known cue still ends the section
        # above it: its lines are kept, typed `other` (unknown), not read as that section's
        return "other", text, False
    return None


def _not_a_heading(text: str) -> bool:
    """A capitalised line that is a figure, a code or a board tag, not a heading:
    "$138,000 - $189,200 USD", "P25858_3542380", "BI-Remote"."""
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    if digits >= letters or re.fullmatch(r"[A-Z]{2}-[A-Za-z]+", text.strip()):
        return True
    return not any(len(w) >= 3 for w in re.findall(r"[A-Za-z]+", text))


def census(text: str, headings=None) -> list:
    """[(visible text, kind or None)] for every heading-shaped line: a `#` heading, a line in
    capitals, wholly bold or ending in a colon. kind is None when nothing typed it."""
    out = []
    for raw in (text or "").splitlines():
        if BULLET.match(raw) or not raw.strip():
            continue
        vis, n, shaped = _norm_heading(raw)
        if not shaped or not n or len(n.split()) > 12 or n.endswith((".", ",", ";")):
            continue
        if _not_a_heading(vis):
            continue
        hk = _heading_kind(raw, headings)
        out.append((vis, hk[0] if hk and hk[2] else None))
    return out


def _requirement_clause(rx, n: str) -> bool:
    """A cue followed by a with/in/of/and clause of more than three words is a requirement
    written in capitals or bold ("EXPERIENCE WITH KAFKA AND HELM IN PRODUCTION"), not a heading."""
    m = rx.match(n)
    rest = n[m.end():].split() if m else []
    return len(rest) > 3 and rest[0] in ("with", "in", "of", "and", "using", "on", "across")


def _ends_on_word(rx, n: str) -> bool:
    m = rx.match(n)
    return bool(m) and (m.end() == len(n) or n[m.end()] == " ")


def split(text: str, headings=None) -> list:
    """Lines with their kind. `headings` maps a heading's lookup form (norm_key) to a kind."""
    out, kind = [], "none"
    for raw in (text or "").splitlines():
        m = BULLET.match(raw)
        body = raw[m.end():].strip() if m else raw.strip()
        if not body:
            out.append(Line("", kind, False, False))
            continue
        hk = None if m else _heading_kind(body, headings)
        if hk:
            kind = hk[0]
            out.append(Line(hk[1], kind, True, False))
            continue
        k = kind
        if k == "required" and PREFERRED_LINE.search(body):
            k = "preferred"
        out.append(Line(body, k, False, bool(m)))
    return out


def found(lines: list) -> bool:
    return any(ln.heading and ln.kind in ("required", "preferred") for ln in lines)


def requirement_lines(lines: list) -> list:
    """The lines that state what the posting asks for: every non-heading line in a required or
    preferred section; with no sections, every bullet (the best available guess)."""
    if found(lines):
        return [ln for ln in lines if ln.text and not ln.heading
                and ln.kind in ("required", "preferred")]
    return [ln for ln in lines if ln.text and ln.bullet]


def years(lines: list) -> list:
    """Years-of-experience asks: a number of years on a line that mentions experience."""
    out = []
    for ln in lines:
        if ln.heading or "experience" not in ln.text.lower():
            continue
        m = YEARS.search(ln.text)
        if not m:
            continue
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else None
        out.append({"min": lo, "max": hi, "kind": ln.kind, "text": ln.text})
    return out
