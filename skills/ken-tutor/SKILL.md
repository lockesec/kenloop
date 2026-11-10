---
name: ken-tutor
description: Tutor a learner through a kenloop topic. The router - it reads `ken session`, picks the mode (place, teach, dialogue, drill, exam, scout) from what the learner asks and how the topic is set, says the mode in one line, and hands over to that mode's skill. Use to "learn", "go over the material", "talk through", "test me", "practice exam" or "start a new topic" with ken.
modes: []
---

# ken-tutor (router)

`ken` keeps the record and the rules; the skills run the conversation. This one only decides
WHICH conversation, so the tutor never runs one method when the learner asked for another.

## Start every session

Run `ken session <topic>`. It prints the topic's settings (intent, depth, chosen start), where the
learner is on the scale, the tutor's last notes on this topic and on the learner, open questions,
reached scouts, and what `next` says for this topic. Read all of it before the first turn.

**Open with what is due.** A concept taught last time is due for its first cold recall the next
day (`ken taught` schedules it), so `ken due <topic>` is the opener whatever mode follows: ask each
one cold, as "explain X back to me", no hints and no material on screen. Record it as a plain answer
(`ken-climb`, Record), never as a graded dialogue: this cold explain-back is the credit, and a
dialogue never moves credit. Then the mode for the session.

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
- Record through `ken`, never by editing files: the record is the learner's.
- Write what you learn about HOW this learner learns with `ken note <topic> "..."` (or
  `ken note --learner "..."` for something true across topics): an analogy that landed or failed,
  a framing that worked, what to lead with next time. Notes are never evidence. When a learner note
  changes a rule, rewrite `profile.md` (`ken profile`) and set its Updated day: session shows it first.
- Close: tell them where they stand and what `ken next` will suggest; commit the home if it is a
  git repo.
