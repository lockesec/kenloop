"""FSRS-6: identities, the Hard fix, the exam clamp, and parity with py-fsrs."""
import datetime as dt
import math


from careerloop import fsrs

D = dt.date(2030, 1, 1)


def test_initial_values():
    assert fsrs.initial_stability(fsrs.GOOD) == fsrs.W[2]
    assert math.isclose(fsrs.initial_difficulty(fsrs.GOOD), 2.118, abs_tol=1e-3)


def test_retrievability_identities_and_interval_checksum():
    assert fsrs.retrievability(5, 0) == 1
    assert math.isclose(fsrs.retrievability(7.3, 7.3), 0.9, abs_tol=1e-9)
    for s in (1.4, 2.3065, 10.6, 300.2):
        assert fsrs.next_interval(s) == max(1, round(s))


def test_a_successful_review_never_shrinks_stability():
    # the defect this pins: multiplying the whole new S by w15 gave 300 -> 255.6
    for s, d, t in ((300, 9, 300), (2.3065, 2.118, 2), (50, 5, 10), (0.5, 10, 1)):
        r = fsrs.retrievability(s, t)
        assert fsrs.recall_stability(d, s, r, fsrs.HARD) >= s
        assert fsrs.recall_stability(d, s, r, fsrs.GOOD) >= fsrs.recall_stability(d, s, r, fsrs.HARD)
    assert math.isclose(fsrs.recall_stability(9, 300, fsrs.retrievability(300, 300), fsrs.HARD), 375.2, abs_tol=0.1)
    assert math.isclose(fsrs.recall_stability(2.118, 2.3065, fsrs.retrievability(2.3065, 2), fsrs.HARD),
                        7.513, abs_tol=0.01)


def test_again_is_tomorrow():
    c = {}
    for g in (fsrs.GOOD, fsrs.GOOD):
        fsrs.update(c, g, D)
    fsrs.update(c, fsrs.AGAIN, D + dt.timedelta(days=10))
    assert c["interval"] == 1


def test_ridgeline():
    assert math.isclose(fsrs.ridge_fraction(7), 0.30, abs_tol=1e-9)
    assert math.isclose(fsrs.ridge_fraction(365), 0.075, abs_tol=1e-9)
    fr = [fsrs.ridge_fraction(d) for d in (1, 7, 30, 100, 365, 5000)]
    assert fr == sorted(fr, reverse=True) and min(fr) >= 0.05 and max(fr) <= 0.40
    assert fsrs.exam_clamp(30, D + dt.timedelta(days=30), D) == (7, "ridgeline")
    assert fsrs.exam_clamp(30, None, D) == (30, "")
    assert fsrs.exam_clamp(30, D, D) == (30, "")                      # exam today: identity
    assert fsrs.exam_clamp(2, D + dt.timedelta(days=30), D) == (2, "")  # never inflates
    assert fsrs.exam_clamp(10, D + dt.timedelta(days=2), D) == (1, "ridgeline")


def test_no_exam_leaves_no_clamp_field():
    c = {}
    fsrs.update(c, fsrs.GOOD, D)
    assert "exam_clamp" not in c
