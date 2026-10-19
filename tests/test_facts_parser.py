"""The facts sheet parser: no preprocessing step can erase or move a heading, comments,
fences and code spans hide text and are named when they do, near-miss headings are named, and the
cheap Markdown edge cases read the way the docs say."""
import pytest

from careerloop import cli, loop
from careerloop import facts as F
from careerloop import home as H
from careerloop.errors import NotEvaluable


def _cfg(tmp_path, facts_text, resume="REST and Docker\n", toml='[ats]\npacks = ["web"]\n'):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text(toml)
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume)
    return H.load_config(h), h


STRAY = "## Held\n- Python\n- ~~1s timeout\n## Learning\n- cap ~~ 2s\n- Docker\n"


def _cfg_2(tmp_path, facts_text, resume="REST and Docker\n"):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


LEX = """name = "web"
[categories]
protocols = ["http", "https", "http/2", "tls", "dns", "websockets"]
api = ["rest", "json", "graphql", "openapi"]
security = ["oauth", "cors", "csrf", "rate limiting"]
ops = ["caching", "cdn", "load balancing", "observability", "docker", "redis", "microservices"]
data = ["sql", "postgresql"]
lang = ["go", "kubernetes"]
"""


def _cfg_3(tmp_path, facts_text, resume="REST and Docker\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


# --- Headings, strike-through, comments, fences and code spans ------------------------------------

def test_stray_strike_pairs_never_cross_a_heading():
    assert F.holds("python", STRAY)
    assert not F.holds("docker", STRAY)               # Docker sits under ## Learning
    assert [b.text for b in F.blocks(STRAY) if b.heading] == ["## Held", "## Learning"]


def test_a_strike_on_one_line_still_ignores_its_text():
    sheet = "## Held\n- Go ~~(Rust)~~\n"
    assert F.holds("go", sheet) and not F.holds("rust", sheet)


@pytest.mark.parametrize("sheet", [
    "## Held\n- Python\n~~ stray\n## Learning\n- Docker ~~ here\n",
    "## Held\n- Python\n- a ~~ b\n- c ~~ d\n## Learning\n- Docker\n",
    "## Held\n- Python\n<!-- ~~ -->\n## Learning\n- ~~ Docker\n",
])
def test_no_strike_layout_moves_docker_into_held(sheet):
    assert F.holds("python", sheet) and not F.holds("docker", sheet)


def test_a_struck_held_entry_is_reported(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n- Python\n- ~~Docker~~\n- Go ~~(old)~~\n")
    assert [n for n, _t in F.analyse(cfg.facts.read_text()).struck] == [3, 4]
    assert not F.holds("docker", cfg.facts.read_text())
    loop.doctor(cfg)
    out = capsys.readouterr().out
    assert "FINDING facts.md line 3" in out and "struck through" in out


def test_unclosed_construct_is_named(tmp_path):
    cfg, h = _cfg(tmp_path, "<!-- opened\n## Held\n- Go\n")
    with pytest.raises(NotEvaluable) as e:
        F.read(cfg)
    assert "line 1" in str(e.value) and "never closes" in str(e.value)


def test_held_means_mentioned_on_a_held_line():
    assert F.holds("docker", "## Held\n- Redis, alongside Docker\n")      # one skill per line is the rule


def test_code_span_semantics_are_unchanged():
    # a comment opener inside a code span is text; outside it opens a comment
    assert F.holds("docker", "## Held\n- `<!--` Docker\n")
    assert not F.holds("docker", "## Held\n- <!-- Docker -->\n")
    assert F.holds("docker", "## Held\n- ``a ` b <!--`` Docker\n")
    assert F.holds("docker", "## Held\n- ``` unclosed <!-- Docker\n") is False


def test_a_leading_rule_is_not_part_of_a_heading_in_a_message():
    sheet = F.analyse("---\ntitle: Held skills\n---\n- REST\n")
    assert not sheet.has_held
    msg = F.no_held_message("facts.md", sheet)
    assert "## --- " not in msg and "---" not in msg.split("line 1 reads")[-1]


# --- Near-miss headings are named -----------------------------------------------------------------

@pytest.mark.parametrize("head", ["## Held:", "## *Held*", "# Held", "## Held skills", "### Held"])
def test_near_miss_headings_are_named(tmp_path, head):
    cfg, h = _cfg(tmp_path, f"{head}\n- Go\n")
    with pytest.raises(NotEvaluable) as e:
        F.read(cfg)
    assert "line 1" in str(e.value) and head in str(e.value)


@pytest.mark.parametrize("sheet,line", [
    ("# Facts\n## Hel\u200bd\n- REST\n", 2),
    ("# Facts\n\uff03\uff03 Held\n- REST\n", 2),
    ("# Facts\n- REST\n\ufeff## Held\n- Go\n", 3),
    ("# Facts\n## Not held\n- REST\n", 2),
    ("# Facts\n## Skills I hold\n- REST\n", 2),
    ("# Facts\n##\u00a0Held\n- REST\n", 2),
])
def test_near_miss_is_named(tmp_path, sheet, line):
    cfg, _h = _cfg_2(tmp_path, sheet)
    with pytest.raises(NotEvaluable) as e:
        F.read(cfg)
    assert f"line {line} reads" in str(e.value)


def test_unrelated_heading_is_no_near_miss(tmp_path):
    cfg, _h = _cfg_2(tmp_path, "# Facts\n## Learning\n- REST\n")
    with pytest.raises(NotEvaluable) as e:
        F.read(cfg)
    assert "reads" not in str(e.value)


def test_facts_side_near_miss_heading_is_named(tmp_path):
    cfg, _h = _cfg_3(tmp_path, "# Facts\n## Hel\u034fd\n- REST\n")
    with pytest.raises(NotEvaluable) as e:
        F.read(cfg)
    assert "line 2 reads" in str(e.value)


# --- A hidden skill is reported as hidden, not as absent ------------------------------------------

def test_comment_opener_inside_inline_code_is_text():
    sheet = "## Held\n- REST, the `<!--` marker\n- Docker\n"
    s = F.analyse(sheet)
    assert s.unclosed == [] and F.holds("docker", sheet)
    sheet2 = "## Held\n- ``a <!-- b`` REST\n- Docker\n"
    assert F.holds("docker", sheet2) and F.holds("rest", sheet2)


def test_unmatched_backtick_is_not_a_code_span():
    sheet = "## Held\n- stray ` tick <!-- opens\n- Docker\n"
    assert not F.holds("docker", sheet) and F.analyse(sheet).unclosed


# --- Markdown edge cases --------------------------------------------------------------------------

def test_empty_heading_ends_held():
    sheet = "## Held\n- REST\n##\n- Docker\n"
    assert F.holds("rest", sheet) and not F.holds("docker", sheet)
    assert not F.holds("docker", "## Held\n- REST\n## \n- Docker\n")


def test_seven_hashes_is_not_a_heading():
    sheet = "## Held\n- REST\n####### Learning\n- Docker\n"
    assert F.holds("docker", sheet)


def test_link_text_counts_as_a_mention_a_url_does_not():
    # a web address states and holds nothing anywhere (a resume's GitHub link is not `https`)
    assert F.holds("docker", "## Held\n- [Docker](https://example.invalid/x)\n")
    assert not F.holds("docker", "## Held\n- [notes](https://example.invalid/docker)\n")
