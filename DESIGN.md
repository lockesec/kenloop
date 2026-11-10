# How kenloop was built

## The question

kenloop is built on one question: do you ken it? Recognising an answer when you see it is not
the same as being able to reach it yourself, and an assistant that hands you answers makes the
difference easy to miss. Each part of the tool asks that question a different way (see the
table at the top of the README) and records the answer honestly:

- only answers you gave without help earn credit;
- reasoning graded by an AI is kept apart from credit;
- a skill reaches your resume only when you say you hold it;
- anything the tool could not check says so.

The decisions below follow from that question.

## How it started

kenloop (named careerloop until 2026-10-22) began as two separate tools in a private
AI-experimentation environment: a job tracker and a study planner. They did not talk to each
other. Extracting them joined them around one contract:

1. **The loop is the product.** Search for roles, find the skills they want that you lack,
   study those, apply, then search again or learn more. `next` reads both halves and names the
   one thing most worth doing. (Since the rename to kenloop, study is the core and the job
   search is one add-on: see "Decision: learning is the core" below.)
2. **The facts sheet is the only source of truth, and only you write it.** A resume may state
   only what `facts.md` lists under `## Held` (rules in docs/trust-rules.md). `check-claims`
   checks the terms in the lexicon packs, plus acronyms with `--acronyms`, and nothing else.
   Study can propose a line for the sheet (`jobs graduate --emit`), but a person pastes it in.
3. **Absence is reported, never scored.** An unreachable job board, a missing resume, a damaged
   log, a board that lists nothing, or `doctor` run on an empty home all report NOT EVALUABLE
   (exit 2). None of them reads as a clean result or a zero.
4. **The log is the record.** Every attempt is appended to `log.jsonl` first. Mastery and
   schedules are computed from it, and can be recomputed from it to check that they have not
   drifted.
5. **Standard library only**, so there is no dependency supply chain to audit.

The scheduler is our own implementation of FSRS-6, tested against the reference library,
py-fsrs. `benchmarks/fsrs_parity.py` ran 6,000 random sequences of 2 to 40 reviews (fixed seed,
ratings 1 to 3) through both:

- **Stability** matched within 0.45% at worst and 0.0016% at the median. The worst cases come
  after long runs of Again, where rounding a very small stability to 4 decimals shows.
- **Difficulty** matched within 0.008%.
- **The interval** (days until the next review) differed in 0.38% of reviews, by up to 2 days.
  300 of those 382 differences came more than ten years into a sequence.

Two differences from FSRS are deliberate: an Again always schedules the next review for
tomorrow, and an exam date shortens intervals so reviews land before the exam.

## Adversarial reviews

Each review was run by a separate AI session that had not written the code. Every finding was
reproduced against the source and pinned to a test before it was fixed, and every finding was
fixed before the next review started. The first review ran on 2026-09-25.

| Review | Fixed | What it found |
|---|---|---|
| 1: paths and config shape | 2026-09-25 | A role slug you supplied could write outside the data directory (`jobs intake --slug ../../escaped`). A config section of the wrong shape (`ats = 1`) crashed with a traceback instead of reporting NOT EVALUABLE. |
| 2: integrity checks | 2026-09-25 | Integrity checks could read clean when they were not. `rebuild --check` compared only the concepts present in the derived file, so a concept that had been dropped looked fine. An unreadable log row was reported and then ignored, so the check said "matches" after reading only part of the record. An explicit `--resume` path that did not exist was silently replaced by another file. Two postings with the same title were imported as one role. |
| 3: claim boundary and qualifiers | 2026-09-25 | 18 findings, two of them serious: the heading of a pasted block could turn a topic title into a held claim, and "no typed attempts" counted as a pass. Also: qualifiers that were missed (`no experience`, `never`, `not yet`, `WIP`); a crash that exited 1 (findings) instead of 2 (could not check); the wheel not shipping THIRD_PARTY_NOTICES. The suite had 149 tests then, 36 of them new, each failing before its fix. |
| 4: graduation | 2026-09-29 | `jobs graduate --emit` trusted cached mastery and ignored problems in the log. It could print a skill as held from a damaged log, or after a later miss that the cache had not caught up with. Graduation now refuses damaged or drifted evidence. |
| 5: held-check phrasings | before release | The held check missed ordinary phrasings ("Learning Docker", "Haven't used GraphQL in production", "JavaScript (basic)"), and the docs said `check-claims` covered more than the lexicon packs. An empty board and `doctor` on an empty home read clean, and `due` and `quiz` exited 0 on a damaged log. All fixed, and the docs now state exactly what is checked. Adding phrases to the list did not fix the first finding for good: see "Decision: held is structural" below. |

The pattern across the reviews: nearly every real defect was a path that **reported clean when
it had not looked**. That is why the exit codes, and the NOT EVALUABLE state in particular,
carry so much of the design. The graduation review found the same kind of defect at the one
point that feeds what goes on a resume.

### The second review series

After the structural held rule (2026-10-15), a separate AI session ran the same reviews again
against the new source. All of this series' fixes landed the same day. The review numbers
below count within this series.

| Review | Fixed | What it found |
|---|---|---|
| 3: headings and diagnostics | 2026-10-15 | A stray `~~`, comment or fence marker could hide a heading, and with it the whole Held section. Blocks printed by `jobs graduate --emit` failed the very check they were meant to pass. `check-claims` and `doctor` did not name the line and the cause of a contradiction. `next` after a fresh `init` did not suggest adding roles. |
| 4: negation and hidden text | 2026-10-15 | A negated skill on a Held line (`- REST (not Docker)`) read as held. A skill hidden by a comment or fence was reported as "not in facts.md". Invisible characters (zero-width, soft hyphen, bidi) and look-alike letters from other alphabets hid a term from the claim check. Headings that were almost right were not named. Also several Markdown edge cases, and the facts sheet being parsed again for every question. |
| 5: disguised terms | 2026-10-15 | The checks for invisible characters (only Unicode category Cf) and look-alike letters (three Latin letters plus one Cyrillic or Greek) were blocklists, and each was short a case: a combining grapheme joiner, a Hangul filler, the braille blank, variation selectors, a combining overlay, `ТLS`, `Gо`, `Redıs` and `Pօstgresql` each got a skill onto a resume with exit 0. A trademark sign un-held a skill (`Docker™` became `DockerTM`). Smaller items: hyphenated words read as negations, a double space hid a qualifier, `jobs check` with no facts sheet read every term as a gap, `validate` ignored a damaged log, and a 5 MB paragraph took 24 s to parse. |

### How disguised terms are caught now

The fix replaced both blocklists with one rule (the full rule is in `docs/trust-rules.md`). It
took three tries:

1. **First version: too strict.** Strip everything Unicode defines as ignorable, then report
   any word that looks like a lexicon term and contains a non-ASCII character. That flagged
   ordinary text.
2. **Second version: special cases.** Normalise the text and look for exact matches
   (2026-10-15). Four later reviews each added a special case: typography at the ends of a
   word, separators, overlays, possessives.
3. **Current version: one rule**, with the special cases as consequences:

- **Each word is read several ways.** A whitespace-separated token is read whole (also
  without the punctuation at its ends), split into parts at every punctuation or symbol
  character, and without a possessive `'s`. For a term of several words, a run of that many
  consecutive tokens is also read whole.
- **Each reading is normalised:** NFKC, invisible characters removed, accents and combining
  marks removed, look-alike letters mapped to Latin, and in the whole-token reading,
  non-ASCII punctuation and superscripts dropped.
- **A reading counts as altered only if normalising changed it** compared with its own plain
  NFKC form. The earlier code compared a trimmed reading with the NFKC form of the untrimmed
  word, which made `ﬁrewalls,` and `Python’s` look altered.
- **Only an altered reading that exactly equals a lexicon term is a finding.** The parts and
  the possessive-free form only add readings, so `Dock·er` is still flagged through its
  whole-token reading.
- **Hyphen-like characters join words; they are never removed.** `Java‑Script` reads as
  `Java-Script`, two parts that spell no term. The words of a multi-word term may be joined by
  a space, a hyphen-like character or a slash, so `rate-limiting` matches `rate limiting` in
  the resume, the posting and `facts.md` alike.
- **Words are joined only within one line.** The first version of the join used `\s`, which
  also matches a newline, so the Held items `- Cloud` and `- Security` together held
  `cloud security`, and a soft-hyphenated word joined its two readings. Normalising now keeps
  line breaks, words join only across spaces and tabs, and the one break allowed is a word
  hyphenated at the end of a line (`machine-` / `learning`). Held blocks are matched as
  blocks, never as one run of text.

The lesson is the same as in the next decision, applied to characters: a list of the
characters that can hide a skill is always one short. So the rule is stated once, and the
special cases follow from it.

## Decision: held is structural, not guessed (2026-10-15)

Two earlier reviews each added words to the qualifier list (`no experience`, `never`, `not yet`, `WIP`).
A probe with new phrasings still read all four of these as held: "Docker (just starting)",
"GraphQL - tutorials only", "Terraform (no real-world use)", "OAuth: read about it". A word
list always misses someone's phrasing, and a miss reads as a claim you are allowed to make.
So whether a skill is held no longer depends on how it is worded:

- **A skill is held only when it is listed under a level-2 `## Held` heading.** Anything
  anywhere else is not held, however it is phrased.
- **The word list is kept, with a smaller job.** A qualifier word on a line under `## Held`
  is a contradiction, and `check-claims` and `doctor` report it as a violation. It blocks
  rather than warns, because a line that argues with itself cannot be trusted either way, and
  a warning that does not stop you sending the resume is just the old guess again. The line
  also counts as not held (fail closed).
- **A non-empty facts sheet with no `## Held` section is NOT EVALUABLE (exit 2).** It must not
  mean "nothing held" (every skill would look like a gap) or "everything held" (how unlisted
  wording used to be read).

The cost: you must file each skill under the right heading, and the tool trusts that filing.
It checks structure, not truth.

## Decision: learning is the core (2026-10-22)

The job search used to be the product, and study served it. That shaped the tool for a
narrower person than intended: a topic studied for its own sake never reached `next`, and
every topic was assumed to end on a resume. The maintainer's premise is the other way round:
build a career while growing your interests, and use AI as a question to learn from, not an
answer to copy. So study became the core, the job search became an add-on, and the tool was
renamed from careerloop to kenloop (ken is the range of what you know).

What changed in the code, and the rule that keeps it that way:

- **The core imports no add-on.** `kenloop.core` (topics, the log, scheduling, mastery,
  dialogue, questions) never imports `kenloop.career` or `kenloop.certs`.
  `tests/test_layers.py` reads every core module with `ast` and fails if one does, including
  an import tucked inside a function, and a known-bad fixture proves the check can see one.
  Only the shell (`cli`, `loop`) imports both, through plain function calls. With only one
  real add-on, a plugin registry was not justified at the time; one was added when more
  modules arrived, and is described in [docs/modules.md](docs/modules.md).
- **Two hand-off points between core and add-on.** An add-on gives a topic a *seed*: the
  concepts, plus a test for which of them you already hold (the job search passes
  `facts.holds`). The core gives back *evidence*: which concepts passed every check, computed
  from the log alone. The job search turns that evidence into a `facts.md` line. One thing
  stayed in the core: the exam date, because the core uses it to keep reviews before the exam
  (`exam_clamp`), and moving it out would make `rebuild --check` report drift.
- **Outlets, not kinds.** A topic has no outlet by default: you study it for its own sake.
  The `career` outlet lets it graduate to your resume; `cert` marks a topic studied toward an
  exam. Before, every topic was a career topic unless marked otherwise.
- **`next` puts learning first.** A role whose deadline is closing still comes first; then
  reviews in any topic, then open questions, then graduation, then the job search. `next`
  takes the first of a fixed list of rules that fires, and `next --all` shows every rule by
  name, so you can see why it chose what it did.
- **A dialogue is never credit.** The graded dialogue (ported from the maintainer's private
  tool) is scored by an assistant. In the private tool those scores counted as answers you
  gave without help, so an assistant's judgement could move a skill toward your resume. Here
  a dialogue row moves only the reasoning scores. It cannot change the streak, the retention
  days, breadth or the schedule. Every row names the grader and keeps a hash of the
  transcript.

The refactor first kept behaviour identical (the demo's output was compared byte for byte
after each structural step), then changed the product in separate, tested steps.

## Decision: your own sense of what's hard steers the order, never the credit (2026-11-01)

A syllabus planned up front can only guess where you will struggle; studying finds out. And a
tool that learns about you only through test answers never hears "I'm lost here". So a topic
grows as you study it, and you can say how an idea feels:

- `ken mark TOPIC CONCEPT problem|fuzzy|solid|clear` records how an idea feels. A `problem`
  mark moves that idea up in what `next` offers; `clear` removes a mark.
- `ken branch` records a detour: while studying one idea you found you needed another (a part
  of it, or something to learn first, `before:`), so you can go down to it and come back.

The rules:

- **A mark changes the order, never your score.** Some real gaps feel solid, so a mark is a
  feeling, not evidence. Nothing you mark moves a streak, a retention day or graduation. And
  if you marked an idea `solid` but your latest attempt since that day failed, the failure
  wins: the idea is treated as a problem again until a later attempt succeeds.
- **If the marks file is damaged, every mark is ignored.** The row that was lost might be the
  `clear` that removed a mark, so steering by what is left could send you the wrong way.
  `map`, `validate` and `doctor` name the damage.
- **Guesses about new pieces are checked.** Whoever adds a new piece (you or the tutor) can
  predict whether it will be a problem (`ken branch --predict problem|solid`). The prediction
  is scored against how you later mark that piece, so a map that grew from use can still be
  judged.

## Deliberate non-goals

- It does not write your resume or cover letter. After `init` writes the `facts.md` template,
  no command changes that file.
- It does not scrape sites that have no public posting API.
- It has no LLM inside. The question bank and the dialogue come from you, or from your
  assistant following [docs/tutor-rules.md](docs/tutor-rules.md) and
  [docs/dialogue-rules.md](docs/dialogue-rules.md).
- It does not make resume PDFs (`ken print --pdf` renders study printouts only).
