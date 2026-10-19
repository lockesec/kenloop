"""[wants]: what you want from a job, one filter per field.

Each filter reads one thing, answers pass, fail (with the reason) or unknown, and has its
own policy for an unknown: `keep` (the default: a posting that does not say is not a posting
that says no), `flag`, or `drop`. Nothing is deleted: a posting that fails, or an unknown
under `drop`, is set aside with its reason.

  workplace   remote / hybrid / onsite, from the board's own field when it has one
              (Ashby, Lever), else the location or title text ("Remote - US")
  pay         a floor in one currency, from the board's field (Ashby, Lever) or the pay
              ranges in the posting text, each read with its label (a bonus, stipend, equity or
              relocation range is not pay), its interval (hourly x 2,080, monthly x 12, weekly
              x 52, each said) and its currency (a code or symbol; a bare "$" is stated only
              where the location says US). A range passes when its top reaches the floor; with
              several pay ranges the highest is judged and the count said. Another or an
              unstated currency is unknown: there is no conversion. `pay_unknown` is the
              "no range stated" policy.

These are kept apart from facts.md on purpose: facts.md is what you hold and what your
resume may claim; [wants] is what you want.
"""
from __future__ import annotations

import re

WORKPLACES = ("remote", "hybrid", "onsite")
POLICIES = ("keep", "flag", "drop")
HOURS_PER_YEAR = 2080
WANT_KEYS = {"workplace", "workplace_unknown", "pay_min", "pay_currency", "pay_unknown",
             "benefits", "benefits_unknown", "benefit_phrases"}

# Spellings postings use for common benefits; a benefit not here is matched as written, and
# [wants.benefit_phrases] adds spellings to any benefit. `against` is a statement that rules
# the benefit out (a fixed number of PTO days is not unlimited PTO).
BENEFITS = {
    "unlimited pto": {"any": ["unlimited pto", "unlimited paid time off", "unlimited vacation",
                              "unlimited time off", "flexible pto", "flexible paid time off",
                              "flexible time off", "flexible vacation", "open pto", "uncapped pto",
                              "take the time you need", "no set limit", "not accrual based",
                              "untracked pto", "untracked time off", "discretionary time off",
                              "discretionary pto", "open time off", "open vacation"],
                      "re": [r"take what you need(?=.*\b(?:pto|time off|vacation|leave)\b)",
                             r"\b(?:pto|time off|vacation|leave)\b.*take what you need"],
                      # a fixed allowance stated as the allowance ("15 days of PTO per year");
                      # a year-end shutdown or holiday block is not one
                      "against": [r"\b\d{1,2}\s+(?:days?|weeks?)\s+(?:of\s+)?(?:paid\s+)?(?:pto|time off|vacation|"
                                  r"annual leave)\b"],
                      "against_skip": r"shutdown|year[- ]end|end of (?:the|each|every) year|winter break|"
                                      r"holiday (?:break|block|closure)|built into"},
    "pet insurance": {"any": ["pet insurance", "pet benefits"]},
    "401k match": {"any": ["401(k) match", "401k match", "401(k) matching", "401k matching",
                           "401(k) with employer match", "401(k) with a match", "employer match"]},
    "health insurance": {"any": ["health insurance", "medical insurance", "medical, dental",
                                 "health, dental", "medical and dental", "medical coverage"]},
    "parental leave": {"any": ["parental leave", "maternity leave", "paternity leave", "family leave"]},
    # "equity" alone is also diversity-equity-inclusion and pay equity: it counts as a benefit
    # only with a compensation sense, or as a bare item in a benefits section
    "equity": {"any": ["stock options", "rsus", "rsu", "restricted stock", "equity grant", "equity grants",
                       "equity compensation", "equity package", "equity award", "equity awards",
                       "equity incentive", "stock grant", "stock awards", "employee stock purchase",
                       "espp", "equity participation", "equity stake"],
               "re": [r"\b(?:offers?|offering|provides?|competitive|meaningful|generous|significant|"
                      r"employee|company)\s+equity\b"],
               "bare": r"(?<![\w-])equity(?![\w])",
               "bare_not": r"pay equity|equal pay|diversity|inclusion|racial|gender|social|health equity|"
                           r"educational equity|equity (?:plan|cap table|ledger|research|market|trad)"},
    "learning budget": {"any": ["learning budget", "education stipend", "professional development budget",
                                "training budget", "certification reimbursement", "learning and development budget",
                                "tuition reimbursement"]},
    "home office stipend": {"any": ["home office stipend", "home office set up", "home office setup",
                                    "remote work stipend", "work from home stipend", "office equipment stipend"]},
    "four day week": {"any": ["four day week", "4-day week", "4 day work week", "four-day work week"]},
}

_CUR = {"$": "USD", "usd": "USD", "us$": "USD", "£": "GBP", "gbp": "GBP", "€": "EUR", "eur": "EUR",
        "cad": "CAD", "c$": "CAD", "ca$": "CAD", "aud": "AUD", "a$": "AUD", "au$": "AUD",
        "nzd": "NZD", "nz$": "NZD", "sgd": "SGD", "s$": "SGD", "hkd": "HKD", "hk$": "HKD",
        "mxn": "MXN", "mx$": "MXN", "inr": "INR", "₹": "INR", "jpy": "JPY", "¥": "JPY", "chf": "CHF"}
_SYM = r"(?<![A-Za-z])(?:US\$|CA\$|AU\$|NZ\$|HK\$|MX\$|C\$|A\$|S\$|\$|£|€|₹|¥)"
_CODES = "USD|GBP|EUR|CAD|AUD|NZD|SGD|HKD|MXN|INR|JPY|CHF"
_CODE = rf"(?<![A-Za-z])(?:{_CODES})(?![A-Za-z])"
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*([kK])?"
_DASH = r"\s*(?:-|–|—|to)\s*"
PAY_RE = re.compile(
    rf"(?:(?P<code>{_CODE})\s*)?(?P<sym>{_SYM})?\s*{_NUM}{_DASH}(?:{_SYM}|{_CODE}\s*)?\s*{_NUM}",
    re.IGNORECASE)
HOURLY_RE = re.compile(r"(?:per\s+hour|an\s+hour|/\s*h(?:ou)?r\b|hourly)", re.IGNORECASE)
MONTHLY_RE = re.compile(r"(?:per\s+month|a\s+month|/\s*mo(?:nth)?\b|monthly)", re.IGNORECASE)
WEEKLY_RE = re.compile(r"(?:per\s+week|a\s+week|/\s*(?:wk|week)\b|weekly)", re.IGNORECASE)
# yearly = stated x factor; hourly at a full-time year, monthly and weekly by the calendar
PER_YEAR = {"year": 1, "hour": HOURS_PER_YEAR, "month": 12, "week": 52}
# a range with one of these in its label is not the salary
_NONPAY = (r"stipends?|allowances?|reimburse\w*|bonus(?:es)?|sign[- ]?on|signing|equity|stock|rsus?|"
           r"grants?|relocation|budget|commissions?|incentives?")
_PAYWORD = r"salary|salaries|base|pay|compensation|range|wages?|annual|remuneration|rate"
_NONPAY_RE = re.compile(rf"\b(?:{_NONPAY})\b", re.IGNORECASE)
_PAYWORD_RE = re.compile(rf"\b(?:{_PAYWORD})\b", re.IGNORECASE)
# "base salary, excluding bonus:" / "bonus-eligible base": the word is not what the range is of
_NEUTRAL_RE = re.compile(
    rf"(?:excluding|exclusive of|not including|plus|\+|in addition to|before|and|with)\s+"
    rf"(?:an?\s+|any\s+|the\s+|annual\s+|target\s+)?(?:{_NONPAY})\b|"
    rf"(?:{_NONPAY})[- ]eligib\w*", re.IGNORECASE)
_NONPAY_AFTER = re.compile(rf"\s*(?:{_CODE}\s*)?(?:sign[- ]?on|signing|relocation|stipend|allowance|"
                           rf"equity|stock|rsus?)\b", re.IGNORECASE)


def _amount(num: str, k) -> float:
    v = float(num.replace(",", ""))
    return v * 1000 if k else v


def _num(v: float):
    return int(v) if v == int(v) else v


def _label(line: str, start: int, prev_end: int, prev_line: str) -> str:
    """The words that say what the range at `start` is a range of: the clause before it on its
    line, else (a bare figure under a short heading) the line above."""
    seg = re.split(r"[.;|]", line[prev_end:start])[-1]
    if (not re.search(r"[A-Za-z]", seg) and prev_line and len(prev_line.split()) <= 8
            and not PAY_RE.search(prev_line)):
        seg = prev_line + " " + seg
    return seg[-100:]


def pay_ranges(text: str) -> list:
    """Every pay RANGE in the text, each read with its label, interval and currency:
    [{min, max, currency, interval, source, currency_stated, kind, label}], kind being "pay"
    (labelled salary/base/pay/compensation), "plain" (no label) or "nonpay" (a bonus, stipend,
    equity, grant, relocation, budget or commission range). A single amount, a funding round
    or a range whose top is under 1,000 (unless it says hourly, monthly or weekly) is not one."""
    out, prev = [], ""
    for n, line in enumerate((text or "").splitlines(), 1):
        prev_end = 0
        for m in PAY_RE.finditer(line):
            label = _label(line, m.start(), prev_end, prev)
            prev_end = m.end()
            lo, hi = _amount(m.group(3), m.group(4)), _amount(m.group(5), m.group(6))
            if hi < lo:
                continue
            k_any = m.group(4) or m.group(6)
            if m.group(4) is None and m.group(6) and lo < 1000:
                lo *= 1000                                   # "$120–150K"
            tail = line[m.end():m.end() + 30]
            window = line[m.start():m.end() + 30]
            interval = ("hour" if HOURLY_RE.search(window) else "month" if MONTHLY_RE.search(window)
                        else "week" if WEEKLY_RE.search(window) else None)
            if interval is None:                             # "Hourly rate:", "Monthly salary:"
                interval = ("hour" if HOURLY_RE.search(label) else "month" if MONTHLY_RE.search(label)
                            else "week" if WEEKLY_RE.search(label) else "year")
            if interval == "year" and hi < 1000 and not k_any:
                continue
            if re.match(r"\s*(?:m|mm|million|b|billion)\b", tail, re.IGNORECASE):
                continue
            # the currency: a code (before, after, or in the label) beats a symbol, a specific
            # symbol (HK$, £) beats a bare "$", and a bare "$" names no currency
            after = re.match(rf"\s*({_CODE})", tail, re.IGNORECASE)
            lab_code = re.search(rf"(?<![A-Za-z])({_CODES})(?![A-Za-z])", label)      # upper case only
            code = (m.group("code") or (after.group(1) if after else None)
                    or (lab_code.group(1) if lab_code else None))
            sym = m.group("sym")
            if code:
                cur, bare = _CUR[code.lower()], False
            elif sym and sym != "$":
                cur, bare = _CUR[sym.lower()], False
            else:
                cur, bare = "USD", True
            clean = _NEUTRAL_RE.sub(" ", label)
            if _NONPAY_RE.search(clean) or _NONPAY_AFTER.match(tail):
                kind = "nonpay"
            elif _PAYWORD_RE.search(clean):
                kind = "pay"
            else:
                kind = "plain"
            out.append({"min": _num(lo), "max": _num(hi), "currency": cur, "interval": interval,
                        "source": f"posting text, line {n}", "currency_stated": not bare,
                        "kind": kind, "label": label.strip()})
        if line.strip():
            prev = line.strip()
    return out


def pay_from_text(text: str, currency: str = None):
    """The pay stated in the text, or None. Every range is read with its label: a bonus,
    stipend, equity, grant, relocation, budget or commission range is not the salary; a
    range labelled salary/base/pay/compensation is preferred to an unlabelled one. When several
    pay ranges remain (location or level tiers) the highest, annualised, is judged and
    `ranges` / `note` say how many; with `currency` the tiers in that currency are the ones
    compared. None when no pay range is stated (`nonpay_only` on `pay_ranges` tells a posting
    with only bonus-like ranges from one with none)."""
    rs = [r for r in pay_ranges(text) if r["kind"] != "nonpay"]
    if not rs:
        return None
    if any(r["kind"] == "pay" for r in rs):
        rs = [r for r in rs if r["kind"] == "pay"]
    pool = [r for r in rs if currency and r["currency"] == currency] or rs
    seen, uniq = set(), []
    for r in pool:
        k = (r["min"], r["max"], r["interval"], r["currency"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    best = max(uniq, key=lambda r: r["max"] * PER_YEAR[r["interval"]])
    out = {k: best[k] for k in ("min", "max", "currency", "interval", "source", "currency_stated")}
    if len(uniq) > 1:
        out["ranges"] = len(uniq)
        out["note"] = f"{len(uniq)} pay ranges stated (location or level tiers); judged on the highest"
    return out


def nonpay_only(text: str) -> list:
    """The labels of ranges found when every range in the text is a bonus, stipend, equity,
    grant or similar (so no pay is stated), else []."""
    rs = pay_ranges(text)
    return [r["label"] for r in rs] if rs and all(r["kind"] == "nonpay" for r in rs) else []


_REMOTE_COMPOUND = r"(?:sensing|access|desktop|control|monitoring|execution|exploit\w*|procedure call)"
_NEG_REMOTE = re.compile(r"(?:\bnot|\bno|\bnever|\bwithout|\bnon)[\s-]+(?:a\s+)?remote\b|\bisn'?t remote\b")
_ONSITE = re.compile(r"\b(?:on[- ]?site|in[- ]office)\b")


def workplace_from_text(meta: dict):
    """(workplace, source) from the location or title, or (None, None). Only an explicit word
    counts: an office city is not 'onsite' (the role may still be remote-friendly). A negated
    remote ("not remote", "no remote", "non-remote") is onsite when the text says onsite, else
    unknown; "remote sensing" and its like are not a workplace; a text naming two workplaces
    ("Hybrid / Remote") answers "remote/hybrid", for the filter to judge: it passes only a
    filter that wants both."""
    for field in ("location", "role"):
        t = str(meta.get(field) or "").lower()
        if _NEG_REMOTE.search(t):
            return ("onsite", f"{field} text") if _ONSITE.search(t) else (None, None)
        modes = []
        if re.search(rf"\bremote\b(?!\s+{_REMOTE_COMPOUND}\b)", t):
            modes.append("remote")
        if re.search(r"\bhybrid\b", t):
            modes.append("hybrid")
        if _ONSITE.search(t):
            modes.append("onsite")
        if modes:
            return "/".join(modes), f"{field} text"
    return None, None


DOLLAR_COUNTRIES = ("australia", "canada", "new zealand", "singapore", "hong kong", "mexico",
                    "taiwan", "brazil", "argentina", "chile", "colombia")


def _dollar_country(meta: dict):
    """The country a bare "$" would not mean USD in, when the location names one."""
    loc = str(meta.get("location") or "").lower()
    return next((c.title() for c in DOLLAR_COUNTRIES if c in loc), None)


_US_STATE_NAMES = (
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming", "district of columbia")      # not "Georgia": it is also a country
_US_CODES = ("AL AK AZ AR CA CO CT DE FL HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
             "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC").split()


def _us_evidence(meta: dict) -> bool:
    """True when the location says United States: US / USA / United States, a state name, or a
    state code after a comma ("Austin, TX"). Nothing else makes a bare "$" USD."""
    loc = str(meta.get("location") or "")
    low = loc.lower()
    # "America" alone is not the US ("Latin America", "South America"): only the full name counts
    if re.search(r"\b(?:u\.?s\.?a?|united states(?: of america)?)\b", low):
        return True
    if any(re.search(rf"\b{re.escape(n)}\b", low) for n in _US_STATE_NAMES):
        return True
    # a state code ends the location or a part of it ("Austin, TX", "Remote - CA", "MA 02110",
    # "OR / WA"); a capitalised word in a phrase is not one ("Hybrid OR Remote", "- IN OFFICE")
    return bool(re.search(rf"(?:^|,|\(|-|/|\s)\s*(?:{'|'.join(_US_CODES)})(?=\s*(?:$|[,)/;|]|\d{{5}}))", loc))


def _money(v: float, cur: str) -> str:
    sym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(cur, cur + " ")
    return f"{sym}{v:,.0f}"


def evaluate(cfg, meta: dict, jd: str = "") -> list:
    """[{filter, verdict, reason, source}] for each filter [wants] sets; [] when it sets none."""
    w = getattr(cfg, "wants", None) or {}
    out = []
    if w.get("workplace"):
        want = w["workplace"]
        got, src = meta.get("workplace"), meta.get("workplace_source") or "board field"
        if not got:
            got, src = workplace_from_text(meta)
        if not got:
            out.append({"filter": "workplace", "verdict": "unknown", "source": None,
                        "reason": "workplace not stated (no board field; location and title do not say)"})
        else:
            modes = got.split("/")
            label = " and ".join({"onsite": "on-site"}.get(g, g) for g in modes)
            if len(modes) > 1:                    # the text names two workplaces: pass only a filter wanting all
                ok = all(g in want for g in modes)
                out.append({"filter": "workplace", "verdict": "pass" if ok else "unknown", "source": src,
                            "reason": f"the text names {label} ({src})" +
                                      ("" if ok else f"; you want {', '.join(want)}, so it is not decided")})
            else:
                ok = got in want
                out.append({"filter": "workplace", "verdict": "pass" if ok else "fail", "source": src,
                            "reason": f"{label} ({src})" + ("" if ok else f"; you want {', '.join(want)}")})
    if w.get("pay_min") is not None:
        floor, cur = w["pay_min"], w.get("pay_currency", "USD")
        pay = meta.get("pay") or pay_from_text(jd, cur)
        where = _dollar_country(meta)
        if pay and pay.get("currency_stated") is False and where:
            out.append({"filter": "pay", "verdict": "unknown", "source": pay["source"],
                        "reason": f"the range is in \"$\" with no currency named, and the posting is "
                                  f"located in {where}, where \"$\" is not USD"})
        elif pay and pay.get("currency_stated") is False and not _us_evidence(meta):
            loc = str(meta.get("location") or "").strip()
            out.append({"filter": "pay", "verdict": "unknown", "source": pay["source"],
                        "reason": "the range is in \"$\" with no currency named, and the location "
                                  + (f"({loc}) " if loc else "(none stated) ") +
                                  "does not say United States, so the currency is not known"})
        elif not pay:
            bonus = nonpay_only(jd)
            out.append({"filter": "pay", "verdict": "unknown", "source": None,
                        "reason": "no pay range stated" if not bonus else
                                  f"no pay range stated (the only range(s) are not pay: {'; '.join(bonus)[:80]})"})
        elif pay["currency"] != cur:
            out.append({"filter": "pay", "verdict": "unknown", "source": pay["source"],
                        "reason": f"pay is in {pay['currency']}, the floor in {cur}; no conversion is made"})
        else:
            per = PER_YEAR.get(pay["interval"], 1)
            top, note = pay["max"] * per, ""
            if pay["interval"] == "hour":
                note = f" ({_money(pay['max'], cur)} an hour at 2,080 hours a year)"
            elif pay["interval"] in ("month", "week"):
                note = f" ({_money(pay['max'], cur)} a {pay['interval']} x {per})"
            if pay.get("note"):
                note += f"; {pay['note']}"
            ok = top >= floor
            out.append({"filter": "pay", "verdict": "pass" if ok else "fail", "source": pay["source"],
                        "reason": (f"pays up to {_money(top, cur)} a year{note}" +
                                   ("" if ok else f", below your floor of {_money(floor, cur)}") +
                                   f" ({pay['source']})")})
    for b in w.get("benefits") or []:
        if b in (meta.get("board_benefits") or []):
            out.append({"filter": f"benefit: {b}", "policy": "benefits", "verdict": "pass",
                        "source": "board field", "reason": "stated in the board field (compensation)"})
        else:
            out.append(_benefit(b, w.get("benefit_phrases", {}), jd, getattr(cfg, "headings", None)))
    return out


# a negation just before a phrase ("not eligible for equity", "do not offer unlimited PTO",
# "no equity") or just after it ("equity is not offered"); only filler words may sit between
_FILLER = (r"(?:(?:eligible|eligibility|for|offer|offers|offered|offering|provide|provides|provided|include|"
           r"includes|included|available|receive|have|has|a|an|any|the|to|of|be|is|are|currently|entitled|"
           r"participate|participation|in|with|we|you|our)\s+){0,3}")
_NEG_WORD = (r"(?:\bnot|\bno|\bnon|\bnever|\bwithout|\bdon'?t|\bdoesn'?t|\bisn'?t|\baren'?t|\bineligible|"
             r"\bexcluding|\bexcluded|\bunavailable)")
_NEG_BEFORE = re.compile(rf"{_NEG_WORD}[\s-]+{_FILLER}$", re.IGNORECASE)
_NEG_AFTER = re.compile(r"^\s+(?:(?:is|are|will be|was)\s+)?(?:not|no longer|never|unavailable|excluded|ineligible)\b|"
                        r"^\s+(?:isn'?t|aren'?t)\b", re.IGNORECASE)
STATEMENT_KINDS = ("benefits", "other", "none")     # not responsibilities, company, legal, required, preferred


def _hits(spec: dict, spellings: list, ln) -> list:
    """[(start, end)] of this benefit's phrases in the line."""
    low = ln.text.lower()
    pats = [rf"(?<![\w-]){re.escape(sp.lower())}(?![\w])" for sp in spellings] + list(spec.get("re", []))
    if ln.kind == "benefits" and spec.get("bare") and not re.search(spec.get("bare_not", r"(?!x)x"), low):
        pats.append(spec["bare"])
    return [m.span() for pat in pats for m in re.finditer(pat, low)]


def _negated(text: str, span: tuple) -> bool:
    low = text.lower()
    clause_start = max(low.rfind(c, 0, span[0]) for c in ".;") + 1
    before = low[clause_start:span[0]]
    after = low[span[1]:span[1] + 30]
    return bool(_NEG_BEFORE.search(before) or _NEG_AFTER.match(after))


def _benefit(name: str, extra: dict, jd: str, headings=None) -> dict:
    """pass when a benefits-type line states the benefit; fail when a line rules it out (a
    negation next to the phrase, or for unlimited PTO a fixed allowance stated as the allowance
    when no line says open); unknown otherwise: a posting that does not mention it has not
    said no. Responsibilities, company, legal, required and preferred text never counts either
    way, and every pass spelling is looked for in the whole posting before any rule-out."""
    from . import sections as S
    spec = BENEFITS.get(name, {})
    spellings = ([] if spec.get("bare") else [name]) + spec.get("any", []) + list(extra.get(name, []))
    lines = [ln for ln in S.split(jd, headings) if ln.text and not ln.heading and ln.kind in STATEMENT_KINDS]
    row = {"filter": f"benefit: {name}", "policy": "benefits"}
    ruled = None
    for ln in lines:
        for span in _hits(spec, spellings, ln):
            if _negated(ln.text, span):
                ruled = ruled or ln
            else:
                return dict(row, verdict="pass", source="posting text", reason=f"stated: {ln.text.strip()[:90]}")
    if ruled is None:
        for ln in lines:
            if spec.get("against_skip") and re.search(spec["against_skip"], ln.text, re.IGNORECASE):
                continue
            if any(re.search(pat, ln.text, re.IGNORECASE) for pat in spec.get("against", [])):
                ruled = ln
                break
    if ruled is not None:
        return dict(row, verdict="fail", source="posting text", reason=f"ruled out: {ruled.text.strip()[:90]}")
    return dict(row, verdict="unknown", source=None, reason="not mentioned in the posting")


def _decide(results, policy) -> tuple:
    fails = [r for r in results if r["verdict"] == "fail"]
    if fails:
        return "exclude", "; ".join(f"{r['filter']}: {r['reason']}" for r in fails)
    flagged = []
    for r in results:
        if r["verdict"] != "unknown":
            continue
        key = r.get("policy", r["filter"])
        p = policy.get(key, "keep")
        if p == "drop":
            return "exclude", f"{r['filter']}: {r['reason']} ({key}_unknown = drop)"
        if p == "flag":
            flagged.append(f"{r['filter']}: {r['reason']}")
    if flagged:
        return "flag", "; ".join(flagged)
    return "keep", ""


def decide(cfg, results: list) -> tuple:
    """('keep' | 'flag' | 'exclude', why). A fail excludes; an unknown follows its own
    filter's `*_unknown` policy (keep by default)."""
    w = getattr(cfg, "wants", None) or {}
    return _decide(results, {k[:-8]: v for k, v in w.items() if k.endswith("_unknown")})


def parse(table: dict, error) -> dict:
    """The [wants] table, checked. `error` is the exception type for a bad value."""
    extra = set(table) - WANT_KEYS
    if extra:
        raise error(f"config: unknown [wants] key(s) {', '.join(sorted(extra))} "
                    f"(known: {', '.join(sorted(WANT_KEYS))})")
    out = {}
    if "workplace" in table:
        v = table["workplace"]
        if not isinstance(v, list) or not v or any(x not in WORKPLACES for x in v):
            raise error(f"config: [wants] workplace must be a list of {', '.join(WORKPLACES)}")
        out["workplace"] = list(v)
    if "pay_min" in table:
        v = table["pay_min"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise error("config: [wants] pay_min must be a number (a yearly amount)")
        out["pay_min"] = v
    if "pay_currency" in table:
        v = str(table["pay_currency"]).upper()
        if v not in set(_CUR.values()):
            raise error(f"config: [wants] pay_currency must be one of {', '.join(sorted(set(_CUR.values())))}")
        out["pay_currency"] = v
    if "benefits" in table:
        v = table["benefits"]
        if not isinstance(v, list) or not v or not all(isinstance(x, str) and x.strip() for x in v):
            raise error("config: [wants] benefits must be a list of benefit names (e.g. \"unlimited pto\")")
        out["benefits"] = [x.strip().lower() for x in v]
    if "benefit_phrases" in table:
        v = table["benefit_phrases"]
        if not isinstance(v, dict) or not all(isinstance(x, list) and all(isinstance(y, str) and y.strip()
                                                                           for y in x) for x in v.values()):
            raise error("config: [wants.benefit_phrases] maps a benefit name to a list of spellings")
        out["benefit_phrases"] = {k.strip().lower(): [y.strip() for y in x] for k, x in v.items()}
    for k in ("workplace_unknown", "pay_unknown", "benefits_unknown"):
        if k in table:
            if table[k] not in POLICIES:
                raise error(f"config: [wants] {k} must be one of {', '.join(POLICIES)}")
            out[k] = table[k]
    return out
