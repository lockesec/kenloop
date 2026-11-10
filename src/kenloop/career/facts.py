"""The facts sheet: what you actually hold, decided by structure, not wording.

``facts.md`` is free Markdown that only you edit; ``init`` writes the template once and
no command modifies it afterwards.
A term is HELD only when a block that mentions it as a whole token sits under
the ``## Held`` heading. A block anywhere else (``## Learning``, ``## Planned``,
free notes, text before the heading) is NOT held, whatever it says. Nothing
guesses from wording.

Heading rule: ``Held`` at level 2, case-insensitive, optional closing ``#``s and
surrounding spaces, ATX (``## Held``, indented at most 3 spaces) or setext
(``Held`` over ``---``). Level 1 or 3 ``Held``, ``Held:``, ``Held skills`` and
``Not held`` are other headings (the NOT EVALUABLE message names the near miss).
A leading BOM is ignored; a heading inside fenced code or an HTML comment, or
indented as code, is not a heading, and an unclosed comment or fence hides the
rest of the file (doctor reports it).
The section runs to the next heading of level 2 or higher; sub-headings inside
it stay held. A non-empty sheet with no such heading is NOT EVALUABLE.

The qualifier word list ("planned", "learning", "not held", ...) no longer
decides anything. It only reports a CONTRADICTION: a block under ``## Held``
that carries a qualifier word, or sits under a sub-heading of Held that does (a
title ABOVE Held disqualifies nothing), or is an unchecked task box. Such a
block is not held (fail closed) and is reported as a violation. A block is a
bullet, a numbered item, a heading or a paragraph; hard-wrapped continuation
lines are joined back onto their block.

HTML comments, fenced code and ~~struck~~ text are ignored: they state nothing.
Strike-through is removed one line at a time, so no stray ``~~`` can erase a heading.

Known limit: a qualifier anywhere in a held block disqualifies every term in
that block. Put one skill per line.
"""
from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left
from dataclasses import dataclass, field, replace
from functools import lru_cache

# The words of the "no experience" family, one place, so the docs table can be checked
# against the pattern (a test reads the table row for each of them).
EXPERIENCE_NOUNS = ("experience", "exposure", "knowledge", "familiarity", "proficiency")
EXPERIENCE_WEAKENERS = ("limited", "little", "minimal", "lack of", "lacking", "without", "zero")
_NOUN_ALT = "|".join(EXPERIENCE_NOUNS)
_WEAK_ALT = "|".join(EXPERIENCE_WEAKENERS)

_JOIN = r"[ /\-\u2010-\u2015\u2212]"           # a space or a joiner: "machine learning", "machine-learning"
_JOINER_ONLY = r"[/\-\u2010-\u2015\u2212\ufe58\ufe63\uff0d]"


def _learn_except() -> str:
    """Lookbehinds so "machine learning", "deep learning", "reinforcement learning" and "e-learning" are
    names, not a qualifier, however their words are joined: a space, a joiner, or a joiner with a space on
    either side or both ("deep / learning", "E\u2013learning"). A lookbehind has a fixed width, so each shape
    is its own. Each shape must start a word (no letter before it), so "Azure - learning" and
    "Vue-learning" are not "e-learning"."""
    out = []
    for w in ("machine", "deep", "reinforcement", "transfer", "supervised", "unsupervised", "federated", "meta",
              "statistical", "ensemble", "contrastive", "shot", "representation", "lifelong", "continual", "task",
              "incremental", "curriculum", "e"):
        shapes = [f"{w}{_JOINER_ONLY}", f"{w} {_JOINER_ONLY}", f"{w}{_JOINER_ONLY} ", f"{w} {_JOINER_ONLY} "]
        if w != "e":
            shapes.append(f"{w} ")
        out += [f"(?<!(?<![^\\W\\d_]){x})" for x in shapes]
    return "".join(out)


_LEARN_EXCEPT = _learn_except()

# Each family: (label, example phrase, pattern). The labels and examples are
# the list documented in docs/trust-rules.md; a test keeps the two in step.
_FAMILIES = (
    ("planned", "Plan to learn Kubernetes",
     r"\bplanned\b|\bplans? to\b|\bplanning to\b|\bsomeday\b|\beventually\b|\bdown the road\b|"
     r"\bnext year\b|\bon my (list|radar|roadmap)\b|\btodo\b|\bwip\b|\baspirational\b|\[verify|"
     r"\bwill (learn|study)\b|\bto be learn(ed|t)\b"),
    ("in progress", "Studying Go",
     r"\bin.progress\b|\bpursuing\b|\bstudying\b|\bnot[ -]yet\b|\bno active\b|"
     r"\bgetting started\b|\bstarting to\b|\bbeginning to\b|\bramping up\b|\bjust started\b"),
    ("learning", "Learning Docker",
     rf"(?=learning\b){_LEARN_EXCEPT}\blearning\b"   # the lookahead first: the lookbehinds run only at "learning"
     r"(?! (management|and development|&|platform|system|tools?|analytics|experience design|sciences?)\b)|"
     r"\(learning\)|\b(i am|i'm|currently|now|still) learning\b"),
    ("wish", "I'd like to use TLS",
     r"\bwant(s|ed)? to\b|\b(hope|hoping|intend|intending|aim|aiming|wish|wishing) to\b|"
     r"\bwould like to\b|\b(i|we)'d like to\b|\blooking to\b|\bgoing to (learn|study|use|try)\b|"
     r"\binterested in\b|\bcurious about\b"),
    ("exploring", "Exploring Redis",
     r"\bexploring\b|\bdabbl(ed|ing)\b|\bexperimenting\b|\btinker(ed|ing)\b|"
     r"\breading (up )?(about|on)\b"),
    ("not held", "Not held",
     r"\bnot held\b|do not (claim|list)|\bnever\b|\bnot? claimed\b"),
    ("not used", "Haven't used GraphQL in production",
     r"\b(haven'?t|have not|hasn'?t|has not|didn'?t|did not|don'?t|do not|doesn'?t|does not) "
     r"(used|use|worked|work|touched|touch|have|had|done|shipped|deployed|run|ran|written|wrote|built|know)\b|"
     r"\bnot (yet |really |fully |very |currently )?(hands.on|used|proficient|experienced|comfortable|"
     r"confident|professional|expert|an expert|familiar)\b|"
     r"\bnot (yet )?(used |deployed |run )?in (a )?(production|prod)\b"),
    ("no experience", "No production experience",
     r"\bno[ -](real |prior |hands.on |production |professional |commercial |practical |direct |work |"
     r"industry )*(experience|exposure)\b|"
     rf"\b({_WEAK_ALT}) (?:[\w-]+ ){{0,2}}({_NOUN_ALT})\b"),
    ("basic level", "JavaScript (basic)",
     # the keyword is a named group so the message quotes it alone, not the letter before it;
     # the second form is a trailing keyword: the last word of the line
     r"\w\s*[(\-\u2013\u2014:,;]\s*(?P<w1>basic|beginner|novice|elementary|rudimentary|entry.level|intro|"
     r"introductory|rusty)\b(?!\s+auth)|"
     r"\w\s+(?P<w2>basic|beginner|novice|elementary|rudimentary|entry.level|intro|introductory|rusty)"
     r"[\s.!?)\]]*$|"
     # the third form is a leading keyword: "- Beginner Docker", "- [x] Basic Docker"
     r"^[\s\-*+\d.\[\]x]*(?P<w3>basic|beginner|novice|elementary|rudimentary|entry.level|intro|introductory|rusty)"
     r"\s+(?!auth)\w|"
     r"\bbasic (knowledge|understanding|familiarity|proficiency|exposure|skills?|level)\b"),
    ("negation", "Redis (not Docker)",
     # "no-code", "not-for-profit", "No.1", "No. 1" and the publisher "No Starch" are names, not negations
     r"\b(not(?!-)|no(?!-|\.\s*\d| starch\b)|never|without|except|instead of)\b"),
    ("familiar with", "Familiar with OAuth from a course",
     r"\bfamiliar(ity)? with\b|\bfamiliarity\b|\bcoursework\b|"
     r"\b(from|via|through) (a |an |the |my |online )*(course|tutorial|class|bootcamp|video|book)s?\b"),
)
QUALIFIER_FAMILIES = tuple((label, example) for label, example, _p in _FAMILIES)
QUALIFIER_RE = re.compile("|".join(f"(?:{p})" for _l, _e, p in _FAMILIES), re.IGNORECASE)
# the same patterns are all lower-case; matching them on lower-cased text without the
# IGNORECASE flag is about a third faster on a large sheet
_QUALIFIER_LOWER = re.compile("|".join(f"(?:{p})" for _l, _e, p in _FAMILIES))
# Strike-through is one line only: a stray "~~" can never reach across a heading.
_STRIKE = re.compile(r"~~[^\n]+?~~")
_FENCE_OPEN = re.compile(r"^\s*(`{3,}[^`]*|~{3,}.*)$")
_THEMATIC = re.compile(r"^ {0,3}(?:-[ \t]*){3,}$")        # `---`: front matter or a rule, never part of a title
_SETEXT = re.compile(r"^\s*(=+|-{2,})\s*$")
_BLOCK_START = re.compile(r"^\s*([-*+]\s|\d+\.\s)|^ {0,3}#{1,6}(?:[ \t]|$)")
_NO_SETEXT = re.compile(r"^(?: {4,}|\t| {0,3}>)")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]|$)")
_HELD_WORD = re.compile(r"\b(held|hold|holds|holding)\b")
_CODE_OR_COMMENT = re.compile(r"<!--|`+")
# a list item that is only a level word ("  - beginner"): it qualifies the item it is nested under
_BARE_LEVEL = re.compile(r"^(?:[-*+]|\d+\.)\s+[(\[]?\s*(basic|beginner|novice|elementary|rudimentary|entry.level|"
                         r"intro|introductory|rusty)\s*[)\]]?[\s.!?,;:]*$")
_UNCHECKED = re.compile(r"^(?:[-*+]|\d+\.)\s+\[ \]")
_ITEM_START = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")


@dataclass(frozen=True)
class Block:
    """One block of the sheet. `why` says what makes a held block qualified."""
    text: str
    qualified: bool
    held: bool
    why: str = ""
    line: int = 0
    heading: bool = False
    norm: str = ""
    lines: tuple = ()      # the folded lines of the block, line breaks kept (text joins them with spaces)


@dataclass(frozen=True)
class Hidden:
    """Text a comment or fence hides. `closed` is False when the construct never ends."""
    line: int
    kind: str          # "comment" or "fence"
    text: str
    opened: int
    closed: bool
    in_held: bool


@dataclass
class Sheet:
    blocks: list
    has_held: bool
    near_misses: list      # [(line, heading text)] headings that look like Held but are not
    unclosed: list         # [(what, line)] a comment or fence that never closes hides the rest
    struck: list           # [(line, text)] lines under ## Held where ~~strike~~ removed text
    hidden: list = field(default_factory=list)   # [Hidden] text a comment or fence hides
    held_norms: tuple = ()  # the normalised text of every unqualified Held block
    held_hay: str = ""      # the same blocks joined by a blank line, which no term match crosses (so one
                            # search over it answers exactly what a block-by-block search would, much faster)


def _straight(text: str) -> str:
    """Curly apostrophes read as straight ones in the qualifier patterns."""
    return text.replace("\u2019", "'").replace("\u2018", "'")


# --- characters that are not text ----------------------------------------------------
#
# Default_Ignorable_Code_Point, from DerivedCoreProperties.txt of Unicode 15.1 (python's
# unicodedata has no property API, so the ranges are written out). These render as
# nothing (or change nothing a reader sees), so they are removed before any matching.
# U+2800 (braille blank) and the Hangul fillers U+115F, U+1160, U+3164, U+FFA0 render as
# blank cells; they are in the Unicode list or are added here on purpose (U+2800).
_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD), (0x034F, 0x034F), (0x061C, 0x061C), (0x115F, 0x1160), (0x17B4, 0x17B5),
    (0x180B, 0x180F), (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F), (0x2800, 0x2800),
    (0x3164, 0x3164), (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0xFFA0, 0xFFA0), (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3), (0x1D173, 0x1D17A), (0xE0000, 0xE0FFF),
)
# Trademark-style marks: NFKC would turn U+2122 into the letters "TM" and glue them to the
# word ("DockerTM"), so they are removed before folding. They state no skill.
_MARKS = (0x00A9, 0x00AE, 0x2117, 0x2120, 0x2122)


def _class(ranges) -> str:
    return "[" + "".join(f"\\U{lo:08x}" + (f"-\\U{hi:08x}" if hi != lo else "") for lo, hi in ranges) + "]"


_IGNORABLE = re.compile(_class(_IGNORABLE_RANGES))
_STRIP_FIRST = re.compile(_class(_IGNORABLE_RANGES + tuple((m, m) for m in _MARKS)))


def strip_ignorable(text: str) -> str:
    """The text without Default_Ignorable_Code_Point characters, U+2800 and trademark marks."""
    return text if text.isascii() else _STRIP_FIRST.sub("", text)


def fold(text: str) -> str:
    """Ignorable characters and trademark marks removed, then NFKC (full-width and
    compatibility forms become plain), then any ignorable or Unicode format character the
    normalisation exposed removed: what a reader sees is what is matched."""
    t = text or ""
    if t.isascii():
        return t
    t = unicodedata.normalize("NFKC", _STRIP_FIRST.sub("", t))
    if t.isascii():
        return t
    return "".join(c for c in _IGNORABLE.sub("", t) if unicodedata.category(c) != "Cf")


# Hyphen-like characters (ASCII hyphen, U+2010 to U+2015, minus, small and full-width hyphen-minus)
# and the slash join the words of a term: a multiword term ("rate limiting", "ci/cd", "nist 800-53")
# is found however its words are joined (a space, one of these characters, or a slash with spaces
# round it). A soft hyphen is read both ways: removed ("Dock\u00ader") and as a space
# ("Load\u00adBalancing").
_HYPHENS = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"
_JOINER_CLASS = re.escape(_HYPHENS + "/")
_JOINERS = re.compile("[" + _JOINER_CLASS + "]")
# The words of a multiword term are joined by HORIZONTAL white space (space, tab, no-break space and
# the other Zs spaces) alone or round one joiner, never across a line break, a list item, a paragraph
# or a Held block. The one exception is end-of-line hyphenation: a word that ends the line with a
# hyphen glued to it (ASCII hyphen, U+2010 or U+2011; a dash or a slash is not hyphenation), and a
# next line that starts directly with the next word ("machine-\nlearning"; a bullet marker or a blank
# line after the hyphen breaks it). That is ALLOWED, because a hard-wrapped paragraph breaks words that
# way. The disguise reader (suspects) joins the same wraps, so both read the text alike.
_HSPACE = "[ \\t\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]"
_WORD_SEP = ("(?:" + _HSPACE + "*[" + _JOINER_CLASS + "]" + _HSPACE + "*|" + _HSPACE + "+)")
# ONE wrap rule, applied to the raw text by BOTH readers (the matcher, in _norm_view, and the disguise
# reader, in suspects) before anything else, so the two can never disagree about a wrap: a word, then a
# hyphen (ASCII, U+2010, U+2011, or the small and full-width hyphen-minus that NFKC folds to ASCII),
# then any line break (LF, CRLF, CR, VT, FF, NEL, the C0 separators, U+2028, U+2029), with horizontal
# white space and invisible characters allowed on either side of the break (only invisible characters
# between the word and the hyphen: a space there breaks the join), then the next word.
_WRAP_HYPHENS = "-\u2010\u2011\ufe63\uff0d"
_WRAP_JUNK = "(?:" + _HSPACE + "|" + _STRIP_FIRST.pattern + ")*"
_JOIN_WRAP = re.compile("(?<=\\S)(?:" + _STRIP_FIRST.pattern + ")*([" + re.escape(_WRAP_HYPHENS) + "])"
                        + _WRAP_JUNK
                        + "(?:\r\n|[\n\r\v\f\x1c-\x1f\x85\u2028\u2029])" + _WRAP_JUNK + "(?=\\S)")   # \S, not \w: a combining mark or a symbol look-alike at the seam still wraps


#: A web address: a scheme (`https://`, `ftp://`) or `www.`, up to white space or a bracket. Its words are
#: not stated skills (`https://github.com/me` does not state `https`), so every reader blanks it first.
_URL = re.compile(r"(?i)(?<![\w.])(?:[a-z][a-z0-9+.-]{1,15}://|www\.)[^\s<>()\[\]{}\"'`]+")


def mask_urls(text: str) -> str:
    """`text` with every web address replaced by a space."""
    return _URL.sub(" ", text) if text and ("://" in text or "www." in text.lower()) else text


def join_wraps(text: str) -> str:
    """`text` with every end-of-line hyphen wrap joined into one word (``rate-`` / ``limiting`` gives
    ``rate-limiting``), by the one rule above."""
    return _JOIN_WRAP.sub(r"\1", text) if text else text
_APOSTROPHES = "\u2019\u2018\u2032\u00b4"
_APOS_MAP = {ord(c): "'" for c in _APOSTROPHES}


def _view(folded: str) -> str:
    """A reading with its joiners as spaces, for comparing a reading with a term."""
    return re.sub(r"\s+", " ", _JOINERS.sub(" ", folded.lower())).strip()


# every character Python's `\s` calls white space and that breaks a line: it is a line break here too, so no
# term is matched across it (the disguise reader keeps NEL and the separators as characters of a word)
_LINE_BREAK = re.compile("\r\n|[\n\r\v\f\x1c-\x1f\x85\u2028\u2029]")
# The disguise reader splits lines on the visible line breaks only: NEL and the C0 separators inside a word
# stay characters of it, so `Doc<U+001F>ker` is reported. Wraps are joined (join_wraps) before either reader
# splits, so both read every hyphen wrap alike.
_DISGUISE_LINE = re.compile("\r\n|[\n\r\v\f\u2028\u2029]")


def _norm_view(t: str) -> str:
    """One reading of `t`: folded, lower case, each line's white space collapsed, blank lines kept as
    one empty line. Line breaks survive: a term is never matched across one."""
    out, blank = [], True
    for ln in _LINE_BREAK.split(fold(join_wraps(mask_urls(t))).lower()):
        ln = re.sub(r"\s+", " ", ln).strip()
        if ln or not blank:
            out.append(ln)
        blank = not ln
    return "\n".join(out).strip("\n")


VIEW_GAP = "\n\n"          # between two readings of one text: a blank line, which no term crosses


def normalize_views(text: str) -> list:
    """The readings of `text` as they are matched: one, or two when it holds a soft hyphen (removed,
    and read as a space)."""
    t = text or ""
    a = _norm_view(t)
    if "\u00ad" in t:
        b = _norm_view(t.replace("\u00ad", " "))
        if b != a:
            return [a, b]
    return [a]


def normalize(text: str) -> str:
    """The text as it is matched: folded, lower case, white space collapsed within each line, line
    breaks kept. Text with a soft hyphen carries a second reading after a blank line, so no match
    can span the two readings."""
    return VIEW_GAP.join(normalize_views(text))


def _term_form(term: str) -> str:
    return normalize_views(term)[0].split("\n")[0]


def term_pattern(term: str) -> str:
    """The regular expression for `term`, its words joined by any joiner (see above)."""
    t = _term_form(term)
    words = [w for w in re.split("[\\s" + _JOINER_CLASS + "]+", t) if w] if len(t) > 1 else []
    return _WORD_SEP.join(re.escape(w) for w in words) if words else re.escape(t)


# --- skill disguises ---------------------------------------------------------------------
#
# ONE rule. A whitespace-separated token is read several ways:
#   (a) whole, and whole without the punctuation at its two ends;
#   (b) split into parts at every character that is ASCII punctuation or a symbol, or a Unicode
#       punctuation / symbol / separator character that is not a look-alike letter, does not
#       expand to letters or digits under NFKC (the numero sign) and is not a superscript,
#       subscript or fraction form (so "Docker-based", "Skills:Docker", "Docker—Redis",
#       "Docker，Redis" give "Docker" as a part, while "Docker№" and "Docker⁺" do not split);
#   (c) with a curly or ASCII possessive "'s" removed ("Docker’s" reads as "Docker").
# For each reading: NFKC, invisible/format/control characters removed, accents and overlays
# removed, look-alike letters mapped to the Latin letter, and (whole readings only) a
# non-ASCII punctuation or symbol character, or a superscript / subscript / fraction form,
# dropped. A reading is ALTERED only if that result differs from the NFKC form of the same
# reading; an altered reading that equals a lexicon term exactly (case-insensitive, one plural
# "s" tolerated) is reported, and nothing else is. There is no fuzzy or subsequence matching,
# so "Sao Paulo" and "Lodz" are never reported. A one-letter term is never reported; a term
# shorter than four letters is not reported on an accent alone (an overlay or enclosing mark
# is not an accent).
_WHITESPACE = re.compile("[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]+")
_POSSESSIVE = re.compile("['’‘′´][sS]$")
_LOOKALIKE = {}
for _src in (
    # Cyrillic
    ("аaеeоoрpсcуyхxіiјjѕsһhԁdԛqԝw"
     "ӏlАAВBЕEКKМMНHОOРPСCТTХXІIЈJ"
     "ЅSУYҮYѱvѵv"),
    # Greek
    ("αaοoρpυuνvιiκKχxΑAΒBΕEΖZΗHΙI"
     "ΚKΜMΝNΟOΡPΤTΥYΧX"),
    # Armenian
    ("օoսuցgոnհhՕOՍUՏTՕOհh"),
    # Greek lunate sigma, Cherokee capitals drawn like a Latin capital, the Cyrillic palochka, lower-case
    # Cyrillic letters that are standard confusables of a lower-case Latin letter, and o with stroke
    ("ϲcϹCᎠDᎡRᎢTᎩYᎪAᎫJᎬEᎳWᎷMᎻHᏀG"
     "ᏃZᏙVᏚSᏞLᏢPᏴBӀlкkгrтtмmнhвb"
     "øoØO"),
    # Latin look-alikes outside ASCII
    ("ıiɡgɑaɦhɗdɓbƙkƭtȷjᴀAʙBᴄCᴅDᴇE"
     "ɢGʜHɪIᴊJᴋKʟLᴍMɴNᴏOᴘPʀRѕsᴛTᴜU"
     "ᴠVᴡWʏYᴢZ"),
):
    for _i in range(0, len(_src), 2):
        _LOOKALIKE[_src[_i]] = _src[_i + 1]
# division slash and fraction slash read as a slash (NFKC leaves them alone)
_LOOKALIKE.update({"∕": "/", "⁄": "/", "⧸": "/", "∖": "\\",
                   # symbols drawn like a letter
                   "∊": "e", "∈": "e", "ϵ": "e", "∪": "u", "⋃": "u", "∩": "n"})
del _src, _i
# Combining marks that are drawn OVER or AROUND a letter (stroke, solidus, tilde and ring overlays,
# the parentheses overlay, enclosing circles and squares): they are not accents, so they count
# as a disguise even in a short term.
_OVERLAYS = frozenset(chr(c) for c in range(0x0300, 0x2100)
                      if unicodedata.category(chr(c)) == "Me"
                      or (unicodedata.category(chr(c)) == "Mn" and "OVERLAY" in unicodedata.name(chr(c), "")))


@dataclass(frozen=True)
class Suspect:
    """A reading that was rewritten before it read as a term. `reading` is the spelling it
    reads as (lower case), `offenders` the characters that were removed or mapped,
    `accent_only` whether they were all accents."""
    word: str
    offenders: tuple          # ((code point text, name), ...) in order of appearance
    reading: str
    accent_only: bool

    @property
    def shown(self) -> str:
        """The word as a message quotes it: a very long one is cut."""
        return self.word if len(self.word) <= 80 else self.word[:80] + "\u2026"


def _decorator(c: str) -> bool:
    """A superscript, subscript or fraction form (the ordinal indicators, the superscript digits and
    plus): drawn small next to a word, so it is dropped from a whole reading like any other symbol."""
    return unicodedata.decomposition(c).startswith(("<super>", "<sub>", "<fraction>"))


def _separator(c: str) -> bool:
    """A character a token is split at: ASCII punctuation or symbol, or a non-ASCII punctuation,
    symbol or separator that is not a look-alike letter, does not expand to a letter or digit
    under NFKC (the numero sign) and is not a superscript, subscript or fraction form."""
    if c.isascii():
        return c.isprintable() and not c.isalnum()
    cat = unicodedata.category(c)
    if cat == "Co" or "\u0080" <= c <= "\u009f":      # private-use (Word bullets), NEL and the other C1 controls
        return True
    if c in _LOOKALIKE or cat[0] not in "PSZ":
        return False
    if any(ch.isalnum() for ch in unicodedata.normalize("NFKC", c)):
        return False
    return not _decorator(c)


def _nfkc(word: str) -> str:
    """What the ordinary matcher reads: NFKC, invisible characters removed, curly apostrophes
    straight, lower case."""
    return fold(word.translate(_APOS_MAP)).lower()


def _reading(word: str):
    """(reading, offender characters, accent_only) for one whitespace-free reading."""
    out, off, accent = [], [], True
    for c in word:
        if c.isascii():
            if c.isprintable():
                out.append(c)
                continue
        elif c in _APOSTROPHES:
            out.append("'")
            continue
        elif c in _HYPHENS:                            # a dash is a joiner, never silently removed
            out.append("-")
            continue
        elif c in _LOOKALIKE:
            out.append(_LOOKALIKE[c])
            off.append(c)
            accent = False
            continue
        else:
            cat = unicodedata.category(c)
            if cat == "Cf":
                continue                               # read through by the ordinary matcher too
            if cat in ("Mn", "Me"):
                off.append(c)
                if c in _OVERLAYS:
                    accent = False
                continue
            if cat[0] in "LN" and not _decorator(c):
                n = unicodedata.normalize("NFKC", c)
                if n != c:                             # compatibility form: one letter or more
                    out.append(n)
                    continue
                d = unicodedata.normalize("NFD", c)
                if d != c and d[0].isascii() and d[0].isalnum() and all(
                        unicodedata.category(m) in ("Mn", "Me") for m in d[1:]):
                    out.append(d[0])                   # an accented Latin letter
                    off.append(c)
                    continue
                out.append(c)                          # another script's letter: kept, so no term matches
                continue
        off.append(c)                                  # symbol, punctuation, control, separator
        accent = False
    return "".join(out).lower(), off, accent


def _examine(reading: str):
    """The Suspect for one reading, or None when it is not altered (its rewrite equals its NFKC form)."""
    if reading.isascii() and reading.isprintable():
        return None
    text = strip_ignorable(reading)
    lo, hi = _inner(text)
    rd, off, accent = _reading(text[lo:hi])
    rd = _nfkc(text[:lo]) + rd + _nfkc(text[hi:])     # punctuation at the ends stays as written
    if _view(rd) == _view(_nfkc(reading)):
        return None
    names, listed = [], set()
    for c in off:
        if c not in listed:
            listed.add(c)
            names.append((f"U+{ord(c):04X}", unicodedata.name(c, "UNNAMED CHARACTER")))
    return Suspect(reading, tuple(names), rd, accent)


def _inner(tok: str):
    """(lo, hi): `tok[lo:hi]` is the token without the separator characters at its two ends."""
    lo, hi = 0, len(tok)
    while lo < hi and _separator(tok[lo]):
        lo += 1
    while hi > lo and _separator(tok[hi - 1]):
        hi -= 1
    return lo, hi


def _readings_of(tok: str):
    """The readings of one token: whole, whole without the punctuation at its ends, the
    possessive-free forms of those, and the parts between separators."""
    lo, hi = _inner(tok)
    whole = (tok, tok[lo:hi])
    cands = list(whole) + [_POSSESSIVE.sub("", w) for w in whole if _POSSESSIVE.search(w)]
    part = []
    for c in tok:
        if _separator(c):
            if part:
                cands.append("".join(part))
                part = []
        else:
            part.append(c)
    if part:
        cands.append("".join(part))
    return dict.fromkeys(c for c in cands if c)


def _window_readings(w: str):
    """The readings of a window of words: whole, without the punctuation at its ends, and the
    possessive-free forms of those."""
    lo, hi = _inner(w)
    whole = (w, w[lo:hi])
    return dict.fromkeys(c for c in list(whole) + [_POSSESSIVE.sub("", x) for x in whole if _POSSESSIVE.search(x)] if c)


def suspects(text: str, window: int = 1) -> list:
    """Every altered reading of every whitespace-separated token of `text` (see the rule above),
    in order, once each. A token that is plain printable ASCII has none. With `window` > 1 the
    readings of every run of 2 to `window` consecutive words that holds a non-ASCII word are
    added (a word that is only a dash or a slash is not counted), for a term of several words."""
    out, seen = [], set()

    def add(cand):
        if cand in seen:
            return
        seen.add(cand)
        sp = _examine(cand)
        if sp:
            out.append(sp)

    def one_line(line):
        toks = [t for t in _WHITESPACE.split(strip_ignorable(line)) if t]
        for tok in toks:
            if not (tok.isascii() and tok.isprintable()):
                for cand in _readings_of(tok):
                    add(cand)
        if window > 1:
            words = [t for t in toks if not all(_separator(c) for c in t)]
            odd = [not (t.isascii() and t.isprintable()) for t in words]
            if any(odd):
                for i in range(len(words) - 1):
                    for n in range(2, min(window, len(words) - i) + 1):
                        if any(odd[i:i + n]):
                            for cand in _window_readings(" ".join(words[i:i + n])):
                                add(cand)

    # a window never spans a line break, except an end-of-line hyphen wrap, which is joined first exactly as
    # the matcher joins it; a soft hyphen is read removed and as a space, each a reading of its own
    for line in _DISGUISE_LINE.split(join_wraps(mask_urls(text or ""))):
        one_line(line)
        if "\u00ad" in line:
            one_line(line.replace("\u00ad", " "))
    return out


def _lookup(reading: str, terms, accent_only: bool) -> str:
    reading = _view(reading)
    for r in (reading, reading[:-1] if len(reading) > 3 and reading.endswith("s") else ""):
        if len(r) > (3 if accent_only else 1) and r in terms:
            return r
    return ""


def _resembles(sp: Suspect, terms) -> str:
    """The term `sp` reads as, "" if none: an exact match, not a likeness."""
    return _lookup(sp.reading, terms, sp.accent_only)


def lexicon_words(terms) -> frozenset:
    """The terms a disguise is compared with, normalised."""
    return frozenset(t for t in (_view(_term_form(x)) for x in terms) if t)


@lru_cache(maxsize=8)
def _max_words(lexwords) -> int:
    """The word count of the longest term: how many consecutive words one reading may span."""
    return max((w.count(" ") + 1 for w in lexwords), default=1)


def disguised(text: str, lexwords) -> list:
    """[(Suspect, term it reads as)] for the words of `text` that are rewritten into a
    skill term by the rule above."""
    out, seen = [], set()
    for sp in suspects(text, _max_words(lexwords)):
        t = _resembles(sp, lexwords)
        key = (t, tuple(cp for cp, _n in sp.offenders))
        if t and key not in seen:                 # "Dockеr/" and "Dockеr" are one finding
            seen.add(key)
            out.append((sp, t))
    return out


@lru_cache(maxsize=8)
def _held_suspects(facts: str, window: int = 1) -> tuple:
    """[(Block, Suspect)] for every rewritten word on a line under ## Held, computed once."""
    return tuple((b, sp) for b in analyse(facts).blocks if b.held and not b.heading
                 for sp in suspects("\n".join(b.lines), window))


def disguised_in_held(term: str, facts: str):
    """(Block, Suspect) for a line under ## Held whose word reads as `term` only once it is
    rewritten ("Dock<Cyrillic e>r"): that line does not hold the term, and it is a
    contradiction with that cause. None if there is none."""
    words = lexicon_words([term])
    for b, sp in _held_suspects(facts or "", _max_words(words)):
        if _resembles(sp, words):
            return b, sp
    return None


def describe(sp: Suspect) -> str:
    cut = sp.offenders[:8]
    more = f", and {len(sp.offenders) - 8} more" if len(sp.offenders) > 8 else ""
    return ", ".join(f"{cp} {name}" for cp, name in cut) + more


def token_in(term: str, hay: str) -> bool:
    """`term` as a whole token of `hay` (compare lower-cased text). Lookarounds,
    not \\b, so terms like ``ci/cd`` and ``att&ck`` match; a plural ``s`` is
    tolerated for terms of three or more characters ("apis", never "was")."""
    t = _term_form(term)
    if not t:
        return False
    plural = "s?" if len(t) >= 3 else ""
    if len(t) == 1:
        # a one-letter term is a whole token only: not "R&D", not "R" + an accented letter
        return re.search(rf"(?<![\w&]){re.escape(t)}(?![\w&+#])", hay) is not None
    # "+" and "#" continue a token, so "c" is not found inside "c++" or "c#"
    return re.search(rf"(?<![a-z0-9]){term_pattern(t)}{plural}(?![a-z0-9+#])", hay) is not None


def _heading_title(line: str) -> str:
    return re.sub(r"\s+#+\s*$", "", line.strip().lstrip("#").strip()).strip()


def _is_held_heading(line: str) -> bool:
    m = _HEADING.match(line)
    if not m or len(m.group(1)) != 2:
        return False
    return _heading_title(line).lower() == "held"


def _near_miss(line: str) -> bool:
    """A heading (after invisible and full-width characters are folded away) that
    names held or hold ("Held:", "Not held", "Skills I hold") without being
    exactly the level-2 Held heading."""
    f = fold(line)
    return (bool(_HEADING.match(f)) and bool(_HELD_WORD.search(_heading_title(f).lower()))
            and not _is_held_heading(line))


def _plain(s: str) -> str:
    """Look-alike letters read as the Latin letter and combining marks removed, so a qualifier word
    written with a Cyrillic letter or an accent ("(l\u0435arning)") is still the qualifier."""
    out = []
    for c in unicodedata.normalize("NFKD", s):
        if c in _LOOKALIKE:
            out.append(_LOOKALIKE[c])
        elif unicodedata.category(c) not in ("Mn", "Me"):
            out.append(c)
    return "".join(out)


def _qualifier(text: str) -> str:
    s = re.sub(r"\s+", " ", _straight(text))      # "Plan  to learn" is "plan to learn"
    if not s.isascii():
        s = _plain(s)
    m = _QUALIFIER_LOWER.search(s.lower())
    if not m:
        return ""
    g = next((n for n in ("w1", "w2", "w3") if m.group(n) is not None), 0)
    orig = s[m.start(g):m.end(g)] if len(s) == len(s.lower()) else m.group(g)
    return orig.strip()


def hidden_qualifier(text: str) -> str:
    """The qualifier word in text a comment hides from the sheet, for `doctor` to name."""
    return _qualifier(re.sub(r"\s*-->\s*$", "", text))


_RUN = re.compile(r"`+")


def _split_line(raw: str, no: int, comment: int):
    """Split one raw line into (visible, hidden, comment_opened_at) honouring
    inline code spans: a ``<!--`` inside backticks is text, as Markdown renders it.
    A code span closes at the next backtick run of exactly the opening length; the runs
    are indexed once per line, so a line of any length is read in linear time."""
    vis, hid, i = [], [], 0
    by_len = None
    while i < len(raw):
        if comment:
            j = raw.find("-->", i)
            if j < 0:
                hid.append(raw[i:])
                i = len(raw)
            else:
                hid.append(raw[i:j + 3])
                comment, i = 0, j + 3
            continue
        m = _CODE_OR_COMMENT.search(raw, i)
        if not m:
            vis.append(raw[i:])
            i = len(raw)
        elif m.group().startswith("`"):
            if by_len is None:
                by_len = {}
                for r in _RUN.finditer(raw):
                    by_len.setdefault(r.end() - r.start(), []).append(r.start())
            n = len(m.group())
            starts = by_len.get(n, ())
            k = bisect_left(starts, m.end())
            end = starts[k] + n if k < len(starts) else m.end()     # no closing run: literal backticks
            vis.append(raw[i:end])
            i = end
        else:
            vis.append(raw[i:m.start()])
            hid.append("<!--")
            comment, i = no, m.end()
    return "".join(vis), "".join(hid), comment


def _visible(text: str):
    """[(line number, visible text, struck, hidden text, hidden kind, opened line)]
    per raw line. Removals are made on single lines only (strike-through) or are
    the Markdown-defined hiding of comments and fenced code, so no heading can
    vanish by a stray marker. Also returns [(what, line)] for a comment or
    fence that never closes."""
    if text.startswith("\ufeff"):
        text = text[1:]                                  # a byte-order mark is not part of line 1
    out, unclosed = [], []
    fence, comment, fence_at = None, 0, 0
    for no, raw in enumerate(re.split(r"\r\n|\r|\n", text), 1):
        if fence:
            if re.match(rf"^\s*{re.escape(fence[0])}{{{fence[1]},}}\s*$", raw):
                fence = None
            out.append((no, "", False, raw, "fence", fence_at))
            continue
        was = comment
        vis, hid, comment = _split_line(raw, no, comment)
        opened = was or (comment or no)
        m = _FENCE_OPEN.match(vis) if not comment else None
        if m:
            run = re.match(r"\s*(`+|~+)", vis).group(1)
            fence = (run[0], len(run), no)
            fence_at = no
            out.append((no, "", False, raw, "fence", no))
            continue
        struck = _STRIKE.sub(" ", vis)
        out.append((no, struck, struck != vis, hid, "comment", opened))
    if comment:
        unclosed.append(("<!-- comment", comment))
    if fence:
        unclosed.append(("code fence", fence[2]))
    return out, unclosed


def _analyse(facts: str) -> Sheet:
    """Parse the sheet. `qualified` on a block under ## Held means it carries a
    qualifier word, an unchecked task box, or sits under a sub-heading of Held
    that does. A heading ABOVE ## Held (the document title) is not part of
    Held and disqualifies nothing."""
    out: list = []
    heads: list = []          # [(level, qualifier, is_held, text)] of the enclosing headings
    near: list = []
    struck_held: list = []
    hidden: list = []
    cur, cur_why, cur_h, cur_line, cur_head, cur_plain = None, "", False, 0, False, False
    cur_ind = 0
    shape: list = []          # (indent, is a list item) per block, parallel to `out`
    cur_more: list = []       # continuation lines of the block, joined once in flush()
    seen_held = False

    def flush():
        nonlocal cur
        if cur is not None:
            text = fold(" ".join([cur, *cur_more]) if cur_more else cur)
            lines = tuple(fold(x) for x in (cur, *cur_more))
            why = cur_why
            if not why and cur_h:
                q = _qualifier(text)
                bare = _BARE_LEVEL.match(_straight(text).lower())
                if not q and bare:
                    q = bare.group(1)
                if q:
                    why = f"qualifier {q!r} in the line"
                elif _UNCHECKED.match(text):
                    why = "an unchecked task box [ ] is a to-do, not a skill you hold"
            out.append(Block(text, bool(why) and cur_h, cur_h, why if cur_h else "", cur_line, cur_head,
                             normalize("\n".join(lines)), lines))
            shape.append((cur_ind, bool(_ITEM_START.match(cur)) and not cur_head))
        cur = None
        cur_more.clear()

    def state():
        """(inherited why, in_held): only headings nested under Held can qualify."""
        hi = next((i for i, h in enumerate(heads) if h[2]), None)
        if hi is None:
            return "", False
        for lvl, q, _h, title in heads[hi + 1:]:
            if q:
                return f"under the sub-heading {title!r} (qualifier {q!r})", True
        return "", True

    lines, unclosed = _visible(facts or "")
    open_at = {line for _w, line in unclosed}
    for no, line, struck, hid, hkind, opened in lines:
        if hid.strip():
            hidden.append(Hidden(no, hkind, hid.strip(), opened, opened not in open_at, state()[1]))
        if not line.strip():
            flush()
            if struck and state()[1]:
                struck_held.append((no, "(whole line struck through)"))
            continue
        if struck and state()[1]:
            struck_held.append((no, line.strip()))
        if _SETEXT.match(line) and cur is not None and not cur_plain and not _BLOCK_START.match(cur):
            title = " ".join([cur, *cur_more])
            line = ("# " if line.strip().startswith("=") else "## ") + title   # "Title\n====" is a heading
            no, cur = cur_line, None
            cur_more.clear()
        if cur is None and _THEMATIC.match(line):
            continue
        h = _HEADING.match(line)
        if h:
            flush()
            level = len(h.group(1))
            while heads and heads[-1][0] >= level:
                heads.pop()
            is_held = _is_held_heading(line)
            seen_held = seen_held or is_held
            if _near_miss(line):
                near.append((no, line.strip()))
            # the "Held" heading itself carries no qualifier; its words are a name
            heads.append((level, "" if is_held else _qualifier(fold(line)), is_held, line.strip()))
            cur, cur_head, cur_line, cur_ind = line.strip(), True, no, 0
            cur_why, cur_h = state()
            flush()
            cur_head = False
            continue
        if fold(line) != line and _near_miss(line):      # "## Hel<ZWSP>d", full-width hashes, NBSP, mid-file BOM
            near.append((no, line.strip()))
        if cur is None or _BLOCK_START.match(line):
            flush()
            cur, cur_line = line.strip(), no
            cur_ind = len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())
            cur_plain = bool(_NO_SETEXT.match(line))
            cur_why, cur_h = state()
        else:
            cur_more.append(line.strip())
    flush()
    # a qualified nested item qualifies the item directly above it ("- Docker" / "  - (learning)")
    stack: list = []          # [(indent, index in out)] of the open list items
    for i, (ind, item) in enumerate(shape):
        if not item:
            stack.clear()
            continue
        while stack and stack[-1][0] >= ind:
            stack.pop()
        b = out[i]
        if stack and b.held and b.qualified:
            j = stack[-1][1]
            if out[j].held and not out[j].qualified:
                out[j] = replace(out[j], qualified=True,
                                 why=f"its nested item on line {b.line} is qualified ({b.why})")
        stack.append((ind, i))
    held_norms = tuple(b.norm for b in out if b.held and not b.qualified)
    return Sheet(out, seen_held, near, unclosed, struck_held, hidden, held_norms, VIEW_GAP.join(held_norms))


@lru_cache(maxsize=8)
def _analyse_cached(facts: str) -> Sheet:
    return _analyse(facts)


def analyse(facts: str) -> Sheet:
    """The parsed sheet, computed once per distinct text (a command asks many questions)."""
    return _analyse_cached(facts or "")


def blocks(facts: str) -> list:
    return analyse(facts).blocks


def has_held_section(facts: str) -> bool:
    return analyse(facts).has_held


def holds(term: str, facts: str) -> bool:
    """Fail-closed: held means mentioned under `## Held` in a block with no
    qualifier word. Anything else, and an empty sheet, holds nothing."""
    return token_in(term, analyse(facts).held_hay)


def held_elsewhere(term: str, facts: str) -> list:
    """Blocks outside `## Held` that mention `term` (evidence for a violation)."""
    return [b.text for b in blocks(facts) if not b.held and token_in(term, b.norm)]


def qualified_blocks(term: str, facts: str) -> list:
    """Blocks under `## Held` that mention `term` but are qualified."""
    return [b for b in blocks(facts) if b.held and b.qualified and token_in(term, b.norm)]


def qualified_in_held(term: str, facts: str) -> list:
    return [b.text for b in qualified_blocks(term, facts)]


def contradiction_blocks(facts: str) -> list:
    """Every block under `## Held` that is qualified (headings excepted)."""
    return [b for b in blocks(facts) if b.held and b.qualified and not b.heading]


def contradictions(facts: str) -> list:
    return [b.text for b in contradiction_blocks(facts)]


def hidden_for(term: str, facts: str):
    """The first Hidden piece (comment or fence text) that mentions `term`, or None."""
    return next((h for h in analyse(facts).hidden if token_in(term, normalize(h.text))), None)


def hidden_cause(h: Hidden) -> str:
    msg = f"hidden by a {h.kind} at facts.md line {h.line}"
    if not h.closed:
        msg += f" (the {h.kind} opened on line {h.opened} never closes, so everything after it is hidden)"
    return msg


def explain(term: str, facts: str) -> str:
    """Why `term` is not held, in one phrase ("" when it is held)."""
    if holds(term, facts):
        return ""
    q = qualified_blocks(term, facts)
    if q:
        return f"listed under ## Held but qualified, line {q[0].line}: {q[0].why}"
    d = disguised_in_held(term, facts)
    if d:
        return (f"listed under ## Held but spelled {d[1].shown!r} with {describe(d[1])}, so it is "
                f"not held, line {d[0].line}")
    if held_elsewhere(term, facts):
        return "mentioned only outside ## Held"
    h = hidden_for(term, facts)
    if h:
        return hidden_cause(h)
    return "not in facts.md"


NO_HELD_MSG = ("{path} has no '## Held' section: add a level-2 heading '## Held' (any case) and list "
               "under it only the skills you hold; anything outside it counts as not held")


def no_held_message(path: str, sheet: Sheet) -> str:
    msg = NO_HELD_MSG.format(path=path)
    for no, head in sheet.near_misses[:3]:
        msg += f"; line {no} reads {head!r}, which is not the Held heading (it must be exactly '## Held')"
        if not head.isascii() or fold(head) != head:
            msg += " and it contains invisible, full-width or look-alike characters"
    for what, no in sheet.unclosed:
        msg += f"; the {what} opened on line {no} never closes, so everything after it is hidden"
    return msg


def read(cfg) -> str:
    """The facts sheet's text; absent or empty is "" (holds nothing). Present but
    unreadable, or non-empty without a `## Held` section, is NOT EVALUABLE: it is
    the claim gate's source of truth."""
    from ..core.errors import NotEvaluable
    try:
        text = cfg.facts.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError) as e:
        raise NotEvaluable(f"facts sheet {cfg.facts} is unreadable: {e}") from e
    if text.strip():
        sheet = analyse(text)
        if not sheet.has_held:
            raise NotEvaluable(no_held_message(cfg.facts.name, sheet))
    return text
