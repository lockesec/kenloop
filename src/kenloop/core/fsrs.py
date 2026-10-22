"""FSRS-6 spaced-repetition scheduling.

The formulas and default parameters are those of py-fsrs 6.3.2
(https://github.com/open-spaced-repetition/py-fsrs, MIT License,
Copyright (c) 2022 Open Spaced Repetition; see THIRD_PARTY_NOTICES). This is
a re-implementation, not a copy, and it is tested against py-fsrs itself.

Configured like ``fsrs.Scheduler(learning_steps=(), relearning_steps=(),
enable_fuzzing=False)`` on whole-day timestamps, with two deliberate
deviations:

1. every Again (a miss, a partial, or a correct that was guessed, hinted or
   read) is scheduled for tomorrow, whatever the stability says;
2. an exam date caps each interval so reviews land before the exam
   (``exam_clamp``).

Ratings used: Again (1), Hard (2, a correct you were unsure of), Good (3).
Easy is never emitted: no signal here distinguishes it from Good.
"""
from __future__ import annotations

import datetime as _dt
import math

W = (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001,
     1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014,
     1.8729, 0.5425, 0.0912, 0.0658, 0.1542)
DECAY = -W[20]
FACTOR = 0.9 ** (1 / DECAY) - 1
DESIRED_RETENTION = 0.9
S_MIN = 0.001
MAX_INTERVAL = 36500
AGAIN, HARD, GOOD = 1, 2, 3


def retrievability(s: float, t: float) -> float:
    if s <= 0:
        return 0.0
    return (1 + FACTOR * max(0.0, t) / s) ** DECAY


def _clamp_d(d: float) -> float:
    return min(10.0, max(1.0, d))


def initial_difficulty(g: int, clamp: bool = True) -> float:
    d = W[4] - math.e ** (W[5] * (g - 1)) + 1
    return _clamp_d(d) if clamp else d


def initial_stability(g: int) -> float:
    return max(S_MIN, W[g - 1])


def next_difficulty(d: float, g: int) -> float:
    delta = -(W[6] * (g - 3))
    damped = d + (10.0 - d) * delta / 9.0
    return _clamp_d(W[7] * initial_difficulty(4, clamp=False) + (1 - W[7]) * damped)


def short_term_stability(s: float, g: int) -> float:
    inc = math.e ** (W[17] * (g - 3 + W[18])) * s ** -W[19]
    if g in (HARD, GOOD):
        inc = max(inc, 1.0)
    return max(S_MIN, s * inc)


def forget_stability(d: float, s: float, r: float) -> float:
    long_term = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.e ** ((1 - r) * W[14])
    return max(S_MIN, min(long_term, s / math.e ** (W[17] * W[18])))


def recall_stability(d: float, s: float, r: float, g: int) -> float:
    hard_penalty = W[15] if g == HARD else 1.0
    return max(S_MIN, s * (1 + math.e ** W[8] * (11 - d) * s ** -W[9]
                           * (math.e ** ((1 - r) * W[10]) - 1) * hard_penalty))


def next_interval(s: float) -> int:
    i = round((s / FACTOR) * (DESIRED_RETENTION ** (1 / DECAY) - 1))
    return min(max(i, 1), MAX_INTERVAL)


# --- exam-date clamp -------------------------------------------------------
# Reviews for a dated exam are spaced as a fraction of the time left, falling
# from about 30% of the gap at a week out to about 7.5% at a year out
# (log-linear between the two anchors, clamped to [0.05, 0.40]).
_A_DAYS, _A_FRAC, _B_DAYS, _B_FRAC = 7, 0.30, 365, 0.075


def ridge_fraction(days: int) -> float:
    slope = (_B_FRAC - _A_FRAC) / (math.log10(_B_DAYS) - math.log10(_A_DAYS))
    f = _A_FRAC + slope * (math.log10(max(1, days)) - math.log10(_A_DAYS))
    return min(0.40, max(0.05, f))


def exam_clamp(interval: int, exam: _dt.date | None, today: _dt.date) -> tuple:
    """(interval, reason). Never lengthens an interval; no exam, or an exam
    today or past, is the identity."""
    if exam is None:
        return interval, ""
    days = (exam - today).days
    if days <= 0:
        return interval, ""
    ridge = max(1, round(ridge_fraction(days) * days))
    before = max(1, days - 1)
    capped = min(interval, ridge, before)
    if capped >= interval:
        return interval, ""
    return capped, ("pre-exam" if before < ridge else "ridgeline")


def update(c: dict, g: int, today: _dt.date, exam: _dt.date | None = None) -> None:
    """Schedule concept `c` after a review graded `g` on `today`."""
    s, d = c.get("stability"), c.get("difficulty")
    if not s or not d:
        s2, d2 = initial_stability(g), initial_difficulty(g)
    else:
        prev = None
        if c.get("due") and c.get("interval"):
            prev = _dt.date.fromisoformat(c["due"]) - _dt.timedelta(days=int(c["interval"]))
        t = (today - prev).days if prev else 1
        if t < 1:
            s2 = short_term_stability(s, g)
        elif g == AGAIN:
            s2 = forget_stability(d, s, retrievability(s, t))
        else:
            s2 = recall_stability(d, s, retrievability(s, t), g)
        d2 = next_difficulty(d, g)
    interval = 1 if g == AGAIN else next_interval(s2)
    interval, why = exam_clamp(interval, exam, today)
    c["stability"], c["difficulty"] = round(s2, 4), round(d2, 4)
    c["interval"] = interval
    c["due"] = (today + _dt.timedelta(days=interval)).isoformat()
    if why:
        c["exam_clamp"] = why
    else:
        c.pop("exam_clamp", None)
