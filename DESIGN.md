# How careerloop was built

## Starting point

careerloop began as a pair of tools inside a private AI-experimentation
environment: a job tracker and a study planner that did not talk to each other.
The extraction joined them around one contract:

1. **The loop is the product.** Search for roles, find the skills they want that
   you lack, study those, apply, then search again or learn more. `next` reads
   both halves and names the one thing most worth doing.
2. **The facts sheet is the only source of truth, and only you write it.** A
   resume may state only what the sheet lists under `## Held`
   (docs/trust-rules.md; `check-claims` checks lexicon-pack terms,
   and acronyms with `--acronyms`, nothing else). Study can
   propose a line for the sheet (`learn graduate --emit`); a human pastes it.
3. **Absence is reported, never scored.** An unreachable board, a missing resume
   or a damaged log, a board that lists nothing, or a `doctor` on an empty home
   is NOT EVALUABLE (exit 2), not a clean result or a zero.
4. **The log is the record.** Every attempt is appended to `log.jsonl` first;
   mastery and schedules are derived from it and can be replayed to check for
   drift.
5. **Standard library only** (plus `tomli` on 3.9 and 3.10), so there is no
   dependency supply chain to audit. The scheduler re-implements FSRS-6 and is
   tested against py-fsrs: `benchmarks/fsrs_parity.py` (fixed seed, 6,000 random
   sequences of 2 to 40 reviews, ratings 1 to 3) measured stability within 0.45%
   relative at worst (0.0016% median; the worst cases follow long runs of Again,
   where 4-decimal rounding of a tiny stability shows) and difficulty within
   0.008%; an interval differed in 0.38% of reviews, by up to 2 days, 300 of the
   382 more than ten years into a sequence. Again always schedules tomorrow and an exam
   date shortens intervals, by design.

## Adversarial reviews

Adversarial reviews were run by separate AI sessions that had not written the code; each finding was reproduced against the source and pinned to a test before it was fixed. Every finding was fixed before the next review. The first review
ran on 2026-09-25.

| Review | Fixed | What it found |
|---|---|---|
| 1: paths and config shape | 2026-09-25 | A caller-supplied role slug could write outside the data directory (`jobs intake --slug ../../escaped`). A config section of the wrong shape (`ats = 1`) raised a traceback instead of reporting NOT EVALUABLE. |
| 2: integrity checks | 2026-09-25 | Integrity checks that could read clean. `rebuild --check` compared only concepts present in the derived file, so a dropped concept read as clean. An unreadable log row was reported, then ignored, so the check said "matches" after reading part of the record. An explicit `--resume` that did not exist was silently swapped for another file. Two postings with one title imported as one role. |
| 3: claim boundary and qualifiers | 2026-09-25 | 18 findings, two of them P1: the pasted block's heading could turn a topic title into a held claim, and "no typed attempts" counted as a pass. Also qualifier gaps (`no experience`, `never`, `not yet`, `WIP`), a crash exiting 1 ("findings") instead of 2, and the wheel not shipping THIRD_PARTY_NOTICES. 149 tests then, 36 of them new pins, each red before its fix. |
| 4: graduation | 2026-09-29 | `learn graduate --emit` trusted cached mastery and discarded log problems: it printed skills as held knowledge from a damaged log, or after a later miss the cache had not yet absorbed. Graduation now refuses damaged or drifted evidence. |
| 5: held-check phrasings | before release | The held-check missed ordinary phrasings ("Learning Docker", "Haven't used GraphQL in production", "JavaScript (basic)"), and `check-claims` was documented as covering more than the lexicon packs. An empty board and `doctor` on an empty home read clean, and `learn due` / `learn quiz` exited 0 on a damaged log. Fixed; the claim wording now states exactly what is checked. Widening the phrase list did not close the first finding: see the decision below. |

The pattern across reviews: nearly every real defect was a path that **reported
clean when it had not looked**, which is why the exit-code contract and the
NOT EVALUABLE state carry the weight of the design. The graduation review found the same
class at the one point that feeds the claim boundary.

### Later review series

After the structural held rule (2026-10-15) the same review, by a separate AI session, was run again
against the current source. A second review series followed; its fixes landed the same day and are
listed here by what each found.

| Review | Fixed | What it found |
|---|---|---|
| 3: headings and diagnostics | 2026-10-15 | A stray `~~`, comment or fence marker could erase a heading and with it the whole Held section. Blocks `learn graduate --emit` printed failed the gate they were meant to pass. `check-claims` and `doctor` did not name the line and the cause of a contradiction. `next` from a fresh `init` did not suggest taking roles in. |
| 4: negation and hidden text | 2026-10-15 | A negated skill on a Held line (`- REST (not Docker)`) read as held. A skill hidden by a comment or fence was reported as "not in facts.md". Invisible characters (zero-width, soft hyphen, bidi) and Latin look-alikes hid a term from the claim gate. Near-miss headings were not named; several Markdown edge cases; the facts sheet was re-parsed for every question. |
| 5: disguised terms | 2026-10-15 | The invisible-character strip (only category Cf) and the look-alike check (three Latin letters and a Cyrillic or Greek one) were blocklists, and a combining grapheme joiner, a Hangul filler, the braille blank, variation selectors, a combining overlay, `ТLS`, `Gо`, `Redıs` and `Pօstgresql` each got a resume past the gate with exit 0. A trademark sign unheld a skill (`Docker™` folded to `DockerTM`). Small items: hyphen compounds read as negations, a doubled space hid a qualifier, `jobs check` with no facts read every term as a gap, `learn validate` ignored a damaged log, a 5 MB paragraph took 24 s to parse. |

The disguised-terms fix replaced both blocklists with one rule (see `docs/trust-rules.md`). Its first
form failed closed: strip everything Unicode defines as ignorable, then report any lexicon-shaped
word containing a non-ASCII character. That flagged ordinary text, so it was
rewritten (2026-10-15) as exact matching after a rewrite, and four later reviews each added a
special case (typography at the ends, separators, overlays, possessives). The current rule is one
statement instead:

- A whitespace token is read **whole** (also without the punctuation at its ends), **split into
  parts** at every punctuation or symbol character, and **without a possessive** `'s`. For a term of
  several words, a run of that many consecutive tokens is read whole too (multiword terms).
- Each reading is rewritten (NFKC, invisible characters removed, accents and combining marks
  removed, look-alike letters mapped to Latin, and in the whole reading a non-ASCII punctuation or
  superscript form dropped).
- A reading is **altered** only if the rewrite differs from its own NFKC form. Comparing it with
  anything else (the earlier code compared a trimmed reading with the NFKC of the untrimmed word)
  made `ﬁrewalls,` and `Python’s` look altered.
- An altered reading that equals a lexicon term exactly is a finding; nothing else is. Parts and the
  possessive-free form only add readings, so `Dock·er` stays flagged through the whole-word reading.
- Hyphen-like characters are joiners, never removed: `Java‑Script` is `Java-Script`, two parts that
  spell no term. The matcher joins the words of a multiword term the same way (a space, a hyphen-like
  character or a slash), so `rate-limiting` is `rate limiting` in the resume, the posting and `facts.md`.
- Words are joined on one line only (line-bound joins). The first version of the join used `\s`, which also
  matches a newline, so Held items `- Cloud` / `- Security` held `cloud security` and a soft-hyphen
  text joined its two readings. Normalisation now keeps line breaks, the joining class is horizontal
  white space, and the one allowed break is end-of-line hyphenation (`machine-` / `learning`). Held
  blocks are matched as blocks, never as one run of text.

The lesson is the one of the decision below, applied to characters: a list of the characters that
hide a skill is always short one, so the rule is stated once and the special cases are consequences.

## Decision: held is structural, not guessed (2026-10-15)

Two earlier reviews each widened the qualifier word list, and a probe with new
phrasings ("Docker (just starting)", "GraphQL - tutorials only", "Terraform (no
real-world use)", "OAuth: read about it") still read all four as held. A word
list always misses someone's phrasing, and a miss reads as a claim you may make.
So heldness no longer depends on wording:

- A skill is held only when listed under a level-2 `## Held` heading. Anything
  elsewhere is not held, however it is phrased.
- The word list is kept, demoted: a qualifier word on a line under `## Held` is
  a contradiction, reported as a violation by `check-claims` and `doctor`. It
  blocks (rather than warns) because a line that argues with itself cannot be
  trusted either way, and a warning that does not stop a send is the guess in
  another form. The line also counts as not held (fail closed).
- A non-empty facts sheet with no `## Held` section is NOT EVALUABLE (exit 2).
  It must not mean "nothing held" (every skill would look like a gap) or
  "everything held" (the old behaviour for unlisted wording).

Cost: the owner must file each skill under the right heading, and the tool
trusts that filing. It checks structure, not truth.

## Deliberate non-goals

- It does not write your resume or cover letter, and after `init` has written the `facts.md` template no command modifies it.
- It does not scrape sites without a public posting API.
- It has no LLM inside. The question bank is yours, or your assistant's under
  [docs/tutor-rules.md](docs/tutor-rules.md).
- It does not make PDFs.
