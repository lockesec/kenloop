# The module standard

kenloop is a small kernel and modules that plug into it through declared seams. The kernel keeps
the record and the rules that turn an answer into credit; everything else (sessions, focus, certs,
promotion, the job search) is a module. This file is the contract a module keeps; the conformance
test is `tests/test_modules.py` (with `tests/test_skills.py` and `tests/test_layers.py`).

## The kernel

`core/learn.py` (the record: rows, `facets`, `repeats`, `apply_row`, replay and audit),
`core/fsrs.py` (the schedule), `core/ledger.py` (every append-only file), `core/height.py` (the
pyramid, derived), the topic settings, and `home`, `errors`, `names`. Around the kernel
in `core/` sit `plan.py` (create and sync a topic, bank questions), `quiz.py` (selection and the
quiz), `reviews.py` (due, graduation evidence, misconceptions, calibration) and `integrity.py`
(rename, rebuild, validate, brief); `learn` re-exports their names, and they reach the kernel
only through `learn.`. Only the kernel moves
credit or the schedule, or writes derived state. Its invariants:

1. One idea, one record: the same idea in two topics (a shared `:: same:` key) is one held set.
2. One path from an answer to state: `apply_row`. Height, views, `next`, notes, sessions and
   dialogues are derived or advisory.
3. Credit needs an unaided answer on the first look at the idea that day. Teaching, guesses
   (`predict`), hints, told answers, repeats and graded dialogues are recorded, never credited.
4. Replay is a pure function of the ledgers and the declared settings; `rebuild --check` can say
   DRIFT. An absent or damaged input reads NOT EVALUABLE, never clean.
5. Ledgers are append-only, declared, and ordered by position.
6. The learner owns the record: a tutor records through `ken`; after `init` writes the template, nothing writes facts.md.

## The seams

| seam | a module declares | read by |
|---|---|---|
| commands | `commands(groups)`: adds parsers to `groups[""]` (top level) or `groups["jobs"]`; each sets `run=fn(cfg, ns) -> exit code` | `cli.build_parser` via `modules.register` |
| ledgers | a `LEDGER` file name, declared in `core/ledger.py` `LEDGERS`; reads with `ledger.read`, writes with `ledger.append` | `.gitattributes`, `doctor`, the docs' data list |
| rules | `rules() -> [(name, fn(ctx), after)]`: a rule for `next`, inserted after the named one; it reports through `ctx.add` and writes nothing | `loop.evaluate` via `modules.rules` |
| doctor | `doctor(cfg) -> [(level, text)]`, level FINDING, NOT EVALUABLE or DRIFT | `loop.doctor` via `modules.doctors` (worst wins) |
| offers | an object with `prefix`, `offers(cfg, slug, reached_only)`, `check_source(cfg, source, rows)` and `report(cfg, rows, slug)`, registered with `core/branches.register_provider` at import: its offers join `ken branch`, `session` and `talk`, its `<prefix>:N` keys are checked by it, its lines join the branch report | `core/branches.py` (`kenloop.scouts` is one) |
| skills | a skill under `skills/` with `modes:` in its frontmatter; every record mode has exactly one owner, every `ken` command a skill names must parse | `tests/test_skills.py` |

## What a module must not do

Call `apply_row`, `fsrs.update` or `save_state`; append to a file except through
`ledger.append`; write facts.md; import another module's private (`_`) names; or, from `core/`,
import the career sidecar. A module may read anything the kernel exposes.

## The modules

| module | what it adds |
|---|---|
| `kenloop.study` | the study verbs: plan, sync, bank, quiz, record, talk, place, branch, ask/rung, recall, map, the views (board, mastery, due, misconceptions, calibration, beliefs, dive, foundations) and the integrity commands (rename, rebuild, brief, validate) |
| `kenloop.career.commands` | `ken jobs ...`: the job-search sidecar's verbs |
| `kenloop.core.settings` | `ken settings`: intent and depth per topic, rung or line; `--migrate` renames old setting names |
| `kenloop.core.marks` | `ken mark` and `ken trail`: how ideas feel (marks.jsonl, never credit) and the path back to what started a thread (trail.jsonl) |
| `kenloop.core.focus` | `ken focus`: what `next` points at (focus.jsonl); a doctor check for a focus on a removed topic |
| `kenloop.session` | `ken session`, `ken note`, `ken taught`: the view a tutor starts from, and the tutor's notes |
| `kenloop.scouts` | `ken scout`: predicted branches (scouts.jsonl), offered through the offers seam once their concept is studied, scored when decided; a doctor check for damaged lines |
| `kenloop.journal` | `ken close`, `ken sessions`: the session journal (sessions.jsonl), never evidence |
| `kenloop.printout` | `ken print`: a topic's reference sheet and session printouts rendered as pages, never evidence |
| `kenloop.gaps` | `ken gap`, `ken gaps`: misses the teaching caused (tutor_gaps.jsonl), never evidence about the learner |
| `kenloop.certs` | `ken cert exam`, `passed`, `exam-date`: a cert: a topic studied toward an exam date |
| `kenloop.career.promote` | `ken jobs promote`: an interest concept put forward as a job skill (promotions.jsonl) |

`cli.py` keeps only the program's own verbs (`init`, `next`, `doctor`) and the `jobs` group; every
other verb is a module's.

## Adding a module

1. Write `kenloop/<name>.py` with `commands(groups)`, and `rules()` / `doctor(cfg)` if it has them.
2. Declare any ledger in `LEDGERS` (and regenerate a study home's `.gitattributes`; `doctor` says
   when one is missing a line).
3. Add the import path to `MODULES` in `kenloop/modules.py` and a row to the table above.
4. If a tutor runs it, give it a skill, or name it in one, and give every new record mode exactly
   one owning skill.
5. `pytest tests/test_modules.py tests/test_skills.py tests/test_layers.py`.
