# Limits

## How well it works

- **Whether it makes you learn better: not measured.** The learning rules come from published research ([references](references.md)). Nothing here compares people using kenloop with people who are not. It has had one serious learner, its author, and one learner cannot show this.
- **The record: checked.** Views are checked against a replay of the log, and every view exits 3 if they disagree. The tests cover the credit rules, and the study home's log is plain text you can read.
- **Scheduling: compared with the reference.** `benchmarks/fsrs_parity.py` compares its FSRS-6 scheduler with the reference implementation. [DESIGN.md](../DESIGN.md) records the differences. The default parameters come from other people's reviews, not yours.

## Known holes

- **A credit is only as honest as what was recorded.** The tool cannot see whether you looked something up. It records what you and your assistant report, so a learner or an assistant that lies gets a clean record.
- **It does not judge understanding.** Dialogue grades come from the assistant and name their grader. A transcript is checked against its fingerprint, which shows the text did not change, not that the grade is right.
- **The study method lives in the assistant's skills,** so a different assistant can follow them differently. The mark and trail records survive that; the teaching may not.
- **The resume gate reads wording, not the truth.** It checks your resume against what you listed under `## Held`, and only for terms in its lexicon. Every shape it does not read: [trust rules, Known limits](trust-rules.md#known-limits).

- **A cycle across topics is caught only through `before:` links.** A loop that runs through a cross-topic `before:` and back through an in-topic `part-of:` is not reported, and the concepts in it wait on each other.

## Not tested

- Use by anyone but the author, or by assistants other than the ones it was built with.
- Job boards change without notice, so a posting source can break between runs. A failed fetch is reported as not evaluable.
