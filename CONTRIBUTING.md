# Contributing

- `python -m pip install -e ".[test]" fsrs && python -m pytest -q` (the `test` extra brings `pytest` and `hypothesis`)
  (`fsrs` is py-fsrs, the parity oracle for the scheduler; without it that test
  skips, visibly).
- FSRS parity figures: `PYTHONPATH=src python benchmarks/fsrs_parity.py` (needs `fsrs`; fixed seed;
  the methodology is in the script's docstring). README and DESIGN quote its output.
- `sh examples/demo.sh` must still walk the whole loop; `tests/test_demo.py`
  asserts what it shows. The README quick start must match its output:
  `sh examples/demo.sh > demo.out && sh examples/check_readme.sh demo.out`.
- A check needs a negative control: a test that fails if the check is removed
  or loosened by one unit.
- Anything that can be absent (a board, a resume, a facts sheet, a demand
  file) must say NOT EVALUABLE (exit 2) when it is, never report a clean or
  zero result.
- Demo and test data must be invented. Never add a real posting, employer,
  person, resume or exam question, even as an example. Each example directory
  carries a `SYNTHETIC-DATA` file stating this; keep it, and add one to any new
  example directory. `tests/test_demo.py` checks the demo's.
