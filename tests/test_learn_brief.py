"""`brief TOPIC`: a bundle for whoever writes the question bank, in the exact format
`validate` accepts; and validate now refuses a question with no answer."""
import re

from kenloop import cli


def run(h, capsys, *argv):
    capsys.readouterr()
    code = cli.main(["--home", str(h), *argv])
    got = capsys.readouterr()
    return code, got.out + got.err


def test_the_brief_lists_concepts_with_their_question_counts_and_the_format(demo, capsys):
    code, out = run(demo, capsys, "brief", "http-fundamentals")
    assert code == 0
    assert out.startswith("# Study brief: ")
    assert "basics:request-and-response  2 question(s)" in out
    assert "### Q:" in out and "- **A:**" in out and "- **Ref:**" in out and "- **Type:**" in out
    assert "recall, applied, edge, comparison, debugging" in out
    assert "ken validate http-fundamentals" in out


def _write_the_example_bank(demo, capsys):
    _, out = run(demo, capsys, "brief", "http-fundamentals")
    concepts = re.findall(r"^- (\S+)  \d+ question\(s\)", out, re.M)
    assert concepts
    example = out.split("```markdown\n")[1].split("```")[0]
    block = example.split("\n", 2)[2]               # the example without its "## <concept>" line
    bank = demo / "topics" / "http-fundamentals" / "questions.md"
    text = bank.read_text()
    return concepts, block, bank, text


def test_a_bank_written_to_the_brief_parses_but_the_unedited_placeholders_fail_validate(demo, capsys):
    concepts, block, bank, text = _write_the_example_bank(demo, capsys)
    for c in concepts:
        text += f"\n## {c}\n\n" + block
    bank.write_text(text)
    code, out = run(demo, capsys, "validate", "http-fundamentals")
    assert code == 1
    fails = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
    assert fails and all("still the brief's placeholder" in ln for ln in fails), fails
    assert len(fails) == 2 * len(concepts)            # the question text and the answer, per question


def test_a_bank_written_to_the_brief_validates_once_the_placeholders_are_replaced(demo, capsys):
    concepts, block, bank, text = _write_the_example_bank(demo, capsys)
    block = block.replace("<one question, asked with no hint in it>", "What does a 404 status mean?")
    block = block.replace("<the one checkable answer>", "The resource was not found")
    for c in concepts:
        text += f"\n## {c}\n\n" + block
    bank.write_text(text)
    code, out = run(demo, capsys, "validate", "http-fundamentals")
    assert code == 0 and "0 failure(s)" in out, out


def test_one_placeholder_is_enough_to_fail(demo, capsys):
    bank = demo / "topics" / "http-fundamentals" / "questions.md"
    bank.write_text(bank.read_text() + "\n## basics:urls\n\n### Q: What is a port?\n"
                    "- **A:** <the one checkable answer>\n- **Ref:** notes.md#urls\n- **Type:** recall\n")
    code, out = run(demo, capsys, "validate", "http-fundamentals")
    assert code == 1 and "answer is still the brief's placeholder" in out
    # a real answer that happens to be an angle-bracket tag is not a placeholder
    bank.write_text(bank.read_text().replace("<the one checkable answer>", "<div>"))
    assert run(demo, capsys, "validate", "http-fundamentals")[0] == 0


def test_a_question_without_an_answer_fails_validate(demo, capsys):
    bank = demo / "topics" / "http-fundamentals" / "questions.md"
    bank.write_text(bank.read_text() + "\n## basics:urls\n\n### Q: What is a port?\n"
                    "- **Ref:** notes.md#urls\n- **Type:** recall\n")
    code, out = run(demo, capsys, "validate", "http-fundamentals")
    assert code == 1 and "question without an answer" in out


def test_an_unknown_topic_is_refused(demo, capsys):
    code, _ = run(demo, capsys, "brief", "no-such-topic")
    assert code in (2, 64)
