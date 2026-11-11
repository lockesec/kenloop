# Changelog

## 0.1.2 (2026-11-10)

**Upgrade note:** `ken gap` has three new kinds (`unverified`, `misread`, `process`). A ken older than
this release reads a row with one of them as a damaged line, so upgrade every ken that reads a study
home before recording a new kind there. `-` as the concept and `--by` are read fine by older versions.

Found while running the daily digest beside a tracked pipeline:

- **`ken jobs digest` knows the roles you track.** A posting you applied to, passed on or closed
  leaves the tables for one line under "Already tracked"; one in your work queue stays, marked
  "tracked". Matched on the posting URL, or the job id at the same company.
- **Start here.** The digest opens with the five best new apply-first postings and a count of the rest;
  `[digest] place_order` ranks them by the places you would rather.
- **Follow-ups.** Roles in status `applied` are listed at day 7 (check the portal), day 14 (a short
  note) and day 30 (the command that closes it as `no_response`).

Moved in from a private helper, so the whole application runs from `ken`:

- **`ken jobs build SLUG`** compiles a role's LaTeX resume, and the cover letter beside it, with
  tectonic, and checks each PDF: one page, the last words of every bullet and of the closing
  paragraph present in the PDF text (a line that ran off the page is named), and no text in the
  bottom 0.25in. Missing tectonic, pdfinfo or pdftotext exits 2 and builds nothing.
- **PDFs are filed by whether the employer has them**: `sent/`, `ready/` and `old/<slug>` under
  `[build] pdf_root`. `ken jobs status` moves the folder when a role crosses over; `sent/` is the
  record of what was submitted, so `build` refuses to write there (`--outdir` builds a copy
  elsewhere) and a move never overwrites a folder.

Found while studying a new topic with the tool:

- **`ken profile --folded`** marks every learner note written so far as taken into the profile
  (Updated today, `Folded:` their count), so a note folded in on the day it was written stops
  showing as new. A count larger than the notes on file is not trusted; the day rule holds.
- **`ken session --brief`** leaves the profile's text out on a second look; new notes still show.
- **Empty rungs are named.** `ken place` and `ken session` say which rungs of a scale have no
  concept yet, and `place` offers `--start 0` before the placement steps.
- **Foundations notes are the lesson's preparation.** The scaffold says to write the note before
  teaching, from sources read that day; it has a say-back section and separates what was read
  from what was written from memory. `ken-tutor` has the tutor write it first; `ken-climb` teaches from it and finishes it after.
- **Tutor skills.** A question with parts is numbered and a short reply is matched part by part
  before any part is called skipped; `ken-place` offers "start at the bottom" before it asks.
- A note that opens with today's date no longer shows the date twice.
- **The tutor reviews its own teaching at the close.** `ken gaps SLUG --review` prints what to
  re-read the session for, the gaps logged today, and one question for the learner ("did you
  notice any sharp edges?"). `ken gap` takes three new kinds (`unverified`, `misread`,
  `process`), `-` for a miss about the session, and `--by learner` for what the learner noticed,
  kept in their words. `ken close` points at the review and `ken session` opens with the last
  three gaps on the topic.
- **A session opens with 3-4 recalls**, weakest and most overdue first; the other due reviews are
  folded into the lesson where they fit, and the rest wait.
- **References cite the human studies** behind self-explanation, question generation and
  curiosity (`docs/references.md`).

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
