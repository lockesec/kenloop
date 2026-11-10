"""ken print: the tutor writes the pages, ken renders them. Self-contained HTML, nothing run."""
import pytest

from kenloop import printout as P
from kenloop.core import learn as L

from conftest import run


@pytest.fixture
def t(cfg, home):
    L.plan(cfg, "t")
    return cfg


def test_the_markdown_a_sheet_uses_renders():
    md = ("# Sheet\n\nA para *with* **bold** and `code`.\n\n## Terms\n\n| term | means |\n|---|---|\n| e | 2.718 |\n\n"
          "- one\n- two\n  wrapped\n\n1. first\n2. second\n\n> You said\n> this\n\n```\na -> b\n```\n\n---\n")
    h = P.render(md)
    assert "<h1>Sheet</h1>" in h and "<em>with</em>" in h and "<strong>bold</strong>" in h and "<code>code</code>" in h
    assert "<th>term</th>" in h and "<td>2.718</td>" in h
    assert "<ul><li>one</li><li>two wrapped</li></ul>" in h and "<ol><li>first</li><li>second</li></ol>" in h
    assert "<blockquote><p>You said this</p></blockquote>" in h and "<pre><code>a -&gt; b</code></pre>" in h
    assert "<hr>" in h


def test_html_in_the_source_is_text_and_no_script_link_survives():
    h = P.render("<script>alert(1)</script> [go](javascript:alert(1)) [ok](https://example.org) <!-- hidden -->")
    assert "<script>" not in h and "&lt;script&gt;" in h
    assert 'href="javascript' not in h and "go (javascript:alert(1))" in h
    assert '<a href="https://example.org">ok</a>' in h and "hidden" not in h


def test_a_page_has_its_title_and_fetches_nothing():
    p = P.page("# Reference sheet: X\n\nbody\n")
    assert "<title>Reference sheet: X</title>" in p and "<script" not in p and "http" not in p.split("<body>")[0]


def test_scaffold_writes_a_template_once(t, home, capsys):
    assert run(home, "print", "t", "--scaffold", "sheet")[0] == 0
    sheet = home / "topics" / "t" / "print" / "reference-sheet.md"
    assert sheet.read_text().startswith("# Reference sheet: ") and "## Easily confused" in sheet.read_text()
    sheet.write_text("# mine\n")
    run(home, "print", "t", "--scaffold", "sheet")
    assert sheet.read_text() == "# mine\n" and "exists; nothing written" in capsys.readouterr().out
    run(home, "print", "t", "--scaffold", "session")
    assert (home / "topics" / "t" / "print" / "session-2030-03-20.md").exists()


def test_print_renders_every_page_and_says_when_there_is_none(t, home, capsys):
    run(home, "print", "t")
    assert "nothing to print in t" in capsys.readouterr().out
    run(home, "print", "t", "--scaffold", "sheet")
    assert run(home, "print", "t")[0] == 0
    html = (home / "topics" / "t" / "print" / "reference-sheet.html").read_text()
    assert html.startswith("<!doctype html>") and "<h2>Easily confused</h2>" in html


def test_pdf_without_a_browser_is_not_evaluable_and_the_html_is_still_made(t, home, capsys, monkeypatch):
    monkeypatch.setattr(P.shutil, "which", lambda name: None)
    run(home, "print", "t", "--scaffold", "sheet")
    code = run(home, "print", "t", "--pdf")[0]
    assert code == 2 and "PDF not made: no Chrome or Chromium" in capsys.readouterr().out
    assert (home / "topics" / "t" / "print" / "reference-sheet.html").exists()


def test_scaffold_and_pdf_together_are_refused(t, home):
    assert run(home, "print", "t", "--scaffold", "sheet", "--pdf")[0] == 64
    assert not (home / "topics" / "t" / "print").exists()


def test_emphasis_never_reaches_into_a_link_address():
    assert P.render("[a](http://x/**y) and **b**") == '<p><a href="http://x/**y">a</a> and <strong>b</strong></p>'
    assert P.render("[**bold** label](https://e.org)") == '<p><a href="https://e.org"><strong>bold</strong> label</a></p>'


def test_a_bar_in_a_code_span_or_escaped_stays_in_its_cell():
    h = P.render("| a | b |\n|---|---|\n| `x|y` | z \\| w |")
    assert "<td><code>x|y</code></td><td>z | w</td>" in h


def test_comments_go_outside_fences_and_stay_inside():
    h = P.render("```\nkeep <!-- this --> text\n```\n<!-- gone -->after")
    assert "keep &lt;!-- this --&gt; text" in h and "gone" not in h and "<p>after</p>" in h


@pytest.mark.parametrize("src", ["[x](&#106;avascript:alert(1))", "[x](data:text/html,1)", "[x](VBScript:1)"])
def test_encoded_or_other_script_schemes_are_never_links(src):
    assert "href" not in P.render(src)
