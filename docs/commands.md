# The loop, `next`, commands, and your data

The loop `careerloop next` walks:

```
        ┌──────────── discover roles ◀───────────┐
        ▼                                         │
  check coverage ──▶ demand for skills you lack   │
        │                     │                   │
        │                     ▼                   │
        │            plan a topic from the gap    │
        │                     │                   │
        │                     ▼                   │
        │          quiz, record, review (FSRS)    │
        │                     │                   │
        │                     ▼                   │
        │       graduate: you paste under ## Held   │
        │                     │                   │
        ▼                     ▼                   │
  tailor, check claims, apply ──▶ outcome ────────┘
```

`next` reads both halves and names the one thing most worth doing now, with the reason.

## What `jobs check` reads from a posting

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

## A posting's history and duplicates

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

## A suggested fit

`jobs check` prints a suggested fit, and `jobs score SLUG` (no `--fit`) shows its working:
`1 + 4 x (0.7 x required held share + 0.3 x preferred held share)`, minus 0.5 when the
experience asked is above `[profile] years`, clamped to 1-5 and rounded to the half point.
Held means held by facts.md (under any alias), not stated on the resume: a resume can be
tailored, what you hold cannot. Without a required/preferred split it uses every term.
Nothing is written until you accept it with `--fit suggested` (recorded as
`fit_source: suggested`) or give your own `--fit N` (`fit_source: you`). It needs a fresh
`jobs check`.

## Writing the application: `jobs brief`

`jobs brief SLUG` prints one Markdown bundle to hand to whoever writes the tailored resume
and cover letter (you, or your assistant). careerloop writes no prose of its own; the brief
is deterministic and holds:

- rules: claim only what facts.md holds, trace each claim to the line quoted; never claim
  what is listed under "Do not claim"; name the requirement each bullet answers; use the
  company's own words for what it does; finish with `jobs check-claims`;
- the role typed: required, preferred and responsibilities, each term marked `[held]` or
  `[not held]`, the responsibilities in the posting's words, and the experience asked;
- the company in its own words: from its template when careerloop has learned one (3 or
  more postings), else from this posting, and it says which;
- the benefits the posting states, plus the company's standing benefits (its template
  lines of kind benefits, in most of its postings), for your judgement, not the letter;
- "You hold", each term with the facts.md line that holds it; "Do not claim"; and the
  requirement lines no known skill was found in, to read yourself.

It needs a fresh `jobs check` (NOT EVALUABLE otherwise, as `tailor`).

## What you want: `[wants]`

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

## Lexicon packs

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

## How `next` decides

The rules are fixed, and the first one that fires wins. `next --all` prints
every rule's evaluation so you can audit the choice, and `next --json` gives
the whole object. Two things the table does not show: rules 2 and 5 suggest
`jobs check SLUG` instead when the role's coverage is missing or stale (tailor
would refuse it), and rules 4 and 7 print *not evaluable* when `upskill.json`
does not exist yet (rule 4 only if reviews are due); run `jobs upskill`.

| # | When | Suggests |
|---|---|---|
| 0 | no roles and no topics | discover / intake (exit 2) |
| 1 | a topic's state disagrees with its log, or fails validation | `learn rebuild` / `learn validate` |
| 2 | a role at or above your fit bar closes within `deadline_days` | `jobs tailor`, or `jobs status … applied` |
| 3 | a concept passed every graduation gate and is not yet under `## Held` in facts | `learn graduate --emit` |
| 4 | reviews are due in a topic whose demand bucket is non-zero, or whose exam is within 14 days | `learn due` |
| 5 | a live role at or above the bar is waiting | `jobs tailor` the best |
| 6 | a demand-linked topic has banked questions for concepts never studied | `learn quiz --weak --interactive` |
| 7 | the top unplanned demand bucket reaches `min_bucket_demand` | `learn plan --from-gap` |
| 8 | roles are waiting to be scored | `jobs score` the oldest |
| 9 | nothing is ripe | `jobs discover --all --intake --keyword WORD` (replace WORD; `next` prints `…`) |

## Commands

```
careerloop init                          create the data directory (facts.md with `## Learning` and `## Held`)
careerloop next [--all] [--json]         the one thing to do now
careerloop doctor                        both halves: 0 clean, 1 findings, 2 not evaluable
                                         (also an empty home or an empty facts.md), 3 drift

careerloop jobs discover --board B --company ORG | --all [--keyword K] [--intake] [--exclude-senior] [--reconcile]
careerloop jobs intake --company C --role R [--jd FILE|-] [--force]
careerloop jobs score SLUG [--fit 1-5 | --fit suggested]   no --fit: the suggested fit and its working
careerloop jobs check SLUG [--resume P]          coverage.json (P: current directory first, then HOME); exit 1 if the resume has a
                                         disguised skill (a posting only warns), 2 if it cannot judge
careerloop jobs tailor SLUG                      review.md: what to state, what not to claim
careerloop jobs status SLUG STATE [--stage S --reason R --probed a,b]
careerloop jobs rank | board | show SLUG | reconcile
careerloop jobs upskill                          upskill.json: weighted demand by bucket
careerloop jobs wants                            every role against [wants]: pass / fail / unknown per filter
careerloop jobs headings [--all]                 headings the section reader did not type, counted across postings
careerloop jobs org NAME                         a company's template and profile, from its postings -> orgs/NAME.json
careerloop jobs brief SLUG                       a Markdown bundle for writing the tailored resume and cover letter
careerloop jobs check-claims RESUME [--acronyms]   lexicon-pack terms only; --acronyms adds
                                         capitalised acronyms and names; held = listed under ## Held
                                         exit 0 clean, 1 violations, 2 not evaluable

careerloop learn plan SLUG [--from-gap BUCKET]   seed concepts from demand (idempotent)
careerloop learn sync | bank | quiz [--interactive] | record | due | exam-date
careerloop learn graduate SLUG [--emit: lines to paste under ## Held] | misconceptions | calibration | gaps
careerloop learn rebuild SLUG [--check] [--skip-damaged] | validate [SLUG]
careerloop learn brief SLUG                      a bundle for writing the topic's questions, in the bank's format
                                         validate: exit 1 on failures, 2 if a log row is damaged
```

`learn brief SLUG` prints a Markdown bundle for whoever writes the topic's questions (you, or
your assistant): the rules (no hint in the question, one checkable answer, a Ref the learner
can open, your own questions rather than an exam's, distractors that name their
misconception, `Provenance: unverified` until checked), every concept with how many
questions it has now (thinnest first), and the exact bank format. A bank written to it
parses, but `learn validate` fails a question whose text or answer is still the brief's
angle-bracket placeholder (`<the one checkable answer>`); edit them and it passes. Validate
also fails a question with no answer and warns on one with no Type.

`learn quiz --interactive` is a complete study session with no assistant:
- it asks the question, as multiple choice when the bank has distractors;
- `?` climbs a four-rung hint ladder (the rung you reach is recorded);
- it asks your confidence *before* revealing the answer;
- it grades a multiple-choice pick itself, and asks you to grade free recall;
- a wrong pick records the misconception that distractor encodes.

Every answer goes through the same code path as `learn record`. If you prefer
to study with an AI assistant, [docs/tutor-rules.md](tutor-rules.md) is
a contract to give it, and it records the same way.

Exit codes: `0` ok · `1` findings · `2` not evaluable · `3` drift · `64` usage.

### Which resumes `doctor` scans

`doctor scans` the resume that each role with a posting resolves to (the role's own `resume`
field in `meta.json`, else `[profile] resume`, else `resumes/resume.md`, `.txt` or `.tex`), once per
file, with exactly what `jobs check-claims RESUME` judges (lexicon-pack terms, not `--acronyms`):
a disguised word, a term that is not held, a Held line that contradicts itself or is spelled with a
look-alike. A resume that no role resolves to is not scanned; run `check-claims` on it yourself.
A resume that is not UTF-8 text, or states no lexicon term, makes `doctor` exit 2 for that file.

### Disguised words: what is and is not examined

One rule. Each whitespace-separated word is read whole, split into parts at every punctuation mark
or symbol, and with a possessive `'s` (also `′s` and `´s`) removed. For a lexicon term of several
words (`rate limiting`) a run of that many consecutive words is read as one reading too
(`Rate Limit<Cyrillic i>ng`; a word that is only a dash or a slash is not counted; a window never spans a line; a soft hyphen reads as a space too; a lexicon term of more than 8 words is skipped with a warning). A reading is altered only if rewriting it (accents,
overlays and look-alike letters changed, symbols dropped) makes it differ from its NFKC form, and
an altered reading that equals a lexicon term is reported as `suspicious-characters`: a term written
with a look-alike letter, an overlay or enclosing mark, a symbol or a control character inside it,
also next to punctuation (`Dock<Cyrillic e>r-based`, `Skills:Dock<Cyrillic e>r`), and a word that
equals a term of four or more letters once its accent is removed (`régression` is `regression`,
`azuré` is `azure`, even when innocent): retype it without the accent. A compatibility form or
possessive alone is not altered (`ﬁrewalls,`, `Python’s`), ordinary typography around a word
(`“Docker”`, `Docker…`) is not examined, a dash between fragments of a one-word term (`Java‑Script`,
`Web–Sockets`) is a joiner and reads as written (clean, like `Java-Script`), words that spell no term
(`São Paulo`, `café`) are clean,
and a term of three letters or fewer is not reported on an accent alone. A superscript, ordinal
or fraction glued to a term (`Docker⁺`, `Docker¹`, `Dockerª`) is a disguise. Exactly what:
[trust-rules](trust-rules.md).

## When a command cannot look (exit 2)

Exit 2 is NOT EVALUABLE: the command says what it could not look at and why, and never prints a
clean 0 or an empty result in its place. Any command that cannot look exits 2 with the cause;
common cases:

| Command | Exits 2 when |
|---|---|
| every command | missing home (no `config.toml` and no directory; run `init`) |
| `doctor` | nothing to check (no role with a posting and no topic), `facts.md` missing, empty or without `## Held`, a damaged role file or topic log, a role with a posting and no resume, a posting or resume that is not UTF-8 text, a resume that states no lexicon term |
| `next` | no roles and no topics (rule 0); an unreadable facts sheet is printed as rule 3 not evaluable and exits 2 |
| `jobs check`, `jobs check-claims` | `facts.md` missing, empty or without `## Held`; the resume missing, not UTF-8 text or not a regular file (`check-claims /etc`); a per-role or `[profile]` resume pointer to a file that is not there; no terms in the posting (`check`) or in the resume (both: `check` writes no `coverage.json` for a resume that states no lexicon term or acronym) |
| `jobs tailor` | the role has no coverage report (without `coverage.json`), or the report is stale (the posting, resume, facts, config or a lexicon changed since): run `jobs check` first |
| `jobs show`, `check`, `tailor`, `score`, `status`, `rank`, `upskill` | a damaged role `meta.json`: invalid JSON, JSON that is not an object (`null`, a list), a missing `company`, `role` or `status`, or a field of the wrong type or value (`fit_score` not a number, `status` not one of the statuses); the file and the field are named |
| `jobs upskill` | no role has a coverage report: it prints `0 bucket(s) from 0 role(s)` with the cause and writes no `upskill.json` |
| `learn gaps` | `upskill.json` absent (prints `0 role(s) analysed`), damaged or not schema-2, or it analysed 0 roles (with roles analysed it prints `N demand bucket(s) from M role(s)` and exits 0) |
| `learn plan --from-gap` | no `upskill.json` yet |
| `learn validate` | no topic in the home (`validate SLUG` prints its own counts); a damaged log row |
| `learn due` | no topic in the home (`due SLUG` prints `SLUG: N due`); a damaged log row |
| `learn calibration` | no confidence-rated, unaided attempts yet |
| `learn quiz` | the topic has no concepts yet (`learn sync` reads them from `syllabus.md`) |
| `learn exam-date` | an exam date is set but the topic has no exam-scope concepts |
| `learn quiz`, `learn calibration`, `learn misconceptions`, `learn sync`, `learn plan` (existing topic), `learn exam-date` | a damaged log row: they print what they can and say how many rows were skipped |
| `learn graduate`, `learn rebuild` | a damaged log row (they refuse; `rebuild --skip-damaged` is the explicit override) |
| `jobs discover` | no `[sources]` targets with `--all`; a board is unreachable or returned no postings at all; a damaged role file or a role directory without `meta.json` (named; the rest is still done); a posting that could not be taken in (named) |
| `jobs reconcile` | no `[sources]` targets; a board is unreachable or returned no postings at all; a damaged role file or a role directory without `meta.json` (named, not checked; the rest is still checked) |
| `jobs rank`, `jobs board` | a damaged role file or a role directory without `meta.json` (on an empty home `jobs board` prints `0 role(s)` and `jobs rank` prints `(0)` for each section; both exit 0: they are listings) |
| `jobs intake --jd FILE` (or `-`), `learn quiz --interactive` | the posting or the typed input is not UTF-8 (named with the byte and offset); the posting is empty ("empty posting", nothing taken in) |

A file that is not UTF-8 (a posting, syllabus, question bank, resume) is named with its path and
the offending byte. A log row that is not UTF-8 is a damaged row, counted and named by line.
`--resume P` (`jobs check`) and the positional `RESUME` of `jobs check-claims` are tried relative to the current
directory first, then relative to HOME; a directory or device is refused alike ("not a regular file", exit 2); `jobs check` stores the resume as an absolute path (or relative to
HOME when it is inside it), so its coverage stays fresh whatever directory you run from. Dates are written exactly `YYYY-MM-DD`; `--n`, `--limit`
and `--top` take a whole number of 1 or more; `jobs board --status` takes one of the role statuses; `--min-fit` a number from 0 to 5; `intake` a non-empty
`--company` and `--role`; `discover` and `reconcile` a known `--board`, and `reconcile --board` needs
`--company`; a `learn plan` slug is 1 to 64 characters of `a-z`, `0-9` and `-` (exit 64 otherwise).
`jobs discover --exclude-senior` prints how many postings it left out, and a posting with no title is
named and skipped.

`learn record` appends the row you gave it and warns about log problems; it exits 0. A keyword that
matches nothing on a board that did list postings is a result (exit 0), printed with its denominator.

## Your data

Everything lives in one directory you own:
- `--home DIR`, else `$CAREERLOOP_HOME`, else `$XDG_DATA_HOME/careerloop`, else `~/.local/share/careerloop`.

Nothing is written inside the package.

```
config.toml      settings: keyword packs, equivalences, demand buckets, fit bar, job-board targets
facts.md         what you hold: only skills under `## Held` count. `init` writes the template once; no command after that modifies it.
resumes/         resume.md (or .txt, .tex)
roles/<slug>/    meta.json, jd.txt, scorecard.md, coverage.json, review.md
topics/<slug>/   topic.json, syllabus.md, questions.md, log.jsonl, concepts.json
lexicons/        your own keyword packs (the package ships web, security, data)
upskill.json     weighted demand (derived)
upskill.md       the same plan as readable text, written by `jobs upskill` (derived)
```

Job boards: the public posting APIs of Greenhouse, Lever and Ashby, plus
`fixture` (a local JSON file). Requests are sequential and rate-limited per
host, and a fetch error is reported as an error, never as an empty board.


## What it does not do

- It does not write your resume or cover letter, and after `init` has written the `facts.md` template no command modifies it.
- It does not scrape sites without a public posting API.
- It has no LLM inside. The question bank is yours, or your assistant's under
  the tutor rules.
- It does not make PDFs. Keep your resume in the tool you like; `check`
  reads Markdown and text, and LaTeX best-effort (with a warning; see the limits in
  [trust rules](trust-rules.md#known-limits)).

