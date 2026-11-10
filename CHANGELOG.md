# Changelog

## 0.1.1 (2026-11-09)

- Python 3.11 or newer is required (3.9 and 3.10 are end-of-life). CI tests 3.11 to 3.14 on `ubuntu-latest`.
- **Author.** The package metadata and NOTICE name the author, locke.
- **The same-day rule follows renames.** An answer after `rename` on the same day is a
  repeat, as it would be under the old name.
- **Damage is named, not a crash.** A concept field or a role's `coverage_pct` of the wrong
  type, and a `deadline` or `complete` that is not a real date, are NOT EVALUABLE with the
  file and the fix; a date typo no longer takes a topic off the schedule.
- **One-line inputs.** `bank`, `branch`, `rung` and `scout` refuse a value holding a line
  break instead of writing a second section into the file.
- **Practice exams** never print a banked question twice; extra draws ask for a new one.
- **Job search.** A board that lists a posting twice no longer stops `discover --intake`;
  pay parsing stays linear on long board text.
- **Concept ids** for names outside Latin script are distinct (an ASCII punycode tail),
  and a domain or name with no letters is refused.
- **Docs.** The skills point at the rule documents by URL; the README says what a clone
  adds over the package and how the tool is built; `ken validate` is back in the command list.

## 0.1.0 (2026-11-09)

First public release, Apache-2.0. The command is `ken` (`kenloop` also works). How it was built and
what its reviews found: [DESIGN.md](DESIGN.md).

**Study**

- Topics and syllabuses, spaced review with FSRS-6, quizzes and practice exams from a question bank.
- Credit only for unaided recall: hints, lookups, guesses and same-day repeats earn none.
- A same-day repeat earns no credit but is still scheduled: a concept predicted or taught first, then answered right the same day, is due tomorrow instead of due now.
- A prediction keeps what was predicted (`record --mode predict --before "..."`), and `ken beliefs` shows each one beside the next answer on it.
- `ken board` shows a topic's dialogue reasoning (`reasoning 1.3/2 on 2`) beside the badges, which quiz credit alone moves.
- Teaching schedules the first cold recall: `ken taught` makes the concept due tomorrow (still no credit), `ken due` lists it, and the tutor skills open each session with it as a cold explain-back recorded as a plain answer.
- A session close takes how much you feel you learned as 1-5 or in your own words, kept as said.
- `ken profile`: a curated learner profile the tutor reads first; `session` shows it, then only the notes written since.
- `before:TOPIC/CONCEPT` in a syllabus line: a concept learned before one in another topic; validate checks it names a real one.
- `ken print`: a topic's reference sheet and session printouts (templates via `--scaffold`) rendered to pages to print, PDF with Chrome.
- `ken gap` / `ken gaps`: a miss the teaching caused is counted against the tutor, never the learner.
- A passed exam topic can stay on the schedule (`settings SLUG --keep-studying on`): the exam is done, the material is not.
- Graded dialogue that records what you believed before and after and where your reasoning broke,
  kept apart from credit.
- A scale to place you on, pieces of a concept, question ladders, and branches for gaps found mid-study.
- `ken mark` and `ken trail`: say what feels like a problem and keep the way back to what started it.
- `ken next` names one thing to do and why; `ken focus` pins it to a topic or lane.
- `ken session`, `ken note` and the `ken-*` skills, so any assistant can pick up where the last stopped.

**Job search and exams, both optional**

- Postings from Greenhouse, Lever, Ashby and Workday, a daily digest, and coverage against your skills.
- `## Held` in `facts.md` as the only source of what you hold, which `jobs check-claims` enforces on a resume.
- Keyword packs for web, security (202 terms, 56 aliases) and data, plus your own.
- Exam dates that shorten reviews, and `ken cert passed` for a credential line you paste yourself.

**The record**

- Plain append-only files, checked against a replay of the log.
- Absence: `doctor` exits 2 on an empty or missing `facts.md`, and every command that could not look says so.
