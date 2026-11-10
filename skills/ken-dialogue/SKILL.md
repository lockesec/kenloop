---
name: ken-dialogue
description: The grading contract for a graded dialogue - how to run and record one. A reference read by ken-climb at height 3 (and when the learner asks to be tested or to argue a concept out); not a mode of its own.
modes: []
---

# ken-dialogue

Why a graded dialogue at all: an answer you accept without understanding is borrowed, and once you
only borrow you cannot tell a good answer from a confident wrong one. So in a dialogue the learner
does the reasoning and curiosity is graded like any answer (arXiv 2510.20635: self-questioning
improved reasoning; self-reported curiosity was unreliable). It needs footing: on a field they
barely know, teach first (`ken-climb` at height 0-1).

Read the dialogue contract once (`docs/dialogue-rules.md` in a clone of kenloop, or https://github.com/lockesec/kenloop/blob/main/docs/dialogue-rules.md). `ken talk <topic> [concept] --protocol`
prints the concept, what humanity knows about it (settled, frontier, open), how their reasoning
went last time, the method and the transcript path.

- **Before the first question**, ask what they believe now and how sure they are (low, med, high),
  in their own words. Do not react to it yet.
- **One question per turn**, a why or a what-if, never "define X". Follow their answer, not a script.
- **Let them try first.** Teaching mid-dialogue is help: note the depth (1 reframe, 2 narrow,
  3 give the fact, 4 tell) and record it with `--hint-depth`.
- **Push back both ways.** Break a weak claim with a case; sometimes challenge a correct one. When
  they catch you wrong, say so plainly and record it with `--claude-wrong`.
- **Settle a disputed fact from the topic's sources** (`## Resources`), not from either side.
- **Be honest about what is known.** On an open question nobody has the answer: credit good
  reasoning about the candidates, never present your guess as fact.

Score only the moves you probed, 0-2 each, at least three: `chain`, `predict`, `pushback`,
`limits`, `connect`, `question`. The verdict is the tool's rule: ok is a mean of at least 1.5 with
no 0, partial at least 0.75. Keep the transcript where `ken talk` says, their words verbatim, with
a grade table citing the turn that earned each score. Ask the closing belief and confidence
*before* telling them how they did. Then:

```
ken record <topic> <concept> ok|partial|miss --mode dialogue --rubric chain=2,predict=1,limits=2 \
  --before "..." --confidence med --after "..." --after-confidence low \
  --held "..." --broke "..." --next "..." --open "CONCEPT :: a question left open" \
  [--hint-depth N] [--claude-wrong "..."] --grader <your model id>
```

A dialogue grade never counts toward mastery. `--grader` is required.
