<h1 align="center">kenloop</h1>

<p align="center"><b>Do you ken?</b> <br> An honest record of what you know</p>

To *ken* something is to know it: to reach the answer yourself, not just recognize it.

kenloop is a command-line study tool that grows with you. You learn with your AI assistant, and
kenloop keeps an honest record of what you can answer without it.

Designed for:

- **The assistant teaches:** helps build your syllabus, explains concepts, asks questions, and
  follows your reasoning.
- **Persistent memory carries context:** your goals, useful explanations, and unfinished questions,
  through your assistant's memory or a tool such as claude-mem.
- **kenloop keeps the learning record:** what you recalled unaided, where your reasoning broke, and
  what needs review. Remembered context never substitutes for study evidence.

Everything kenloop keeps stays in plain files, so any assistant can pick up where the last one stopped.

An AI can help you study; only what you answer without it counts.

Optional job-search and exam tools connect your study to a practical goal.

How it is built: a plain-Python CLI with no AI calls and plain files for every record; over
2,200 tests, property tests among them; a scheduler checked against the reference py-fsrs
implementation ([DESIGN.md](DESIGN.md)); and one rule throughout: when kenloop cannot read
what it needs, it says NOT EVALUABLE (exit 2) instead of reporting a clean result.

## See it in action

The offline demo uses invented data. This excerpt shows a changed belief, a review
recommendation, and a resume claim that fails the check. CI checks each line against the
demo's actual output.

```console
$ ken beliefs http-fundamentals
    before (high): a cookie is sent to every site
    after  (med): a cookie goes back only to the site that set it
    right up to: the server sets it with a response header
    broke at   : so every later request carries it
    learn next : the Domain and SameSite attributes
$ ken next
NEXT: ken due http-fundamentals  — 3 review(s) due in http-fundamentals (~6 min)
$ ken jobs check-claims resumes/draft-example-folio.md
VIOLATION not held     oauth: not under ## Held: - OAuth — planned
```

After installing, clone the repository to run the full demo (not included in the package):

```sh
git clone https://github.com/lockesec/kenloop
cd kenloop
sh examples/demo.sh
```

## How it works

Choose a question or topic → learn the concepts → try them yourself → review what needs work.

Start with something you want to understand; you and your assistant build from there. A gap
can become a prerequisite, a piece of a concept, or a new topic. Over time, your map grows
with your questions and understanding. You do not need to plan the whole course up front.
Go as fast as you like: an early unaided answer can earn credit, subject to the daily rules below.

| What you need | What kenloop does | Commands |
|---|---|---|
| Remember what you learn | Quizzes, spaced reviews, and confidence compared with results | `quiz`, `record`, `due`, `calibration` |
| Understand your mistakes | Records beliefs before and after a dialogue, where reasoning held, and where it broke | `talk`, `beliefs` |
| Find a starting point | Breaks a question into prerequisites and records your starting rung in a topic | `ask`, `rung`, `place` |
| Learn before you're tested | You guess first; the assistant teaches. Teaching earns nothing but books a cold recall for your next session, and that recall is the credit | `record --mode predict`, `taught`, `due` |
| Follow a gap deeper | Connects concepts to their parts and to the same idea in other topics, and turns gaps into further study | `map`, `branch` |
| Say what feels shaky | Puts what you mark as a problem first and keeps the way back to what started it; marks earn no credit | `mark`, `trail` |
| Decide what to do now | Suggests one next action and explains why; you can pin it to a topic | `next`, `focus` |
| Keep the teaching honest | A miss caused by a gap in the explanation counts against the tutor, never you | `gap`, `gaps` |
| Take it with you | A reference sheet and session printouts, as pages or PDF | `print` |

Topics can mark concepts as **settled**, **frontier** (active research), or **open**. Your
own knowledge gaps and the field's unanswered questions stay distinct.

## Quick start

For the intended workflow, use an assistant that can read your kenloop files and run `ken`,
with persistent memory configured in that assistant. kenloop makes no AI calls and does not
install or configure a memory service. It also works on its own with a question bank.

Requires Python 3.11+. Install in a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install git+https://github.com/lockesec/kenloop
ken init
ken plan black-holes --goal "why light cannot escape"
```

`ken init` prints your data directory (normally `~/.local/share/kenloop`). In that directory,
edit `topics/black-holes/syllabus.md` and add a line under `## Concepts`:

```markdown
- gravity :: event horizon :: why light cannot escape from inside it
```

Then load the concept and start a dialogue:

```sh
ken sync black-holes
ken talk black-holes
ken next
```

Give your assistant the `talk` output and [dialogue rules](docs/dialogue-rules.md).
For quizzes, use the [tutor rules](docs/tutor-rules.md); once you have a question bank,
`ken quiz black-holes --interactive` runs without an assistant. `ken brief black-holes`
prints the instructions and format for building that bank.

With Claude Code, copy the [skills/](skills/) folder's `ken-*` skills into `~/.claude/skills/`.
The skills, the rule documents and the demo live in the repository, not in the installed
package, so clone it for them: `git clone https://github.com/lockesec/kenloop`.
`ken-tutor` is the router: it starts each session with `ken session` (which shows your learner profile,
`ken profile`, first), picks the mode from what you
ask and how the topic is set (place, teach, dialogue, drill, exam, scout), says which, and hands
over to that mode's skill. Your assistant can help create the syllabus and question bank as you go.

The command is `ken`; `kenloop` also works. All study data lives in plain files in your
data directory. Set `KENLOOP_HOME` to choose another location.

## Job search and exams

Two optional sidecars connect study to a goal: `jobs` for the job search and `cert` for exams.

**Job search.** List your skills under `## Held` in `facts.md`, put your resume at
`resumes/resume.md`, and configure company boards in `config.toml`, all in your data directory.

```sh
ken jobs digest                              # new postings, filtered by your preferences
ken jobs check ROLE                          # compare a posting with your skills and resume
ken jobs upskill                             # calculate demand for missing skills
ken plan web-security --from-gap "Web security"
ken jobs check-claims resumes/resume.md       # check claims against facts.md
```

`jobs digest` is made for a daily run and leads with what is new since yesterday. Boards,
keyword packs and what the claim check can and cannot see: [the job search](docs/commands.md#the-job-search).

**Exams.** `ken cert exam-date TOPIC --set YYYY-MM-DD` schedules reviews before an exam.
`ken cert exam TOPIC` runs a practice exam from your question bank; misses guide further study.
After you pass, `ken settings TOPIC --keep-studying on` keeps the material on the schedule.

## What the record means

- **Mastery comes from unaided recall.** Hints, lookups, guesses, and correct same-day
  repeats earn no credit. You can review early; progress does not require waiting until due.
- **Dialogue records reasoning separately.** Each grade names its grader. When a transcript
  is attached, `ken validate` checks it against its stored fingerprint. The tool does not
  independently judge understanding.
- **You control your skills sheet.** Study can suggest skills after retention and question
  variety checks, but you decide what to paste under `## Held`. No command except `init`
  writes `facts.md`.
- **The log is the record.** Attempts are appended to a log. Every view checks what it shows
  against a replay of that log and exits 3 if they disagree; `record` will not add to a
  damaged log.
- **Missing evidence is explicit.** An unavailable board, missing resume, or damaged log is
  reported as not evaluable, not clean. See [which commands report this](docs/commands.md#when-a-command-cannot-look-exit-2).

No accounts are required. The tool's only network use is fetching public job boards.
It uses the Python standard library only.
CI covers Python 3.11–3.14 and checks the demo transcript.

Exit codes: **0** clean/done · **1** findings · **2** not evaluable or internal error ·
**3** derived-state drift · **64** usage error.

## What's different

Quizzing and review come from the tutors in [Credits](#credits). Placement and picking the next
item are what ALEKS and Math Academy do, and kenloop is not ahead of them there. What it adds:

- **Reasoning is graded but kept out of credit**, with the grader named and the transcript
  fingerprinted.
- **Belief records:** what you thought before and after a dialogue, and where the reasoning broke.
- **The `## Held` rule:** a skill reaches your resume only after you list it yourself, and
  `jobs check-claims` catches one that has not.

## Where it falls short

- **Whether it makes you learn better has not been measured.** It has had one serious learner, its author.
- **The record is only as honest as what goes in.** It can't see whether you looked something up, and it doesn't judge understanding.
- **The resume gate reads wording, not the truth.**

How it was checked and known holes: [docs/limits.md](docs/limits.md).

## Documentation

- [Commands and data layout](docs/commands.md): full reference, configuration, and how `next` decides
- [Limits](docs/limits.md): how it was checked, known holes, what is untested
- [Trust rules](docs/trust-rules.md): credit, graduation, claim checks, and every shape the gate does not read
- [Dialogue rules](docs/dialogue-rules.md) and [tutor rules](docs/tutor-rules.md): instructions for your assistant
- [Research references](docs/references.md): sources behind the learning design
- [Design and review history](DESIGN.md): implementation decisions and what was checked

## Credits

kenloop began as careerloop, a job tracker joined to a study planner. The maintainer
designed and directed it; much of the code was written with AI coding agents and reviewed
in separate AI sessions.

- **Code:** the scheduler re-implements the FSRS-6 formulas and default parameters of
  [py-fsrs](https://github.com/open-spaced-repetition/py-fsrs) 6.3.2 (MIT).
  `benchmarks/fsrs_parity.py` compares them; [DESIGN.md](DESIGN.md) records the differences.
  See [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).
- **Ideas adapted, no code taken:**
  [claude-tutor](https://github.com/kirilxd/claude-tutor) (MIT, plan, quiz, review);
  [agent-tutor-skill](https://github.com/Bhala-Srinivash/agent-tutor-skill) (MIT, zero-hint quizzing, misconception notes);
  [DeepTutor](https://github.com/HKUDS/DeepTutor) (Apache-2.0, question bank, typed errors);
  [tutor-skills](https://github.com/bevibing/tutor-skills) and [learn-faster-kit](https://github.com/hluaguo/learn-faster-kit) (MIT, same patterns);
  [career-ops](https://github.com/career-ops-hq/career-ops) (MIT, status enum, weighted fit scorecard);
  [ai-job-search](https://github.com/MadsLorentzen/ai-job-search) (MIT, ATS keyword coverage).
- **Research:** curiosity grading and the `question` move draw on Wang et al.,
  “Why Did Apple Fall: Evaluating Curiosity in Large Language Models” (2025).
  See [references](docs/references.md).

Attribution corrections are welcome.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
