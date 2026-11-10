"""Keyword coverage: which terms a posting asks for, and which you state or hold.

Terms come from LEXICON PACKS, TOML files of categorised terms. Packs ship with
the package (``kenloop/career/lexicons/``); your own go in ``HOME/lexicons/`` and
win on a name clash. Nothing about any one person is built in.

For a posting and a resume, every extracted term is exactly one of:

- present   the resume states it;
- equiv     the resume states an equivalent term AND the facts sheet holds that
            equivalent (an equivalence to something you do not hold is not cover);
- missing   neither. A missing term is then split by the facts sheet into
            held-but-unstated (a resume fix: state the literal term) and
            not held (a real gap: study it, or leave it off; never claim it).
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.errors import NotEvaluable
from ..core.home import tomllib
from . import facts as F
from . import sections as S

PACKAGE_LEXICONS = Path(__file__).resolve().parent / "lexicons"

# ALLCAPS and CamelCase tokens ("SIEM", "GitHub"; not "Python").
ACRONYM_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*[A-Z0-9][A-Za-z0-9+/.&-]*)\b")
ACRONYM_NOISE = {
    "eeo", "eoe", "usd", "pto", "401k", "faq", "ceo", "cto", "cfo", "hr", "us", "usa", "uk",
    "ii", "iii", "iv", "ok", "etc", "ie", "eg", "bs", "ba", "ms", "phd", "gpa", "ada",
    "llc", "inc", "ltd", "am", "pm", "est", "pst", "cst", "utc", "tbd", "asap", "fte",
    "api", "apis", "nyc", "sf", "la", "dc", "eu", "eur", "gbp", "cad", "aud", "emea", "apac",
    "latam", "ll", "ve", "re",
    # time zones: shift hours, not skills
    "aest", "aedt", "awst", "acst", "nzst", "nzdt", "gmt", "bst", "cet", "cest", "eet", "ist", "jst",
    "sgt", "hkt", "edt", "pdt", "cdt", "mst", "mdt", "akst", "hst",
}
_FUNCTION_WORDS = {"the", "you", "we", "our", "what", "about", "and", "for", "to", "of", "with",
                   "your", "is", "are", "will", "who", "why", "how", "in", "on", "a", "an"}
# Section headings that job posts write in capitals.
STRUCTURAL = {
    "about", "requirements", "responsibilities", "qualifications", "preferred", "required",
    "benefits", "overview", "summary", "role", "team", "you", "we", "our", "the", "and",
    "what", "who", "why", "how", "bonus", "nice", "must", "have", "plus", "note", "apply",
}
# English words that a posting writes in capitals for emphasis ("this role is NOT for ..."): not skills
CAPS_WORDS = {
    "not", "and", "or", "all", "any", "the", "for", "but", "are", "was", "has", "had", "can", "may", "will",
    "with", "from", "this", "that", "into", "over", "per", "via", "yes", "only", "also", "than", "then",
    "they", "them", "what", "when", "where", "which", "who", "why", "how", "each", "both", "more", "most",
    "such", "very", "just", "like", "your", "their", "its", "our", "you", "must", "should", "would", "could",
    "nor", "off", "out", "now", "new", "one", "two", "too", "own", "same", "other", "none", "never",
}
# job codes, roman numerals, and board tags such as LI-Remote or BI-Hybrid
JOB_CODE_RE = re.compile(r"^([A-Z]\d{4}-\d{4}|[A-Z]\d{5,7}|LI-\w+|[A-Z]{2}-(?:Remote|Hybrid|Onsite|Office)|[IVX]+)$")
MAX_TERM_WORDS = 8     # a lexicon term longer than this is skipped with a warning (see docs/trust-rules.md)


def _warn(msg: str) -> None:
    import sys
    print(msg if msg.startswith("warn:") else "warn: " + msg, file=sys.stderr)


#: A tag, a comment, a declaration or a processing instruction: a `<` that starts none of these
#: (`<3 years`) is text and stays.
#: Tags a browser lays out as blocks: they end lines, so words in two list items, paragraphs, cells
#: or headings are never one phrase (a multiword term never joins across a line break).
_BLOCK_TAGS = frozenset("""br hr p li ul ol div section article header footer nav aside main table thead
tbody tfoot tr td th dl dt dd h1 h2 h3 h4 h5 h6 blockquote pre figure figcaption address details
summary center form fieldset legend caption body html head video audio canvas iframe object noscript
menu hgroup search dialog select option textarea""".split())
#: Elements whose text keeps its line breaks when rendered.
_PRE_TAGS = frozenset({"pre", "textarea", "listing", "plaintext", "xmp"})
#: Elements whose content is not shown.
_HIDDEN_BODY_TAGS = frozenset({"script", "style", "template"})
#: In plain text (no block tag anywhere), only these inline tags are markup; any other `<word>`
#: (`List<String>`) is text.
_PLAIN_INLINE_TAGS = frozenset("a b i u em strong span small sup sub code font abbr mark s".split())
_TAG_AT = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9-]*)(?![A-Za-z0-9-])[^<>]*>")
_BLOCK_PROBE = re.compile(r"<\s*/?\s*(" + "|".join(sorted(_BLOCK_TAGS, key=len, reverse=True))
                          + r")(?![A-Za-z0-9-])", re.IGNORECASE)


_HEADING_TAGS = frozenset("h1 h2 h3 h4 h5 h6".split())


def strip_html(text: str, structure: bool = False) -> str:
    """Visible text, in one linear left-to-right pass. In markup (a block tag is present) a source
    line break is a space, as a browser renders it, except inside `<pre>` and the like; block tags
    end lines and inline tags are a space; comments, `<!...>` declarations, `<?...?>` and the
    bodies of `<script>`, `<style>` and `<template>` are dropped (an unclosed comment or script
    hides the rest, as in a browser). Plain text keeps its own lines, and only common inline tags
    are removed from it. A `<` that starts no tag (`<3 years`) is text."""
    t = text or ""
    markup = bool(_BLOCK_PROBE.search(t))
    out: list[str] = []
    pos, n, pre = 0, len(t), 0

    def emit(chunk: str) -> None:
        if markup and not pre:
            chunk = re.sub(r"\r\n|\r|\n", " ", chunk)   # the readers collapse white space later
        out.append(chunk)

    low = None
    while pos < n:
        lt = t.find("<", pos)
        if lt < 0:
            emit(t[pos:])
            break
        emit(t[pos:lt])
        if t.startswith("<!--", lt):
            e = t.find("-->", lt + 4)
            pos = n if e < 0 else e + 3
            out.append(" ")
            continue
        if t.startswith(("<!", "<?"), lt) and lt + 2 < n and (t[lt + 2].isalpha() or t[lt + 1] == "?"):
            e = t.find(">", lt + 2)
            pos = n if e < 0 else e + 1
            out.append(" ")
            continue
        m = _TAG_AT.match(t, lt)
        if not m:
            out.append("<")
            pos = lt + 1
            continue
        name = m.group(2).lower()
        closing = bool(m.group(1))
        if not markup and name not in _PLAIN_INLINE_TAGS:
            out.append("<")
            pos = lt + 1
            continue
        pos = m.end()
        if name in _HIDDEN_BODY_TAGS and not closing:
            if low is None:
                low = t.lower()
            e = low.find("</" + name, pos)
            if e < 0:
                pos = n
            else:
                g = t.find(">", e)
                pos = n if g < 0 else g + 1
            out.append(" ")
            continue
        if name in _PRE_TAGS:
            pre = max(0, pre + (-1 if closing else 1))
        # with `structure` (postings), a list item starts a `- ` line and a heading a `## ` line,
        # so the section reader never takes a list item for a heading
        if structure and not closing and name == "li":
            out.append("\n\n- ")
        elif structure and not closing and name in _HEADING_TAGS:
            out.append("\n\n## ")
        else:
            out.append("\n\n" if name in _BLOCK_TAGS else " ")
    return html.unescape("".join(out))


def has_visible_text(text: str) -> bool:
    """True when `text` shows something: a letter, digit, punctuation or symbol character once markup
    (also markup written as entities) is removed. White space, controls, format and private-use
    characters and lone combining marks show nothing."""
    import unicodedata
    t = strip_html(html.unescape(strip_html(text or "")))
    return any(unicodedata.category(c)[0] in "LNPS" for c in t)


@dataclass
class Lexicon:
    terms: list          # [(term_lower, "pack/category")] in load order; first wins
    acronym_noise: set
    aliases: dict = field(default_factory=dict)   # other spelling (lower) -> term

    def forms(self, term: str) -> list:
        """The term and every alias that names it: one skill, several spellings."""
        t = term.lower()
        return [t] + [a for a, c in self.aliases.items() if c == t]

    def holds(self, term: str, facts: str) -> bool:
        """Held under any of its spellings (an alias is the same skill, unlike an
        `[ats] equivalence`, which is a related one and must be stated literally)."""
        return any(F.holds(f, facts) for f in self.forms(term))

    def words(self):
        """Every spelling the packs know, for the disguised-word check."""
        return F.lexicon_words([t for t, _c in self.terms] + list(self.aliases))

    def category(self, term: str) -> str:
        t = term.lower()
        for x, c in self.terms:
            if x == t:
                return c
        return "acronym"


def _load_pack(path: Path) -> tuple:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise NotEvaluable(f"lexicon pack {path} does not parse: {e}") from e
    name = str(raw.get("name") or path.stem)
    cats = raw.get("categories", {}) or {}
    if not isinstance(cats, dict):
        raise NotEvaluable(f"lexicon pack {path}: `categories` must be a table")
    terms = []
    for cat, words in cats.items():
        if not isinstance(words, list) or not all(isinstance(w, str) and w.strip() for w in words):
            raise NotEvaluable(f"lexicon pack {path}: `categories.{cat}` must be a list of terms")
        for w in words:
            n = len([x for x in re.split("[\\s" + F._JOINER_CLASS + "]+", w.strip()) if x])
            if n > MAX_TERM_WORDS:
                # the disguise check reads windows of as many words as the longest term has
                _warn(f"lexicon pack {path}: the term {w.strip()[:60]!r} has {n} words (more than "
                       f"{MAX_TERM_WORDS}) and is skipped")
                continue
            terms.append((w.strip().lower(), f"{name}/{cat}"))
    ext = raw.get("extraction", {}) or {}
    noise = {s.lower() for s in ext.get("acronym_noise", []) or []}
    al = raw.get("aliases", {}) or {}
    if not isinstance(al, dict) or not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
                                           for k, v in al.items()):
        raise NotEvaluable(f"lexicon pack {path}: `aliases` must map spellings to terms (strings)")
    aliases = {k.strip().lower(): v.strip().lower() for k, v in al.items()}
    return terms, noise, aliases


def pack_path(cfg, name: str) -> Path:
    for base in (cfg.home / "lexicons", PACKAGE_LEXICONS):
        p = base / f"{name}.toml"
        if p.exists():
            return p
    raise NotEvaluable(f"lexicon pack {name!r} not found in {cfg.home / 'lexicons'} or the package "
                       f"(shipped: {', '.join(sorted(p.stem for p in PACKAGE_LEXICONS.glob('*.toml')))})")


def on_do_not_claim(term: str, cfg, lex=None) -> bool:
    """Listed under [ats] do_not_claim by any spelling of the same skill (the term or an alias)."""
    t = term.lower()
    if t in cfg.do_not_claim:
        return True
    return lex is not None and any(f in cfg.do_not_claim for f in lex.forms(lex.aliases.get(t, t)))


def claimable(term: str, facts: str, cfg, lex=None) -> bool:
    """May a resume state this term: held in facts.md (under any spelling the lexicon knows) and
    not listed under [ats] do_not_claim. With no lexicon (a missing pack), literal spellings only."""
    t = term.lower()
    held = lex.holds(t, facts) if lex is not None else F.holds(t, facts)
    return held and not on_do_not_claim(t, cfg, lex)


def load_lexicon(cfg) -> Lexicon:
    """The configured packs in order, then the user lexicon. A pack that is
    named but cannot be found is NOT EVALUABLE, never silently skipped."""
    paths = [pack_path(cfg, n) for n in cfg.packs]
    if cfg.user_lexicon:
        p = cfg.home / cfg.user_lexicon
        if not p.exists():
            raise NotEvaluable(f"user lexicon {p} does not exist")
        paths.append(p)
    terms, noise, seen, aliases = [], set(ACRONYM_NOISE), set(), {}
    for p in paths:
        t, n, a = _load_pack(p)
        for term, cat in t:
            if term not in seen:
                seen.add(term)
                terms.append((term, cat))
        noise |= n
        for k, v in a.items():
            aliases.setdefault(k, v)
    kept = {}
    for k, v in aliases.items():
        if v not in seen:
            _warn(f"lexicon: alias {k!r} names {v!r}, which no loaded pack has; skipped")
        elif k in seen:
            _warn(f"lexicon: {k!r} is both a term and an alias of {v!r}; read as the term")
        else:
            kept[k] = v
    return Lexicon(terms, noise, kept)


def _bounded(term: str) -> str:
    return rf"(?<![a-z0-9]){F.term_pattern(term)}(?![a-z0-9])"


def _shouted(line: str) -> bool:
    """A heading written in capitals ("ABOUT THE JOB", "PERKS"), not a skill list."""
    s = line.strip().rstrip(":")
    if not s or s[0] in "-*+" or not any(c.isalpha() for c in s) or s != s.upper():
        return False
    words = re.findall(r"[A-Za-z']+", s)
    if len(words) == 1:
        return len(words[0]) >= 5
    # "UNITED STATES", "REFERRAL INSTRUCTIONS": a short capitalised line with a long word and no
    # list punctuation is a heading; "SIEM SOAR EDR" or "SIEM, SOAR" is not
    if len(words) <= 8 and not re.search(r"[,/;|]", s) and any(len(w) >= 6 for w in words):
        return True
    return any(w.lower() in _FUNCTION_WORDS for w in words)


def _skill_line(body: str, pos: int, forms: list) -> bool:
    """True when the line holding `pos` also holds a known lexicon term: the only company in which
    a two-letter capital pair ("ES" in "Splunk ES") is read as a skill and not as prose noise."""
    start = body.rfind("\n", 0, pos) + 1
    end = body.find("\n", pos)
    line = F.normalize(body[start:end if end >= 0 else len(body)])
    return any(F.token_in(f, line) for f in forms)


def extract(text: str, lex: Lexicon, excluded=(), acronyms: bool = True) -> list:
    """Terms a text asks for: lexicon terms first (whole tokens, on the
    normalised text), then acronyms and CamelCase names (on the original text).

    A lexicon term that only ever occurs inside a longer matched term counts
    once, as the longer term ("http" inside "http/2"). Case-insensitively
    de-duplicated, first spelling wins. Web addresses are not read (F.mask_urls). `excluded` (the company's own name)
    removes any term that contains it as a whole token."""
    text = F.mask_urls(text or "")
    norm = F.normalize(text)                  # before fold: a soft hyphen is read as a space too
    text = F.fold(text)
    # Every spelling the packs know, terms and aliases alike, is a surface. A surface that only
    # ever occurs inside a longer matched surface counts once, as the longer one ("http" inside
    # "http/2", "sentinel" inside "sentinel one", "azure" inside "azure ad"); an alias counts as
    # its term. Each term is kept once, first spelling wins.
    surfaces = [(t, t) for t, _c in lex.terms] + list(lex.aliases.items())
    found = [(f, c) for f, c in surfaces if F.token_in(f, norm)]
    forms = [f for f, _c in found]
    kept, used = [], []
    for f, c in found:
        # strictly longer: two spellings of one phrase ("sentinel one", "sentinel-one") contain
        # each other and must not cancel each other out
        longer = [o for o in forms if o != f and F.token_in(f, o) and not F.token_in(o, f)]
        rest = norm
        for o in longer:
            rest = re.sub(_bounded(o), " ", rest)
        if F.token_in(f, rest):
            used.append(f)
            if c not in kept:
                kept.append(c)
    # an acronym that is a word of a matched surface ("AD" in "Azure AD", "ATLAS" in "MITRE
    # ATLAS") is that surface, not a term of its own
    inside = {w for f in used for w in re.split("[\\s" + F._JOINER_CLASS + "]+", f) if w}
    seen = set(kept)
    body = "\n".join(ln for ln in (text or "").splitlines() if not _shouted(ln)) if acronyms else ""
    for m in ACRONYM_RE.finditer(body):
        a = m.group(1).rstrip(".-")
        adj = re.fullmatch(r"([A-Z0-9]{2,})-[a-z]+", a)      # "AI-generated", "SIEM-based": an adjective
        if adj:
            a = adj.group(1)
        low = a.lower()
        if (not 2 <= len(a) <= 20 or "/" in a or low in lex.acronym_noise or low in STRUCTURAL
                or low in CAPS_WORDS or low in lex.aliases or low in inside
                or ("&" in a and all(len(x) <= 2 for x in a.split("&")))      # "DE&TH", "R&D", "M&A"
                or (len(a) == 2 and not _skill_line(body, m.start(), forms))
                or JOB_CODE_RE.match(a) or low in seen or body[max(0, m.start() - 1):m.start()] in ("'", "\u2019")):
            continue
        seen.add(low)
        kept.append(a)
    ex = [F.normalize(e) for e in excluded if e and e.strip()]
    return [k for k in kept if not any(F.token_in(e, k.lower()) for e in ex)]


_LATEX_BREAK = re.compile(
    r"\\(?:item|par|newline|linebreak|break|pagebreak|newpage|clearpage|hline|cline|midrule|toprule|bottomrule"
    r"|bigskip|medskip|smallskip|vfill|vspace|vskip|textbullet"
    r"|begin|end|(?:sub){0,2}section|chapter|(?:sub)?paragraph|part|cventry|cvitem|cvitemwithcomment"
    r"|cvlistitem|cvlistdoubleitem|cvdoubleitem|cventry|skillitem|entry"
    r"|resumeItem\w*|resumeSubItem\w*|resumeSubheading\w*|resumeSubSubheading\w*|resumeProjectHeading\w*)"
    r"(?![a-zA-Z])\*?(?:\[[^\]\n]{0,200}\])?((?:\s*\{[^{}\n]{0,500}\}){0,4})")


#: Markup between two letters of one word: Dock**er**, Dock<span></span>er, Dock&#101;r, Dock[er](url).
_SPLIT_WORD = re.compile(r"[A-Za-z](?:\*{1,3}|_{2,3}|~~|`+|<[^>\n]{0,80}>|&#?\w{1,8};|\[)+[A-Za-z][^\s]{0,40}")


def resume_text(path: Path) -> str:
    """Markdown or plain text as is; LaTeX with comments and commands removed
    (``\\&`` survives as ``&``)."""
    try:
        data = path.read_bytes()
    except OSError as e:
        raise NotEvaluable(f"resume {path} is unreadable: {e}") from e
    cause = ""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        cause = "it starts with a UTF-16 or UTF-32 byte-order mark"
    elif b"\x00" in data:
        cause = "it contains a NUL byte (UTF-16 or a binary file)"
    else:
        try:
            raw = data.decode("utf-8")
        except UnicodeDecodeError as e:
            cause = f"byte 0x{data[e.start]:02x} at offset {e.start} is not valid UTF-8"
    if cause:
        raise NotEvaluable(f"resume {path} is not UTF-8 text ({cause}); a resume that cannot be read cannot be "
                           "checked, so save it as UTF-8 Markdown, text or LaTeX")
    if path.suffix == ".tex":
        _warn("LaTeX is read heuristically (commands removed): a macro whose argument is a value, such as "
              "{\\color{blue}Docker}, can hide a term; to rely on check-claims, check a plain-text export "
              "(pandoc -t plain, detex)")
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")      # CRLF and CR line endings read as LF
        raw = re.sub(r"(?<!\\)%[^\n]*(?:\n[ \t]*)?", "", raw)       # a comment eats its line break too
        raw = re.sub(r"\n[ \t]*(?=\n)", "\n", raw)                   # a white-space line is a blank line
        raw = re.sub(r"(?<!\n)\n(?!\n)", " ", raw)                     # a single line break is a space in LaTeX
        raw = re.sub(r"\\\\(\[[^\]\n]{0,200}\])?\*?", "\n", raw)       # two backslashes are a line break, not a command glued to the next word
        # structure is a paragraph break: words in two items, sections or paragraphs are never one phrase
        # a structural command and each of its argument groups stand on lines of their own
        # (\section*{Python} then text reads `Python` alone, not glued to the next word)
        raw = _LATEX_BREAK.sub(lambda m: "\n\n" + "\n\n".join(re.findall(r"\{([^{}\n]*)\}", m.group(1) or ""))
                               + "\n\n", raw)
        raw = raw.replace("\\&", "\x00").replace("\\_", "\x01")
        raw = re.sub(r"(?<!\\)&", "\n", raw)                   # a table cell separator
        raw = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]\n]{0,200}\])?", " ", raw)
        raw = raw.replace("{}", "")                              # an empty group prints nothing: Dock{}er
        raw = re.sub(r"(?<=\w)\{|\}(?=\w)", "", raw)              # a group glued to a word: textbf{Dock}er
        raw = re.sub(r"[{}$&~^_\\]", " ", raw).replace("\x00", "&").replace("\x01", "_")
    elif _SPLIT_WORD.search(raw):
        _warn(f"markup splits a word in {path.name} ({_SPLIT_WORD.search(raw).group(0)!r}): it renders as one word but "
              "is read as two, so check-claims can miss a term; check a plain-text export (pandoc -t plain)")
    return raw


def coverage(jd: str, resume: str, facts: str, cfg, lex: Lexicon, excluded=(), template=None) -> dict:
    """The coverage report (``coverage.json``). A posting that yields no terms
    is NOT EVALUABLE: 0 of 0 is not 0%."""
    keywords = extract(jd, lex, excluded)
    keywords, set_aside = _place_acronyms(jd, keywords, lex, getattr(cfg, "headings", None), template)
    if not keywords:
        raise NotEvaluable("no lexicon terms or acronyms found in the posting, so coverage "
                           "cannot be judged (add a lexicon pack that fits this field)")
    rnorm = F.normalize(resume)
    jdn = F.normalize_views(jd)
    present, equiv, missing = [], [], []
    for k in keywords:
        kl = k.lower()
        if any(F.token_in(f, rnorm) for f in lex.forms(kl)):
            present.append(k)
            continue
        anchor = cfg.equivalence.get(kl)
        if anchor and F.token_in(anchor, rnorm) and lex.holds(anchor, facts):
            equiv.append({"term": k, "via": anchor})
            continue
        held = claimable(kl, facts, cfg, lex)
        missing.append({"term": k, "held": held, "category": lex.category(k),
                        "jd_count": max(sum(len(re.findall(_bounded(f), v)) for f in lex.forms(kl))
                                        for v in jdn)})
    missing.sort(key=lambda m: -m["jd_count"])          # stable: extraction order on ties
    covered, denom = len(present) + len(equiv), len(keywords)
    rep = {"schema": 2, "present": present, "equiv": equiv, "missing": missing,
           "covered": covered, "denom": denom, "pct": round(100.0 * covered / denom, 1),
           "acronyms_set_aside": set_aside}
    rep.update(placement(jd, keywords, {k.lower() for k in present} | {e["term"].lower() for e in equiv},
                         lex, excluded, getattr(cfg, "headings", None), template))
    return rep


_RANK = {k: i for i, k in enumerate(S.KINDS)}
_NOT_THE_JOB = ("company", "benefits", "legal", "logistics")


def _place_acronyms(jd, keywords, lex, headings, template):
    """(kept, set aside). An acronym is an unvetted term: when the posting has sections, it
    counts only if it appears where the job is described (required, preferred,
    responsibilities, or untyped text), not only in the company, benefits, legal or logistics
    parts or the company template ("HSA", "AD&D", "RRSP" are benefit words, not skills)."""
    lines = S.split(jd, headings)
    if not S.found(lines):
        return keywords, []
    kept, aside = [], []
    for k in keywords:
        if lex.category(k) != "acronym":
            kept.append(k)
            continue
        rx = re.compile(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])")
        kinds = {("template" if template and re.sub(r"\s+", " ", ln.text.strip().lower()) in template
                  else ln.kind) for ln in lines if ln.text and not ln.heading and rx.search(ln.text)}
        if kinds and kinds <= set(_NOT_THE_JOB) | {"template"}:
            aside.append(k)
        else:
            kept.append(k)
    return kept, aside      # a term asked in several places: the strongest


def placement(jd: str, keywords: list, covered: set, lex: Lexicon, excluded=(), headings=None,
              template=None) -> dict:
    """Which section each term was asked in, the required/preferred split, years of
    experience, and the requirement lines no lexicon term was found in."""
    lines = S.split(jd, headings)
    want = {k.lower() for k in keywords}
    where, matched, reqs = {}, 0, S.requirement_lines(lines)
    if template:      # a company's template line is not this role's requirement
        reqs = [ln for ln in reqs if re.sub(r"\s+", " ", ln.text.strip().lower()) not in template]
    req_ids = {id(ln) for ln in reqs}
    unread = []
    parts = {}
    for ln in lines:
        if not ln.text or ln.heading:
            continue
        is_template = bool(template) and re.sub(r"\s+", " ", ln.text.strip().lower()) in template
        parts.setdefault("template" if is_template else ln.kind, []).append(ln.text)
        got = {t.lower() for t in extract(ln.text, lex, excluded)} & want
        for t in got:
            if t not in where or _RANK[ln.kind] < _RANK[where[t]]:
                where[t] = ln.kind
        if id(ln) in req_ids and not is_template:
            if got:
                matched += 1
            else:
                unread.append(ln.text)
    for k in want:                       # a term only the whole text yields (it spans lines)
        where.setdefault(k, "none")
    if S.found(lines):
        split = {kind: {"covered": sum(1 for t, w in where.items() if w == kind and t in covered),
                        "denom": sum(1 for w in where.values() if w == kind)}
                 for kind in ("required", "preferred", "responsibilities")}
        sec = {"found": True, **split}
    else:
        sec = {"found": False, "required": None, "preferred": None}
    if not sec["found"]:
        sec["responsibilities"] = None
    return {"sections": sec, "term_sections": dict(sorted(where.items())), "parts": parts,
            "years": S.years(lines),
            "unread": {"lines": len(reqs), "matched": matched, "unread": unread}}
