"""Parity with py-fsrs itself. Kept in its own module so that, when py-fsrs is
absent, only this oracle skips; the scheduler's own tests always run."""
import datetime as dt
import math
import os

import pytest

from kenloop.core import fsrs

try:
    import fsrs as py_fsrs
except ImportError:                 # CI sets KENLOOP_REQUIRE_ORACLE so a skip cannot pass silently there
    if os.environ.get("KENLOOP_REQUIRE_ORACLE"):
        raise
    pytest.skip("py-fsrs not installed: the parity oracle did not run", allow_module_level=True)


@pytest.mark.parametrize("seq", [
    [(0, 3), (2, 3), (9, 3), (40, 3)],
    [(0, 3), (2, 2), (5, 3), (6, 1), (7, 3)],
    [(0, 1), (1, 3), (1, 3), (4, 2), (20, 3)],
    [(0, 2), (3, 2), (10, 2), (30, 2)],
])
def test_matches_py_fsrs(seq):
    """Same stability and difficulty as py-fsrs 6 with no learning steps, no
    fuzz, day timestamps. Intervals are compared only where our deliberate
    deviation (Again -> 1 day) does not apply."""
    sch = py_fsrs.Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)
    card = py_fsrs.Card()
    ours = {}
    t0 = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
    for day, g in seq:
        when = t0 + dt.timedelta(days=day)
        card, _log = sch.review_card(card, py_fsrs.Rating(g), review_datetime=when)
        fsrs.update(ours, g, when.date())       # derives elapsed days from due - interval
        assert math.isclose(ours["stability"], card.stability, rel_tol=1e-3), (day, g)
        assert math.isclose(ours["difficulty"], card.difficulty, rel_tol=1e-3), (day, g)
        if g != 1:
            assert ours["interval"] == (card.due - when).days
