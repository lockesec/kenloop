# careerloop

Track the jobs you want, see which skills they ask for that you lack, study those,
and never put a skill on your resume before you hold it. Works beside any AI
assistant; no LLM inside.

careerloop pulls openings from the companies you target, helps you score each
one, shows which skills a posting asks for that you do not hold yet, and turns
the gaps the market keeps asking for into a study plan. As you learn, each skill
you have proved goes back onto your skills list, and the next round of
applications starts from a stronger place.

Bring your own AI assistant for the conversation: drafting your resume and cover
letter, reading postings with you, quizzing you. careerloop is the part that
stays when you change assistants or models: the record, the scores, the checks,
and a straight answer to "what should I do next?". Everything it knows lives in
plain files in your own directory.

## The loop

1. **Find.** `jobs discover` pulls postings from the Greenhouse, Lever and Ashby
   boards of the companies you target.
2. **Score.** Each role gets a 1-5 scorecard: the work itself, skill match,
   level, pay, legitimacy and growth. Roles at or above your bar (4.0 by default)
   rise to the top; the rest are listed below the bar.
3. **See the gap.** `jobs check` shows, per posting, what you hold, what you hold
   but forgot to say, and what you would need to learn.
4. **Grow.** `jobs upskill` and `learn gaps` weigh what the roles you track keep
   asking for, recent ones counting more, and `learn plan --from-gap` turns the
   top gap into a study topic with spaced review.
5. **Earn it.** A skill counts as learned only after you answer it right on
   separate days, in more than one question form, and without hints. Then you
   add it to your skills sheet yourself.
6. **Apply honestly.** `jobs tailor` briefs your assistant on what to state and
   what not to claim, and `jobs check-claims` catches a draft that claims a skill
   you do not hold before anyone else does.
7. **Next.** `careerloop next` names the one thing most worth doing now, and why.

## Quick start

    pip install git+https://github.com/sethpsonnier/careerloop
    careerloop init        # then list your skills under ## Held in facts.md; put a resume at resumes/resume.md

Name the companies to follow in `config.toml` (in your data directory; the boards
are `greenhouse`, `lever` and `ashby`), then pull their postings:

    [sources]
    targets = [{board = "greenhouse", org = "acme"}]

    careerloop jobs discover --all --intake

To watch the whole loop once on invented data (Dana Example, Example Folio Books,
a topic on HTTP), clone and run the demo; it is not in the pip package:

    git clone https://github.com/sethpsonnier/careerloop && cd careerloop
    pip install . && sh examples/demo.sh

An excerpt of what it prints (CI checks it against the real output):

```console
$ careerloop jobs score example-folio-api-engineer --fit 3.5
example-folio-api-engineer: fit 3.5 (below the bar 4.0)
$ careerloop jobs check example-folio-api-engineer
example-folio-api-engineer: coverage 2/4 = 50.0%  (resume resumes/resume.md)
  required 2/3 · preferred 0/1 · responsibilities 0/0 · elsewhere in the posting 0/0
  experience: asks 3+ years (required)
  not looked at: 2 of 5 requirement line(s) mention no skill term it knows; listed so you can read them yourself
    - 3+ years of experience building partner integrations
    - Terraform for the partner sandbox
  covered by a held equivalent: openapi via rest
  not held (study it, or leave it off): oauth, rate limiting
$ careerloop jobs upskill
wrote upskill.json: 3 bucket(s), 2 quick win(s), from 6 role(s)
    8.00  Web security  (oauth, cors, csrf, rate limiting)
$ careerloop learn plan web-security --from-gap Web security
web-security: created topics/web-security; from 'Web security': 5 concept(s) added, 0 skipped (held or present)
$ careerloop jobs check-claims resumes/draft-example-folio.md
VIOLATION not held     oauth: not under ## Held: - OAuth — planned
checked 6 resume term(s): 1 violation(s); 0 sheet contradiction(s) elsewhere in facts.md
$ careerloop next
NEXT: careerloop jobs tailor example-folio-integration-engineer  — example-folio-integration-engineer: deadline in 2 day(s), fit 4.2
```

Studying works with your assistant (give it [docs/tutor-rules.md](docs/tutor-rules.md)
and the output of `learn quiz`; answers are recorded with `learn record`) or on
its own with `learn quiz --interactive`. Either way the record is the same.

## Why you can trust its answers

- **You decide what you hold.** A skill counts as held only when you list it
  under `## Held` in `facts.md`; `init` writes the template once and after that
  no command modifies the file, only you. A line under `## Held` that says
  "planned" or "learning" is reported as a violation, and a sheet with no
  `## Held` section is NOT EVALUABLE (exit 2).
- **It holds your resume to your own sheet.** `jobs check-claims`
  covers the terms in your lexicon packs (`--acronyms` adds acronyms and names).
  Invisible characters are removed before matching, and a term written with a
  look-alike letter, an accent, a symbol or a control character inside it is
  reported as `suspicious-characters` (an innocent accented word is the one
  known false alarm: [docs/trust-rules.md](docs/trust-rules.md)).
- **It says when it could not look.** When it cannot look (board down, resume
  missing, no `## Held` section) it exits 2 and says why, never a clean 0:
  [which commands](docs/commands.md#when-a-command-cannot-look-exit-2).
- **The log is the record.** Every study attempt is appended to a log, and
  `learn rebuild --check` exits 3 if anything derived from it has drifted.
- **Tested.** about 1,400 tests, CI on Python 3.9 to 3.14, hash-pinned dependencies. The demo
  is CI's acceptance test, and CI checks the console block above against its output.
- **Local.** No accounts; the only network use is the public job-board fetch.
  Standard library only, Python 3.9+ (`tomli` on 3.9 and 3.10).

The full rules (how terms are matched, what counts as a disguise, every gate):
[docs/trust-rules.md](docs/trust-rules.md).

## How it was made

Developed in a private AI-experimentation environment and extracted as a standalone tool. The maintainer designed and directed it; much of the code was written with AI coding agents, and the adversarial review rounds were run by separate AI sessions. Credits below; attribution corrections welcome.

## Exit codes

| code | meaning |
|---|---|
| 0 | clean / done |
| 1 | findings (e.g. a resume claim you do not hold) |
| 2 | NOT EVALUABLE: it could not look (named in the output), or an internal error |
| 3 | drift: derived state disagrees with the log |
| 64 | usage error |

## Known limits

- It writes no resume or cover letter and makes no PDFs. The claim gate is for
  Markdown and plain-text resumes; a LaTeX resume is read best-effort (commands
  removed) with a warning, so check a plain-text export when it matters. Boards: Greenhouse, Lever, Ashby, a local `fixture`; no scraping.
- Matching is lexicon-based (packs: web, security, data); other terms are
  bucketed, not understood. Held means "you listed it under `## Held`": the
  tool cannot tell whether what you listed is true, only that you said so.
- The question bank is yours, or your assistant's ([docs/tutor-rules.md](docs/tutor-rules.md)).

## Prior art

career-ops and ai-job-search track a pipeline and check keyword coverage;
claude-tutor and DeepTutor cover quiz and review. Those each cover one half.
careerloop joins them: what you study feeds back into what your resume may
claim. It is not ahead of them on either half alone.

## Docs

- [docs/commands.md](docs/commands.md) - every command, the `next` rule table, your data directory
- [docs/trust-rules.md](docs/trust-rules.md) - the `## Held` rule, coverage, demand, study credit, graduation
- [docs/tutor-rules.md](docs/tutor-rules.md) - a contract to give an AI assistant that quizzes you
- [docs/references.md](docs/references.md) - the research behind the design choices
- [DESIGN.md](DESIGN.md) - how it was built: the contract, the review rounds, what each found

## Credits

- **Code:** the scheduler re-implements the FSRS-6 formulas and default
  parameters of [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs)
  6.3.2 (MIT); `benchmarks/fsrs_parity.py` compares the two, and DESIGN.md gives
  the measured differences. See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).
- **Ideas adapted, no code taken:**
  [career-ops](https://github.com/career-ops-hq/career-ops) (MIT, status enum,
  weighted fit scorecard);
  [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) (MIT, ATS
  keyword coverage);
  [claude-tutor](https://github.com/kirilxd/claude-tutor) (MIT, plan, quiz,
  review);
  [agent-tutor-skill](https://github.com/Bhala-Srinivash/agent-tutor-skill) (MIT,
  zero-hint quizzing, misconception notes);
  [DeepTutor](https://github.com/HKUDS/DeepTutor) (Apache-2.0, question bank,
  typed errors);
  [tutor-skills](https://github.com/bevibing/tutor-skills) and
  [learn-faster-kit](https://github.com/hluaguo/learn-faster-kit) (MIT, same
  patterns).
- **Original here:** `next`, outcome-weighted demand and the gap-to-topic seam,
  the structural `## Held` rule, four-gate graduation, replay drift checking.

## License

Apache-2.0 - see [LICENSE](https://github.com/sethpsonnier/careerloop/blob/main/LICENSE)
and [NOTICE](NOTICE).
