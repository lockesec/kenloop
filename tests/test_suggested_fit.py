"""A suggested fit, computed from what you hold, with its working shown; you confirm it.

suggested = 1 + 4 x (0.7 x required held share + 0.3 x preferred held share), minus 0.5 when
the experience asked is above [profile] years, clamped to 1-5 and rounded to the half point.
Without sections it uses every term. Nothing is written until you accept it."""
import json

from careerloop import cli

POSTING = """## Requirements
- Splunk
- Incident response
- KQL
- 5+ years of experience in a SOC
## Nice to have
- Sigma rules
- Python
"""


def setup(home, years="3"):
    (home / "config.toml").write_text(f'[profile]\nresume = "resumes/resume.md"\nyears = "{years}"\n'
                                      '[ats]\npacks = ["security"]\n')
    (home / "lexicons" / "web.toml").unlink()
    (home / "resumes").mkdir(exist_ok=True)
    (home / "resumes" / "resume.md").write_text("Splunk\n")
    (home / "facts.md").write_text("## Held\n- Splunk\n- Incident response\n- Python\n")
    (home / "jd.txt").write_text(POSTING)
    cli.main(["--home", str(home), "jobs", "intake", "--company", "Acme", "--role", "SOC",
              "--jd", str(home / "jd.txt")])
    return "acme-soc"


def run(home, capsys, *argv):
    capsys.readouterr()
    code = cli.main(["--home", str(home), *argv])
    got = capsys.readouterr()
    return code, got.out + got.err


def test_score_without_fit_shows_the_suggestion_and_its_working_and_writes_nothing(home, capsys):
    slug = setup(home)
    run(home, capsys, "jobs", "check", slug)
    before = (home / "roles" / slug / "meta.json").read_text()
    code, out = run(home, capsys, "jobs", "score", slug)
    assert code == 0
    # required 2/3 held (splunk, incident response; not kql), preferred 1/2 (python)
    # 1 + 4 x (0.7 x 0.667 + 0.3 x 0.5) = 3.47 ; asks 5+, profile 3: -0.5 -> 2.97 -> 3.0
    assert "suggested fit 3.0" in out
    assert "required 2/3 held" in out and "preferred 1/2 held" in out and "-0.5" in out
    assert "--fit suggested" in out
    assert (home / "roles" / slug / "meta.json").read_text() == before


def test_fit_suggested_records_it_with_its_source(home, capsys):
    slug = setup(home)
    run(home, capsys, "jobs", "check", slug)
    code, out = run(home, capsys, "jobs", "score", slug, "--fit", "suggested")
    assert code == 0 and "fit 3.0" in out
    meta = json.loads((home / "roles" / slug / "meta.json").read_text())
    assert meta["fit_score"] == 3.0 and meta["fit_source"] == "suggested"
    run(home, capsys, "jobs", "score", slug, "--fit", "4")
    meta = json.loads((home / "roles" / slug / "meta.json").read_text())
    assert meta["fit_score"] == 4.0 and meta["fit_source"] == "you"


def test_no_fresh_coverage_means_no_suggestion(home, capsys):
    slug = setup(home)
    code, out = run(home, capsys, "jobs", "score", slug)
    assert code == 2 and "jobs check" in out
    code, _ = run(home, capsys, "jobs", "score", slug, "--fit", "suggested")
    assert code == 2


def test_a_bad_fit_value_is_a_usage_error(home, capsys):
    slug = setup(home)
    assert run(home, capsys, "jobs", "score", slug, "--fit", "lots")[0] == 64
    assert run(home, capsys, "jobs", "score", slug, "--fit", "9")[0] == 64


def test_check_mentions_the_suggestion(home, capsys):
    slug = setup(home)
    _, out = run(home, capsys, "jobs", "check", slug)
    assert f"suggested fit 3.0 (`careerloop jobs score {slug}` shows the working)" in out
