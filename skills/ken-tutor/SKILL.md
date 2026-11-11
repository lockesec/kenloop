---
name: ken-tutor
description: Tutor a learner through a kenloop topic. The router - it reads `ken session`, picks the mode (place, teach, dialogue, drill, exam, scout) from what the learner asks and how the topic is set, says the mode in one line, and hands over to that mode's skill. Use to "learn", "go over the material", "talk through", "test me", "practice exam" or "start a new topic" with ken.
modes: []
---

# ken-tutor (router)

`ken` keeps the record and the rules; the skills run the conversation. This one only decides
WHICH conversation, so the tutor never runs one method when the learner asked for another.

## Start every session

Run `ken session <topic>` (`--brief` on a second look in the same sitting leaves the profile's text
out). It prints the topic's settings (intent, depth, chosen start), where the
learner is on the scale, the tutor's last notes on this topic and on the learner, open questions,
reached scouts, and what `next` says for this topic. Read all of it before the first turn.

**Open with what is due, but only a few.** A concept taught last time is due for its first cold
recall the next day (`ken taught` schedules it), so `ken due <topic>` is the opener whatever mode
follows: ask each one cold, as "explain X back to me", no hints and no material on screen. Record it
as a plain answer (`ken-climb`, Record), never as a graded dialogue: this cold explain-back is the
credit, and a dialogue never moves credit.

- **Cap the opener at 3-4 recalls**, weakest and most overdue first. Call it a warm-up, not drill
  (drill is the mode a learner asks for with "quiz me").
- **Fold the rest into the lesson:** ask a due recall just before the part of the lesson that builds
  on it, as its on-ramp (embeddings before text analysis). It is still a cold recall: ask it before
  any teaching on it, and record it the same way.
- **What is still due at the end waits** for the next session. A day late costs little; a long run
  of recalls before anything new drains the session the lesson needs.

Then the mode for the session.

**Prepare a new idea before the lesson.** When the `on-ramp:` line asks for a foundations note, write
it first (`ken foundations <topic> <concept> --scaffold`) from sources you read today, and teach from
it. What you could not read goes under "From memory, not checked", and you say so when it matters.

## Pick the mode, in this order

1. **Their words this turn win.**

| they say | mode | skill |
|---|---|---|
| "start a new topic", "where do I stand", "build the scale" | place | `ken-place` |
| "go over the material", "teach me", "start at the bottom", "really learn" | climb | `ken-climb` |
| "test me", "argue it out", "grill me on X" | climb at height 3 (graded dialogue) | `ken-climb`, grading by `ken-dialogue` |
| "quiz me", "drill", "what's due" | drill | `ken-drill` |
| "practice exam", "am I ready", "just pass it" | exam | `ken-exam` |
| "find the branches ahead", "scout this topic" | scout | `ken-scout` |
| "let's do black holes next", "pivot to X", "back to auto" | (any) | `ken focus X` / `ken focus auto`, then the mode for X |

2. **Then the session's `mode:` line.** `ken session` prints each idea in play with its pyramid
   height and one `mode:` line with `how:`, computed from the height and the line's intent. For
   `understand` or unset, use `ken-climb`: long explanations the learner interrupts, each chunk closed
   by one act of theirs. For `pass`, drill and exam toward exam level. A syllabus line's own intent wins for that idea.
3. **Then the tool's suggestion** (`next here:` in the session view).

**Say the mode in one line before the first turn**, copied from the session's `mode:` line or from
their words: "mode: teach, embeddings at height 0, depth mechanism, because you asked to go over the
material". When their words change the mode mid-session, say so and
switch. Branch decisions happen inside any mode: see `ken-branch`.

## In every mode

- Keep what is sourced apart from what you infer, and say which is which.
- Number the parts of a question that has more than one. Learners often answer two parts in one
  unbroken line: match each clause of a short reply to a part before calling one skipped, credit
  what is there, and ask only for the missing part. A setup question (intent, depth, where to start)
  gets its own turn, or propose an answer and set it.
- Record through `ken`, never by editing files: the record is the learner's.
- Write what you learn about HOW this learner learns with `ken note <topic> "..."` (or
  `ken note --learner "..."` for something true across topics): an analogy that landed or failed,
  a framing that worked, what to lead with next time. Notes are never evidence. When a learner note
  changes a rule, rewrite `profile.md` (`ken profile`), then `ken profile --folded`: session shows the
  profile first and only the notes written after it.
- Close: tell them where they stand and what `ken next` will suggest; commit the home if it is a
  git repo.

## Review your own teaching at every close

Most of a tutor's misses are only visible afterwards. After `ken close`, run `ken gaps <topic>
--review` and do what it prints:

1. Re-read the session for what YOU did wrong: a fact taught without reading it today, an answer you
   misread, a question the text never prepared, a question they did not need. Log each with
   `ken gap <topic> <concept> "..." --kind unverified|misread|step|process` (`-` for the concept when
   it is about the session). Correct anything you taught wrong, in the lesson and in the note.
2. Tell them in a line each what you found (or that you found nothing), then ask once: "Did you
   notice any sharp edges: anything I got wrong, or made harder than it needed to be?"
3. Keep their answer in their words: `ken gap <topic> <concept>|- "..." --by learner`. If they
   correct one of your findings, they are right about their own answers: fix the row's story with a
   new gap (`--kind misread`), never argue it. "No" is not recorded.

`ken session` shows the last gaps on a topic before the first turn: do not repeat them.
