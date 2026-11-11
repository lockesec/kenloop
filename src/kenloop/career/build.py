"""Build a role's LaTeX resume (and cover letter) to PDF and check it fits.

``jobs build SLUG`` compiles with tectonic and checks each PDF: one page, every
bullet's last words present in the PDF text (a clipped bullet loses them), and
no text inside the bottom margin. Missing tools are NOT EVALUABLE, never a pass.

PDFs live in one folder per role under ``[build] pdf_root`` (default ``pdf``),
filed by whether the employer has them:

- ``sent/<slug>``  applied, interviewing, offer, rejected: the record of what was
  submitted. ``build`` refuses to write here, and nothing overwrites it.
- ``ready/<slug>`` everything not sent yet.
- ``old/<slug>``   roles that ended without sending (passed, closed).

``jobs status`` moves the folder when the role crosses a line.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from ..core.errors import FINDINGS, NOT_EVALUABLE, OK, NotEvaluable, Refused, UsageError
from . import roles as R

SENT_STATES = frozenset({"applied", "interviewing", "offer", "rejected"})
OLD_STATES = frozenset({"passed", "closed"})
TOOLS = ("tectonic", "pdfinfo", "pdftotext")
TOOL_HINTS = {"tectonic": "https://tectonic-typesetting.github.io (one binary; ~/.local/bin is searched)",
              "pdfinfo": "poppler-utils", "pdftotext": "poppler-utils"}
BOTTOM_MARGIN_PT = 18.0     # 0.25in, the print-safe floor
MARGIN_SLACK_PT = 2.0


def bucket(status: str) -> str:
    return "sent" if status in SENT_STATES else "old" if status in OLD_STATES else "ready"


def pdf_root(cfg) -> Path:
    raw = cfg.raw.get("build") or {}
    if not isinstance(raw, dict):
        raise NotEvaluable("config: `build` must be a table ([build])")
    root = raw.get("pdf_root", "pdf")
    if not isinstance(root, str) or not root.strip():
        raise NotEvaluable("config: `build.pdf_root` must be a path string")
    p = Path(root).expanduser()
    return p if p.is_absolute() else cfg.home / p


def _abs(cfg, rel: str) -> Path:
    p = Path(rel).expanduser()
    return p if p.is_absolute() else cfg.home / p


def show(cfg, p: Path) -> str:
    """A path as the record stores it: relative to the home when inside it, else absolute."""
    try:
        return p.resolve().relative_to(cfg.home.resolve()).as_posix()
    except ValueError:
        return str(p)


# --- filing -------------------------------------------------------------------

def plan_move(cfg, slug: str, meta: dict, status: str):
    """(src, dest) when the role's PDF folder must move for `status`, else None.
    A folder already at the destination is NOT EVALUABLE: nothing is overwritten."""
    cur = meta.get("pdf_dir")
    if not cur:
        return None
    src = _abs(cfg, cur)
    if not src.is_dir():
        return None
    dest = pdf_root(cfg) / bucket(status) / slug
    if src.resolve() == dest.resolve():
        return None
    if dest.exists():
        raise NotEvaluable(f"{slug}: {show(cfg, dest)} already exists; not overwriting it with {cur} "
                           "(move one aside by hand, then re-run)")
    return src, dest


def do_move(cfg, meta: dict, move) -> str:
    src, dest = move
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    meta["pdf_dir"] = show(cfg, dest)
    return meta["pdf_dir"]


# --- the checks (pure: text in, findings out) ---------------------------------

def expand_inputs(tex: Path, depth: int = 0) -> str:
    """The .tex source with every \\input{...} inlined (relative to the file's folder)."""
    text = tex.read_text(encoding="utf-8")
    if depth > 5:
        return text

    def sub(m: re.Match) -> str:
        name = m.group(1)
        f = tex.parent / (name if name.endswith(".tex") else name + ".tex")
        return expand_inputs(f, depth + 1) if f.exists() else ""
    return re.sub(r"\\input\{([^}]+)\}", sub, text)


def _plain_words(tex: str) -> list:
    t = re.sub(r"(?<!\\)%.*", " ", tex)
    t = re.sub(r"\\(begin|end)\{[^}]*\}", " ", t)           # an environment's name is not text
    t = re.sub(r"\\[a-zA-Z]+\*?", " ", t)
    t = t.replace("\\&", "&").replace("---", " ").replace("--", " ")
    t = re.sub(r"[{}$~`'\\]", " ", t)
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9&+./-]*", t)


def item_tails(source: str, n: int = 3) -> list:
    """The last `n` words of every \\item: what must be visible if nothing is clipped."""
    body = re.sub(r"(?<!\\)%.*", " ", source)
    out = []
    for chunk in re.split(r"\\item\b", body)[1:]:
        chunk = re.split(r"\\end\{|\\item\b|\\subsection|\\section", chunk)[0]
        words = _plain_words(chunk)
        if words:
            out.append(" ".join(words[-n:]))
    return out


_LAYOUT_ONLY = re.compile(r"^(\s|\\(vspace|hspace|hfill|vfill|newpage|clearpage|noindent|par|medskip|"
                          r"smallskip|bigskip|end|begin)\*?(\{[^}]*\})*)*$")


def final_tail(source: str, n: int = 3):
    """The last `n` words of the document's last text paragraph (a closing line that is not an
    \\item, such as a certifications line, is lost first when a page overflows)."""
    m = re.search(r"\\begin\{document\}(.*?)(\\end\{document\}|\Z)", source, re.S)
    if not m:
        return None
    body = re.sub(r"(?<!\\)%.*", " ", m.group(1))
    for para in reversed(re.split(r"\n\s*\n", body)):
        para = para.strip()
        if not para or _LAYOUT_ONLY.match(para):
            continue
        words = _plain_words(re.split(r"\\end\{(?!document)", para)[0] if para.startswith("\\end") else para)
        if words:
            return " ".join(words[-n:])
    return None


def _norm(text: str) -> str:
    """Word-level form for both sides: PDF text keeps punctuation, quotes and ligatures (U+FB01)."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u2011", "-").replace("\u2010", "-").replace("\u00ad", "")
    text = re.sub(r"-\s*\n\s*", "-", text)
    return " ".join(w.lower() for w in re.findall(r"[A-Za-z0-9]+", text))


def clipped(source: str, rendered: str) -> list:
    """Bullet endings, and the document's final words, that are not in the PDF text."""
    r = f" {_norm(rendered)} "
    tails = item_tails(source)
    last = final_tail(source)
    if last and last not in tails:
        tails.append(last)
    return [t for t in tails if f" {_norm(t)} " not in r]


def lowest_text(bbox_html: str):
    """(lowest word bottom, page height) from `pdftotext -bbox` output, or None."""
    h = re.search(r'<page[^>]*height="([0-9.]+)"', bbox_html)
    ys = [float(y) for y in re.findall(r'<word[^>]*yMax="([0-9.]+)"', bbox_html)]
    return (max(ys), float(h.group(1))) if h and ys else None


def judge(name: str, source: str, pages, text: str, bbox: str) -> tuple:
    """(verdict, findings) for one PDF. pages None = pdfinfo gave no count (a finding, not a pass)."""
    findings, verdict = [], "ok"
    if pages != 1:
        findings.append(f"{name}: {pages if pages is not None else 'unknown'} page(s), want 1")
        verdict = "OVER"
    lost = clipped(source, text)
    if lost:
        findings.append(f"{name}: {len(lost)} line ending(s) missing from the PDF (clipped?): "
                        + "; ".join(repr(x) for x in lost[:3]))
        verdict = "CLIPPED"
    low = lowest_text(bbox)
    if low is None:
        findings.append(f"{name}: no text positions from pdftotext -bbox, so the margin cannot be checked")
        verdict = verdict if verdict != "ok" else "UNCHECKED"
    elif low[0] > low[1] - BOTTOM_MARGIN_PT + MARGIN_SLACK_PT:
        findings.append(f"{name}: text runs {low[0] - (low[1] - BOTTOM_MARGIN_PT):.0f}pt into the bottom "
                        f"margin (lowest {low[0]:.1f} of {low[1]:.0f}pt); cut a line")
        verdict = verdict if verdict != "ok" else "MARGIN"
    return verdict, findings


# --- the build ----------------------------------------------------------------

def find_tool(name: str):
    found = shutil.which(name)
    if found:
        return found
    local = Path.home() / ".local" / "bin" / name
    return str(local) if local.exists() else None


def _run(argv) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def sources(cfg, slug: str, meta: dict, resume=None, cover=None) -> tuple:
    """(resume.tex, cover.tex or None). The resume is --resume, else the role's `resume` field, else the
    resume its last `jobs check` measured (`coverage_resume`). The cover is --cover, else the resume's
    sibling named cover-letter-<rest> for resume-<rest>."""
    rel = resume or meta.get("resume")
    if not rel and meta.get("coverage_resume"):
        rel = meta["coverage_resume"]
        print(f"  resume: {rel} (the one `jobs check` last measured; set the role's `resume` field to choose)")
    if not rel:
        raise UsageError(f"{slug}: no resume named for this role (set its `resume` field, or pass --resume)")
    rp = _abs(cfg, rel)
    if rp.suffix != ".tex":
        raise UsageError(f"{slug}: build compiles LaTeX; {rel} is not a .tex file")
    if not rp.is_file():
        raise UsageError(f"{slug}: resume {rel} does not exist")
    if cover:
        cp = _abs(cfg, cover)
        if not cp.is_file():
            raise UsageError(f"{slug}: cover letter {cover} does not exist")
        return rp, cp
    if rp.name.startswith("resume-"):
        cp = rp.with_name("cover-letter-" + rp.name[len("resume-"):])
        if cp.is_file():
            return rp, cp
    return rp, None


def build(cfg, slug: str, resume=None, cover=None, outdir=None, run=_run, tool=find_tool) -> int:
    meta = R.load(cfg, slug)
    status = meta.get("status", "")
    if outdir is None and status in SENT_STATES:
        raise Refused(f"{slug} is {status}: {meta.get('pdf_dir') or 'its sent folder'} is the record of what "
                         "was sent and is not rebuilt (pass --outdir to build a copy elsewhere)")
    rp, cp = sources(cfg, slug, meta, resume, cover)
    tools = {n: tool(n) for n in TOOLS}
    missing = [n for n, p in tools.items() if not p]
    if missing:
        print(f"{slug}: build NOT EVALUABLE, missing " + ", ".join(f"{n} ({TOOL_HINTS[n]})" for n in missing))
        return NOT_EVALUABLE
    if outdir is not None:
        out = _abs(cfg, outdir)
    else:
        move = plan_move(cfg, slug, meta, status)
        if move:
            do_move(cfg, meta, move)
        out = _abs(cfg, meta["pdf_dir"]) if meta.get("pdf_dir") else pdf_root(cfg) / bucket(status) / slug
    out.mkdir(parents=True, exist_ok=True)
    findings = []
    for src in [rp] + ([cp] if cp else []):
        r = run([tools["tectonic"], "-X", "compile", str(src), "--outdir", str(out)])
        pdf = out / (src.stem + ".pdf")
        if r.returncode != 0 or not pdf.exists():
            findings.append(f"{src.name}: tectonic failed (exit {r.returncode}): "
                            f"{(r.stderr or r.stdout or '').strip()[-300:]}")
            print(f"  {show(cfg, pdf)}: not built")
            continue
        m = re.search(r"^Pages:\s+(\d+)", run([tools["pdfinfo"], str(pdf)]).stdout or "", re.M)
        pages = int(m.group(1)) if m else None
        text = run([tools["pdftotext"], "-layout", str(pdf), "-"]).stdout or ""
        bbox = run([tools["pdftotext"], "-bbox", str(pdf), "-"]).stdout or ""
        source = expand_inputs(src)
        verdict, f = judge(src.name, source, pages, text, bbox)
        findings += f
        print(f"  {show(cfg, pdf)}: {pages if pages is not None else '?'} page(s), "
              f"{len(item_tails(source))} bullet(s) checked: {verdict}")
    if not cp:
        print("  (no cover letter found: resume only)")
    if outdir is None:                       # a copy built elsewhere is not the role's record
        meta["pdf_dir"] = show(cfg, out)
        R.history(meta, f"build {'CLEAN' if not findings else 'FINDINGS'}")
        R.save(cfg, slug, meta)
    for f in findings:
        print(f"FINDING {f}")
    print(f"{slug}: build {'CLEAN' if not findings else 'FINDINGS'} -> {show(cfg, out)}")
    return FINDINGS if findings else OK
