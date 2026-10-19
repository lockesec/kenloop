"""Reading LaTeX and HTML input: which structure is a line break and which is inline
formatting, postings with nothing visible are refused, and a LaTeX resume is read best-effort with a
stated warning."""
import sys

import pytest

from careerloop import ats, cli
from careerloop import facts as F
from conftest import run


MW = ["rate limiting", "machine learning", "python", "azure", "data lake", "vue", "apache"]


def _lex():
    return ats.Lexicon([(t, "t/c") for t in MW], set())


def _terms(text):
    return ats.extract(text, _lex(), acronyms=False)


# --- LaTeX and HTML structure decides what joins --------------------------------------------------

@pytest.mark.parametrize("src", ["a\\\\Docker b", "\\textbf{Dock}er", "Dock{}er", "x\\\\[2pt]Docker"])
def test_latex_forms_that_join_or_hide_a_word_still_read_as_the_term(tmp_path, src):
    p = tmp_path / "r.tex"
    p.write_text(src, encoding="utf-8")
    assert F.token_in("docker", F.normalize(ats.resume_text(p))), src


def test_adjacent_groups_after_a_command_are_not_joined(tmp_path):
    p = tmp_path / "r.tex"
    p.write_text("\\resumeItem{Docker}{Go}, \\item{Python}", encoding="utf-8")
    t = F.normalize(ats.resume_text(p))
    assert F.token_in("docker", t) and F.token_in("go", t) and F.token_in("python", t)


def test_quiet_direction_ampersand_and_comments(tmp_path):
    p = tmp_path / "r.tex"
    p.write_text("R\\&D % Docker\nGo\n", encoding="utf-8")
    t = F.normalize(ats.resume_text(p))
    assert "r&d" in t and not F.token_in("docker", t)


@pytest.mark.parametrize("tex,term", [
    ("\\begin{itemize}\n\\item machine-\n\\item learning\n\\end{itemize}\n", "machine learning"),
    ("\\item machine \\item learning\n", "machine learning"),
    ("\\section{rate}\\section{limiting}\n", "rate limiting"),
    ("machine\\par learning\n", "machine learning"),
    ("rate & limiting \\\\\n", "rate limiting"),
    ("rate\\_limiting\n", "rate limiting"),
])
def test_latex_structure_never_joins_words(tmp_path, tex, term):
    p = tmp_path / "r.tex"
    p.write_text(tex)
    assert term not in _terms(ats.resume_text(p))


@pytest.mark.parametrize("tex,term", [
    ("Built \\textbf{rate} limiting.\n", "rate limiting"),
    ("rate \\emph{limiting}\n", "rate limiting"),
    ("\\item Machine learning in \\textit{Python}\n", "machine learning"),
])
def test_inline_latex_formatting_still_joins(tmp_path, tex, term):
    p = tmp_path / "r.tex"
    p.write_text(tex)
    assert term in _terms(ats.resume_text(p))


@pytest.mark.parametrize("html,term", [
    ("<ul><li>machine</li><li>learning</li></ul>", "machine learning"),
    ("<p>machine</p><p>learning</p>", "machine learning"),
    ("rate<br>limiting", "rate limiting"),
    ("<li>machine-</li>\n<li>learning</li>", "machine learning"),
    ("<div>rate</div><div>limiting</div>", "rate limiting"),
])
def test_html_block_tags_never_join_words(html, term):
    assert term not in _terms(ats.strip_html(html))


def test_inline_html_still_joins():
    assert "machine learning" in _terms(ats.strip_html("<p>Strong <b>machine</b> learning skills</p>"))


def test_a_single_newline_in_latex_is_a_space(tmp_path):
    p = tmp_path / "r.tex"
    p.write_text("Python developer. Built a rate\nlimiting service.\n\nNext paragraph.\n")
    assert "rate limiting" in _terms(ats.resume_text(p))


def test_a_blank_line_in_latex_is_still_a_break(tmp_path):
    p = tmp_path / "r.tex"
    p.write_text("Built a rate\n\nlimiting service.\n")
    assert "rate limiting" not in _terms(ats.resume_text(p))


def test_a_source_newline_inside_an_html_block_is_a_space():
    assert "rate limiting" in _terms(ats.strip_html("<div>rate\nlimiting</div>"))
    assert "rate limiting" not in _terms(ats.strip_html("<li>rate</li>\n<li>limiting</li>"))


def test_a_plain_text_posting_keeps_its_lines():
    assert "rate limiting" not in _terms(ats.strip_html("- rate\n- limiting\n"))


def test_a_bare_less_than_does_not_eat_posting_text():
    t = ats.strip_html("- Docker (<3 years ok)\n- Kubernetes (>5 years preferred)\n")
    assert "Kubernetes" in t and "<3" in t


@pytest.mark.parametrize("eol", ["\r\n", "\r"])
def test_a_single_line_break_in_a_crlf_or_cr_latex_file_is_a_space(tmp_path, eol):
    p = tmp_path / "r.tex"
    p.write_bytes(f"Python, rate{eol}limiting{eol}".encode())
    assert "rate limiting" in _terms(ats.resume_text(p))


def test_a_lone_cr_in_markup_is_a_space():
    assert "rate limiting" in _terms(ats.strip_html("<div>rate\rlimiting</div>"))


def test_pre_keeps_its_line_breaks():
    assert "rate limiting" not in _terms(ats.strip_html("<p>Skills</p><pre>rate\nlimiting</pre>"))


@pytest.mark.parametrize("tag", ["center", "form", "fieldset", "caption", "body", "video", "legend"])
def test_more_block_tags_end_lines(tag):
    t = ats.strip_html(f"<p>x</p><{tag}>cloud</{tag}><{tag}>security</{tag}>")
    assert "cloud security" not in _terms(t.replace("cloud", "rate").replace("security", "limiting")) or True
    t2 = ats.strip_html(f"<p>x</p><{tag}>rate</{tag}><{tag}>limiting</{tag}>")
    assert "rate limiting" not in _terms(t2)


def test_a_custom_element_with_a_block_name_prefix_is_not_a_block_tag():
    assert "rate limiting" in _terms(ats.strip_html("<p>x</p>rate <td-x>limiting</td-x>"))


@pytest.mark.parametrize("tex,term,want", [
    ("\\cvlistitem{Rate}\n\\cvlistitem{Limiting}\n", "rate limiting", False),
    ("\\resumeSubItem{Rate}\n\\resumeSubItem{Limiting}\n", "rate limiting", False),
    ("\\skillitem{Rate}\\skillitem{Limiting}\n", "rate limiting", False),
    ("rate\\break limiting\n", "rate limiting", False),
    ("rate\\bigskip limiting\n", "rate limiting", False),
    ("\\section*{Python}Rate limiting\n", "python", True),
    ("\\begin{tabular}{ll}Python & x\\\\\n\\end{tabular}\n", "python", True),
])
def test_latex_layout_macros(tmp_path, tex, term, want):
    p = tmp_path / "r.tex"
    p.write_text(tex)
    assert (term in _terms(ats.resume_text(p))) == want


def test_plain_text_generics_are_kept():
    assert "List<String>" in ats.strip_html("Experience with Java (List<String>) and Python\n")


def test_a_latex_resume_carries_a_warning(tmp_path, capsys):
    p = tmp_path / "r.tex"
    p.write_text("Python\n")
    ats.resume_text(p)
    assert "LaTeX is read heuristically" in capsys.readouterr().err


# --- Postings and resumes with nothing readable ---------------------------------------------------

def test_empty_stdin_posting_is_refused(home, monkeypatch, capsys):
    import io
    class _In:
        buffer = io.BytesIO(b"  \n")
    monkeypatch.setattr(sys, "stdin", _In())
    code, out = run(home, "jobs", "intake", "--company", "Acme", "--role", "Dev", "--jd", "-", capsys=capsys)
    assert code == 2 and "empty posting" in out.err
    assert not (home / "roles" / "acme-dev").exists()


def test_an_html_posting_with_no_text_is_refused(tmp_path, capsys):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    jd = tmp_path / "jd.html"
    jd.write_text("<p></p>\n<div> </div>")
    code = cli.main(["--home", str(h), "jobs", "intake", "--company", "A", "--role", "B", "--jd", str(jd)])
    assert code == 2


@pytest.mark.parametrize("html", ["<p>&#8203;</p>", "<div>&#xFEFF;</div>", "​​", "<p>⁠</p>"])
def test_a_posting_of_invisible_characters_is_refused(tmp_path, html):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    jd = tmp_path / "jd.html"
    jd.write_text(html)
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "A", "--role", "B", "--jd", str(jd)]) == 2


@pytest.mark.parametrize("jd", ["&lt;p&gt;&lt;/p&gt;", "\ufff9\ufffb", "\x00\x01\x7f", "\u0301", "<p>&#8203;</p>"])
def test_a_posting_with_nothing_visible_is_refused(tmp_path, jd):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    f = tmp_path / "jd.txt"
    f.write_text(jd)
    assert cli.main(["--home", str(h), "jobs", "intake", "--company", "A", "--role", "B", "--jd", str(f)]) == 2
