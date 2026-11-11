---
name: ken-place
description: Build a topic's scale with the learner and find where they start - by placement questions, or by the learner's own choice. Use when a topic is new, has no `## Path`, or the learner asks where they stand.
modes: []
---

# ken-place

## Build the scale with them

List the topic's domains under `## Path` in `syllabus.md` as rungs, ground first, each leaning
only on the rungs below (`0. **ground** — what it covers`). Their own field is often rung 0.
Sibling domains that do not lean on each other still each take a rung; say they are siblings in
the Path text. A concept that belongs lower than its domain's rung takes `:: rung:<domain>` on its
syllabus line. Then ask how they want to study it and set it:
`ken settings <topic> --intent understand|pass --depth exam|mechanism|first-principles`
(one line may differ: `:: intent:pass` / `:: depth:exam`).

A rung with no concept on it cannot be asked about or taught: `ken place` and `ken session` name
the empty rungs. A new topic needs a first concept line on each rung the learner may be placed on;
the rest of the map still grows from use (`ken-branch`).

## Then where they start

Before asking, propose: say where you would start and the evidence for it, and let them agree or
correct you. In the same message, offer the other way in plain words: "or start at the bottom, with
no questions". Ask no placement question until they have picked; one asked early is wasted when
they choose the bottom. Keep the verdict with `ken note --learner "..."`; it tells later sessions how well the
tutor reads this learner.

- **They choose** ("start at the bottom", "from the ground up"): record it and stop placing.
  `ken place <topic> --start 0`. No probes: someone who chose the bottom wants to learn, not to be
  tested rung by rung. Hand over to `ken-climb`.
- **They want to find out:** `ken place <topic>`. Ask which rung they think they stand on; ask
  there first. One open question per rung, a why or a what-if, never multiple choice. "I don't
  know" is an answer. Record each answer verbatim:
  `ken place <topic> --rung N --result pass|partial|miss --probe "..." --answer "..."`.
  `place` names the next rung to ask (the one that halves where they could start).
  After a miss, explain briefly: a failed question still helps the learning that follows.

Placement earns no credit. It decides where teaching starts and how hard the dialogues push.

## Starting from a question instead of a topic

`ken ask "why is lithium the best metal for batteries?"` records a question and shows what is
already on their map. Get their answer first: it shows where the ladder starts. Propose rungs from
the ground up, reuse existing concepts, and add each rung only after they approve it
(`ken rung <qid> <topic> "DOMAIN :: CONCEPT :: DESC"`).
