---
name: ken-exam
description: Get a learner through an exam - practice exams in the exam's format, readiness, the exam date, and recording the pass. Use for `intent: pass` lines and topics, "practice exam", "am I ready", "just pass it".
modes: [exam]
---

# ken-exam

For what an exam needs, not deep understanding (that is `ken-climb`). Exam-scope concepts only.

- The date: `ken cert exam-date <topic> --set YYYY-MM-DD`; reviews then land before it.
- A practice exam drawn across domains by size: `ken cert exam <topic> --n 20`; record each answer
  `ken record <topic> <concept> ok|partial|miss --mode exam`.
- Readiness: read the domain mix of misses; drill the weakest domain with `ken-drill`.
- After the real exam: `ken cert passed <topic> --emit` prints the credential line for
  `## Held` in facts.md (the learner pastes it); the topic is then complete and off the schedule.
