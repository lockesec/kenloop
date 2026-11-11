"""`jobs build` and the sent / ready / old PDF folders.

Each check is planted to fail once: a 2-page PDF, a clipped bullet, text in the bottom margin, a lost
closing line, missing tools, an unreadable page count, a rebuild of what was sent, and a move onto an
existing folder. The fake runner stands in for tectonic and poppler; the last tests run the real tools
when they are installed.
"""
import json
import subprocess

import pytest

from kenloop.career import build as B
from kenloop.career import jobs as J
from kenloop.core.errors import FINDINGS, NOT_EVALUABLE, OK, NotEvaluable, Refused, UsageError

TEX = r"""\documentclass{article}
\begin{document}
\begin{itemize}
\item Ran endpoint patching for four hundred hosts
\item Wrote detections for credential theft
\end{itemize}
Certifications: Security+ and AZ-500
\end{document}
"""
ALL_TEXT = ("Ran endpoint patching for four hundred hosts\nWrote detections for credential theft\n"
            "Certifications: Security+ and AZ-500\n")


def bbox(lowest=700.0, height=792.0):
    return (f'<page width="612" height="{height}"><word xMin="1" yMin="1" xMax="2" yMax="100">a</word>'
            f'<word xMin="1" yMin="1" xMax="2" yMax="{lowest}">b</word></page>')


class Fake:
    """tectonic writes an empty PDF; pdfinfo and pdftotext answer from the fields."""

    def __init__(self, pages=1, text=ALL_TEXT, box=None, compile_rc=0):
        self.pages, self.text, self.box, self.compile_rc = pages, text, box if box is not None else bbox(), compile_rc
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        name = argv[0].rsplit("/", 1)[-1]
        out = ""
        if name == "tectonic":
            if self.compile_rc == 0:
                from pathlib import Path
                src = Path(argv[3])
                (Path(argv[5]) / (src.stem + ".pdf")).write_bytes(b"%PDF")
            return subprocess.CompletedProcess(argv, self.compile_rc, "", "! Undefined control sequence")
        if name == "pdfinfo":
            out = f"Title: x\nPages:          {self.pages}\n" if self.pages is not None else "Title: x\n"
        elif "-bbox" in argv:
            out = self.box
        else:
            out = self.text
        return subprocess.CompletedProcess(argv, 0, out, "")


def tools(name):
    return f"/bin/{name}"


def role(cfg, home, status="tailoring", cover=True):
    slug, _ = J.intake(cfg, "Acme", "SOC Analyst", jd="SIEM and EDR")
    src = home / "career" / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "resume-acme.tex").write_text(TEX)
    if cover:
        (src / "cover-letter-acme.tex").write_text(TEX)
    m = json.loads((home / "roles" / slug / "meta.json").read_text())
    m["resume"], m["status"] = "career/src/resume-acme.tex", status
    (home / "roles" / slug / "meta.json").write_text(json.dumps(m))
    return slug


def meta(home, slug):
    return json.loads((home / "roles" / slug / "meta.json").read_text())


def test_clean_build_files_into_ready_and_checks_both(cfg, home, capsys):
    slug, fake = role(cfg, home), Fake()
    assert B.build(cfg, slug, run=fake, tool=tools) == OK
    assert meta(home, slug)["pdf_dir"] == f"pdf/ready/{slug}"
    out = capsys.readouterr().out
    assert "resume-acme.pdf: 1 page(s), 2 bullet(s) checked: ok" in out
    assert "cover-letter-acme.pdf" in out and "build CLEAN" in out
    assert meta(home, slug)["history"][-1].endswith("build CLEAN")


@pytest.mark.parametrize("fake, word", [
    (Fake(pages=2), "2 page(s), want 1"),
    (Fake(text=ALL_TEXT.replace("credential theft", "")), "missing from the PDF"),
    (Fake(text=ALL_TEXT.replace("and AZ-500", "")), "missing from the PDF"),     # the closing line, not an item
    (Fake(box=bbox(lowest=780.0)), "into the bottom margin"),
    (Fake(box=""), "margin cannot be checked"),
    (Fake(pages=None), "unknown page(s)"),
    (Fake(compile_rc=1), "tectonic failed"),
])
def test_each_planted_failure_reads_findings(cfg, home, capsys, fake, word):
    slug = role(cfg, home)
    assert B.build(cfg, slug, run=fake, tool=tools) == FINDINGS
    out = capsys.readouterr().out
    assert word in out and "build FINDINGS" in out
    assert meta(home, slug)["history"][-1].endswith("build FINDINGS")


def test_ligatures_and_punctuation_are_not_read_as_clipped(cfg, home):
    slug = role(cfg, home)
    text = ALL_TEXT.replace("theft", "theﬁt").replace("credential theﬁt", "credential theft,")
    assert B.build(cfg, slug, run=Fake(text=text), tool=tools) == OK


@pytest.mark.parametrize("gone", ["tectonic", "pdfinfo", "pdftotext"])
def test_a_missing_tool_is_not_evaluable_and_builds_nothing(cfg, home, capsys, gone):
    slug, fake = role(cfg, home), Fake()
    assert B.build(cfg, slug, run=fake, tool=lambda n: None if n == gone else tools(n)) == NOT_EVALUABLE
    assert fake.calls == [] and gone in capsys.readouterr().out
    assert "pdf_dir" not in meta(home, slug) and not (home / "pdf").exists()


def test_a_sent_role_is_never_rebuilt_but_a_copy_elsewhere_is_allowed(cfg, home, tmp_path):
    slug = role(cfg, home)
    assert B.build(cfg, slug, run=Fake(), tool=tools) == OK
    J.status(cfg, slug, "applied")
    sent = home / "pdf" / "sent" / slug
    assert meta(home, slug)["pdf_dir"] == f"pdf/sent/{slug}" and (sent / "resume-acme.pdf").exists()
    before = (sent / "resume-acme.pdf").read_bytes()
    with pytest.raises(Refused, match="record of what was sent"):
        B.build(cfg, slug, run=Fake(), tool=tools)
    elsewhere = tmp_path / "copy"
    assert B.build(cfg, slug, outdir=str(elsewhere), run=Fake(), tool=tools) == OK
    assert (elsewhere / "resume-acme.pdf").exists()
    m = meta(home, slug)
    assert m["pdf_dir"] == f"pdf/sent/{slug}" and "build" not in m["history"][-1]   # a copy leaves the record alone
    assert (sent / "resume-acme.pdf").read_bytes() == before


def test_status_files_the_folder_by_whether_the_employer_has_it(cfg, home):
    slug = role(cfg, home)
    B.build(cfg, slug, run=Fake(), tool=tools)
    J.status(cfg, slug, "passed")
    assert meta(home, slug)["pdf_dir"] == f"pdf/old/{slug}" and (home / "pdf/old" / slug).is_dir()
    J.status(cfg, slug, "tailoring")
    assert meta(home, slug)["pdf_dir"] == f"pdf/ready/{slug}"
    J.status(cfg, slug, "interviewing")
    J.status(cfg, slug, "rejected")                                     # sent to sent: no move
    assert meta(home, slug)["pdf_dir"] == f"pdf/sent/{slug}"


def test_a_move_onto_an_existing_folder_is_refused_before_anything_changes(cfg, home):
    slug = role(cfg, home)
    B.build(cfg, slug, run=Fake(), tool=tools)
    (home / "pdf" / "sent" / slug).mkdir(parents=True)
    (home / "pdf" / "sent" / slug / "what-was-sent.pdf").write_bytes(b"sent")
    before = meta(home, slug)
    with pytest.raises(NotEvaluable, match="already exists"):
        J.status(cfg, slug, "applied")
    assert meta(home, slug) == before
    assert (home / "pdf" / "sent" / slug / "what-was-sent.pdf").read_bytes() == b"sent"
    assert (home / "pdf" / "ready" / slug / "resume-acme.pdf").exists()


def test_a_status_change_with_no_pdfs_moves_nothing(cfg, home):
    slug = role(cfg, home)
    J.status(cfg, slug, "applied")
    assert "pdf_dir" not in meta(home, slug) and not (home / "pdf").exists()


def test_pdf_root_from_config_and_paths_outside_the_home_stay_absolute(cfg, home, tmp_path):
    cfg.raw["build"] = {"pdf_root": "career/pdf"}
    slug = role(cfg, home)
    B.build(cfg, slug, run=Fake(), tool=tools)
    assert meta(home, slug)["pdf_dir"] == f"career/pdf/ready/{slug}"
    outside = tmp_path / "elsewhere"
    cfg.raw["build"] = {"pdf_root": str(outside)}
    J.status(cfg, slug, "applied")
    assert meta(home, slug)["pdf_dir"] == str(outside / "sent" / slug)
    cfg.raw["build"] = ["not", "a", "table"]
    with pytest.raises(NotEvaluable, match="build"):
        B.pdf_root(cfg)


def test_sources_need_a_named_tex_resume(cfg, home):
    slug = role(cfg, home, cover=False)
    m = meta(home, slug)
    del m["resume"]
    (home / "roles" / slug / "meta.json").write_text(json.dumps(m))
    with pytest.raises(UsageError, match="no resume named"):
        B.build(cfg, slug, run=Fake(), tool=tools)
    m["coverage_resume"] = "career/src/resume-acme.tex"                 # what `jobs check` measured
    (home / "roles" / slug / "meta.json").write_text(json.dumps(m))
    assert B.build(cfg, slug, run=Fake(), tool=tools) == OK
    del m["coverage_resume"]
    (home / "roles" / slug / "meta.json").write_text(json.dumps(m))
    (home / "career/src/resume.md").write_text("x")
    with pytest.raises(UsageError, match="not a .tex"):
        B.build(cfg, slug, resume="career/src/resume.md", run=Fake(), tool=tools)
    with pytest.raises(UsageError, match="does not exist"):
        B.build(cfg, slug, resume="career/src/nope.tex", run=Fake(), tool=tools)
    assert B.build(cfg, slug, resume="career/src/resume-acme.tex", run=Fake(), tool=tools) == OK


def test_without_a_cover_letter_it_builds_the_resume_only(cfg, home, capsys):
    slug, fake = role(cfg, home, cover=False), Fake()
    assert B.build(cfg, slug, run=fake, tool=tools) == OK
    assert sum(c[0].endswith("tectonic") for c in fake.calls) == 1
    assert "resume only" in capsys.readouterr().out


def test_cli_wiring(home, capsys):
    from kenloop import cli
    assert cli.main(["--home", str(home), "jobs", "build", "--help"]) == 0
    assert "--outdir" in capsys.readouterr().out


# --- the real tools, when installed --------------------------------------------

real = pytest.mark.skipif(not all(B.find_tool(n) for n in B.TOOLS), reason="tectonic and poppler not installed")


@real
def test_real_one_page_build_is_clean(cfg, home):
    slug = role(cfg, home, cover=False)
    assert B.build(cfg, slug) == OK


@real
def test_real_two_page_resume_is_a_finding(cfg, home, capsys):
    slug = role(cfg, home, cover=False)
    (home / "career/src/resume-acme.tex").write_text(TEX.replace(r"\end{itemize}", r"\end{itemize}\newpage x"))
    assert B.build(cfg, slug) == FINDINGS
    assert "2 page(s), want 1" in capsys.readouterr().out


# --- the text checks on their own ------------------------------------------------

SRC = ("\\begin{zitemize}\n"
       "  \\item Portfolio across financial services, oil \\& gas, manufacturing, and agriculture\n"
       "  \\item Vuln mgmt, sustaining an ``A'' Tenable grade % a comment, not content\n"
       "  \\item Secrets via HashiCorp Vault-managed secrets (AppRole), and controlled egress\n"
       "\\end{zitemize}\n")


def test_item_tails_are_the_last_words_of_each_bullet():
    assert B.item_tails(SRC) == ["manufacturing and agriculture", "A Tenable grade", "and controlled egress"]


def test_pdf_punctuation_quotes_and_hyphen_glyphs_converge_with_the_source():
    rendered = ("• Portfolio across financial services, oil & gas, manufacturing, and agriculture\n"
                "• Vuln mgmt, sustaining an \u201cA\u201d Tenable grade\n"
                "• Secrets via HashiCorp Vault\u2011managed secrets (AppRole), and controlled egress\n")
    assert B.clipped(SRC, rendered) == []
    assert B.clipped(SRC, rendered.rsplit(", and", 1)[0]) == ["and controlled egress"]


def test_ligature_glyphs_are_not_clips():
    src = "\\begin{zitemize}\n  \\item findings from the fleet side.\n\\end{zitemize}\n"
    assert B.clipped(src, "\u2022 \ufb01ndings from the \ufb02eet side.\n") == []
    assert B.clipped(src, "\u2022 \ufb01ndings from the\n") == ["the fleet side."]


DOC = ("\\begin{document}\n\\begin{zitemize}\n  \\item Owns EDR end to end\n\\end{zitemize}\n"
       "\\skills{Certifications \\& Training:} CompTIA Security+ $\\cdot$ CDSA track, "
       "blue- and red-team labs\n\n\\vspace{0.3em}\n\\end{document}\n")


def test_the_last_paragraph_of_the_document_is_checked_too():
    assert B.final_tail(DOC) == "and red-team labs"
    cut = "\u2022 Owns EDR end to end\nCertifications & Training: CompTIA Security+ \u00b7\n"
    assert B.clipped(DOC, cut) == ["and red-team labs"]
    assert B.clipped(DOC, cut.rstrip("\n") + " CDSA track, blue- and red-team labs\n") == []


def test_layout_only_paragraphs_are_not_the_last_line():
    assert B.final_tail("\\begin{document}\nJane Doe\n\n\\vspace{1em}\\hfill\n\\end{document}") == "Jane Doe"
    assert B.final_tail("no document environment at all") is None


def test_lowest_text_reads_the_bbox():
    box = ('<page width="612.000000" height="792.000000">'
           '<word xMin="50" yMin="700" xMax="90" yMax="712.5">a</word>'
           '<word xMin="50" yMin="782" xMax="90" yMax="790.6">b</word></page>')
    assert B.lowest_text(box) == (790.6, 792.0)
    assert B.lowest_text("<page></page>") is None


def test_expand_inputs_inlines_sections(tmp_path):
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "exp.tex").write_text("\\item Inner bullet text here\n")
    top = tmp_path / "resume-x.tex"
    top.write_text("\\begin{zitemize}\\input{sections/exp}\\end{zitemize}\n")
    assert "Inner bullet text here" in B.expand_inputs(top)


def test_an_environment_name_is_never_read_as_the_last_words():
    """A list closing the document leaked its name: the tail read 'MITRE ATT&CK zitemize', which no PDF
    holds, so a fully visible resume read as clipped."""
    doc = "\\begin{document}\n\\begin{zitemize}\n  \\item Mapped detections to MITRE ATT\\&CK\n\\end{zitemize}\n\\end{document}\n"
    assert B.final_tail(doc) == "to MITRE ATT&CK"
    assert B.clipped(doc, "• Mapped detections to MITRE ATT&CK\n") == []
