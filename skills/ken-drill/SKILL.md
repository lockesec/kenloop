---
name: ken-drill
description: Quiz-shaped practice from the topic's question bank - due reviews, weak concepts, diagnosis - recorded answer by answer. Use when the learner asks to be quizzed, to drill, or for what is due.
modes: [practice, diagnose]
---

# ken-drill

Follow the tutor rules (`docs/tutor-rules.md` in a clone of kenloop, or https://github.com/lockesec/kenloop/blob/main/docs/tutor-rules.md) (question craft, hints one rung at a time, confidence before the
answer, one scored attempt per concept per day, true/false safety). The pieces:

- What to ask: `ken due <topic>` or `ken quiz <topic>`; weak first: `ken quiz <topic> --weak`.
- Record each answer as it happens:
  `ken record <topic> <concept> ok|partial|miss --qtype recall|applied|edge|comparison|debugging --confidence low|med|high [--hint-depth N]`.
- Bank a good question you asked off the record: `ken bank <topic> <concept> --q "..." --a "..." --ref "..."`.
- After a block: `ken misconceptions <topic>` and `ken calibration <topic>`.
- `--mode diagnose` for a first sweep that finds where they are, not credit.
