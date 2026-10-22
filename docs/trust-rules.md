# The rules that make it trustworthy

[README](../README.md) has the short version.

**Your facts sheet is the only source of truth. `init` writes the template once; no command after that modifies it, only you.**
`facts.md` is plain Markdown. A term counts as *held* only when a block (a
bullet, a numbered item, a heading or a paragraph) under the `## Held` heading
mentions it as a whole word and carries none of the qualifier words below.
Nothing outside `## Held` is ever held: `## Learning`, `## Planned`, free notes
and text before the heading all read as not held, whatever they say. No wording
decides heldness. HTML comments, fenced code and ~~struck~~ text state nothing.
A strike-through covers one line only, so a stray `~~` can never swallow a heading.
Held means *mentioned on a Held line that carries no qualifier word*:
`- Redis, alongside Docker` holds both. A negated line holds neither:
`- Redis (not Docker)` is reported as a contradiction (fail closed), because
"not" is a qualifier, so write one skill per line. Link text on a Held line counts
as a mention (`- [Docker](https://example.invalid/x)` mentions Docker); a web
address never does, here or in a resume or posting (`https://github.com/me/docker`
states and holds nothing, so a resume's links never fail the gate). An unchecked task box (`- [ ] Docker` or `1. [ ] Docker`) is a to-do, not a skill you
hold: it is not held and is reported like a qualifier. `- [x] Docker` is held.
A nested item governs the item above it: `- Docker` with `  - (learning)` indented under it is
not held, because the child carries a qualifier (only the item directly above is affected,
so `- Python` over `  - Django (learning)` also becomes a contradiction; reword it, or put one
skill and its status on one line).

```
# Facts
## Held
- Python: 6 years in production
- SQL daily for reporting
## Learning
- Docker (just starting)
- Kubernetes: want to learn
```

A resume that states Docker is a violation here: Docker is not under `## Held`.

The heading rule, so it is predictable: `Held` at level 2 (`## Held`, or `Held`
over a `---` line), case-insensitive, optional closing `#`s, spaces or tabs
after the hashes. Level 1 or 3, `Held:`, `Held skills`, `Not held` and
`Skills I hold` are different headings: when the sheet has no `## Held`, the
message names the line of any heading that mentions held or hold (after
invisible, full-width and similar characters are folded away, so `## Hel<zero-width space>d`,
a full-width `\uff03\uff03 Held`, a mid-file byte-order mark and `##` followed by a
no-break space are named, not silently skipped). None of those is a heading as
Markdown renders it, so none of them is `## Held`. A leading byte-order mark is
ignored. A `## Held` inside fenced code (any indentation, or never closed),
inside an HTML comment (an unclosed `<!--` hides the rest of the file), or
indented four spaces is not a heading. A `<!--` inside an inline code span
(backticks) is text, not a comment. A setext title (`Held` over `---`) cannot be
an indented-code line or a blockquote line, and seven or more `#` is not a
heading. An empty heading (`##` alone) is a heading and ends the Held section.
`doctor` reports an unclosed comment or fence, and a closed comment or fence that
hides a list item under `## Held`. The section runs
to the next level-2-or-higher heading; a `###` inside it stays held. A
non-empty facts sheet with no `## Held` section is NOT EVALUABLE (exit 2), and
the message says to add it; an empty or absent sheet holds nothing. `init`
creates the sheet with `## Learning` and `## Held` (Held last, so
`jobs graduate --emit >> facts.md` lands under it).

**A qualifier word under `## Held` is a contradiction.** The list below no
longer decides what is held. It only catches a line you filed under Held that
says otherwise ("Docker, planned"). Such a line is not held, and
`check-claims` and `doctor` report it as a violation (exit 1): a sheet that
argues with itself cannot gate a resume. Reword the line or move it. A
qualifier on a sub-heading inside Held governs the blocks beneath it; a
qualifier on a heading *above* Held (a title such as `# Facts (work in
progress)`) does not disqualify Held, only headings inside it count. A
qualifier anywhere in a block disqualifies every term in that block: put one
skill per line.

The message for a basic-level or other qualifier quotes just the matched word (`qualifier 'beginner' in the line`).
Words that were considered and left out because they read as ordinary prose on a skill
line: aspiring, limited (alone), junior.

The qualifier words, by family (matched case-insensitively; the example is a
phrase that makes a Held line a contradiction):

| Family | Example | Also matches |
|---|---|---|
| planned | Plan to learn Kubernetes | planned, planning to, will learn, to be learned, someday, eventually, todo, wip, aspirational, `[verify`, next year, down the road, on my list |
| in progress | Studying Go | in progress, pursuing, not yet (or not-yet), no active, getting started, just started, starting to, ramping up |
| learning | Learning Docker | learning (but not machine, deep, reinforcement, transfer, supervised, unsupervised, federated, meta, statistical, ensemble, contrastive, few-/zero-shot, representation, lifelong, continual, multi-task, incremental, curriculum or e-learning as whole words, however joined, or "learning management"; `Azure - learning`, `Vue-learning`, `online learning` and `active learning` are qualifiers), `(learning)`, I am learning |
| wish | I'd like to use TLS | want to, hope to, intend to, aim to, wish to, would like to, looking to, interested in, curious about |
| exploring | Exploring Redis | dabbled, experimenting, tinkering, reading about |
| not held | Not held | do not claim, do not list, never, not claimed |
| negation | Redis (not Docker) | not, no, never, without, except, instead of (whole words: "notifications", "node" and "know" do not match; "Python, not just scripting" does, so reword it). Compounds are names, not negations: "no-code", "not-for-profit", "No.1", "No. 1" and the publisher "No Starch" do not match |
| not used | Haven't used GraphQL in production | did not use, don't have, not hands-on, not proficient, not in production |
| no experience | No production experience | no (or no-) real, prior, hands-on, production, professional, commercial, practical, direct, work or industry experience or exposure; limited, little, minimal, zero, lack of, lacking or without, optionally followed by up to two words (a hyphenated word counts as one: "lacking hands-on experience"), then experience, exposure, knowledge, familiarity or proficiency (so "Zero knowledge proofs" reads as a contradiction: reword it) |
| basic level | JavaScript (basic) | basic, beginner, novice, elementary, rudimentary, entry level, intro, introductory or rusty, parenthesised or after a dash, colon, comma or semicolon, or as the last word of the line (`Docker beginner`; trailing means the end of the line, so `Docker beginner-friendly images` and `Docker for beginners` do not match); basic knowledge, understanding or familiarity (not "Basic auth") |
| familiar with | Familiar with OAuth from a course | familiarity, coursework, from a course, tutorial, class, bootcamp, video or book |

**What is stripped, and what the disguise rule checks.** Before anything is matched,
in the facts sheet, the resume and the posting alike:

1. Every Default_Ignorable_Code_Point character is removed (the ranges are written out
   from DerivedCoreProperties of Unicode 15.1, because Python has no property API):
   soft hyphen, combining grapheme joiner U+034F, zero-width and bidi controls, word
   joiner and invisible operators, the Hangul fillers U+115F, U+1160, U+3164 and U+FFA0,
   Mongolian and other variation selectors (U+FE00 to U+FE0F, U+E0100 to U+E01EF), tag
   characters, the byte-order mark. U+2800 (braille blank) is removed as well. Trademark
   marks (the trademark, registered, copyright, service-mark and sound-recording-copyright
   signs) are removed before NFKC, which would otherwise turn the trademark sign into the letters "TM"
   and glue them to the word. Then NFKC is applied (full-width and compatibility forms
   become plain). A skill written with any of the removed characters inside it
   (`Doc<U+034F>ker`) is therefore read as the plain skill, and held or not held like it.
2. **How a term is matched.** A term of several words is found however its words are joined: by
   a space, by an ASCII hyphen, U+2010 to U+2015, the minus sign U+2212, U+FE58, U+FE63 or U+FF0D,
   or by a slash with or without spaces round it. `rate limiting` is found in `rate-limiting`,
   `Rate‑Limiting` (U+2011), `Rate–Limiting`; `ci/cd` in `CI / CD`, `CI–CD` and `CI CD`; `nist 800-53`
   in `NIST 800 53`. A soft hyphen (U+00AD) is read both ways: removed (`Dock<U+00AD>er` is `Docker`)
   and as a space (`Load<U+00AD>Balancing` is `load balancing`). Nothing else joins words: `ratelimiting`,
   `rate_limiting` and `Open ID Connect` (the lexicon lists `openid connect` only) do not match.
   **Words are joined on one line only.** The joining white space is horizontal: a space, a tab, a
   no-break space or another Zs space (two spaces or a tab between the words are fine). A line break
   (LF, CR, VT, FF, NEL, U+2028, U+2029 and the C0 separators), a list item, a paragraph or a Held
   block never joins words: `- Cloud` / `- Security` does not hold `cloud security`, `Built rate`, a
   blank line and `limiting` does not state `rate limiting`, and `machine` / `- learning` is two
   things. In `facts.md` every Held block is matched on its own (the blocks are joined by a blank line
   for speed, which no match crosses), and the hard-wrapped lines of ONE item are separate lines too.
   The one exception is **end-of-line hyphenation, which is allowed**: a word that ends the line with a
   hyphen glued to it (ASCII `-`, U+2010, U+2011, or the small and full-width hyphen-minus U+FE63 and
   U+FF0D, which NFKC folds to `-`; an en or em dash or a slash at the end of a line is not
   hyphenation), then any line break (LF, CRLF, CR, VT, FF, NEL, the C0 separators, U+2028, U+2029),
   then the next word (`machine-` then `learning`), reads as `machine-learning`, so it states
   `machine learning`, because a hard-wrapped paragraph breaks words that way. Invisible characters
   between the word and the hyphen, and white space or invisible characters on either side of the
   break (an indent, a tab, a no-break space, a zero-width or bidi mark, a soft hyphen), do not
   matter; a space before the hyphen, a bullet marker or a blank line after it breaks the join. ONE
   function applies this rule to the raw text before anything else, and both the matcher and the
   disguise check (rule 3) call it, so the two read a wrap the same way (a `-` bullet directly after a hyphen-ended line is read
   as part of the wrap by the disguise check, which can only add a report): `rate-` then an indented
   `lim<Cyrillic i>ting` is reported as a disguise of `rate limiting`. In a Markdown or text resume a phrase hard-wrapped at a plain space
   (`rate` / `limiting` on two lines) is two words, not one phrase.
   Structure in other formats is a line break too: in a posting's HTML, block tags (`<li>`, `<p>`,
   `<br>`, `<div>`, headings, table cells and rows, `<center>`, `<form>`, `<fieldset>`, `<caption>`,
   `<body>` and the other elements a browser lays out as blocks) separate lines while inline tags
   (`<b>`, `<a>`, a custom element such as `<td-x>`) are a space, and a line break in the markup
   source (LF, CRLF or CR) is a space, except inside `<pre>` and
   `<textarea>`, which keep their lines. Comments, declarations and the bodies of `<script>`,
   `<style>` and `<template>` are dropped (an unclosed one hides the rest, as in a browser). A
   posting with no block tag is plain text: it keeps its lines, only common inline tags (`<b>`,
   `<a>`, `<span>`, ...) are removed from it, and any other `<word>` (`List<String>`) is text; a `<`
   that starts no tag (`<3 years`) is text. In a LaTeX resume (LF, CRLF or CR line endings) a single
   line break is a space and a blank line a paragraph break, as LaTeX reads them; `\item`, `\par`,
   `\section` and the other sectioning commands, `\begin`/`\end`, `\newline`, `\break`, the vertical
   skips, two backslashes, a table cell `&`, and the common template item macros (`\cvitem`,
   `\cvlistitem`, `\cventry`, `\resumeItem`, `\resumeSubItem`, `\resumeSubheading`, `\skillitem`,
   `\entry`, ...) separate lines, and each argument of such a command stands on a line of its own
   (`\section*{Python}Rate` reads `Python`, then `Rate`); inline formatting
   (`\textbf{rate} limiting`) does not separate. A soft-hyphen text is read in two readings (removed, and as a space) that are kept
   apart, so no term is matched across them. Cost: the disguise windows read as many consecutive words
   as the longest lexicon term has, so a term longer than 8 words is skipped with a named warning when
   the lexicon is loaded.
   The same rule decides held-or-not in `facts.md`. A qualifier word written with a look-alike letter
   or a combining mark (`(l<Cyrillic e>arning)`, `(p<U+0332>lanned)`) is read as the plain word.
3. **The disguise rule (`suspicious-characters`). One rule.** The text is split on whitespace.
   Each token is examined in these readings, and nothing else:
   (a) whole, and whole without the punctuation at its two ends;
   (b) split into parts at every character that is ASCII punctuation or a symbol, or a Unicode
   punctuation, symbol or separator character (`P*`, `S*`, `Z*`) that is not a look-alike letter,
   does not expand to a letter or digit under NFKC (the numero sign) and is not a superscript,
   subscript or fraction form. So `Docker-based`, `Skills:Docker`, `Docker&Redis`, `Docker+Redis`,
   `Docker_Redis`, `Docker.io`, `Docker(Redis)`, an em or en dash, an ellipsis, a full-width comma
   and the ideographic comma all give `Docker` as a part. A private-use character (a Word
   symbol bullet, U+F0B7) and NEL or another C1 control are separators too, so at a word's end they
   are not a disguise (inside a word they still are: the whole-word reading drops them);
   (c) with a curly or ASCII possessive `'s` removed (`Docker's`, `Docker’s`, `Docker′s`, `Docker´s`);
   (d) for a lexicon term of several words, every run of 2 up to that many consecutive words (the
   longest term's word count; a word that is only a dash or a slash is not counted), joined by a
   space and read whole, without the punctuation at its ends, and possessive-free. So
   `Rate Limit<Cyrillic i>ng` is reported as `rate limiting`; words further apart, or on another line,
   are not a window. A soft hyphen is also read as a space here (`Load<U+00AD>Balanc<Cyrillic i>ng`).
   Parts and the possessive-free form only ADD readings; the whole-word reading is never dropped.
   Each reading is rewritten: NFKC (full-width forms and ligatures become plain), invisible,
   format and control characters removed, accents and combining marks removed, curly apostrophes
   read as `'`, and the fixed table of look-alike letters (Cyrillic including a few lower-case
   ones such as к, г, т, м, н, в and the palochka, Greek including the lunate sigma, some Cherokee
   capitals, Armenian, dotless i, o with stroke, a few hooked or small-capital Latin letters, a few
   symbols drawn like a letter such as the element-of sign, the division slash) mapped to the Latin
   letter. A hyphen-like character (U+2010 to U+2015, U+2212, U+FE58, U+FE63, U+FF0D) is a joiner:
   it is read as a hyphen in the whole-word reading and compared like an ASCII one, never silently
   removed, so `Java‑Script`, `Web–Sockets`, `Open‑API` and `Post‑greSQL` (fragments of a one-word
   term) are clean, like `Java-Script`. In the whole-word reading (not in a part, which holds no
   punctuation) any other non-ASCII punctuation or symbol character inside the word, and a
   superscript, subscript, ordinal or fraction form (`Docker⁺`, `Docker¹`, `Docker²`, `Dockerª`, `Docker½`), is also dropped, as is the
   numero sign.
   A reading is **altered** only if that result differs from the NFKC form of the same reading.
   An altered reading that equals a lexicon term **exactly** (ignoring case, one plural `s`
   tolerated) is a `suspicious-characters` finding, whether or not you hold the term. An
   unaltered reading never is: `ﬁrewalls,`, `ＡＷＳ.`, `Python’s`, `(ﬁrewalls)`, `“Docker”` and
   `Docker…` are ordinary text, read as `firewalls`, `aws`, `python` and `docker` like any other
   word. A combining mark drawn over or around a letter (a stroke, solidus, tilde, ring or
   parentheses overlay such as U+0334 to U+0338, U+20D2, U+20D3, or an enclosing circle, square or
   sign such as U+20DD and U+0488) is a disguise, not an accent, even in a term of three letters
   (`S<U+0336>QL`). Examples that are reported: `Dock` with a Cyrillic e (alone, or in
   `Dock<Cyrillic e>r-based`, `Skills:Dock<Cyrillic e>r`, `Dock<Cyrillic e>r…Redis`),
   `Dock·er` (decided: the middle dot is dropped from the whole-word reading, so one word is
   `Docker`), `Dock` + the element-of sign + `r`, `CI` + division slash + `CD`, `Docker⁺`,
   `Docker№`, `Docker¹`, a bell character inside `Docker`, a word written wholly in Cyrillic
   look-alikes that spells `TCP`, `S<U+0336>QL`, `S<U+20DD>QL`.
   There is never a fuzzy or subsequence match, and two limits keep ordinary text clean:
   a one-letter term (such as `r`) is only ever matched as a whole token (`R&D`, `Ré` and
   `Ŕ` are not `r`), and a term of three letters or fewer is not reported on an accent
   alone. In `check-claims` a finding exits 1. `jobs check` applies the same rule to the
   resume (exit 1, the coverage report is still written) and to the posting, where it
   prints `WARNING suspicious-characters (posting)` and does not change the exit code: the
   posting is third-party text you cannot retype. `doctor` reports a disguised word in the
   resume of a checked role as a finding, so it does not say CLEAN while `check-claims`
   exits 1 (see "Which resumes `doctor` scans" in [commands](commands.md)). A message quotes
   the word cut at 80 characters.
   A LaTeX resume is read best-effort, with a warning on every read: comments and commands are
   removed (see Known limits). Two backslashes, list items,
   sectioning commands, `\par` and table cells are line breaks (see rule 1), an empty group `{}`
   prints nothing, a group glued to a word (`\textbf{Dock}er`, `Dock{}er`) reads as one word, and
   `\_` stays an underscore (`rate\_limiting` is not `rate limiting`).
4. A line under `## Held` that spells a skill with such characters (`- Dock<Cyrillic e>r`)
   does not hold it: `check-claims` reports the resume term as a `contradiction` naming
   that line and the code points, and `jobs check` gives the same cause.

What the rule does and does not catch. It catches a lexicon term (from your packs) written
as a whitespace-separated word, or a part of one between punctuation, with characters in it that
the rewrite above removes or maps. It does not catch: a word that is not rewritten into an exact term (a misspelling,
`Dockr`, or a letter missing); a look-alike character that is not in the table (the table is
a list, not a complete Unicode confusables set); a multiword term split over words further apart
than its own word count, or glued to
a neighbouring word or to Chinese, Japanese or Korean text (`熟悉Docker部署` is one word that
is not examined); a skill outside your packs, or a name (`--acronyms` adds capitalised
acronyms and names to the terms checked, not to this rule); a term that is a
word in another language once an accent is removed, only because it is one: ordinary words such as
`São Paulo`, `Łódź`, `Ödön`, `été`, `está`, `así`, `Zürich`, `café`, `Straße`, `Москва`
are clean because they do not spell a term. A word that does equal a term of four or more letters once its
accents are removed is reported even when innocent (`régression` is the term `regression`, `azuré` is
`azure`); retype it without the accent. The rule runs on lexicon
terms; it does not establish that anything else on the resume is true.

This is a list of phrasings, not language understanding, and it can miss yours.
That is why it is only a tripwire: the structure, not the wording, keeps an
unheld skill off a resume. The tool trusts what you file under Held; it checks
structure, not truth.

Known limits of the Markdown reading (a full parser would be needed): an indented
code block is read as text unless it is a setext title candidate, a code span that
continues over several lines is not recognised, and link reference definitions,
HTML blocks other than comments, and tables are read as plain text.

**Coverage separates three different things.** For each posting it lists what
your resume states, what you hold but do not state (a resume edit: say the
word), and what you do not hold (a gap: study it, or leave it off). An
equivalence ("the posting says OpenAPI, I did REST") counts only if the facts
sheet holds the term you are leaning on. The percentage counts
every posting term the resume states, held or not (the output lists the stated-but-unheld
ones separately; run `check-claims` to gate them), so a high percentage is not a claim
that you hold those terms. A posting with no recognisable terms is *not evaluable*,
never 0%, and so is a missing or empty `facts.md` (`jobs check` exits 2: with nothing
held every term would read as a gap).

**`check-claims` gates a resume before you send it.** Every term the resume
states must be held. A term that is not under `## Held` is a violation (kind `not held`; a Held line
with a qualifier word is a `contradiction`), and so is one the sheet never
mentions (`unsupported`). It checks the terms in your lexicon packs
(the config's `packs`, default `web`; also shipped: `security`, `data`; or your
own). A skill that is in none of your packs (Rust, a PhD or CISSP are in none of the shipped ones) is not
looked at; `--acronyms` adds capitalised acronyms and names. The output says
which scope it checked.

A resume term that appears in facts.md only inside a comment or fence is reported
as `hidden`, naming the line and the construct ("hidden by a comment at facts.md
line 4"); an unclosed one is also printed as a note, and `jobs check` gives the
same cause. Each contradiction names its line and the qualifier or sub-heading that caused it.
The summary counts resume-term violations and sheet contradictions separately; a
contradiction already shown against a resume term is not counted twice. Either one exits 1.

```console
$ ken jobs check-claims resumes/draft-example-folio.md
VIOLATION not held     oauth: not under ## Held: - OAuth — planned
checked 6 resume term(s): 1 violation(s); 0 sheet contradiction(s) elsewhere in facts.md
```

**Demand is weighted, not counted.** A skill's demand is the sum, over roles
that lack it, of *status weight × recency*. Closed and passed roles weigh
nothing, a rejection a quarter (half if you reached an interview), and weight
halves every 60 days. A skill an interviewer probed (`jobs status … --probed
tls`) adds a bonus. Terms your config does not bucket are grouped by category
(`Unmapped: web/ops`). They are never discarded as noise.

**Study credit is strict.** A correct answer earns streak, retention and
breadth credit only when it was unaided: no guess, no hint, not read off the
page, not a massed re-read. A correct you were unsure of still earns credit,
but you see it again sooner.

**Only the first look at a concept on a day can earn credit.** After a quiz
answer, a miss, a hint, a dialogue or a read-through, you have seen the
concept, so a later answer that day is a repeat. A correct repeat is counted
(attempts, correct, and `mastery` shows the repeats) but earns nothing: no
streak, retention day, breadth, confidence or review date. Five correct
answers in a row on one day are one correct answer and four repeats. A wrong
repeat still counts against you, as any miss does: being shown it and still
getting it wrong is evidence. Nothing is refused.

**A dialogue is evidence of reasoning, not of a held skill.** A dialogue
(`record --mode dialogue`) is graded by an assistant, so it never moves the
streak, the retention days, breadth or the review schedule, and it can never
graduate a skill. It does not reset a quiz streak either. Its scores per move
are kept beside the quiz results (`mastery`). The verdict is the rubric's
rule (ok: a mean of at least 1.5 with no move at 0; partial: a mean of at
least 0.75), so `record` refuses a result the scores do not give. Every grade
names its grader; a transcript under `dialogues/` is logged with its sha256,
and a copy is kept as graded under `dialogues/.graded/`; `validate` fails if
the transcript later goes missing or changes, and names the copy to compare or
restore from (a grade with no transcript is a warning). A miss with a note
is kept as a misconception, which a later unaided quiz pass resolves.

**A topic reaches your facts sheet only through a career outlet.** A topic
with no outlet is studied for its own sake and never graduates. `plan
--career` gives it the career outlet; `plan --from-gap` does too.

**facts.md is your resume source, and only that.** What you learn for its own
sake lives in the study record (`board`, `mastery`, `beliefs`), derived from
the log; it is never written as a claim. `doctor` compares `## Held` with that
record and warns (it never fails: a held skill may come from work) when a
Held line names a career topic's concept that is not mastered yet, or matches
a topic you study for its own sake.

**A concept graduates only when it has earned it**, which means passing four
gates:
- mastered (3 unaided in a row);
- correct on at least 2 separate days;
- at least 2 question types at 60% or better;
- answered unaided on a day when at least 3 other concepts were also studied
  (the log has dates, not sessions: the same calendar day is the unit).

`jobs graduate --emit` prints lines framed as "held knowledge from study;
a knowledge claim, separate from work claims" for you to paste under `## Held` in `facts.md`. The loop closes
through your hands, on purpose.

**The log is the record.** Every attempt is appended to `log.jsonl` before
anything else is written. Mastery and schedules are derived from it, and
`rebuild --check` exits 3 if the two ever disagree. The log is
append-only and merges cleanly between machines (`merge=union`).

**Absence is reported, never scored.** An unreachable board, a board that
returns no postings at all, a missing resume, a `doctor` run on a home with no
roles and no topics, and a topic that has an exam date but no exam-scope
concepts are all *not evaluable* (exit 2). None of them reads as a clean
result. An empty board never marks a posting as gone. A keyword that matches
nothing on a board that did list postings is a result (exit 0) and prints its
denominator: `0 of 12 posting(s) matched 'zebra'`. `due`, `quiz`, `calibration`,
`misconceptions`, `sync` and `cert exam-date` on a topic whose log has a damaged row
print as usual, say how many rows were skipped, then exit 2 (`jobs graduate`, `rebuild`
and `validate` also exit 2); `cert exam-date --set` saves the date but does not store a
schedule derived from a partial log. On an empty home `doctor`, `next`, `validate`, `due`,
`jobs upskill` (which then writes nothing) and `jobs gaps` exit 2 and print the denominator
(`0 topic(s)`, `0 role(s)`) with the cause (`jobs gaps` prints `0 role(s) analysed` only when
there is no `upskill.json`; a damaged one is named, not counted). A resume that is not UTF-8 text (a UTF-16 or
binary file, bytes that do not decode) is not evaluable; it is not read with replacement
characters; a posting (`jd.txt`), syllabus or question bank that is not UTF-8 is named the same
way, and a log row that is not UTF-8 is a damaged row (counted and named by line). The common
cases are in [commands](commands.md#when-a-command-cannot-look-exit-2).

## Known limits

Each line is a shape the tool does not read the way a reader of the rendered page would; the gate
is built for Markdown and plain text, and these are the places it is not exact.

- LaTeX: a macro whose argument is a value (`{\color{blue}Docker}`, `\hspace{1em}Docker`) can glue
  that value to the next word and hide a term; arguments of adjacent inline macros
  (`\cvtag{rate}\cvtag{limiting}`) and of a command with more than four or nested arguments are read
  as consecutive words; text LaTeX would not print (`\iffalse`, `comment` environments, `\phantom`,
  white text) is read as stated. Check a plain-text export (`pandoc -t plain`, `detex`) to rely on
  the gate.
- Markdown and text: a phrase hard-wrapped at a plain space (`rate` / `limiting` on two lines) is
  two words.
- HTML postings: an attribute value holding `<` or `>` (`title="a>b"`) can leave attribute text in
  the posting; `<!-->` and `--!>` are read as an unclosed comment that hides the rest; a posting
  with no block tag keeps `<script>` text. Postings only give warnings and demand counts, never the
  gate's exit code.
- The visible-text check that refuses an empty posting counts U+2800 (braille blank) and U+3164
  (Hangul filler) as visible.
- Only lexicon terms are checked (`--acronyms` adds acronyms and names); anything else on a resume
  is not judged.
- A one-word term hyphenated across a line end (`Kuber-` / `netes`, as a PDF text export may wrap
  it) is read as `Kuber-netes`, not `kubernetes`; only a hyphen between the words of a multiword
  term (`machine-` / `learning`) rejoins.
- A synonym, abbreviation or singular of a lexicon term (`Postgres`, `K8s`, `JS`, `HTTP2`,
  `webhook`) is not that term and is not checked; add it to your own pack.
- In a resume, text inside an HTML comment, a code fence or span, a `<details>` block, an indented
  code block or `~~strike~~` is read as stated (it fails closed), unlike `facts.md`, where those
  constructs state nothing.
- An email address or a bare domain (`dana@docker.example`, `docker.example`) states its words; only a web
  address with a scheme or `www.` is skipped.
- A visible letter-like character that is not in the look-alike table (Arabic tatweel U+0640,
  modifier letters such as U+02BC) inside a term is neither matched nor reported.
- A course or tutorial named without `from a` / `via a` (`Docker (Udemy course)`, `Docker
  tutorial`, `Docker, bootcamp`) is not a qualifier; `from a course`, `via a book`, `coursework`
  and `familiarity` are.
- A `lexicons/<pack>.toml` in your home replaces the shipped pack of the same name.
