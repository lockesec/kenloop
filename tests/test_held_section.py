"""The structural held rule: a skill is held only when listed under `## Held`.

Wording never decides heldness. The qualifier word list only reports a
contradiction on a line that sits under `## Held`.
"""
import pytest

from kenloop import cli
from kenloop.career import facts as F
from kenloop.core.errors import NotEvaluable

SHEET = """# Facts
## Held
- Python: 6 years in production
- SQL daily for reporting
## Learning
- Docker (just starting)
- Kubernetes: want to learn
"""

# Four phrasings the old word list did not know; each read as held.
UNSEEN = ["Docker (just starting)", "GraphQL - tutorials only",
          "Terraform (little real-world use)", "OAuth: read about it"]


def test_held_only_under_the_held_heading():
    assert F.holds("python", SHEET) and F.holds("sql", SHEET)
    assert not F.holds("docker", SHEET) and not F.holds("kubernetes", SHEET)


@pytest.mark.parametrize("line", UNSEEN)
def test_unseen_wordings_outside_held_are_never_held(line):
    term = line.split()[0].lower()
    assert not F.holds(term, f"## Held\n- Python\n## Notes\n- {line}\n")


@pytest.mark.parametrize("line", UNSEEN)
def test_the_same_clean_looking_line_is_held_under_held(line):
    term = line.split()[0].lower()
    assert F.holds(term, f"## Held\n- {line}\n")      # the owner put it there


def test_free_notes_and_other_sections_are_not_held():
    assert not F.holds("rust", "## Held\n- Python\n## Notes\n- Rust at work\n")
    assert not F.holds("rust", "- Rust\n## Held\n- Python\n")      # before the heading


def test_heading_rules_are_exact_and_predictable():
    for ok in ("## Held", "## held", "##   HELD  ##", "Held\n----"):
        assert F.has_held_section(f"{ok}\n- Go\n"), ok
        assert F.holds("go", f"{ok}\n- Go\n"), ok
    for no in ("# Held", "### Held", "## Held skills", "## Not held", "## Held:", "<!-- ## Held -->"):
        assert not F.has_held_section(f"{no}\n- Go\n"), no
    assert F.holds("go", "## Held\n### Cloud\n- Go\n## Other\n- Rust\n")   # sub-heading stays inside
    assert not F.holds("rust", "## Held\n### Cloud\n- Go\n## Other\n- Rust\n")


def test_a_qualifier_inside_held_is_a_contradiction_and_not_held():
    sheet = "## Held\n- Python\n- Docker, planned\n- Go: studying\n"
    assert F.holds("python", sheet)
    assert not F.holds("docker", sheet)
    assert [c for c in F.contradictions(sheet)] == ["- Docker, planned", "- Go: studying"]
    assert F.contradictions(SHEET) == []


def test_no_held_section_is_not_evaluable_with_the_fix(cfg, home):
    (home / "facts.md").write_text("# Facts\n- Python\n- SQL\n")
    with pytest.raises(NotEvaluable) as e:
        F.read(cfg)
    assert "## Held" in str(e.value) and "facts.md" in str(e.value)


def test_empty_or_absent_facts_still_hold_nothing(cfg, home):
    (home / "facts.md").write_text("")
    assert F.read(cfg) == ""
    (home / "facts.md").unlink()
    assert F.read(cfg) == ""


def _resume(home, *terms):
    (home / "resumes" / "r.md").write_text("# R\n" + "\n".join(f"- {t}" for t in terms) + "\n")


def test_check_claims_the_example_sheet(cfg, home, capsys):
    (home / "facts.md").write_text(SHEET.replace("Python", "REST").replace("SQL", "SQL"))
    _resume(home, "REST", "SQL", "Docker")
    assert cli.main(["--home", str(home), "jobs", "check-claims", "resumes/r.md"]) == 1
    out = capsys.readouterr().out
    assert "VIOLATION" in out and "docker" in out.lower() and "not under ## Held" in out
    assert out.count("VIOLATION") == 1


@pytest.mark.parametrize("line", UNSEEN)
def test_check_claims_unseen_phrasings_outside_held(cfg, home, capsys, line):
    term = line.split()[0]
    (home / "facts.md").write_text(f"## Held\n- REST\n## Notes\n- {line}\n")
    (home / "lexicons" / "web.toml").write_text(
        'name = "web"\n[categories]\nx = ["rest", "docker", "graphql", "terraform", "oauth"]\n')
    _resume(home, "REST", term)
    assert cli.main(["--home", str(home), "jobs", "check-claims", "resumes/r.md"]) == 1
    assert "VIOLATION" in capsys.readouterr().out


def test_check_claims_contradiction_blocks(cfg, home, capsys):
    (home / "facts.md").write_text("## Held\n- REST\n- SQL, planned\n")
    _resume(home, "REST", "SQL")
    assert cli.main(["--home", str(home), "jobs", "check-claims", "resumes/r.md"]) == 1
    out = capsys.readouterr().out
    assert "contradiction" in out and "SQL" in out


def test_check_claims_without_held_section_exits_2(cfg, home, capsys):
    (home / "facts.md").write_text("- REST\n- SQL\n")
    _resume(home, "REST")
    assert cli.main(["--home", str(home), "jobs", "check-claims", "resumes/r.md"]) == 2
    assert "## Held" in capsys.readouterr().err


def test_init_template_has_both_sections(tmp_path):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    text = (h / "facts.md").read_text()
    assert F.has_held_section(text) and "## Learning" in text
    assert F.read(__import__("kenloop.career.config", fromlist=["x"]).load(h)) == text
    assert not F.holds("anything", text)


def test_graduate_emit_pastes_under_held(demo, capsys):
    assert cli.main(["--home", str(demo), "jobs", "graduate", "http-fundamentals", "--emit"]) == 0
    out = capsys.readouterr().out
    body = out.split("-->", 1)[1]
    assert "#" not in body                                 # no heading of its own: it goes under yours
    assert "## Held" in out.split("-->", 1)[0]             # the comment tells where to paste
    assert "held knowledge from study; a knowledge claim, separate from work claims" in out
    facts = (demo / "facts.md").read_text()
    pasted = facts[: facts.index("## Held") + len("## Held\n")] + out
    assert F.holds("status codes", pasted) or any(
        F.holds(l.split("-", 1)[1].split("(")[0].strip().lower(), pasted)
        for l in out.splitlines() if l.startswith("- "))


def test_doctor_reports_a_contradiction_and_a_missing_held_section(cfg, home, capsys):
    (home / "facts.md").write_text("## Held\n- REST\n- SQL, planned\n")
    assert cli.main(["--home", str(home), "doctor"]) == 1
    assert "under ## Held but qualified" in capsys.readouterr().out
    (home / "facts.md").write_text("- REST\n")
    assert cli.main(["--home", str(home), "doctor"]) == 2
    assert "## Held" in capsys.readouterr().out


def test_next_without_a_held_section_is_not_evaluable(cfg, home, capsys):
    (home / "facts.md").write_text("- REST\n")
    assert cli.main(["--home", str(home), "next", "--all"]) == 2
    cap = capsys.readouterr()
    assert "## Held" in cap.err and "?" in cap.out
