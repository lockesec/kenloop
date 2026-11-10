"""How a lexicon term is found in resumes, postings and the Held section: multiword terms join
across the documented hyphens, dashes and slashes, never across a line, a list item, a paragraph or a
Held block (end-of-line hyphenation is the one allowed exception), and web addresses are not skills."""
import pytest

from kenloop.career import ats
from kenloop import cli
from kenloop.career import facts as F
from conftest import run


MW = ["rate limiting", "machine learning", "load balancing", "ci/cd", "openid connect", "a/b testing",
      "nist 800-53", "python", "java", "script", "docker"]


def _lex():
    return ats.Lexicon([(t, "t/c") for t in MW], set())


def _terms(text):
    return ats.extract(text, _lex(), acronyms=False)


def _cfg(tmp_path, facts="## Held\n- Python\n", resume="Python rate-limiting\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "t.toml").write_text('name = "t"\n[categories]\nx = ["python", "rate limiting", "load balancing"]\n')
    (h / "config.toml").write_text('[ats]\npacks = ["t"]\n')
    (h / "facts.md").write_text(facts, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return h


MW_2 = ["cloud security", "rate limiting", "load balancing", "zero trust", "machine learning", "ci/cd",
      "data quality", "python", "docker"]


def _lex_2():
    return ats.Lexicon([(t, "t/c") for t in MW_2], set())


def _terms_2(text):
    return ats.extract(text, _lex_2(), acronyms=False)


MW_3 = ["rate limiting", "machine learning", "python", "azure", "data lake", "vue", "apache"]


def _lex_3():
    return ats.Lexicon([(t, "t/c") for t in MW_3], set())


def _terms_3(text):
    return ats.extract(text, _lex_3(), acronyms=False)


SEPS = ["\n", "\r\n", "\r", "\v", "\f", "\u2028", "\u2029", "\x85", "\u200b\n", "\n\u200e", "\u00ad\n",
        "\ufeff\n", "\n\u2060", " \n  ", "\t\n\t"]


HYPHENS = ["-", "\u2010", "\u2011", "\ufe63", "\uff0d"]


MW_4 = ["rate limiting", "python", "http", "https", "sql"]


def _terms_4(text):
    return ats.extract(text, ats.Lexicon([(t, "t/c") for t in MW_4], set()), acronyms=False)


# --- Multiword terms match across hyphens, dashes and slashes -------------------------------------

def test_machine_learning_is_still_held_and_c_is_not_cpp():
    assert F.holds("machine learning", "## Held\n- Machine learning pipelines in Python")
    assert not F.holds("c", "## Held\n- C++") and F.holds("c++", "## Held\n- C++") and F.holds("c", "## Held\n- C and Go")


def test_shouted_headings_and_places_are_not_skills(cfg):
    jd = "ABOUT THE JOB\nWHAT YOU'LL DO\nBuild REST APIs and JSON feeds. Location: NYC or SF. Salary in EUR.\nPERKS\n"
    got = ats.extract(jd, ats.load_lexicon(cfg))
    assert [g.lower() for g in got] == ["rest", "json"]


@pytest.mark.parametrize("text,term", [
    ("rate-limiting", "rate limiting"), ("Rate Limiting", "rate limiting"), ("Rate‐Limiting", "rate limiting"),
    ("Machine‑Learning", "machine learning"), ("Load­Balancing", "load balancing"),
    ("CI–CD", "ci/cd"), ("CI / CD", "ci/cd"), ("CI/CD", "ci/cd"), ("CI-CD", "ci/cd"),
    ("OpenID-Connect", "openid connect"), ("OpenID Connect", "openid connect"),
    ("A / B testing", "a/b testing"), ("NIST 800‑53", "nist 800-53"), ("NIST 800 53", "nist 800-53"),
    ("machine–learning", "machine learning"), ("Machine-Learnings", "machine learning"),
])
def test_a_multiword_term_matches_across_hyphens_dashes_and_slashes(text, term):
    assert term in _terms("We need " + text + " skills"), text


@pytest.mark.parametrize("text", ["Open ID Connect", "ratelimiting", "Rate_Limiting", "rate and limiting", "cicd"])
def test_only_the_listed_equivalences_match(text):
    got = _terms(text)
    assert not set(got) & {"rate limiting", "openid connect", "ci/cd"}, (text, got)


def test_facts_hold_a_hyphenated_spelling(tmp_path):
    sheet = "## Held\n- Python\n- Rate-limiting\n- Machine‑Learning\n"
    assert F.holds("rate limiting", sheet) and F.holds("machine learning", sheet)
    assert not F.holds("load balancing", sheet)


def test_check_claims_sees_a_hyphenated_claim_like_the_spaced_one(tmp_path, capsys):
    for spelling in ("Python Rate Limiting", "Python rate-limiting", "Python rate‑limiting"):
        h = _cfg(tmp_path / spelling.replace(" ", "_").replace("‑", "u"), resume=spelling + "\n")
        code, out = run(h, "jobs", "check-claims", "resumes/resume.md", capsys=capsys)
        assert code == 1 and "rate limiting" in out.out, (spelling, out.out)


# --- Held items, paragraphs and lines are separate blocks -----------------------------------------

@pytest.mark.parametrize("items,term", [
    (["Cloud", "Security", "Python"], "cloud security"),
    (["Rate", "Limiting"], "rate limiting"),
    (["Load", "Balancing"], "load balancing"),
    (["Zero", "Trust"], "zero trust"),
    (["Machine", "Learning"], "machine learning"),
    (["Python, CI", "CD"], "ci/cd"),
])
def test_separate_held_items_do_not_hold_the_composite(items, term):
    sheet = "## Held\n" + "".join(f"- {i}\n" for i in items)
    assert not F.holds(term, sheet)
    assert not F.holds(term, "## Held\n" + "".join(f"1. {i}\n" for i in items))


def test_blank_line_between_words_is_two_blocks():
    assert not F.holds("rate limiting", "## Held\n- Rate\n\nLimiting\n")
    assert not F.holds("rate limiting", "## Held\nRate\n\nLimiting\n")


def test_a_hard_wrapped_line_break_inside_one_item_is_not_a_join_either():
    assert not F.holds("cloud security", "## Held\n- Cloud\n  Security\n")


@pytest.mark.parametrize("text", [
    "## Skills\n- Cloud\n- Security\n- Python\n",
    "- Data\n- Quality\n", "– Data\n– Quality\n", "* Data\n* Quality\n",
    "Used machine\n- learning daily", "Built rate\n\nlimiting", "machine\n- learning",
    "Built rate\nlimiting", "Cloud\r\nSecurity", "Cloud Security", "Cloud\x0bSecurity", "Cloud\x85Security",
    "Cloud\fSecurity", "Cloud\x1cSecurity", "Cloud\x1fSecurity",
])
def test_resume_and_posting_words_on_separate_lines_are_not_a_composite(text):
    got = _terms_2(text)
    assert not set(got) & {"cloud security", "data quality", "machine learning", "rate limiting"}, (text, got)


@pytest.mark.parametrize("text", [
    "rate limiting", "rate-limiting", "Rate‑Limiting", "Rate‐Limiting", "CI/CD", "CI / CD",
    "Load­Balancing", "cloud  security", "cloud\tsecurity", "cloud security", "cloud security",
    "Rate - Limiting", "rate–limiting",
])
def test_the_listed_joins_still_match(text):
    got = _terms_2("We need " + text + " skills")
    assert set(got) & {"rate limiting", "ci/cd", "load balancing", "cloud security"}, (text, got)


def test_end_of_line_hyphenation_is_the_one_allowed_line_break():
    assert "machine learning" in _terms_2("Built machine-\nlearning systems")
    assert "machine learning" in _terms_2("Built machine‐\nlearning systems")
    assert F.holds("machine learning", "## Held\nMachine-\nlearning\n")
    # not when a marker or blank line follows, or a space precedes the hyphen
    for t in ("machine-\n- learning", "machine-\n\nlearning", "machine -\nlearning", "machine/\nlearning"):
        assert "machine learning" not in _terms_2(t), t


def test_soft_hyphen_views_never_join_across_the_seam():
    sheet = "## Held\n- Limiting fac­tors, Python, the rate\n"
    assert not F.holds("rate limiting", sheet)
    assert "rate limiting" not in _terms_2("Limiting fac­tors, Python, the rate")
    assert "rate limiting" not in _terms_2("the rate\nLimiting fac­tors")
    assert "load balancing" in _terms_2("Load­Balancing")


def test_a_search_of_the_joined_held_text_equals_a_block_by_block_search():
    sheet = ("## Held\n- Cloud\n- Security\n- Rate-\nlimiting\n- Load\n\nBalancing\n- Machine-\n- learning\n"
             "- Python, CI\n- CD\n- Zero Trust\n- Docker\n")
    sh = F.analyse(sheet)
    for t in MW_2 + ["rate limiting", "ci/cd", "balancing", "trust"]:
        assert F.holds(t, sheet) == any(F.token_in(t, n) for n in sh.held_norms), t
    assert F.holds("rate limiting", sheet) and F.holds("zero trust", sheet)
    assert not (F.holds("cloud security", sheet) or F.holds("load balancing", sheet)
                or F.holds("machine learning", sheet) or F.holds("ci/cd", sheet))


# --- Line-end wraps join only when the matcher and the disguise reader agree ----------------------

@pytest.mark.parametrize("dash", ["\u2014", "\u2013", "/"])
def test_a_dash_or_slash_at_a_line_end_does_not_join(dash):
    assert "rate limiting" not in _terms_3(f"Built rate{dash}\nlimiting\n")


@pytest.mark.parametrize("hy", ["-", "\u2010", "\u2011"])
def test_a_hyphen_at_a_line_end_joins(hy):
    assert "rate limiting" in _terms_3(f"Built rate{hy}\nlimiting\n")


@pytest.mark.parametrize("wrap", ["rate-\n  limіting", "rate-\n\tlimіting", "rate- \nlimіting",
                                  "rate-\n​limіting", "rate-\n limіting"])
def test_the_disguise_reader_joins_every_wrap_the_matcher_joins(wrap):
    lw = F.lexicon_words(MW_3)
    assert F.disguised(f"- Built {wrap} at scale\n", lw)
    plain = wrap.replace("і", "i")
    assert "rate limiting" in _terms_3(f"- Built {plain} at scale\n")


@pytest.mark.parametrize("sep", SEPS)
@pytest.mark.parametrize("hy", HYPHENS)
def test_the_matcher_and_the_disguise_reader_join_the_same_wraps(sep, hy):
    lw = F.lexicon_words(MW_3)
    plain = f"Python, rate{hy}{sep}limiting\n"
    disguised = f"Python, rate{hy}{sep}limit\u0456ng\n"
    assert ("rate limiting" in _terms_3(plain)) == bool(F.disguised(disguised, lw)), (repr(sep), repr(hy))


@pytest.mark.parametrize("sep", SEPS)
def test_a_dash_or_slash_wrap_joins_in_neither(sep):
    lw = F.lexicon_words(MW_3)
    for d in ("\u2014", "\u2013", "/"):
        assert "rate limiting" not in _terms_3(f"rate{d}{sep}limiting\n")
        if "\x85" not in sep:      # NEL inside a word is a suspicious character to the reader (fails closed)
            assert not F.disguised(f"rate{d}{sep}limit\u0456ng\n", lw)


@pytest.mark.parametrize("text", ["machine-\n- learning", "machine-\n* learning", "rate-\n> limiting",
                                  "rate -\nlimiting", "rate-\n\nlimiting"])
def test_markers_spaces_and_blank_lines_still_break_a_join_for_the_matcher(text):
    lex = ats.Lexicon([("machine learning", "t/c"), ("rate limiting", "t/c")], set())
    assert ats.extract(text, lex, acronyms=False) == []


# --- Web addresses are not skills -----------------------------------------------------------------

@pytest.mark.parametrize("text", ["See [my site](https://example.com) and SQL",
                                  "github: https://github.com/someone, SQL",
                                  "Portfolio www.example.com/http-notes and SQL",
                                  "\\href{https://example.com}{GitHub} SQL"])
def test_a_url_is_not_a_stated_skill(text):
    got = _terms_4(text)
    assert "https" not in got and "http" not in got and "sql" in got


def test_http_as_a_word_is_still_a_term():
    assert "http" in _terms_4("Built HTTP services")


def test_a_resume_with_a_url_and_held_skills_passes(tmp_path):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "facts.md").write_text("## Held\n- Docker\n")
    r = tmp_path / "r.md"
    r.write_text("Docker work. See [my site](https://example.com) and http://example.org/x.\n")
    assert cli.main(["--home", str(h), "jobs", "check-claims", str(r)]) == 0
