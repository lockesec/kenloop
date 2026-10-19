# Changelog

## 0.1.0 (2026-10-19)

First public release.

Licensed under Apache-2.0.

- `[wants]` filters, one module per field: `workplace` (the board's field on Ashby and
  Lever, else the location or title) and a `pay_min` floor (the board's field, else a pay
  range in the posting text; hourly converted at 2,080 hours; another currency, or a bare
  "$" outside the US, is unknown). Each answers pass / fail / unknown and has its own
  `*_unknown` policy (keep, flag, drop). `jobs discover --intake` sets aside what fails,
  with the reason; `jobs wants` reports every role with each filter's unknown count.
  Greenhouse posting text is now stored as text (its content arrives entity-escaped).
  `benefits = [...]`: one row per benefit, pass when stated (quoting the line, or the
  board's equity field), fail only when ruled out, else unknown under `benefits_unknown`;
  a catalogue of spellings plus `[wants.benefit_phrases]`. A heading in capitals may now
  run to 12 words ("BENEFITS AVAILABLE TO ALL FULL-TIME ... EMPLOYEES (GLOBAL)" on a live
  posting had been read as part of the section above it).
- `[wants]` pay and benefits fixes: pay reads every range with its label (a bonus,
  stipend, equity, grant or relocation range is not the salary), monthly and weekly
  intervals (x 12, x 52, said), a currency code or symbol before or after the range or in
  a "(CAD)" label (CAD AUD NZD SGD HKD MXN INR JPY CHF added), several salary ranges judged
  on the highest with the count said; a bare "$" is USD only where the location says
  United States, else unknown. Benefits count only benefits-type lines, a negation beside
  the phrase rules it out, "equity" needs a compensation sense, open-PTO spellings ("take
  what you need", "not accrual based") are checked across the whole posting before a
  fixed allowance rules unlimited PTO out. Workplace text: negated remote, "remote
  sensing" and "Hybrid / Remote" are no longer read as remote.
- Duplicates: a role taken in earlier in the same `discover` run is now known to later
  postings (two aliased boards no longer take the same job in twice); a closed role no
  longer masks an active repost; `offer` and `on-hold` roles count as active (only
  `rejected`, `passed`, `closed` or vanished from the board do not).
- Company template: a line is never set aside as template when it is required, preferred
  or a responsibility in any posting (it had followed the first posting read, so a posting
  without headings could hide a requirement and zero the about/benefit text); the result no
  longer depends on scan order; `[sources] aliases` pool a company's postings; `jobs org`
  exits 2 (NOT EVALUABLE) under 3 postings and still writes the profile; `jobs brief`
  lists the company's standing benefits when every benefit line is template.
- Section reader: a cue-led line in capitals or bold that continues with a with/in/of/and
  clause ("EXPERIENCE WITH KAFKA AND HELM IN PRODUCTION") is a requirement line, not a
  heading (it had been consumed and dropped); new cues "Roles/Duties and Responsibilities",
  "Job Description", "What you'll be doing", "What success looks like", "Travel",
  "Education", "Compensation & Benefits", "Salary and Benefits", "Benefits at <Name>",
  "What we offer you" and "About <Name>" close the section above as plain lines.
- Acronym extraction no longer counts capitalised English words ("NOT"), "AI-generated"
  style adjectives, "DE&TH"-style pairs or a stray two-letter pair ("ES", "QL", "TS") as
  skills; SIEM, EDR, KQL, AWS and GCP still count.
- `jobs discover` no longer reports CHANGED for a whitespace-only edit (the text is hashed
  with runs collapsed, lines stripped and blank lines and CRLF ignored; older roles are
  compared by their stored `jd.txt`).
- Posting history: `jobs discover` marks a known posting whose text changed on the board
  (CHANGED, stored text kept, recorded once), does not take in a DUPLICATE (same company,
  title and location under another id or board; `[sources] aliases` joins org names), and
  takes in a REPOSTED job with `reposted_from` naming the closed or vanished role.
- `learn brief SLUG`: a bundle for writing a topic's questions (rules, each concept with
  its question count, the exact bank format). `learn validate` fails a question with no
  answer, or whose text or answer is still the brief's `<placeholder>`, and warns on one with
  no Type.
- A suggested fit from what facts.md holds of the required and preferred terms (0.7 /
  0.3) with an experience penalty; `jobs check` prints it, `jobs score SLUG` shows the
  working, `--fit suggested` accepts it (`fit_source` records who set the score).
- `jobs brief SLUG`: a deterministic Markdown bundle for writing the tailored resume and
  cover letter: rules for what may be claimed, the role typed with each term held or not,
  "You hold" with the facts.md line that proves each, "Do not claim", the company in its
  own words (from its learned template when there is one) and the requirement lines no
  skill was found in.
- A company's template, learned from its own postings (a line in most of them): kept out
  of "not looked at", still read for skills, never claiming a requirement line; `jobs org
  NAME` prints it and writes the company profile (about, benefits, legal text) for
  tailoring. Acronyms count only where the job is described; benefit jargon and
  capitalised country headings are set aside and listed. On six live postings from one company
  "not looked at" went from 29 of 40 lines to 4 of 7, and the gaps from 18 terms (HRA,
  AD&D, RRSP, UNITED, STATES ...) to 5 real ones.
- `jobs headings`: a census of the headings the section reader did not type, counted
  across every posting taken in, and `[headings]` in `config.toml` to map one to a type
  once (it beats the built-in reading). Four headings the census found on live postings are
  now built in: "What we do", "Other notices", "Referral instructions", "What you can look
  forward to".
- Typed sections: besides required and preferred, a posting's lines are typed as
  responsibilities, company, benefits, legal, logistics or unknown, and every line is
  kept under its type in `coverage.json` `parts` (nothing dropped). `jobs check` counts
  responsibilities apart (`responsibilities x/y`); company and responsibilities text is
  kept for tailoring.
- Fixes from live Greenhouse, Lever and Ashby postings: a heading must look like one, so a benefit or list line holding a cue word
  ("our preferred provider", "Kafka required", "Annual bonus") no longer opens a section;
  HTML list items and headings keep their shape; "Preferred Qualifications", "NICE-TO-HAVES",
  "What you'll bring to the role", "What we require" and "What we value" read correctly;
  Lever postings include their `lists`; the bare alias `mitre` is gone (D3FEND and ATLAS no
  longer ask for ATT&CK); an acronym inside a matched term ("AD" in "Azure AD") is not
  counted again; "Sentinel One" reads as SentinelOne; "Six Sigma", "unique IDs" and "a proxy
  for" no longer read as security terms; an unusable `[profile] years` says so; an old
  `coverage.json` reads as not measured in `upskill`.
- Lexicon packs take `[aliases]`: another spelling of a term (`k8s`, `ATT&CK`,
  `Sentinel`) counts as that term in a posting, on a resume and under `## Held`, so
  `MITRE`, `ATT&CK` and `MITRE ATT&CK` are one term asked once. The shipped `security`
  pack grows from 61 to 202 terms with 56 aliases, and now names the products and
  certifications SOC postings ask for (Splunk, Microsoft Sentinel, CrowdStrike, KQL,
  Sigma, Security+, CySA+). On four live Greenhouse SOC postings the triple-counted
  ATT&CK became one term and the benefit and time-zone words stopped reading as gaps.
- `jobs check` reads where a posting asks for each term: a required/preferred split
  from the posting's headings (and "a plus" / "preferred" lines), years of experience
  with their section (compared with `[profile] years` when set), and every
  requirement line in which no lexicon term was found, with the count beside the
  total. A posting without headings says the split is NOT EVALUABLE. `jobs upskill`
  totals the unread lines across roles. Stored in `coverage.json` as `sections`,
  `term_sections`, `years` and `unread`.

- One loop in one tool: job discovery and scoring, ATS-style coverage against
  your facts sheet and resume, weighted skill demand, topics seeded from the gap,
  spaced-repetition study (FSRS-6), and `next`, which names the one thing most
  worth doing now.
- `jobs check-claims` gates a resume: every stated term must be held, and a
  term that is not listed under `## Held`, or is unmentioned, is a violation.
- A skill is held only when listed under `## Held` in `facts.md`. Wording
  outside that section never counts; a qualifier word ("planned", "learning")
  on a line under `## Held` is reported as a contradiction and blocks. A
  non-empty facts sheet with no `## Held` section is NOT EVALUABLE (exit 2).
  `init` writes both sections; `learn graduate --emit` prints lines for pasting
  under `## Held`.
  Strike-through, comments and fences are removed one line at a time or as
  Markdown defines them, so a stray marker cannot hide a heading; an unchecked
  task box is not held; `check-claims` and `doctor` name the line and the cause
  of each contradiction; `--emit` refuses to print a line that would fail the
  same gate.
- `learn graduate --emit` prints concepts that passed four gates, for you to paste
  into `facts.md`; no command modifies the facts sheet after `init` creates the template.
- Exit contract: 0 clean, 1 findings, 2 not evaluable (or internal error),
  3 drift, 64 usage. Absence is reported, never scored.
- A negated line under `## Held` (not, no, never, without, except, instead of) is a
  contradiction. A skill hidden by a comment or fence is reported as hidden, with the
  line. `benchmarks/fsrs_parity.py` reproduces the FSRS parity figures.
- Disguised skills: every Default_Ignorable_Code_Point character (Unicode 15.1), the braille
  blank U+2800 and trademark marks are removed before matching, in the facts sheet, the
  resume and the posting. A whitespace-separated word that is then rewritten (symbols,
  control characters, accents removed, a table of look-alike letters mapped to Latin,
  compatibility forms expanded) and equals a lexicon term exactly is a
  `suspicious-characters` finding: exit 1 for the resume in `check-claims` and `jobs check`,
  a warning for the posting. Never a fuzzy or subsequence match, so ordinary non-English
  words are clean; a one-letter term such as `r` matches whole tokens only (not `R&D`).
  `doctor` reports a disguised resume word. `docs/trust-rules.md` says exactly what is and
  is not caught. A Held line spelled with such a character is a contradiction naming the
  code points. A trademark sign after a skill no longer unholds it. "lacking hands-on
  experience" now reads as a qualifier.
- "no-code", "not-for-profit", "No.1" and "No Starch" are not negations; extra spaces no
  longer hide a qualifier phrase; the "no experience" row lists every word the pattern
  matches (knowledge, exposure, familiarity, proficiency too).
- `jobs check` with a missing or empty `facts.md` exits 2 and `learn validate` exits 2
  on a damaged log row, instead of exit 0. Facts sheets whose paragraphs have hundreds
  of thousands of lines are parsed in linear time.
- Absence: `doctor` exits 2 on an empty or missing `facts.md`; `learn calibration`,
  `misconceptions`, `sync`, `plan` and `exam-date` report a damaged log and exit 2 (`exam-date --set`
  no longer stores a replay that skipped rows); on an empty home `learn validate`, `learn due`,
  `learn gaps` and `jobs upskill` exit 2 with the denominator and the cause (`jobs upskill` writes no
  file then); a resume that is not UTF-8 text (UTF-16, a NUL byte, bytes that do not decode) is
  NOT EVALUABLE instead of being read with replacement characters. The README and
  `docs/commands.md` list exactly which commands exit 2 on absence. Disguises: typography at a
  word's ends (curly quotes, dashes, ellipsis, bullets, arrows, check marks, currency, section and
  dagger signs, full-width punctuation) no longer flags a word; a word joined to a neighbour by
  `/ , | ;` or a bullet is examined part by part; overlay combining marks (strokes, solidus, rings)
  are disguises even in a three-letter term; the look-alike table gains the lunate sigma, some
  Cherokee capitals, the palochka, lower-case Cyrillic к г т м н в and o with stroke; the accent rule
  (four or more letters, retype the word) is stated in the README and `docs/commands.md`. `doctor`
  reports everything `check-claims` would exit 1 on, per resume, and the docs say which resumes it
  scans. `learn record --hint-depth` accepts 0 to 4 only (usage error otherwise). Held lines: a
  qualified nested item qualifies the item above it, a trailing `beginner`/`basic`/`novice`
  qualifies, `1. [ ] Docker` is an unchecked box, `will learn`, `to be learned` and `just started`
  are qualifiers, and the message quotes the qualifier alone. `init` says when it recreated
  `facts.md`; code spans and backtick runs on one line parse in linear time; a fixture entry that is
  not an object, has no title or has a field of the wrong type is named instead of becoming an empty
  role.
- The disguise check is now ONE rule instead of four successive special cases: a
  word is read whole, split into parts at every punctuation or symbol, and without a possessive;
  a reading is altered only if its rewrite differs from its own NFKC form; an altered reading that
  equals a lexicon term exactly is reported. So `ﬁrewalls,`, `ＡＷＳ.`, `Python’s` and `(ﬁrewalls)` are
  clean, while `Dock<Cyrillic e>r-based`, `Dock<Cyrillic e>r's`, `Skills:Dock<Cyrillic e>r`, `Dock<Cyrillic e>r+Python`, an
  em or en dash, an ellipsis and full-width or ideographic commas next to a disguised term are
  flagged. Superscript digits, ordinals and fractions glued to a term (`Docker¹`, `Dockerª`) are
  flagged like `Docker⁺`; enclosing marks (U+20DD, U+0488) are overlays; LaTeX `\\Docker`,
  `\textbf{Dock}er` and `Dock{}er` read as the word. A false-positive sweep of nine system word
  lists with seven wrappers each flags only accent-rule words (`azuré`, `régression`, `säst`).
  Docs: the exit-2 table is reworded as common cases and now lists the rest (tailor without
  coverage, calibration, quiz, exam-date, `plan --from-gap`, `discover --all`/`reconcile` without
  targets, a missing home, a damaged `upskill.json` or `meta.json`), each row run by a test;
  `next` and `learn gaps` print the denominator on an empty home; DESIGN.md states the current rule.
  Smaller fixes: a bare level word nested under a skill (`- Docker` / `  - beginner`) qualifies it;
  `doctor` names a role whose resume is gone (exit 2); `jobs check --resume` and `check-claims`
  resolve a relative path the same way (current directory, then HOME); a non-UTF-8 log row is a
  damaged row and a non-UTF-8 posting, syllabus or question bank is named; `discover
  --exclude-senior` prints how many it left out and a posting with no title is named and skipped;
  `learn calibration NOPE` is a usage error; dates must be `YYYY-MM-DD`; `--n`, `--limit`, `--top`
  must be 1 or more; `jobs board --status` is validated; `exam-date --clear` no longer prints
  "cleared saved"; a leading `---` is not folded into a heading; a quoted word is cut at 80 characters.
- Multiword lexicon terms are found however their words are joined (space, ASCII
  hyphen, U+2010 to U+2015, minus, slash with or without spaces, soft hyphen read as a space), in the
  posting, the resume and `facts.md`; the disguise rule also reads runs of consecutive words, so
  `Rate Limit<Cyrillic i>ng` is reported; a hyphen-like character between fragments of a one-word
  term (`Java‑Script`, `Web‑Sockets`) is a joiner and no longer a disguise. A private-use character
  or C1 control at a word's end, and a prime or acute used as an apostrophe (`Docker′s`), are not
  disguises; a qualifier written with look-alike letters or combining marks still disqualifies a
  Held line. `jobs tailor` refuses stale coverage (exit 2); `jobs check --resume RELATIVE` stores an
  absolute path so coverage stays fresh from any directory; a lone surrogate in a posting is replaced
  by U+FFFD and named instead of aborting discovery; a new role is built in a temporary directory
  and renamed, so a failed intake leaves no empty role directory, and `rank`, `board`, `doctor`,
  `reconcile` and `discover` name a role directory without `meta.json` or with a damaged one (exit 2,
  the rest still done); `jobs check` on a resume that states no term is NOT EVALUABLE and writes no
  `coverage.json`; `learn plan` validates the slug (1 to 64 characters). Named causes instead of
  "internal error" for wrong field types in `meta.json`, `topic.json`, `concepts.json` and
  `upskill.json`, a non-UTF-8 `--jd` or quiz input, a per-role resume pointer to a missing file,
  `check-claims` on a directory or device; usage errors (64) for `--min-fit nan`, an empty
  `--company`, `reconcile --board` without `--company`, and an unknown `--board`.
- A multiword term's words are joined only by horizontal white space and the
  documented joiners, never across a line break, a list item, a paragraph or a Held block (Held items
  `- Cloud` / `- Security` no longer hold `cloud security`; `Built rate` / blank line / `limiting` no
  longer states `rate limiting`); end-of-line hyphenation (`machine-` then `learning`) is the one
  allowed break. Held blocks are matched as blocks, and the two soft-hyphen readings of a text can no
  longer join (`Limiting fac<U+00AD>tors, Python, the rate` is not `rate limiting`). The disguise
  windows stay on one line and read a soft hyphen as a space. `jobs check --resume DIR` says "not a
  regular file"; a `meta.json` that is `null` or any non-object is damaged (exit 2, file named), and
  every role field is validated on read and named when wrong (`rank` names a role it cannot read);
  the `learning` qualifier exceptions are joiner-aware (`e‑learning`, `E–learning`, `deep / learning`);
  `jobs intake --jd -` with empty input is refused; a lexicon term of more than 8 words is skipped with
  a warning (disguise windows cost words times term length); docs: `check-claims` takes a positional RESUME.
- The `learning` exceptions (machine, deep, reinforcement, e-learning) match whole
  words only, so `- Azure — learning` and `- Vue-learning` are qualifiers again (a regression from
  the earlier whole-line join). Structure is a line break for joining: HTML block tags in a posting and LaTeX items,
  sections, `\par` and table cells in a resume; `\_` stays an underscore. End-of-line hyphenation is
  a real hyphen only (ASCII, U+2010, U+2011), and the disguise check joins the same wraps, so a
  disguised term wrapped at a hyphen is reported. A posting that is markup with no visible text is
  refused; slugs keep accented letters (`Café` gives `cafe`); a `fit_score` outside 1-5 (or NaN) is
  named; a bad deadline in a discovered posting names that field; lexicon-load warnings start with
  `warn:`. The disguise check joins the wraps the matcher joins; a single line break is a
  space in LaTeX and in HTML markup (a plain-text posting keeps its lines); a `<` that starts no tag
  is text; a posting of only markup or invisible characters is refused on `intake` and
  `discover --intake` (which names and skips it); slugs transliterate ß, æ, œ, ø, ł, đ, þ;
  `transfer`, `supervised`, `unsupervised`, `federated`, `meta` and `statistical` learning are names.
- Web addresses are not read as skills (a resume's GitHub or LinkedIn link no longer
  fails the gate as `https`); the hyphen-wrap boundary accepts a combining mark or symbol at the
  seam; long white-space runs and repeated `\\[` read in linear time; a LaTeX resume prints a
  warning that it is read best-effort; the docs say the gate is for Markdown and plain text and
  list the known limits.
- The hyphen-wrap rule is one function applied to the raw text by both the matcher
  and the disguise check, so the two read a wrap the same way (every line-break kind, invisible
  characters at the seam, and the small and full-width hyphen-minus). LaTeX files with CRLF or CR
  line endings read a single break as a space; `<pre>` keeps its lines; more HTML block tags and
  LaTeX item macros separate lines, and a structural command's arguments stand alone; HTML
  stripping is one linear pass (an unclosed comment or script no longer costs quadratic time) and
  keeps `List<String>` in plain text; a posting with nothing visible (escaped markup, format or
  control characters, a lone combining mark) is refused; more machine-learning field names.
