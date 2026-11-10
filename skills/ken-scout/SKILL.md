---
name: ken-scout
description: Read a topic's sources ahead of the learner and store the branches they will want as scored predictions. Use when a learner wants to grow many branches from a topic, or asks to scout it.
modes: []
---

# ken-scout

- Read the topic's sources (its `## Resources`, the course units, the exam guide). Every scout rests
  on a source you read; say what it says and cite it.
- Store each predicted branch, anchored on the concept where the gap will show:
  `ken scout <topic> <concept> "DOMAIN :: NAME :: DESC" --why "..." --url <source>`
  (`--before` for something learned first, `--topic` for material that belongs in its own topic).
- Prefer quality: a few per rung. Show the learner the list before storing; each scout is a
  prediction that gets scored.
- A scout stays dormant until its concept is studied; then `ken session` and `ken branch <topic>`
  show it, and it is decided like any offer (`ken-branch`). `ken branch <topic>` scores the
  scouting: precision (taken of decided) and recall (kept branches a scout predicted), and lists
  what scouting missed.
