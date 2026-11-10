"""Pay parsing reads text supplied by job boards (up to 20 MB), so it must stay linear: a run of
"a." with no spaces once took 46 s at 80 KB, and a long run of spaces was quadratic too."""
import time

import pytest

from kenloop.career import wants


def _secs(text):
    best = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        wants.pay_ranges(text)
        best = min(best, time.perf_counter() - t0)
    return best


@pytest.mark.parametrize("unit,n", [("a.", 2000), (" ", 4000), ("\t", 4000), ("$1 ", 2000),
                                    ("x" * 50 + ".pdf ", 200)])
def test_pay_ranges_is_linear(unit, n):
    small, big = _secs(unit * n), _secs(unit * 4 * n)
    assert big < max(small, 0.005) * 8, (unit, small, big)
