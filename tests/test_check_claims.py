"""What check-claims and jobs check report: which line and why, contradictions versus
suspicious words, hidden skills named as hidden, and postings that warn while resumes fail."""
import pytest

from kenloop import cli, loop
from kenloop.career import facts as F
from kenloop.career import jobs as J
from kenloop.career import config as CC
from conftest import run


def _cfg(tmp_path, facts_text, resume="REST and Docker\n", toml='[ats]\npacks = ["web"]\n'):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text(toml)
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume)
    return CC.load(h), h


def _cfg_2(tmp_path, facts_text, resume="REST and Docker\n"):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return CC.load(h), h


def _claims(cfg, capsys, resume="resumes/resume.md"):
    capsys.readouterr()
    rc = J.check_claims(cfg, resume)
    return rc, capsys.readouterr().out


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
    return CC.load(h), h


LEX_2 = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes"]
"""


def _cfg_4(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX_2)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return CC.load(h), h


def _claims_2(cfg, capsys):
    capsys.readouterr()
    rc = J.check_claims(cfg, "resumes/resume.md")
    return rc, capsys.readouterr().out


NON_ENGLISH = ["São Paulo", "Łódź", "Ödön", "été", "está",
               "así", "créé", "熟悉Docker部署", "熟悉REST部署",
               "Nürnberg", "Gdańsk", "Łukasz", "R&D", "Ré", "Ŕ", "Björk"]


LEX_3 = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services", "bash", "mongodb", "hbase"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes", "python"]
"""


def _cfg_5(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX_3)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_bytes(resume if isinstance(resume, bytes) else resume.encode("utf-8"))
    return CC.load(h), h


# --- check-claims and jobs check say which line and why -------------------------------------------

def test_an_equivalence_does_not_license_a_claim(cfg, home, capsys):
    cfg.equivalence = {"openapi": "rest"}
    (home / "facts.md").write_text("## Held\n- REST APIs\n")
    (home / "resumes" / "cv.md").write_text("OpenAPI specs for REST services")
    assert J.check_claims(cfg, "resumes/cv.md") == 1
    assert "openapi" in capsys.readouterr().out.lower()


def test_check_claims_checks_lexicon_terms_only_by_default(cfg, home, capsys):
    (home / "facts.md").write_text("## Held\n- REST\n")
    (home / "resumes" / "cv.md").write_text("DANA EXAMPLE\nSoftware Engineer, IBM, NYC. REST services.")
    assert J.check_claims(cfg, "resumes/cv.md") == 0


def test_counts_are_split_and_contradictions_name_line_and_cause(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n- REST\n- Learning Kubernetes\n- Docker, planned\n",
                  resume="REST\nDocker\n")
    rc = J.check_claims(cfg, "resumes/resume.md")
    out = capsys.readouterr().out
    assert rc == 1
    assert "checked 2 resume term(s): 1 violation(s); 1 sheet contradiction(s)" in out
    assert "SHEET CONTRADICTION facts.md line 3: - Learning Kubernetes" in out
    assert "qualifier 'Learning'" in out


def test_heading_inherited_qualifier_prints_the_heading(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n### Learning\n- REST\n", resume="REST\n")
    rc = J.check_claims(cfg, "resumes/resume.md")
    out = capsys.readouterr().out
    assert rc == 1 and "contradiction" in out and "### Learning" in out
    loop.doctor(cfg)
    assert "### Learning" in capsys.readouterr().out


def test_the_document_title_above_held_disqualifies_nothing(tmp_path, capsys):
    sheet = "# Facts (work in progress)\n\n## Held\n- REST\n- Docker\n"
    assert F.holds("rest", sheet) and F.holds("docker", sheet) and F.contradictions(sheet) == []
    cfg, h = _cfg(tmp_path, sheet)
    assert J.check_claims(cfg, "resumes/resume.md") == 0
    assert "0 violation(s); 0 sheet contradiction(s)" in capsys.readouterr().out


def test_jobs_check_names_the_real_cause(tmp_path, capsys):
    cfg, h = _cfg(tmp_path, "## Held\n- REST\n- Docker (learning)\n")
    slug, _ = J.intake(cfg, "acme", "x", jd="REST and Docker and CORS")
    capsys.readouterr()
    J.check(cfg, slug)
    out = capsys.readouterr().out
    assert "docker (listed under ## held but qualified, line 3" in out.lower()


@pytest.mark.parametrize("text", [w for w in NON_ENGLISH if w not in ("熟悉Docker部署",)])
def test_non_english_words_keep_check_claims_clean(tmp_path, capsys, text):
    cfg, _h = _cfg_4(tmp_path, resume=f"REST in {text}\n")
    rc, out = _claims_2(cfg, capsys)
    assert rc == 0 and "suspicious" not in out, out


def test_a_middle_dot_inside_a_word_makes_check_claims_exit_1(tmp_path, capsys):
    cfg, _h = _cfg_4(tmp_path, resume="REST Dock·er\n")
    rc, out = _claims_2(cfg, capsys)
    assert rc == 1 and "suspicious-characters" in out and "U+00B7" in out


def test_check_claims_names_the_control_character(tmp_path, capsys):
    cfg, _h = _cfg_4(tmp_path, resume="REST Doc\x07ker\n")
    rc, out = _claims_2(cfg, capsys)
    assert rc == 1 and "U+0007" in out


def test_typography_sentence_passes_check_claims(tmp_path, capsys):
    cfg, _h = _cfg_5(tmp_path, "## Held\n- REST\n- Docker\n- Python\n- Services\n",
                   "Built services with “Docker” and Python.\n")
    capsys.readouterr()
    rc = J.check_claims(cfg, "resumes/resume.md")
    assert rc == 0 and "suspicious" not in capsys.readouterr().out


def test_a_disguised_term_joined_to_a_neighbour_makes_check_claims_exit_1(tmp_path, capsys):
    cfg, _h = _cfg_5(tmp_path, resume="Skills: REST/Dockеr\n")
    capsys.readouterr()
    assert J.check_claims(cfg, "resumes/resume.md") == 1


def test_check_claims_exit_1(tmp_path, capsys):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "t.toml").write_text('name = "t"\n[categories]\nx = ["cloud security", "python"]\n')
    (h / "config.toml").write_text('[ats]\npacks = ["t"]\n')
    (h / "facts.md").write_text("## Held\n- Cloud\n- Security\n- Python\n")
    r = tmp_path / "r.md"
    r.write_text("Python and Cloud security work\n")
    code, out = run(h, "jobs", "check-claims", str(r), capsys=capsys)
    assert code == 1 and "cloud security" in out.out


def test_check_names_stated_terms_that_are_not_held(home, capsys):
    cfg = CC.load(home)
    J.intake(cfg, "Acme", "Dev", jd="REST and OAuth and JSON")
    (home / "facts.md").write_text("## Held\n- REST and JSON\n## Learning\n- OAuth\n")
    (home / "resumes" / "resume.md").write_text("REST, JSON, OAuth")
    code, out = run(home, "jobs", "check", "acme-dev", capsys=capsys)
    assert code == 0 and "coverage 3/3" in out.out            # coverage still means: what the resume states
    assert "stated on the resume but not held" in out.out and "oauth (mentioned only outside ## held)" in out.out.lower()
    assert "check-claims" in out.out


def test_control_nothing_unheld_prints_no_such_line(home, capsys):
    cfg = CC.load(home)
    J.intake(cfg, "Acme", "Dev", jd="REST and JSON")
    (home / "facts.md").write_text("## Held\n- REST and JSON\n")
    (home / "resumes" / "resume.md").write_text("REST, JSON")
    out = run(home, "jobs", "check", "acme-dev", capsys=capsys)[1]
    assert "not held" not in out.out


# --- A hidden skill is reported as hidden, not as absent ------------------------------------------

def test_closed_comment_hides_and_is_named(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n<!--\n- Docker\n-->\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "hidden by a comment at facts.md line 4" in out and "not in facts.md" not in out


def test_closed_fence_hides_and_is_named(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n```\n- Docker\n```\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "hidden by a fence at facts.md line 4" in out


def test_unclosed_comment_note_in_check_claims(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n<!-- oops\n- Docker\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "hidden by a comment at facts.md line 4" in out
    assert "never closes" in out and "line 3" in out


def test_jobs_check_names_hidden_cause(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n<!--\n- Docker\n-->\n")
    assert "hidden by a comment at facts.md line 4" in F.explain("docker", cfg.facts.read_text())


# --- Postings warn, resumes fail ------------------------------------------------------------------

def test_posting_words_are_warned_about_by_jobs_check(tmp_path, capsys):
    # a posting is third-party text, so it warns and the exit code stays 0
    cfg, _h = _cfg_3(tmp_path, "## Held\n- REST\n")
    slug, _ = J.intake(cfg, "acme", "dev", jd="We need REST and Dock\u0435r")
    capsys.readouterr()
    rc = J.check(cfg, slug)
    out = capsys.readouterr().out
    assert rc == 0 and "WARNING suspicious-characters" in out and "posting" in out and "U+0435" in out


def test_posting_disguise_warns_and_exits_zero(tmp_path, capsys):
    cfg, _h = _cfg_4(tmp_path)
    slug, _ = J.intake(cfg, "acme", "dev", jd="We need REST and Dockеr")
    capsys.readouterr()
    rc = J.check(cfg, slug)
    cap = capsys.readouterr()
    assert rc == 0
    assert "WARNING" in cap.out + cap.err and "posting" in cap.out + cap.err and "U+0435" in cap.out + cap.err
    assert "VIOLATION" not in cap.out


def test_resume_disguise_still_exits_one_in_jobs_check(tmp_path, capsys):
    cfg, _h = _cfg_4(tmp_path, resume="REST and Dockеr\n")
    slug, _ = J.intake(cfg, "acme", "dev", jd="We need REST and Docker")
    capsys.readouterr()
    rc = J.check(cfg, slug)
    assert rc == 1 and "suspicious-characters (resume)" in capsys.readouterr().out
