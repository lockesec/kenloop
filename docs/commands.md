# Commands, how `next` decides, and your data

kenloop's core is study: topics, quizzes, spaced review, graded dialogues and question
ladders. Two sidecars read it: the job search (`ken jobs ...`) and exams (`ken cert ...`).
`next` reads all three and names the one thing most worth doing now, with the reason.

## Commands

```
ken init                          create the data directory
ken next [career|interest] [--topic SLUG] [--all] [--json] [--candidates]   the one thing to do now, and why; a lane limits it to career
                                  (may feed facts.md; certs are always career) or interest topics
ken focus [TOPIC|career|interest|auto] [--why W]   pin what `next` points at until you pivot;
                                  alone, shows it; auto hands it back to the rules (focus.jsonl keeps every pivot)
ken doctor [--fix]                study and the sidecars (--fix adds missing .gitattributes ledger lines): 0 clean, 1 findings, 2 not evaluable
                                         (also an empty home or an empty facts.md), 3 drift
ken mark TOPIC CONCEPT problem|fuzzy|solid|clear [--why W]   how an idea feels: moves what comes next, never credit
ken trail [TOPIC CONCEPT --why W | --back]   the path from what started this; alone, shows it
ken board                         every topic: its outlets, mastery and reviews due; once a topic has graded
                                         dialogues, their reasoning too (`reasoning 1.3/2 on 2`), which badges never show

# study
ken plan SLUG [--goal G] [--career] [--from-gap BUCKET [--top N]] [--force]
                                         a topic; no outlet = studied for its own sake;
                                         --career lets it graduate into facts.md (--from-gap implies it)
ken sync SLUG                     read new concepts from syllabus.md
ken place SLUG [--rung N --result pass|partial|miss --probe Q --answer A]
                                         find the rung of the topic's scale (## Path) you start on;
                                         no credit, its own record (placement.jsonl)
ken bank SLUG CONCEPT --q Q --a A --ref R [--why W --qtype T --d 'wrong :: misconception']
ken quiz SLUG [--interactive] [--weak] [--n N] [--concept C]
                                         a concept answered today waits until tomorrow (named; a second
                                         answer today earns no credit); --concept asks it anyway
ken record SLUG CONCEPT ok|partial|miss [--confidence L --qtype T --etype E --hint-depth N --lookup --guess --mode M --depth D]
                                         --depth exam|mechanism|first-principles: how deep the question went
                                         (default: the line, rung or topic depth); --mode predict: the guess
                                         before an explanation, recorded and never credited (--before "..."
                                         keeps what was guessed; `beliefs` shows it beside the next answer)
ken due [SLUG | --lane career|interest]   reviews due today, including the first cold recall of a concept taught before today
ken settings SLUG [--intent understand|pass] [--depth exam|mechanism|first-principles] [--clear K] [--keep-studying on|off] [--migrate [--check]]
                                  how you study a topic; a `## Path` rung or one syllabus line overrides it
                                  (:: intent: / :: depth:); a line's :: same:KEY links the same idea in another topic: one idea,
                                  one held set (an answer after it was seen under either topic that day is a repeat)
ken place SLUG --start N | --clear-start   start on rung N by choice: no placement probes
ken dive SLUG [CONCEPT]           go over it together, answers open (a check after is --mode learn: no credit)
ken foundations SLUG [CONCEPT [--scaffold]]   a from-the-ground-up note per concept
ken mastery SLUG | misconceptions SLUG | calibration SLUG
ken rebuild SLUG [--check] [--skip-damaged] | validate [SLUG] | brief SLUG
ken recall SLUG CONCEPT [--listed "a; b"] name a concept's pieces from memory, scored against the map
                                          (no credit); missed pieces show on the map and come first in next
ken map [SLUG]                            concepts as wholes and their pieces, by rung: climbed, ready, or
                                          waiting (and on what); then the frontier, what is ready to study
ken rename SLUG OLD NEW                   after renaming a concept's syllabus line: its history, links,
                                          bank section and note follow the new id (the log is not rewritten)
ken validate [SLUG]                       the syllabus, bank, links and log: exit 1 on failures, 2 if a log
                                          row is damaged

# reasoning and questions
ken close SLUG [--three T]... [--fuzzy F] [--perceived 1-5|WORDS] [--idea C]... [--minutes N --chunks N --acts N --why N --what N --woven N --digressions N]
                                  the one-minute close of a session (sessions.jsonl); `ken sessions [SLUG]` reads them back
ken profile [--scaffold|--folded]  the curated learner profile (profile.md): who, goals, background by field, how to
                                  teach you; `session` prints it, then only the learner notes written since. --folded
                                  marks every note so far as taken in (Updated today, Folded: the count)
ken print SLUG [--pdf] | --scaffold sheet|session
                                  the topic's reference sheet and session printouts (print/*.md, written by the
                                  tutor) rendered to self-contained .html, and .pdf with Chrome or Chromium on PATH
ken gap SLUG CONCEPT|- TEXT [--kind step|notation|example|order|unverified|misread|process|other] [--by tutor|learner]
                                  a miss the teaching caused, counted against the tutor (tutor_gaps.jsonl); `-` when it
                                  is about the session, --by learner when they noticed it (their words);
                                  `ken gaps [SLUG]` lists them by concept beside how many concepts were taught
ken gaps SLUG --review            the tutor's review at the close: what to re-read the session for, the gaps logged
                                  today, and the question to ask the learner; `session` shows the last three
ken session SLUG [--brief]        start a study session: settings, scale, the ideas in play with their pyramid height
                                  and the foundations under them, one mode line for the tutor, notes, open questions,
                                  scouts, next here; names rungs with no concepts; --brief leaves the profile text out
ken taught SLUG CONCEPT [--note]  record that a concept was taught (teach mode): no credit; its first cold recall is due tomorrow
ken note SLUG "..." | --learner "..."   a dated tutor note on how you learn (never evidence)
ken talk SLUG [CONCEPT] [--protocol]   one concept: what is known, how your reasoning went; --protocol for a graded dialogue
ken record SLUG CONCEPT RESULT --mode dialogue --rubric chain=2,predict=1,limits=2 --grader ID
           [--before B --confidence L --after A --after-confidence L --held H --broke K --next N
            --open Q ... --claude-wrong E]      (--open "CONCEPT :: Q" names the concept it is about)
ken beliefs SLUG [CONCEPT]        what you believed before and after, where it held and broke, what is open;
                                         and each prediction beside the next answer on it
ken ask ["QUESTION"]              start a ladder; alone, every question and how far you have climbed
ken rung QID TOPIC "DOMAIN :: CONCEPT :: DESCRIPTION" | --existing CONCEPT
ken branch SLUG CONCEPT "DOMAIN :: NAME :: DESCRIPTION" --by learner|tutor|tool [--before] [--topic NEW]
           [--title T] [--predict problem|solid] [--gap G] [--source KEY]        a gap found while studying CONCEPT: a piece of it (part-of),
                                         learned before it, or a topic of its own
ken branch SLUG CONCEPT --note G | --decline G --by WHO [--source KEY]   kept as a note, or turned down
ken scout SLUG CONCEPT "LINE" --why "..." [--url U] [--before|--topic]   a predicted branch (the scouts
                                  module): dormant until CONCEPT is studied, then offered; decide it with --source scout:N
ken branch [SLUG]                 the tool's offers from the record, and how well offers are picked

# the job search (jobs)
ken jobs discover --board B --company ORG | --all [--keyword K] [--intake] [--exclude-senior] [--reconcile]
ken jobs intake --company C --role R [--jd FILE|-] [--force]
ken jobs score SLUG [--fit 1-5 | --fit suggested]   no --fit: the suggested fit and its working
ken jobs check SLUG [--resume P]          coverage.json (P: current directory first, then HOME); exit 1 if the resume has a
                                         disguised skill (a posting only warns), 2 if it cannot judge
ken jobs tailor SLUG                      review.md: what to state, what not to claim
ken jobs status SLUG STATE [--stage S --reason R --probed a,b]   also files the role's PDF folder (below)
ken jobs build SLUG [--resume P --cover P --outdir D]   LaTeX to PDF, checked: 1 page, nothing clipped; exit 1 on findings
ken jobs rank | board | show SLUG | reconcile
ken jobs upskill                          upskill.json: weighted demand by bucket
ken jobs wants                            every role against [wants]: pass / fail / unknown per filter
ken jobs digest [--dry-run]               every board once, postings bucketed by [digest] and [wants], newest first
ken jobs headings [--all]                 headings the section reader did not type, counted across postings
ken jobs org NAME                         a company's template and profile, from its postings -> orgs/NAME.json
ken jobs brief SLUG                       a Markdown bundle for writing the tailored resume and cover letter
ken jobs check-claims RESUME [--acronyms]   lexicon-pack terms only; --acronyms adds
                                         capitalised acronyms and names; held = listed under ## Held
                                         exit 0 clean, 1 violations, 2 not evaluable
ken jobs graduate SLUG [--emit]           a career topic's proved skills; --emit prints lines to paste under ## Held
ken jobs promote SLUG CONCEPT --why "..." [--revoke]   put one interest concept forward as a job skill: recorded
                                         (promotions.jsonl), needs a keyword-pack term, still passes the four gates
ken jobs gaps                             demand buckets, and which are planned

# exams (cert)
ken cert exam SLUG [--n N]                a practice exam: questions drawn across domains by size
ken cert exam-date SLUG [--set YYYY-MM-DD | --clear]   reviews land before it; adds or removes the cert outlet
ken cert passed SLUG [--on YYYY-MM-DD] [--emit|--clear] record a passed exam (topic complete, off next/due); prints its ## Held line
```


`brief SLUG` prints a Markdown bundle for whoever writes the topic's questions (you, or
your assistant): the rules (no hint in the question, one checkable answer, a Ref the learner
can open, your own questions rather than an exam's, distractors that name their
misconception, `Provenance: unverified` until checked), every concept with how many
questions it has now (thinnest first), and the exact bank format. A bank written to it
parses, but `validate` fails a question whose text or answer is still the brief's
angle-bracket placeholder (`<the one checkable answer>`); edit them and it passes. Validate
also fails a question with no answer and warns on one with no Type.

`quiz --interactive` is a complete study session with no assistant:
- it asks the question, as multiple choice when the bank has distractors;
- `?` climbs a four-rung hint ladder (the rung you reach is recorded);
- it asks your confidence *before* revealing the answer;
- it grades a multiple-choice pick itself, and asks you to grade free recall;
- a wrong pick records the misconception that distractor encodes.

Every answer goes through the same code path as `record`. If you prefer
to study with an AI assistant, [docs/tutor-rules.md](tutor-rules.md) is
a contract to give it, and it records the same way.

Exit codes: `0` ok · `1` findings · `2` not evaluable (or an internal error) · `3` drift · `64` usage.

### Which resumes `doctor` scans

When it runs, doctor scans the resume that each role with a posting resolves to (the role's own
`resume` field in `meta.json`, else `[profile] resume`, else `resumes/resume.md`, `.txt` or `.tex`),
once per file. It judges exactly what `jobs check-claims RESUME` judges: lexicon-pack terms, not
`--acronyms`. A resume that no role resolves to is not scanned; run `check-claims` on it yourself. A
resume that is not UTF-8 text, or states no lexicon term, makes `doctor` exit 2 for that file.

### Disguised words

A skill written with look-alike letters, overlays or hidden characters is reported as
`suspicious-characters`, and so is a word that equals a term of four or more letters once its accent
is removed: retype it without the accent. The exact rule and its limits:
[trust-rules](trust-rules.md#disguised-words).

### The syllabus line

`- domain :: name :: what it covers [:: key:value ...]`. Keys: `intent:`, `depth:`, `rung:DOMAIN`,
`same:KEY`, `scope:exam|depth`, `status:settled|frontier|open`, `cluster:ID`, `part-of:CONCEPT` and
`before:CONCEPT`; `before:TOPIC/CONCEPT` names a concept in another topic (a math piece learned before
a model lesson: the lesson waits on it and `session` shows it under "rests on"). Scale, rung, placement, map and branch are explained in
[the on-ramp](#the-on-ramp-a-scale-a-placement-and-the-pieces-of-a-concept).

## The pyramid: height

Every idea has a height on your pyramid, read from the record at the depth it is studied at
(the line's, rung's or topic's `depth`). It decides how the conversation goes, never what is
credited, and you cannot set it: only unaided recall raises it, and a recall that misses steps it
down one.

| height | when | the session |
|---|---|---|
| 0 new | nothing recorded | your guess first, then long explanations you interrupt; every chunk ends with one act by you |
| 1 heard | taught, guessed or answered with help; no unaided recall holding | cold recall first, then the gap; hints before answers |
| 2 held | an unaided recall is holding | you explain first; the tutor fills the gaps |
| 3 carried | two or more unaided recalls in a row, a week or more apart | you teach it; the tutor plays a novice and grills |

For a `pass` line the top is exam questions cold, not teaching. Depth: an unaided correct answer
counts for its depth and every shallower one; a miss counts against its depth and every deeper
one. The same idea in two topics (a shared `:: same:` key) has one height.

## How `next` decides

**Your focus comes first.** `ken focus black-holes` makes a bare `ken next` answer inside that
topic until you pivot (`ken focus blockchain`), point it at a lane (`ken focus interest`), or
hand it back to the rules (`ken focus auto`, the default). `next career` or `next --topic X`
asks about somewhere else for one call without moving the focus. A focus on a topic that has
since been removed is reported and read as auto.

**Inside the `study` rule, your marks set the order.** `ken mark` puts what you marked a problem first,
then fuzzy, then what is unmarked, and what you marked solid last, across topics unless a focus or
`--topic` narrows it. A latest attempt that missed or was partial, on or after the day you marked an idea solid, outweighs that
mark until a later success. `--mode predict` and `--mode learn` rows do not count as attempts; a graded
dialogue and a `--guess` answer do. `branch --predict problem|solid` records your guess about a new piece; `ken branch`
reads it against later marks (right on problem or fuzzy for `problem`, on solid for `solid`, and a solid mark a miss
outweighs reads as a problem).
Marks never move credit. A damaged marks file is named and ignored until it is fixed.

The rules are fixed, and the first one that fires wins (`loop.RULES`; a module may add one after a
named rule by declaring `rules()`, see [modules](modules.md)). `next --candidates` also prints up to two
other rules that fired. With `[next] intent_rank = true` (off by default), `study` puts an
`understand` idea before a `pass` one of the same kind. `next --all` prints every rule's
evaluation so you can audit the choice, and `next --json` gives the whole object (`rule` is
the rule's name). A closing role deadline outranks reviews and study. Two things
the table does not show: `deadline` and `role` suggest `jobs check SLUG` instead when the
role's coverage is missing or stale (tailor would refuse it), and `seed` prints *not
evaluable* when `upskill.json` does not exist yet; run `jobs upskill`.

| rule | when | suggests |
|---|---|---|
| `empty` | no topics and no roles | `plan` a topic; with `[sources]` targets, take roles in (exit 2) |
| `integrity` | a topic's state disagrees with its log, or fails validation | `rebuild` / `validate` |
| `deadline` | a role at or above your fit bar closes within `deadline_days` | `jobs tailor`, or `jobs status … applied` |
| `reviews` | reviews are due in any topic: an exam within 14 days first, then job demand, then the most due | `due` |
| `continue` | off unless `[next] continue_last = true`: no focus or filter is set and you have studied before | `session` the topic you studied last |
| `onramp` | a fresh topic has a scale (`## Path`) and no placement; else the rung you are climbing has a concept with no foundations note, or not yet gone over | `place`, then `foundations --scaffold`, then `dive` |
| `question` | a dialogue left a question open that no later dialogue on that concept followed up; else a question with no rungs | `talk`, or `ask` |
| `graduation` | a concept in a career topic passed every graduation gate and is not yet under `## Held` | `jobs graduate --emit` |
| `role` | a live role at or above the bar is waiting | `jobs tailor` the best |
| `fresh` | a topic has banked questions for concepts never studied | `quiz --weak --interactive` |
| `study` | the study graph (`ken map`) has a concept ready and not yet climbed: a rung of a question you asked first, then a piece of a concept, then by rung; branch offers waiting are counted | `quiz --concept C --interactive`, or `talk` when it has no banked question |
| `seed` | the top unplanned demand bucket reaches `min_bucket_demand` | `plan --from-gap` |
| `score` | roles are waiting to be scored | `jobs score` the oldest |
| `fallback` | nothing is ripe | `ask "…"`; with `[sources]` targets, `jobs discover --all --intake --keyword WORD` |

## The job search

Everything below, up to the exit codes, is about the `jobs` sidecar: what it reads from a
posting, how it scores and matches, and what you can tell it you want. The claim check covers
recognized terms: it cannot verify whether you actually hold a skill, or judge every claim on a
resume. It reads Markdown and plain text (LaTeX best-effort) and writes no resumes or cover letters.

### What `jobs check` reads from a posting

Beside the overall coverage, `jobs check` reports where each term was asked:

- **Required vs preferred.** Headings split the posting. A heading is a line that looks like
  one (a Markdown `#` heading, an HTML `<h1>`-`<h6>`, a line wholly in bold, a line ending in a
  colon, a line in capitals) and starts with a cue, or a line that is nothing but a cue. So
  "Experience" alone is a heading, while "Experience with Splunk", "Annual bonus" or "health
  insurance through our preferred provider" are not; nor is a cue followed by a
  with/in/of/and clause of more than three words, even in capitals or bold ("EXPERIENCE WITH
  KAFKA AND HELM IN PRODUCTION" is a requirement line, kept and counted); an HTML list item is always a line of
  its section, never a heading. Preferred cues are read first ("Preferred Qualifications",
  "Nice-to-haves", "Bonus points", "What we value"), then required ("Requirements", "Minimum
  qualifications", "What you'll bring to the role", "What we require", "About you"), then
  the rest, each its own type: **responsibilities** ("Responsibilities", "What you'll do",
  "About the role", "Roles and Responsibilities", "Job Description", "What you'll be
  doing", "What success looks like"), **company** ("About us", "About Acme Corp", "Our
  mission", "The Acme experience"), **benefits** ("Benefits", "Benefits at Acme", "What we
  offer you", "Compensation & Benefits", "Salary and Benefits"), **legal** ("Equal
  opportunity", "Accommodations") and **logistics** ("How to apply", "Location",
  "Travel"); "Education" is a required cue. A `#` heading with no
  known cue also closes the section above it, and its lines are kept as `other` (unknown);
  a colon line with no cue ("Strong knowledge of:") does not. Safe first: only a clear
  heading types a line, and no line is dropped. Every line is kept under its type in
  `coverage.json` `parts`, so each use reads its own part: coverage reads required,
  preferred and responsibilities; tailoring reads company and responsibilities. Inside a required
  section a line that says "a plus", "preferred" or "ideally" reads preferred. A term asked
  in several places takes the strongest. The line is `required x/y · preferred x/y ·
  responsibilities x/y · elsewhere in the posting x/y`: a skill named under
  responsibilities is what the job does, counted apart from both. A posting with no such heading has no split, and says so
  (NOT EVALUABLE), never "0 required". Lever postings are read with their `lists` (where
  Lever keeps the requirements), each list as a heading.
- **Your own headings.** `jobs headings` lists every heading-shaped line the reader did not
  type, with how many of your postings use it (figures, job codes and board tags are left
  out); `--all` lists the typed ones with their type too. Map one once in `config.toml` and
  every later `check`, `wants` and census reads it that way; a mapping beats the built-in
  reading:

  ```toml
  [headings]
  "where you will grow" = "preferred"
  "our stack" = "required"     # required | preferred | responsibilities | company |
                               # benefits | legal | logistics | other
  ```
- **A company's template.** A line that appears in most (60%, and at least 3) of one
  company's postings is its template: the about-us text, the benefits list, the legal
  notices. It is labelled, never deleted: `jobs check` keeps it out of the "not looked at"
  list and still reads it for skills, and `parts.template` holds it. A template never
  claims a line that sits in a required, preferred or responsibilities section in ANY of
  the company's postings (a line one posting leaves unheaded and three others list under
  Requirements is a requirement): a company that posts many similar roles repeats its
  requirements too. The about, benefits and legal text comes from the kind a line takes in
  the postings that have headings, whatever order the postings are read in. Postings under
  `[sources] aliases` names are pooled with the company. Fewer than 3 postings from a
  company give nothing to compare (NOT EVALUABLE: `jobs org NAME` still writes the profile
  and exits 2). `jobs org NAME` prints the template with its
  counts and writes `orgs/NAME.json` with the about, benefits and legal text, kept for
  tailoring a resume and cover letter to that company. The template is learned when
  `check` runs, so re-run `check` after more of a company's postings arrive.
- **Acronyms are placed.** An acronym is an unvetted term, so when a posting has sections
  it counts only where the job is described (requirements, preferred, responsibilities, or
  untyped text). One that appears only in company, benefits, legal or logistics text or
  the company template ("HSA", "AD&D", "RRSP") is set aside and listed in
  `coverage.json` `acronyms_set_aside`. A short capitalised line with a long word
  ("UNITED STATES", "REFERRAL INSTRUCTIONS") is a heading, not a run of acronyms. Capitalised
  English words ("NOT", "AND", "ALL", "ANY", "FOR"), a hyphenated adjective ("AI-generated"
  reads as "AI", "SIEM-based" as "SIEM"), a short pair joined by "&" ("DE&TH", "R&D"), and a
  two-letter acronym ("ES", "TS") are not skills; a two-letter one counts only when it is in
  your lexicon or on a line that also holds a lexicon term ("Splunk ES").
- **Experience.** A number of years on a line that mentions experience (`5+ years`,
  `3-5 years`), with its section. Set `[profile] years = "3"` in `config.toml` and a
  larger ask reads `below the ask`; a value that is not a number says the comparison is
  NOT EVALUABLE.
- **Not looked at.** Every requirement line (each line of a required or preferred
  section; with no sections, each bullet) in which no lexicon term or acronym was
  found is listed, with the count beside the total. A skill no pack knows (Kafka,
  Helm, Django in the shipped packs) shows here instead of reading as "no gap". `jobs
  upskill` adds the totals across roles, so its demand table says how much of the
  postings it could not read; a role whose `coverage.json` predates the count is named
  as not measured (re-run `jobs check`), never as having no lines.

All of it lands in `coverage.json` (`sections`, `term_sections`, `years`, `unread`).

### A posting's history and duplicates

`jobs discover` remembers each posting's text (a hash in `meta.json`):

- **CHANGED**: a posting you already have whose text changed on the board (compared with
  whitespace normalised: re-spacing, blank lines and CRLF are not a change; a role stored by
  an older version is compared by its stored `jd.txt`). It is printed on
  every discover while it differs, recorded once in the role's history (`board_changed`),
  and the stored text is kept; `jobs intake ... --force` takes the new text and keeps your
  status and history.
- **DUPLICATE**: a new posting with the same company, title and location as a role you
  already track (another posting id, or another board, including a board earlier in the same run) is not
  taken in again; two postings of one title in the same board listing are two openings. `[sources] aliases = {"acme-careers" = "acme"}` says two board org names
  are one company. A role you track counts unless its status is `rejected`, `passed` or
  `closed` or it has vanished from the board: `found`, `scored`, `tailoring`, `applied`,
  `interviewing`, `offer` and `on-hold` all count. Where a closed role and an active one
  share the job, the active one is the one named.
- **REPOSTED**: the same job back after the only role you had was closed (`rejected`,
  `passed`, `closed`) or vanished from the board is taken in as a new role with
  `reposted_from` naming the old one.

### A suggested fit

`jobs check` prints a suggested fit, and `jobs score SLUG` (no `--fit`) shows its working:
`1 + 4 x (0.7 x required held share + 0.3 x preferred held share)`, minus 0.5 when the
experience asked is above `[profile] years`, clamped to 1-5 and rounded to the half point.
Held means held by facts.md (under any alias), not stated on the resume: a resume can be
tailored, what you hold cannot. Without a required/preferred split it uses every term.
Nothing is written until you accept it with `--fit suggested` (recorded as
`fit_source: suggested`) or give your own `--fit N` (`fit_source: you`). It needs a fresh
`jobs check`.

### Writing the application: `jobs brief`

`jobs brief SLUG` prints one Markdown bundle to hand to whoever writes the tailored resume
and cover letter (you, or your assistant). kenloop writes no prose of its own; the brief
is deterministic and holds:

- rules: claim only what facts.md holds, trace each claim to the line quoted; never claim
  what is listed under "Do not claim"; name the requirement each bullet answers; use the
  company's own words for what it does; finish with `jobs check-claims`;
- the role typed: required, preferred and responsibilities, each term marked `[held]` or
  `[not held]`, the responsibilities in the posting's words, and the experience asked;
- the company in its own words: from its template when kenloop has learned one (3 or
  more postings), else from this posting, and it says which;
- the benefits the posting states, plus the company's standing benefits (its template
  lines of kind benefits, in most of its postings), for your judgement, not the letter;
- "You hold", each term with the facts.md line that holds it; "Do not claim"; and the
  requirement lines no known skill was found in, to read yourself.

It needs a fresh `jobs check` (NOT EVALUABLE otherwise, as `tailor`).

### Building the PDFs: `jobs build`

`jobs build SLUG` compiles the role's LaTeX resume with tectonic, and its cover letter when one sits
beside it (`cover-letter-<x>.tex` for `resume-<x>.tex`, or `--cover`). The resume is `--resume`, else
the role's `resume` field, else the one its last `jobs check` measured. Each PDF is checked:

- one page (pdfinfo);
- the last three words of every `\item`, and of the document's last paragraph, are in the PDF text
  (pdftotext); a line that ran off the page is missing, and the build names it;
- no text within 0.25in of the bottom edge (`pdftotext -bbox`).

Any failure exits 1 and names the file and the line. Missing tectonic, pdfinfo or pdftotext exits 2 and
builds nothing; so does a PDF whose text positions cannot be read, since the margin was not checked.

PDFs are filed by whether the employer has them, one folder per role under `[build] pdf_root`
(default `pdf`, relative to the home):

| Folder | Statuses | |
|---|---|---|
| `sent/<slug>` | applied, interviewing, offer, rejected | the record of what was submitted: `build` refuses to write here (exit 1); `--outdir` builds a copy elsewhere and leaves the record alone |
| `ready/<slug>` | found, scored, tailoring, on-hold | |
| `old/<slug>` | passed, closed | |

`jobs status` moves the folder when a role crosses from one to another, and records it in
`meta.json` (`pdf_dir`). A folder already at the destination is never overwritten: the status
change stops (exit 2) before anything is written, and you move one aside by hand.

### What you want: `[wants]`

Filters for what you want from a job, kept apart from `facts.md` (that is what you hold
and what your resume may claim). Each filter is its own module and answers **pass**,
**fail** (with the reason) or **unknown**, and each has its own policy for an unknown:
`keep` (the default: a posting that does not say is not a posting that says no), `flag`
or `drop`.

```toml
[wants]
workplace = ["remote"]        # remote, hybrid, onsite
workplace_unknown = "keep"    # keep | flag | drop
pay_min = 120000              # a yearly floor
pay_currency = "USD"
pay_unknown = "drop"          # the "no pay range stated" policy
benefits = ["unlimited pto", "pet insurance"]
benefits_unknown = "keep"     # applies to every benefit row

[wants.benefit_phrases]       # more spellings for any benefit, yours or the catalogue's
"four day week" = ["32-hour week"]
```

- **workplace** reads the board's own field when it has one (Ashby and Lever
  `workplaceType`), else an explicit word in the location or title ("Remote - US",
  "Hybrid"). An office city alone is unknown, not on-site. A negated remote ("not remote",
  "no remote", "non-remote") is on-site when the text says on-site, else unknown;
  "remote sensing", "remote access" and the like are not a workplace; a text naming two
  workplaces ("Hybrid / Remote") is unknown unless your `workplace` list holds both.
- **pay** reads the board's field (Ashby compensation, Lever `salaryRange`), else every
  pay *range* in the posting text, each with its label, interval and currency
  ("$120,000 - $150,000", "$120K–$150K", "USD 95,000 to 110,000", "$55 - $65 per hour").
  A single amount or a funding round is not a range. A range labelled stipend, allowance,
  reimbursement, bonus, sign-on, equity, stock, RSU, grant, relocation, budget or
  commission is not pay and is ignored; a range labelled salary, base, pay or compensation
  is preferred to an unlabelled one; a posting with only the ignored kinds has no pay
  stated (the reason says so). Hourly is compared at 2,080 hours a year, monthly ("per
  month", "monthly") at x 12 and weekly at x 52, and the reason shows the conversion. When
  several pay ranges remain (location or level tiers) the highest top is judged against
  your floor and the reason says "N pay ranges stated (location or level tiers); judged on
  the highest". A range passes when its top reaches the floor. The currency is read from a
  code or symbol before or after the range or in the line's label ("CAD $120,000",
  "Salary (CAD):", "HK$900,000", "$110,000 to $140,000 AUD"; USD, GBP, EUR, CAD, AUD, NZD,
  SGD, HKD, MXN, INR, JPY and CHF are known); another currency is unknown (no conversion).
  A bare "$" names no currency: it counts as USD only when the location says United States
  (US, USA, a state name, or a state code that ends the location or a part of it, such as
  "Austin, TX" or "OR / WA"; not "Latin America", not "Hybrid OR Remote") and the posting
  does not name one; elsewhere (Australia, Canada, "Toronto, ON", or no location) the currency is
  unstated, so unknown.

- **benefits**: each wanted benefit is its own row. It passes when a line of the posting
  that states benefits (a benefits, other or unheaded line; never responsibilities,
  about-the-company, legal, required or preferred text) names it, or when the board states it as a field (Ashby
  equity); the row quotes the line it rests on, so you can judge a spelling such as
  "Flexible PTO" counted as unlimited PTO. "Equity" counts only with a compensation sense
  (equity grant, compensation or package; stock, stock options, RSUs; "offers equity") or
  as a bare item in a benefits section; "pay equity" and "diversity, equity and inclusion"
  are not equity. It fails when a line rules it out: a negation beside the phrase ("Not
  eligible for equity", "We do not offer unlimited PTO"), or, for unlimited PTO, a fixed
  allowance stated as the allowance ("20 days of vacation", "15 days of PTO per year")
  when no line anywhere in the posting says open PTO. A year-end shutdown or holiday block
  is not an allowance. Unlimited PTO's spellings include "take what you need", "not accrual
  based", "untracked PTO", "discretionary time off", "open time off" and "no set limit".
  Every pass spelling is looked for in the whole posting before any rule-out. Otherwise it
  is unknown: a posting that does not mention pet insurance has not said there is none. A
  catalogue of common spellings ships for unlimited pto, pet insurance, 401k match,
  health insurance, parental leave, equity, learning budget, home office stipend and four
  day week; any other benefit is matched as written.

`jobs discover --intake` sets aside what fails (and unknowns under `drop`), printing each
as `EXCLUDED ... : <reason> [wants]`, and never takes it in; nothing already taken in is
touched. `jobs wants` reports every stored role: each filter's pass / fail / unknown with
its denominator, then the roles it would set aside or flag, with the reason. The unknown
count is the number to watch: it says how far each reader can be trusted on your boards.

### The daily digest: [digest]

`jobs digest` reads every `[sources]` board once and sorts each posting into a bucket, so a
scheduled run each morning shows what went up overnight. Applying early matters: the digest
leads with what is NEW since the last digest and says how old each posting is (`posted`, the
board's own date, where it gives one).

```toml
[digest]
families = [   # the title picks the family; first match wins
  {name = "Security operations", match = ["soc", "incident response", "detection"], prefer = true},
  {name = "Threat intelligence", match = ["threat intel"]},
]
near = ["austin", "texas"]   # a non-remote posting fits when its location holds one of these
exclude = ["product manager", "sales"]   # titles that are never this search
search = ["security"]        # Workday is searched server side, once per word
fresh_days = 14
place_order = ["austin", "remote", "texas"]   # optional: which places you would rather; ranks the top picks
```

| Bucket | When |
|---|---|
| apply first | a `prefer` family, not senior, in a place that fits, `[wants]` not failed |
| stretch | a `prefer` family at a senior level (not management), in a place that fits |
| worth a look | another listed family in a place that fits, or a `prefer` family elsewhere in the US |
| set aside | a `[wants]` filter failed, a management title (director, manager, head of, VP, chief), a posting outside the US, or neither family nor place fits (counted by reason) |

A place fits when the posting is remote and its location says US or nothing beyond "remote",
or when it is not remote and its location holds a `near` word. A remote posting naming another
country does not fit. A title matching no family, or holding an `exclude` word, is outside
your search and only counted.

The digest opens with **Start here**: the five best NEW apply-first postings, and a count of
the rest. Without `place_order` they are newest first; with it, a posting in an earlier place
comes first (`"remote"` stands for a remote posting, any other word is looked for in the
location of one that is not remote).

The digest reads the roles you track (`roles/<slug>/meta.json`). A posting is a tracked role
when its URL is the role's `source_url`, or its id is the role's `job_id` at the same company
(for Workday, the requisition number its `/job/...` path ends with also counts).

| The role's status | In the digest |
|---|---|
| applied, interviewing, offer, rejected, passed, closed | leaves the tables; one line under **Already tracked** ("already applied 03-18") |
| found, scored, tailoring, on-hold | stays in its table, marked "(tracked: scored)"; never a Start-here pick |

**Follow-ups** lists every role in status `applied` by days since the applied date: from day 7,
check the portal and that the posting is still up; from day 14, send a short note if you have a
recruiter contact; from day 30, the command that closes it as `no_response`. These are
suggestions; nothing is changed for you. "It was in today's listing" is said only when the
posting was read today; a posting not seen is not called gone. A role record that cannot be
read is counted at the top, since a posting may then be one you already track.

It writes `digests/<date>.md` and `digests/seen.json` (the day each posting was first listed:
what "new" means); `--dry-run` prints and writes nothing. A board that did not answer is named
at the top and the exit code is 2: an unreachable board is never "no new jobs". A Workday
listing is searched and paged by relevance, so it can be partial; the digest says so, and
`jobs reconcile` never marks a role gone from a partial listing.

Workday targets need the career site beside the org:
`{board = "workday", org = "acme", host = "acme.wd1.myworkdayjobs.com", site = "External"}`.

### Lexicon packs

A pack is a TOML file of categorised terms. Three ship with the package (`web`,
`security`, `data`); one of yours in `HOME/lexicons/<name>.toml` replaces the shipped
pack of the same name, and `[ats] packs = [...]` in `config.toml` picks which are read.

```toml
name = "security"
[categories]
tools = ["splunk", "microsoft sentinel", "crowdstrike"]
frameworks = ["mitre att&ck"]
[aliases]                       # another spelling of a term above: the same skill
"sentinel" = "microsoft sentinel"
"att&ck" = "mitre att&ck"
[extraction]
acronym_noise = ["soc"]         # capitalised words that are not skills
```

An alias counts as its term everywhere: in a posting (`ATT&CK` and `MITRE ATT&CK`
are one term, asked once), on a resume (`k8s` covers a posting's Kubernetes), and in
`facts.md` (`- k8s` under `## Held` holds Kubernetes, for `check`, `check-claims`
and `upskill`). That is the difference from `[ats] equivalence` in `config.toml`,
which maps a term to a *related* one you hold (OpenAPI via REST) and still asks you
to state the term itself. An alias whose term no loaded pack has is skipped with a
warning; a word that is both a term and an alias reads as the term.

The shipped `security` pack (202 terms, 56 aliases) names products and
certifications as postings do (Splunk, Microsoft Sentinel, CrowdStrike, KQL, Sigma
rules, Security+, CySA+), beside functions and frameworks. Most words that are also
ordinary English appear only in an unambiguous form (`elastic security`, `windows
server`, `golang`, `web proxy`, `intrusion detection`, `sigma rules`), so "Six Sigma" or
"unique IDs" read as nothing. A few short words are kept because security postings
use them bare and mean the skill: `sentinel` (Microsoft Sentinel; "Sentinel One" reads
as SentinelOne), `playbooks`, `pam`, `bash`, `rust`, `jira`, `sso`. Outside a security
posting those can misread.

## When a command cannot look (exit 2)

Exit 2 is NOT EVALUABLE: the command says what it could not look at and why, and never prints a
clean 0 or an empty result in its place. Any command that cannot look exits 2 with the cause;
common cases:

| Command | Exits 2 when |
|---|---|
| every command | missing home (no `config.toml` and no directory; run `init`) |
| `doctor` | nothing to check (no role with a posting and no topic), `facts.md` missing, empty or without `## Held`, a damaged role file or topic log, a role with a posting and no resume, a posting or resume that is not UTF-8 text, a resume that states no lexicon term |
| `next` | no topics and no roles (`empty`); an unreadable facts sheet (`graduation`) or `asks.jsonl` (`question`) is printed as not evaluable and exits 2 |
| `jobs check`, `jobs check-claims` | `facts.md` missing, empty or without `## Held`; the resume missing, not UTF-8 text or not a regular file (`check-claims /etc`); a per-role or `[profile]` resume pointer to a file that is not there; no terms in the posting (`check`) or in the resume (both: `check` writes no `coverage.json` for a resume that states no lexicon term or acronym) |
| `jobs tailor` | the role has no coverage report (without `coverage.json`), or the report is stale (the posting, resume, facts, config or a lexicon changed since): run `jobs check` first |
| `jobs show`, `check`, `tailor`, `score`, `status`, `rank`, `upskill` | a damaged role `meta.json`: invalid JSON, JSON that is not an object (`null`, a list), a missing `company`, `role` or `status`, or a field of the wrong type or value (`fit_score` not a number, `status` not one of the statuses); the file and the field are named |
| `jobs build` | tectonic, pdfinfo or pdftotext missing (the message says which and where to get it) |
| `jobs status` | the role's PDF folder would move onto a folder that already exists |
| `jobs upskill` | no role has a coverage report: it prints `0 bucket(s) from 0 role(s)` with the cause and writes no `upskill.json` |
| `jobs gaps` | `upskill.json` absent (prints `0 role(s) analysed`), damaged or not schema-2, or it analysed 0 roles (with roles analysed it prints `N demand bucket(s) from M role(s)` and exits 0) |
| `plan --from-gap` | no `upskill.json` yet |
| `validate` | no topic in the home (`validate SLUG` prints its own counts); a damaged log row |
| `due` | no topic in the home (`due SLUG` prints `SLUG: N due`); a damaged log row |
| `calibration` | no confidence-rated, unaided attempts yet |
| `quiz`, `talk`, `dive`, `mastery`, `foundations` | the topic has no concepts yet (`sync` reads them from `syllabus.md`) |
| `ask`, `rung` | a line of `asks.jsonl` cannot be read (`ask` then lists what it can and numbers no new question); `validate` and `doctor` report it too |
| `board` | a topic's state or settings are damaged (named; the rest is listed); a damaged log row in any topic |
| `cert exam` | the topic has no exam-scope concepts (there is no exam to sit) |
| `beliefs`, `talk`, `dive`, `mastery` | a damaged log row: they print what they can and say so |
| `cert exam-date` | an exam date is set but the topic has no exam-scope concepts |
| `quiz`, `calibration`, `misconceptions`, `sync`, `plan` (existing topic), `cert exam-date` | a damaged log row: they print what they can and say how many rows were skipped |
| `jobs graduate`, `rebuild` | a damaged log row (they refuse; `rebuild --skip-damaged` is the explicit override) |
| `record` | a damaged log row: nothing is recorded, since a row added now would be replayed against a record that cannot be read in full |
| `jobs discover` | no `[sources]` targets with `--all`; a board is unreachable or returned no postings at all; a damaged role file or a role directory without `meta.json` (named; the rest is still done); a posting that could not be taken in (named) |
| `jobs reconcile` | no `[sources]` targets; a board is unreachable or returned no postings at all; a damaged role file or a role directory without `meta.json` (named, not checked; the rest is still checked) |
| `jobs rank`, `jobs board` | a damaged role file or a role directory without `meta.json` (on an empty home `jobs board` prints `0 role(s)` and `jobs rank` prints `(0)` for each section; both exit 0: they are listings) |
| `jobs intake --jd FILE` (or `-`), `quiz --interactive` | the posting or the typed input is not UTF-8 (named with the byte and offset); the posting is empty ("empty posting", nothing taken in) |

The views (`due`, `quiz`, `mastery`, `board`, `beliefs`, `calibration`, ...) print from the derived
`concepts.json`, so each ends with an integrity check against the log: after its normal output
it exits 2 on a damaged log row, and 3 when what it showed has drifted from the log (the
concepts are named; `rebuild SLUG` replays the log and clears it).

A file that is not UTF-8 (a posting, syllabus, question bank, resume) is named with its path and
the offending byte. A log row that is not UTF-8 is a damaged row, counted and named by line.
`--resume P` (`jobs check`) and the positional `RESUME` of `jobs check-claims` are tried relative to the current
directory first, then relative to HOME; a directory or device is refused alike ("not a regular file", exit 2); `jobs check` stores the resume as an absolute path (or relative to
HOME when it is inside it), so its coverage stays fresh whatever directory you run from. Dates are written exactly `YYYY-MM-DD`; `--n`, `--limit`
and `--top` take a whole number of 1 or more; `jobs board --status` takes one of the role statuses; `--min-fit` a number from 0 to 5; `intake` a non-empty
`--company` and `--role`; `discover` and `reconcile` a known `--board`, and `reconcile --board` needs
`--company`; a `plan` slug is 1 to 64 characters of `a-z`, `0-9` and `-` (exit 64 otherwise).
`jobs discover --exclude-senior` prints how many postings it left out, and a posting with no title is
named and skipped.

`record` appends the row you gave it and warns about log problems; it exits 0. A keyword that
matches nothing on a board that did list postings is a result (exit 0), printed with its denominator.

## Your data

Everything lives in one directory you own:
- `--home DIR`, else `$KENLOOP_HOME`, else `$XDG_DATA_HOME/kenloop`, else `~/.local/share/kenloop`.

Nothing is written inside the package.

```
config.toml      settings for the sidecars: keyword packs, equivalences, demand buckets, fit bar, job-board targets
facts.md         what you hold: only skills under `## Held` count. `init` writes the template once; no command after that modifies it.
resumes/         resume.md (or .txt, .tex)
roles/<slug>/    meta.json, jd.txt, scorecard.md, coverage.json, review.md
pdf/             sent/ ready/ old/<slug>: built PDFs, by whether the employer has them (`[build] pdf_root`)
topics/<slug>/   topic.json (title, goal, origin, outlets, deadline, complete, intent, depth, start; the old
                 names exam_date and passed are still read, and renamed only by `settings SLUG --migrate`), syllabus.md, questions.md,
                 log.jsonl (the record: every answer and dialogue; each row carries the question's depth and
                 whether it was asked because it was due), concepts.json (derived),
                 dialogues/ (transcripts; .graded/ keeps each as it was graded), foundations/ (notes),
                 placement.jsonl (where you start on the scale; no credit), recall.jsonl (pieces
                 recalled), marks.jsonl (how ideas feel to you; never evidence), renames.jsonl (concept renames), promotions.jsonl (interest concepts
                 promoted to job skills), tutor.md (tutor notes on this topic; never evidence)
asks.jsonl       your questions and their rungs (append-only, like a topic's log)
branches.jsonl   every gap found mid-study, who raised it and what became of it (append-only)
scouts.jsonl     scouted (predicted) branches, decided through branches.jsonl (append-only)
tutor_gaps.jsonl misses the teaching caused, counted against the tutor, never the learner (never evidence)
sessions.jsonl   the session journal: each closed session's three things, fuzzy one, felt (1-5 or words) and counts (never evidence)
focus.jsonl      where `next` points: every pivot, its day and why; the last row wins (append-only)
trail.jsonl      the path from what started a study thread: each step down and back (append-only; two
                 machines going down and back at once merge in file order, so `back` may then pop the other's step)
learner.md       tutor notes on how you learn, across topics (`ken note --learner`; never evidence)
profile.md       the curated learner profile the tutor reads first, rewritten from those notes (`ken profile`; never evidence)
lexicons/        your own keyword packs (the package ships web, security, data)
upskill.json     weighted demand (derived)
upskill.md       the same plan as readable text, written by `jobs upskill` (derived)
```

Job boards: the public posting APIs of Greenhouse, Lever, Ashby and Workday, plus
`fixture` (a local JSON file). Requests are sequential and rate-limited per
host, and a fetch error is reported as an error, never as an empty board.


## What it does not do

- It does not write your resume or cover letter, and after `init` has written the `facts.md` template no command modifies it.
- It does not scrape sites without a public posting API.
- It has no LLM inside. The question bank and the dialogue are yours, or your assistant's
  under the [tutor rules](tutor-rules.md) and the [dialogue rules](dialogue-rules.md); the
  tool keeps the record and checks it.
- It does not make resume PDFs (`ken print --pdf` renders study printouts only). Keep your resume in the tool you like; `check`
  reads Markdown and text, and LaTeX best-effort (with a warning; see the limits in
  [trust rules](trust-rules.md#known-limits)).

## The on-ramp: a scale, a placement, and the pieces of a concept

A dialogue that picks apart what you know is the right first step only when you have footing.
In a field you have barely heard of, it tests reasoning you never had the chance to build. So a
new topic starts with a **scale**: its domains listed under `## Path` as rungs, ground first,
each leaning only on the rungs below it.

```
## Path

0. **ground** — bugs, crashes and fuzzing
1. **code** — how source becomes machine code
2. **basics** — what a proof is
```

`ken place SLUG` then finds the rung you start on. Your assistant asks one open question per
rung, starting on the rung you think you stand on. A scale is ordered, so each answer narrows
where you could start: a pass rules out the rungs below it, a miss the ones above. `place` then
names the rung whose answer halves what is left (so five rungs take about three questions), a
partial gets one more question, and a rung carried above a missed one is named as a
contradiction rather than averaged. Until study starts, `next` asks that question; you can stop
at any point and start on the working guess. Each answer is recorded verbatim with
`--rung N --result R --probe Q --answer A`. Placement earns no credit, because a handful of
questions says little about what you will remember; it lives in `placement.jsonl`, apart from the
log. A rung is carried when its latest answer passed, and not carried after a miss or two
partials in a row. You start on the lowest rung not carried.

What follows depends on the rung:

| where the concept sits | what `talk` and `next` say |
|---|---|
| below your start | nothing: talk, and expect to be pushed |
| on your start, not yet studied | read the foundations note (`foundations --scaffold` writes one), then `dive`, then talk |
| above your start | taught first; not graded yet |

A topic studied before it had a scale is never nagged to place; placement is optional there.

**Branching.** A gap found mid-study is usually a piece of the thing you are studying, not a
tangent. `ken branch SLUG CONCEPT "DOMAIN :: NAME :: DESC"` adds it as a concept marked
`part-of:CONCEPT`, on the same rung or one below. `--before` marks something learned before the
concept instead. `--topic NEW` makes it a topic of its own, seeded with that concept, whose
`origin` names where it grew from. The rule of thumb: a gap of one to three concepts with no goal
of its own is a piece; one with its own goal, or more than about five concepts, is a topic; one
you could step past is a note (`--next` on the record). Pieces nest at most two deep. Below
that, a gap is a topic or a note, so a decomposition cannot run away. `talk` on a concept whose
pieces you have not climbed says to climb them first, and names what is marked to come before it.
The links are recorded now so that credit can later flow between a concept and its pieces; today,
none does. `validate` fails a link that cannot be followed: a concept linked to itself, a link to a
concept the syllabus does not have, and a cycle (a piece comes before its whole, so a loop is an
order no one can follow).

**The map.** `ken map` reads the topic as one graph: a concept's pieces (`part-of`), what is marked
to come before it (`before`), the rungs below it on any question ladder, and, with a scale, your
starting rung. A concept is climbed at good or mastered; one that is not is ready when every piece,
everything before it and every lower ladder rung is climbed and it is not above your start
untaught. Otherwise it waits, and the map says on what. The frontier is everything ready and not yet
climbed. The map writes nothing and moves no credit: structure decides what you are asked next,
only your answers decide what you hold.

**Recall the pieces.** `ken recall SLUG CONCEPT` asks you to name what a concept is made of, from
memory; `--listed "first; second"` scores your list against its pieces on the map (by name or id,
case and punctuation ignored): recalled, missed, and anything not on the map yet, offered as a
branch. It is practice, not a test: no credit, no schedule change, its own record
(`recall.jsonl`). A piece missed in your latest recall of its whole is marked on the map, and
`next` takes it first among pieces. Why recall and not a drawn map: listing from memory beat
building a concept map, even on a concept-map test (Karpicke & Blunt, Science 2011).

**Renaming a concept.** A concept's id is its syllabus line's `domain:name`, and the log records
history by id, so editing the line alone would leave the old id holding the history (`validate`
warns about it). Rename the line, then `ken rename SLUG OLD NEW`: a row in `renames.jsonl` maps the
old id, replay reads the history under the new one, and the links in `syllabus.md`, the bank's
`## <id>` heading and the foundations note follow. It refuses when the new id already has a
history of its own: two histories are not merged.

The tutor skill that runs this with you, offering branches as it goes, is
[skills/ken-tutor](../skills/ken-tutor/SKILL.md).

**Who raises a branch, and how well the offers are picked.** A gap can be raised three ways: by
you, by your assistant in a dialogue, or by the tool from the record. `ken branch SLUG` lists the
tool's offers: a dialogue's `--broke` or `--next` that names nothing on the syllabus, a dialogue
taught at hint depth 3 or more, an open question with no concept to land on, and a placement
miss. Each offer has a key; decide it with `--by tool --source KEY`, and it is not offered again.

Every decision, including a note and a declined offer, is one row of `branches.jsonl` in the
home, and `--by` is required, because the ratios are read from it. `ken branch` prints them with
their counts: how many offers were taken (low: too many offers), how many kept branches you raised
before anyone offered (high: the offers are missing gaps), and how many branches built as a piece,
a before or a topic were studied since. With no offers yet it says so rather than print a rate. A
line of the record that cannot be read stops any append and makes `branch` exit 2.

