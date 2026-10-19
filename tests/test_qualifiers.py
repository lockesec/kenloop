"""Qualifiers on a Held line: negation, "lacking" phrases, level words, learning
qualifiers and their documented exceptions, nested items and unchecked task boxes decide whether a
skill counts as held."""
import pytest

from careerloop import cli
from careerloop import facts as F
from careerloop import home as H
from careerloop import jobs as J


def _cfg(tmp_path, facts_text, resume="REST and Docker\n"):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


def _claims(cfg, capsys, resume="resumes/resume.md"):
    capsys.readouterr()
    rc = J.check_claims(cfg, resume)
    return rc, capsys.readouterr().out


# --- Negation and lacking phrases on a Held line --------------------------------------------------

@pytest.mark.parametrize("line", [
    "- No experience with Kubernetes yet", "- I have never used Kubernetes", "- Kubernetes (learning)",
    "- Studying Kubernetes", "- Want to learn Kubernetes", "- Kubernetes: not yet", "- Kubernetes (WIP)",
    "- ~~Kubernetes~~", "<!-- Kubernetes -->", "```\nkubectl  # Kubernetes\n```", "Planned\n=======\n\n- Kubernetes",
])
def test_negative_and_non_content_lines_are_not_held(line):
    assert not F.holds("kubernetes", "## Held\n- Go\n\n" + line)


@pytest.mark.parametrize("line", [
    "- REST (not Docker)", "- REST; no Docker yet", "- REST, never Docker", "- REST without Docker",
    "- REST, except Docker", "- REST instead of Docker", "- Docker, not just scripting",
    "- REST; No Docker",
])
def test_negation_on_a_held_line_is_a_contradiction(line):
    sheet = f"## Held\n{line}\n"
    assert not F.holds("docker", sheet)
    assert len(F.contradictions(sheet)) == 1


def test_check_claims_exits_1_and_names_it(tmp_path, capsys):
    cfg, _h = _cfg(tmp_path, "## Held\n- REST (not Docker)\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "contradiction" in out and "line 2" in out and "docker" in out.lower()


@pytest.mark.parametrize("line", [
    "- Notifications service", "- Node.js", "- I know REST", "- Knowledge graphs", "- Nothing but SQL daily",
    "- Docker at work", "- Annotation tooling", "- Kubernetes, Nodes and Docker",
])
def test_negation_words_are_word_bounded(line):
    assert F.contradictions(f"## Held\n{line}\n") == []


@pytest.mark.parametrize("line", ["No-code tools", "Not-for-profit sector", "No Starch Press books",
                                  "No.1 ranking", "No. 1 ranking"])
def test_compounds_are_no_negation(line):
    assert F.contradictions(f"## Held\n- Docker; {line}\n") == [], line


@pytest.mark.parametrize("line", ["REST; no Docker", "REST, not Docker", "REST. No."])
def test_real_negations_still_fire(line):
    assert F.contradictions(f"## Held\n- {line}\n")


def test_row_lists_every_noun_and_weakener():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[1] / "docs" / "trust-rules.md").read_text(encoding="utf-8")
    row = next(ln for ln in doc.splitlines() if ln.startswith("| no experience"))
    for w in (*F.EXPERIENCE_NOUNS, *F.EXPERIENCE_WEAKENERS):
        assert w in row, w


@pytest.mark.parametrize("noun", ["experience", "exposure", "knowledge", "familiarity", "proficiency"])
def test_every_listed_noun_triggers(noun):
    assert F.contradictions(f"## Held\n- Docker, limited {noun}\n")


@pytest.mark.parametrize("line", ["Docker, lacking hands-on experience", "Docker (lack of real production exposure)",
                                  "Docker; without any hands-on experience", "Docker, minimal prior work experience"])
def test_lacking_phrases_with_compounds_contradict(line):
    assert F.contradictions(f"## Held\n- {line}\n"), line


def test_plain_held_line_is_not_a_contradiction():
    assert F.contradictions("## Held\n- Docker (3 years of experience)\n") == []


# --- Nested items and checkboxes ------------------------------------------------------------------

def test_unchecked_task_box_is_not_held():
    sheet = "## Held\n- [x] Go\n- [ ] Docker\n"
    assert F.holds("go", sheet) and not F.holds("docker", sheet)
    assert F.contradictions(sheet) == ["- [ ] Docker"]


def test_nested_qualifier_child_disqualifies_its_parent():
    sheet = "## Held\n- Docker\n  - (learning)\n- Redis\n"
    assert not F.holds("docker", sheet)
    assert F.holds("redis", sheet)
    bl = [b for b in F.analyse(sheet).blocks if b.text == "- Docker"][0]
    assert bl.qualified and "line 3" in bl.why


def test_nested_children_without_a_qualifier_hold():
    sheet = "## Held\n- Docker\n  - Compose\n  - Swarm\n"
    assert F.holds("docker", sheet) and F.holds("compose", sheet)


def test_a_qualified_sibling_does_not_disqualify_the_next_item():
    sheet = "## Held\n- Docker\n- (learning)\n- Redis\n"
    assert F.holds("docker", sheet) and F.holds("redis", sheet)


def test_a_qualifier_in_a_sibling_subtree_does_not_reach_a_parent_of_another():
    sheet = "## Held\n- Cloud\n  - Docker\n- Other\n  - Redis (learning)\n"
    assert F.holds("docker", sheet) and F.holds("cloud", sheet)
    assert not F.holds("redis", sheet) and not F.holds("other", sheet)


def test_numbered_unchecked_box_is_not_held():
    assert not F.holds("docker", "## Held\n1. [ ] Docker\n")
    assert not F.holds("docker", "## Held\n- [ ] Docker\n")
    assert F.holds("docker", "## Held\n1. [x] Docker\n")


# --- Level words and learning qualifiers ----------------------------------------------------------

@pytest.mark.parametrize("line", ["Docker (Plan  to learn)", "Docker (plan\tto\tlearn)", "Docker, not   yet",
                                  "Docker (would   like to)", "Docker \u00a0 in \u00a0 progress"])
def test_extra_whitespace_does_not_hide_a_qualifier(line):
    assert F.contradictions(f"## Held\n- {line}\n"), line


@pytest.mark.parametrize("line", ["Docker beginner", "Docker basic", "Docker novice.", "Docker rusty",
                                  "Docker entry level", "Docker intro"])
def test_trailing_basic_words_qualify(line):
    assert not F.holds("docker", f"## Held\n- {line}\n"), line


@pytest.mark.parametrize("line", ["Basic auth over HTTPS with Docker", "Docker beginner-friendly images",
                                  "Docker for beginners", "Docker intro course author"])
def test_trailing_basic_words_quiet_direction(line):
    assert F.holds("docker", f"## Held\n- {line}\n"), line


@pytest.mark.parametrize("line", ["Docker (will learn)", "Docker, to be learned", "Docker: just started",
                                  "Will learn Docker"])
def test_added_qualifiers(line):
    assert not F.holds("docker", f"## Held\n- {line}\n"), line


def test_qualifier_text_is_quoted_without_a_stray_letter():
    for line, want in (("Docker (beginner)", "beginner"), ("Docker, basic", "basic"),
                       ("Docker - rusty", "rusty"), ("Docker beginner", "beginner")):
        b = [x for x in F.analyse(f"## Held\n- {line}\n").blocks if x.qualified][0]
        assert b.why == f"qualifier '{want}' in the line", (line, b.why)


@pytest.mark.parametrize("child", ["beginner", "basic", "novice", "rusty", "intro", "(beginner)", "Beginner."])
def test_a_bare_level_word_nested_under_a_skill_qualifies_it(child):
    sheet = f"## Held\n- Docker\n  - {child}\n- REST\n"
    assert not F.holds("docker", sheet)
    assert F.holds("rest", sheet)


def test_quiet_direction_a_nested_item_that_is_not_a_level_stays_held():
    assert F.holds("docker", "## Held\n- Docker\n  - compose\n  - swarm\n")
    assert F.holds("docker", "## Held\n- Docker\n  - Basic auth middleware\n")


def test_a_qualifier_written_with_lookalikes_still_disqualifies():
    for line in ("- Docker (lеarning)", "- Docker (p̲lanned)", "- Docker (léarning)"):
        sheet = "## Held\n" + line + "\n"
        assert not F.holds("docker", sheet), line
        assert F.contradictions(sheet), line


@pytest.mark.parametrize("text", ["e‑learning", "e‐learning", "E–learning", "e-learning",
                                  "deep / learning", "deep/learning", "machine‑learning",
                                  "reinforcement - learning", "deep—learning"])
def test_documented_learning_exceptions_are_not_a_qualifier(text):
    assert F._qualifier(text) == "", text


@pytest.mark.parametrize("text", ["Learning Docker", "learning", "deeply learning", "Rust - learning"])
def test_a_real_learning_qualifier_still_fires(text):
    assert F._qualifier(text) != "", text


@pytest.mark.parametrize("line", [
    "- Azure \u2014 learning", "- Azure - learning", "- Data lake - learning", "- Vue \u2014 learning",
    "- Apache - learning", "- Terraform (some \u2014 learning)", "- Pipe -learning", "- Vue-learning",
    "- Docker (rule-learning)", "- Azure \u2013 learning", "- Azure / learning",
])
def test_a_word_ending_in_e_before_a_joiner_does_not_excuse_learning(line):
    b = [x for x in F.blocks("## Held\n" + line + "\n") if x.held and not x.heading]
    assert b and b[0].qualified, line


@pytest.mark.parametrize("line", [
    "- e-learning platforms", "- E\u2013learning", "- e \u2011 learning", "- deep / learning",
    "- machine-learning", "- Machine \u2010 learning", "- reinforcement learning",
])
def test_the_documented_exceptions_still_hold(line):
    b = [x for x in F.blocks("## Held\n" + line + "\n") if x.held and not x.heading]
    assert b and not b[0].qualified, line


def test_azure_learning_is_a_contradiction_through_check_claims(tmp_path):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "t.toml").write_text('name = "t"\n[categories]\nx = ["azure", "data lake", "python"]\n')
    (h / "config.toml").write_text('[ats]\npacks = ["t"]\n')
    (h / "facts.md").write_text("## Held\n- Azure \u2014 learning\n- Data lake - learning\n- Python\n")
    r = tmp_path / "r.md"
    r.write_text("Python, Azure and a data lake.\n")
    assert cli.main(["--home", str(h), "jobs", "check-claims", str(r)]) == 1


@pytest.mark.parametrize("name", ["Transfer", "supervised", "unsupervised", "Self-supervised", "federated",
                                  "meta", "statistical"])
def test_more_learning_names_are_not_a_qualifier(name):
    b = [x for x in F.blocks(f"## Held\n- {name} learning\n") if x.held and not x.heading]
    assert b and not b[0].qualified


@pytest.mark.parametrize("name", ["ensemble", "contrastive", "few-shot", "zero-shot", "representation",
                                  "lifelong", "continual", "multi-task", "incremental", "curriculum"])
def test_still_more_learning_names(name):
    b = [x for x in F.blocks(f"## Held\n- {name} learning\n") if x.held and not x.heading]
    assert b and not b[0].qualified
