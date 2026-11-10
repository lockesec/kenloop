"""Printouts: a topic's reference sheet and session printouts, as pages to print and keep.

A tutor writes two kinds of page under topics/<slug>/print/: one reference sheet that grows with the
topic (the picture first, then terms with worked numbers and where each fits, easily-confused pairs,
formulas last as a summary of arithmetic already done, the attacker's view, what is still open) and
one printout per session (where the learner stood, what changed, the conversation as it was said).
Writing them takes judgement, so the tutor writes them; `ken print` only does the mechanical part.

    ken print SLUG --scaffold sheet          # write print/reference-sheet.md from the template
    ken print SLUG --scaffold session        # write print/session-<today>.md from the template
    ken print SLUG [--pdf]                   # render every print/*.md to .html (and .pdf)

The HTML is self-contained (inline style, no scripts, nothing fetched) and rendered by a small
Markdown reader in this module: headings, paragraphs, lists, tables, quotes, code, rules, bold,
italic, inline code and links. HTML in the source is shown as text, never run. A PDF is made only
with --pdf and only when a Chrome or Chromium binary is on PATH; when none is, the run says so and
the HTML is still there to print from a browser. Nothing here is evidence: no credit or schedule
reads it.
"""
from __future__ import annotations

import html
import re
import shutil
import subprocess

from .core import home as H
from .core import learn as L
from .core.errors import NOT_EVALUABLE, OK, UsageError

SHEET = """# Reference sheet: {title}

<!-- Grown after each session; print it and keep it beside you. Order: the picture first, then
     terms (each with a plain meaning, an example with real numbers, and where it fits), formulas
     LAST and only as a summary of arithmetic already done by hand. Mark what is sourced vs
     inferred, and settled vs open, where it matters. -->

## The picture

```
A -> B -> C
```

## Terms

### A. (piece of the picture)

| term | plain meaning | example with numbers | fits in |
|---|---|---|---|
| | | | |

## Easily confused

| this | is not | the difference |
|---|---|---|
| | | |

## Formulas (summary of what you already did by hand)

### (name)

- **In words:**
- **Worked:**
- **Formula:** `...`

## Attacker's view

## Still open for me

## Sources
"""

SESSION = """# Session: {title}, {date}

<!-- The conversation is copied, not summarised, so the reasoning and the corrections are both on
     paper. Tool calls and bookkeeping are left out. -->

| | |
|---|---|
| ideas | |
| mode | |
| close | three from memory, fuzzy point, felt |

## Where you stood

## What changed

<!-- One line per correction that mattered: what you said -> what is right -> why. -->

## Next session opens on

## The conversation

<!-- Each turn under a heading, "### You" or "### Tutor", kept verbatim. -->
"""

STYLE = """
body{font:11pt/1.45 Georgia,serif;max-width:7.2in;margin:0 auto;color:#111;background:#fff}
h1{font-size:18pt}h2{font-size:14pt;border-bottom:1px solid #999;margin-top:1.4em}
h2,h3,h4{page-break-after:avoid}h3{font-size:12pt;margin-top:1.2em}h4{font-size:11pt}
table{border-collapse:collapse;width:100%;font-size:9.5pt;margin:.5em 0}tr{page-break-inside:avoid}
th,td{border:1px solid #bbb;padding:3px 6px;text-align:left;vertical-align:top}th{background:#eee}
pre,code{font:9pt/1.35 Menlo,Consolas,monospace}pre{background:#f5f5f5;padding:6px;white-space:pre-wrap}
blockquote{border-left:3px solid #4a7;margin:.4em 0;padding:.1em .8em;background:#f3faf5}
@page{margin:.6in}
"""

BROWSERS = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
_RULE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_ITEM = re.compile(r"^(\s*)(?:[-*+]|(\d+)[.)])\s+(.*)$")
_ROW = re.compile(r"^\s*\|.*\|\s*$")
_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")


_SPAN = re.compile(r"(`+)(.+?)\1|\[([^\]]+)\]\(([^)\s]+)\)")


def _emphasis(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)


def _inline(text: str) -> str:
    """Escape and mark up. Code spans and links are cut out first, so nothing inside a code span is
    touched and emphasis never reaches into a link's address; plain text gets bold and italic."""
    out, at = [], 0
    for m in _SPAN.finditer(text):
        out.append(_emphasis(html.escape(text[at:m.start()], quote=False)))
        if m.group(1):
            out.append(f"<code>{html.escape(m.group(2), quote=False)}</code>")
        else:
            out.append(_link(_emphasis(html.escape(m.group(3), quote=False)), m.group(4)))
        at = m.end()
    out.append(_emphasis(html.escape(text[at:], quote=False)))
    return "".join(out)


def _link(label: str, url: str) -> str:
    if not re.match(r"(?i)^(?:https?://|mailto:|#|[\w./-]+$)", url):
        return f"{label} ({html.escape(url)})"          # no javascript: or data: links in a printout
    return f'<a href="{html.escape(url)}">{label}</a>'


def _cells(row: str) -> list:
    """Cells split on | outside code spans; an escaped \\| is a literal bar."""
    body = row.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    cells, cur, tick, i = [], "", 0, 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and body[i + 1:i + 2] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "`":
            n = len(body[i:]) - len(body[i:].lstrip("`"))
            tick = 0 if tick == n else (n if not tick else tick)
            cur += "`" * n
            i += n
            continue
        if ch == "|" and not tick:
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur.strip())
    return cells


_FENCED = re.compile(r"^[ \t]*(```+|~~~+).*?^[ \t]*\1[ \t]*$", re.M | re.S)


def _uncomment(md: str) -> str:
    """Drop HTML comments outside fenced code; a fence keeps its text as written."""
    out, at = [], 0
    for m in _FENCED.finditer(md):
        out.append(re.sub(r"<!--.*?-->", "", md[at:m.start()], flags=re.S))
        out.append(m.group(0))
        at = m.end()
    out.append(re.sub(r"<!--.*?-->", "", md[at:], flags=re.S))
    return "".join(out)


def render(md: str) -> str:
    """Markdown to an HTML fragment. HTML comments are dropped; any other HTML is shown as text."""
    lines = _uncomment(md).split("\n")
    out, i, para = [], 0, []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        fence = re.match(r"^\s*(```+|~~~+)", ln)
        if fence:
            flush()
            body, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith(fence.group(1)):
                body.append(lines[i])
                i += 1
            out.append("<pre><code>" + html.escape("\n".join(body), quote=False) + "</code></pre>")
            i += 1
            continue
        if not ln.strip():
            flush()
            i += 1
            continue
        h = _HEAD.match(ln)
        if h:
            flush()
            n = len(h.group(1))
            out.append(f"<h{n}>{_inline(h.group(2))}</h{n}>")
            i += 1
            continue
        if _RULE.match(ln):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if _ROW.match(ln) and i + 1 < len(lines) and _SEP.match(lines[i + 1]):
            flush()
            head = _cells(ln)
            rows, i = [], i + 2
            while i < len(lines) and _ROW.match(lines[i]):
                rows.append(_cells(lines[i]))
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
                       + "</tbody></table>")
            continue
        if ln.lstrip().startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + render("\n".join(quote)) + "</blockquote>")
            continue
        m = _ITEM.match(ln)
        if m:
            flush()
            tag = "ol" if m.group(2) else "ul"
            items, i = [], i
            while i < len(lines):
                m = _ITEM.match(lines[i])
                if m:
                    items.append(m.group(3))
                elif lines[i].startswith((" ", "\t")) and lines[i].strip() and items:
                    items[-1] += " " + lines[i].strip()      # a wrapped item continues
                else:
                    break
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def page(md: str) -> str:
    first = next((ln for ln in md.split("\n") if ln.strip()), "printout")
    title = html.escape(re.sub(r"^#+\s*", "", first).strip(), quote=False)
    return (f"<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>{title}</title>"
            f"<style>{STYLE}</style></head><body>\n{render(md)}\n</body></html>\n")


def _dir(cfg, slug):
    return L.tdir(cfg, slug) / "print"


def scaffold(cfg, slug, kind) -> int:
    conf = L.load_config(cfg, slug)
    title = conf.get("title", slug)
    d = _dir(cfg, slug)
    today = H.today().isoformat()
    p = d / ("reference-sheet.md" if kind == "sheet" else f"session-{today}.md")
    if p.exists():
        print(f"{p.relative_to(cfg.home).as_posix()} exists; nothing written")
        return OK
    d.mkdir(parents=True, exist_ok=True)
    H.write_text(p, (SHEET if kind == "sheet" else SESSION).format(title=title, date=today))
    print(f"wrote {p.relative_to(cfg.home).as_posix()}")
    return OK


def _browser():
    for b in BROWSERS:
        found = shutil.which(b)
        if found:
            return found
    return None


def make(cfg, slug, pdf=False) -> int:
    d = _dir(cfg, slug)
    srcs = sorted(d.glob("*.md")) if d.is_dir() else []
    if not srcs:
        print(f"nothing to print in {slug}: no print/*.md yet; "
              f"`{H.PROG} print {slug} --scaffold sheet|session` writes one from the template")
        return OK
    browser = _browser() if pdf else None
    made, failed = 0, []
    for src in srcs:
        out = src.with_suffix(".html")
        H.write_text(out, page(H.read_text(src, "printout")))
        line = f"  {out.relative_to(cfg.home).as_posix()}"
        if browser:
            target = src.with_suffix(".pdf")
            try:
                subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                                f"--print-to-pdf={target}", out.resolve().as_uri()],
                               check=True, capture_output=True, timeout=120)
                line += f", {target.name}"
            except (subprocess.SubprocessError, OSError) as e:
                failed.append(f"{src.name}: {type(e).__name__}")
        print(line)
        made += 1
    print(f"printed {made} page(s) from {d.relative_to(cfg.home).as_posix()}")
    if pdf and not browser:
        print("PDF not made: no Chrome or Chromium on PATH; open the .html and print it from a browser")
        return NOT_EVALUABLE
    if failed:
        print("PDF failed for " + "; ".join(failed) + " (the .html is there)")
        return NOT_EVALUABLE
    return OK


def commands(groups) -> None:
    a = groups[""].add_parser("print", help="a topic's reference sheet and session printouts as pages to print "
                                            "(print/*.md to .html, --pdf with Chrome); --scaffold writes a template")
    a.add_argument("slug")
    a.add_argument("--scaffold", choices=("sheet", "session"))
    a.add_argument("--pdf", action="store_true", help="also a PDF, when Chrome or Chromium is on PATH")

    def run(cfg, ns):
        L.need_topic(cfg, ns.slug)
        if ns.scaffold and ns.pdf:
            raise UsageError("--scaffold writes a template; print it after it is filled")
        return scaffold(cfg, ns.slug, ns.scaffold) if ns.scaffold else make(cfg, ns.slug, ns.pdf)
    a.set_defaults(run=run)
