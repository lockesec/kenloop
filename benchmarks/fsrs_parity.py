"""Parity of careerloop's FSRS-6 scheduler against py-fsrs 6.3.2.

Run (py-fsrs is an optional dependency, installed or on PYTHONPATH; it is not
needed by careerloop itself):

    PYTHONPATH=src python3 benchmarks/fsrs_parity.py            # 6000 sequences, seed 20260101
    PYTHONPATH=src python3 benchmarks/fsrs_parity.py --n 6000 --seed 20260101

Methodology (everything below is fixed by the seed and the constants here):

* py-fsrs is configured ``Scheduler(learning_steps=(), relearning_steps=(),
  enable_fuzzing=False)`` with whole-day timestamps, the configuration careerloop
  mirrors.
* Each sequence has 2 to 40 reviews (uniform). Ratings are Again 20%, Hard
  20%, Good 60% (Easy is never used: careerloop never emits it).
* Gap model: the next review is on py-fsrs's due date 70% of the time,
  otherwise 1 to 2x that interval days after the previous review (uniform
  integer, at least 1). The same dates are fed to both implementations.
* Both implementations keep their own state through the whole sequence, so
  careerloop's 4-decimal rounding of stability and difficulty accumulates.
* Careerloop stores stability to 4 decimals. After a long run of Again the
  stability sits near its 0.001 floor, where that rounding is a large fraction of
  the value; that is where the largest stability errors come from.
* Stability and difficulty are compared after every review as relative
  error. Intervals are compared after every non-Again review, because
  careerloop deliberately schedules every Again for tomorrow.

The script prints one block of figures and exits 0; it asserts nothing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import statistics
import sys

try:
    import fsrs as py_fsrs
except ImportError:
    print("NOT EVALUABLE: py-fsrs is not importable (pip install fsrs==6.3.2, or set PYTHONPATH)",
          file=sys.stderr)
    sys.exit(2)

from careerloop import fsrs as ours_mod

T0 = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)


def one_sequence(rng: random.Random):
    sch = py_fsrs.Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)
    card = py_fsrs.Card()
    ours: dict = {}
    when = T0
    rows = []                                   # (day_in_seq, rating, s_err, d_err, interval_diff or None)
    for k in range(rng.randint(2, 40)):
        g = rng.choices((1, 2, 3), weights=(20, 20, 60))[0]
        if k:
            span = max(1, (card.due - when).days)
            gap = span if rng.random() < 0.7 else rng.randint(1, 2 * span)
            when = when + dt.timedelta(days=max(1, gap))
        card, _ = sch.review_card(card, py_fsrs.Rating(g), review_datetime=when)
        ours_mod.update(ours, g, when.date())
        s_err = abs(ours["stability"] - card.stability) / card.stability
        d_err = abs(ours["difficulty"] - card.difficulty) / card.difficulty
        diff = None if g == 1 else ours["interval"] - (card.due - when).days
        rows.append(((when - T0).days, g, s_err, d_err, diff))
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=6000, help="number of sequences")
    ap.add_argument("--seed", type=int, default=20260101)
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    seqs = [one_sequence(rng) for _ in range(a.n)]
    rows = [r for s in seqs for r in s]
    s_err = [r[2] for r in rows]
    d_err = [r[3] for r in rows]
    iv = [r for r in rows if r[4] is not None]
    differ = [r for r in iv if r[4] != 0]
    late = [r for r in iv if r[0] > 3650]
    late_diff = [r for r in late if r[4] != 0]
    try:
        from importlib.metadata import version
        ver = version("fsrs")
    except Exception:
        ver = "version unknown"
    print(f"py-fsrs {ver}; seed {a.seed}; "
          f"{a.n} sequences, {len(rows)} reviews")
    print(f"stability relative error:  max {max(s_err):.4%}  median {statistics.median(s_err):.4%}")
    print(f"  reviews with stability error above 0.2%: {sum(1 for e in s_err if e > 0.002)} of {len(rows)}")
    print(f"difficulty relative error: max {max(d_err):.4%}  median {statistics.median(d_err):.4%}")
    print(f"non-Again intervals compared: {len(iv)}; differ: {len(differ)} ({len(differ) / len(iv):.2%}); "
          f"max |diff| {max((abs(r[4]) for r in iv), default=0)} day(s)")
    print(f"  of the differing: {sum(1 for r in differ if r[0] > 3650)} are more than 10 years "
          f"into a sequence; of {len(late)} reviews that late, {len(late_diff)} differ")
    print(f"sequences with any interval difference: {sum(1 for s in seqs if any(r[4] for r in s))} of {a.n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
