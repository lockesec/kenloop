---
name: ken-climb
description: Run the study conversation for one idea at its pyramid height - long explanations the learner interrupts at the base, the learner explaining first in the middle, the learner teaching at the top - and record what happened. Use to "go over the material", "teach me", "start at the bottom", "really learn", "test me" or "grill me on X"; the default whenever the topic's intent is understand or unset.
modes: [teach, learn, predict, dialogue]
---

# ken-climb

One conversation, four heights (the learner's pyramid: cognitive apprenticeship). `ken session
<topic>` prints each idea in play with its height and the foundations under it, and one `mode:` line
with `how:`. Do what that line says; when the learner asks for something else, say so and switch.
Height is read from the record. Never raise it because something "made sense": feeling you learned
and having learned do not track each other.

**Every height: wide in explanation, never passive.** Explanations can be long, and the learner interrupts
whenever they like; but every chunk ends with one small act by them: say it back in a sentence,
predict the next step, or one "why does that follow?" / "what would break if...?". Gentle, not a
quiz. When they ask a question, answer it, then have them restate the answer.

| height | you |
|---|---|
| 0 new | ask their guess first ("what do you think happens when...?"); explain bottom-up from the foundations note you prepared (`ken-tutor`), around one concrete worked example, to the line's depth; if the idea rests on foundations they hold (the `rests on` list), have THEM pull those up first instead of restating them |
| 1 heard | open with cold recall of what was covered, no hints; feedback; then teach the gap in shorter chunks; hint ladder (question, hint, partial step, answer last); ask "how sure: low/med/high?" before each reveal |
| 2 held | they explain it first; you fill gaps and push on the weakest step; weave in one old idea they could confuse with it (not vocabulary) |
| 3 carried | roles flip: they teach it to you; you play a novice and ask follow-ups, then bring a new case. This is the graded dialogue: follow `ken-dialogue` (the grading contract) |

For an `intent: pass` line the shape is the same at 0-1 but at exam level; at 2-3 it is exam-format
questions (untimed, then cold) rather than teaching. Keep digressions on the question they asked; a
detour that matters becomes a branch, and `ken-branch` says how to move when an idea stalls.

## Build each chunk backward

1. **Name the skill.** The one thing this chunk is for, and the next chunk needs.
2. **Write the question that proves it.** It must take reasoning from the text, never copying: it
   differs from every worked example in at least one way, a small reach.
3. **Write only what makes it answerable.** Numbers before symbols; a letter appears only after they
   have done its job by hand. Cut what the question does not need; keep the wide view that says why
   the skill matters.
4. **Check before sending.** Is every move the question needs taught above it, and every calculation
   shown step by step on a worked example (not only its results)? If not, teach it or change it.

When they stick on a question the text did not prepare, the gap is yours: say so, teach the move,
record nothing against them, and log it on yourself (`ken gap`). Prepared but stuck: go lower.

## Record (every act, as it happens)

- Their guess before an explanation: `ken record <topic> <concept> ok|partial|miss --mode predict
  --before "what they guessed"` (never credited; `ken beliefs` shows it beside what happened).
- After teaching: `ken taught <topic> <concept> --note "what was covered"` (no credit; a same-day
  answer is a repeat; the first cold recall is due tomorrow and opens the next session).
- Then finish the foundations note for them to reread: add their say-back with what it missed, fix
  what the lesson showed was unclear, every section filled (incl. the attacker's view and sources).
  `ken foundations <topic>` lists the notes; `ken dive <topic> <concept>` goes over one.
- Their cold recall at the start of a session, or an answer with no help: `ken record <topic> <concept>
  ok|partial|miss --confidence med` (add `--hint-depth N` when a hint was used). This is the only
  thing that raises height. A cold explain-back on a later day is one: `--qtype recall`, never a dialogue.
- A say-back or check inside a teaching block is part of the teaching, not evidence: do not record
  it as a row (a partial on the same day would count against them before the idea is even taught);
  put what it showed in the `ken taught --note` and the foundations note.
- At height 3, the graded dialogue: `ken talk <topic> <concept> --protocol`, then record as
  `ken-dialogue` says.
- How they learn (an analogy that landed, one that misled): `ken note <topic> "..."`.

## Close (one minute)

Three things that matter, from memory; you correct; the one still fuzzy; how much they learned (1-5
or their words). `ken close <topic> --three ".." --fuzzy ".." --perceived 4 --chunks 6 --acts 5 --why 3
--what 1`; the fuzzy one opens the next session. Then the printouts: add the session to
`print/reference-sheet.md`, write `print/session-<date>.md` (`ken print <topic> --scaffold`), `ken print --pdf`.
