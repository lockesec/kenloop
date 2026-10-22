# kenloop

Build a career while growing your interests. Use AI as a question to learn from, not an
answer to copy.

kenloop keeps an honest record of what you know. You study topics you choose, with spaced
review. You reason through ideas with an AI tutor that asks rather than tells. You see where
your reasoning held and where it broke. Your questions become ladders of concepts to climb.
Your *ken* is the range of what you know; the tool's job is to show you its edges.

Two sidecars hang off that core. The **job search** finds roles, shows which skills they ask
for that you lack, and lets a skill onto your resume only after you have proved it. **Cert**
prepares you for an exam. Each loop starts in study and comes back to it.

Works beside any AI assistant; no LLM inside. Everything lives in plain files in your own
directory.

## The loop

```
          ┌── question ─> try it yourself ─> feedback: held / broke ─> review (spaced) ──┐
  study   │                                                                              │
          └── open questions ─> new ladders, new topics <────────────────────────────────┘
                 ▲ seeds (what the jobs you want ask for)        │ evidence (what you proved)
     jobs:  postings ─> coverage ─> demand ─> a topic ─> facts.md ─> applications ─> new gaps
     cert:  exam date ─> reviews land before it ─> practice exam ─> misses ─> the next drill
```

- **Study.** `plan` a topic, `quiz` and `record` your answers, `due` for spaced reviews.
- **Reason.** `talk` sets up a graded dialogue on one concept. `beliefs` shows what you
  believed before and after, where your reasoning held, where it broke, and what you left open.
- **Ask.** `ask "why ..."` starts a ladder: the concepts you need, easiest first, reusing what
  is already on your map.
- **Next.** `next` names the one thing most worth doing now, and why. A closing deadline
  comes first, then your reviews and open questions, then the job search.

## See it

The demo runs on invented data (Dana Example, Example Folio Books, a topic on HTTP). An
excerpt of what it prints (CI checks it against the real output):

```console
$ ken board
TOPIC                   OUTLETS       MASTERED      DUE   BADGES
http-fundamentals       career        1/10 (10%)    7     mastered 1 good 1 fair 4 weak 3 new 1
$ ken record http-fundamentals semantics:cookies partial --mode dialogue --rubric chain=2,predict=1,limits=1 --grader demo-tutor --before "a cookie is sent to every site" --confidence high --after "a cookie goes back only to the site that set it" --after-confidence med --held "the server sets it with a response header" --broke "so every later request carries it" --next "the Domain and SameSite attributes" --open "how does SameSite stop a cross-site request?"
semantics:cookies: dialogue partial, graded by demo-tutor; reasoning chain 2.0/2  limits 1.0/2  predict 1.0/2; push on: limits (reasoning is kept apart from quiz credit)
$ ken beliefs http-fundamentals
    before (high): a cookie is sent to every site
    after  (med): a cookie goes back only to the site that set it
    right up to: the server sets it with a response header
    broke at   : so every later request carries it
    learn next : the Domain and SameSite attributes
$ ken next
NEXT: ken due http-fundamentals  — 4 review(s) due in http-fundamentals (~8 min)
$ ken plan web-security --from-gap "Web security"
web-security: created topics/web-security; from 'Web security': 5 concept(s) added, 0 skipped (held or present)
$ ken jobs check-claims resumes/draft-example-folio.md
VIOLATION not held     oauth: not under ## Held: - OAuth — planned
$ ken next
NEXT: ken jobs tailor example-folio-integration-engineer  — example-folio-integration-engineer: deadline in 2 day(s), fit 4.2
```

To run it yourself (the demo is not in the pip package):

    git clone https://github.com/sethpsonnier/kenloop && cd kenloop
    pip install . && sh examples/demo.sh

## Quick start

    pip install git+https://github.com/sethpsonnier/kenloop
    ken init
    ken plan black-holes --goal "why light cannot escape"     # then list concepts in its syllabus.md
    ken sync black-holes
    ken talk black-holes                                       # give your assistant the output
    ken next

The command is `ken` (`kenloop` also works). Give your assistant
[docs/dialogue-rules.md](docs/dialogue-rules.md) for a dialogue and
[docs/tutor-rules.md](docs/tutor-rules.md) for a quiz; `quiz --interactive` works with no
assistant at all. Either way the record is the same.

**The job search** (optional): list your skills under `## Held` in `facts.md`, put a resume
at `resumes/resume.md`, name the companies to follow in `config.toml`, then:

    ken jobs discover --all --intake
    ken jobs check SLUG              # what the posting asks for that you hold, and what you lack
    ken plan SLUG --from-gap BUCKET  # turn what the market keeps asking for into a topic

## Why you can trust it

- **Reasoning is not credit.** A dialogue is graded by an AI, so its grade shows how you
  reason but never counts toward mastery. Only answers you give unaided, on separate days, in
  more than one question form, can make a skill a candidate for your skills sheet, and you
  paste it there yourself. Every dialogue grade names its grader, and the transcript is kept
  with a fingerprint that `validate` checks.
- **It marks what nobody knows.** A concept can be marked `settled`, `frontier` (active
  research) or `open` (no one knows yet), and `talk` shows the mark. Under the dialogue rules,
  calling an open problem solved scores 0 on `limits`.
- **You decide what you hold.** A skill counts as held only when you list it under `## Held`
  in `facts.md`; no command writes that file after `init`. A topic reaches it only if you give
  the topic a career outlet. `jobs check-claims` catches a resume that claims a skill you do
  not hold, including one disguised with look-alike letters or invisible characters.
- **It says when it could not look.** A board that is down, a missing resume, a damaged log:
  it exits 2 and says why, never a clean 0
  ([which commands](docs/commands.md#when-a-command-cannot-look-exit-2)).
- **The log is the record.** Every answer and dialogue is appended to a log; `rebuild --check`
  exits 3 if anything derived from it has drifted.
- **Tested.** About 1,500 tests, CI on Python 3.9 to 3.14, hash-pinned dependencies. The demo
  is CI's acceptance test, and CI checks the console block above against its output.
- **Local.** No accounts; the only network use is the public job-board fetch. Standard
  library only, Python 3.9+ (`tomli` on 3.9 and 3.10).

The full rules: [docs/trust-rules.md](docs/trust-rules.md).

## Exit codes

| code | meaning |
|---|---|
| 0 | clean / done |
| 1 | findings (e.g. a resume claim you do not hold) |
| 2 | NOT EVALUABLE: it could not look (named in the output), or an internal error |
| 3 | drift: derived state disagrees with the log |
| 64 | usage error |

## Known limits

- No LLM inside: the questions, the dialogue and its grade come from you or your assistant,
  under the written rules. The tool keeps the record and checks it; it does not judge
  understanding itself.
- It writes no resume or cover letter and makes no PDFs. The claim check reads Markdown and
  plain text; a LaTeX resume is read best-effort with a warning. Boards: Greenhouse, Lever,
  Ashby; no scraping.
- Skill matching on postings is lexicon-based (packs: web, security, data). Held means "you
  listed it under `## Held`": the tool cannot tell whether what you listed is true.

## Prior art and credits

Developed in a private AI-experimentation environment and extracted as a standalone tool,
first as careerloop. The maintainer designed and directed it; much of the code was written
with AI coding agents, and adversarial reviews were run by separate AI sessions.

claude-tutor and DeepTutor cover quiz and review; career-ops and ai-job-search track a job
pipeline and check keyword coverage. kenloop is not ahead of them on either half alone.
Original here: the graded dialogue kept apart from credit, belief records with the point
where reasoning broke, question ladders, what-humanity-knows marks, `next`, the seam from job
demand to study topics, the structural `## Held` rule, four-gate graduation and replay drift
checking.

- **Code:** the scheduler re-implements the FSRS-6 formulas and default parameters of
  [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) 6.3.2 (MIT);
  `benchmarks/fsrs_parity.py` compares the two, and DESIGN.md gives the measured differences.
  See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).
- **Ideas adapted, no code taken:**
  [claude-tutor](https://github.com/kirilxd/claude-tutor) (MIT, plan, quiz, review);
  [agent-tutor-skill](https://github.com/Bhala-Srinivash/agent-tutor-skill) (MIT, zero-hint quizzing, misconception notes);
  [DeepTutor](https://github.com/HKUDS/DeepTutor) (Apache-2.0, question bank, typed errors);
  [tutor-skills](https://github.com/bevibing/tutor-skills) and [learn-faster-kit](https://github.com/hluaguo/learn-faster-kit) (MIT, same patterns);
  [career-ops](https://github.com/career-ops-hq/career-ops) (MIT, status enum, weighted fit scorecard);
  [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) (MIT, ATS keyword coverage).
- **Research:** grading curiosity by what you do, and the `question` move, follow
  "Why Did Apple Fall: Evaluating Curiosity in Large Language Models" (Wang et al., 2025,
  arXiv:2510.20635); the rest is in [docs/references.md](docs/references.md).

Attribution corrections are welcome.

## Docs

- [docs/commands.md](docs/commands.md): every command, how `next` decides, your data directory
- [docs/dialogue-rules.md](docs/dialogue-rules.md): a contract for an AI assistant that runs a dialogue
- [docs/tutor-rules.md](docs/tutor-rules.md): a contract for an AI assistant that quizzes you
- [docs/trust-rules.md](docs/trust-rules.md): study credit, graduation, the `## Held` rule, coverage, demand
- [docs/references.md](docs/references.md): the research behind the design choices
- [DESIGN.md](DESIGN.md): how it was built, the decisions, and what each review found

## License

Apache-2.0 - see [LICENSE](https://github.com/sethpsonnier/kenloop/blob/main/LICENSE)
and [NOTICE](NOTICE).
