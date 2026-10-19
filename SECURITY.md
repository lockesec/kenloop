# Security policy

## Supported versions

Only the latest release receives security fixes.

## What it touches

- It **reads and writes only its data directory** (`--home`, `$CAREERLOOP_HOME`
  or the XDG data dir), plus a resume path you name and any file you pass as
  `--jd FILE` (both read only). It never writes inside the package, and after
  `init` has written the `facts.md` template no command modifies it.
- It **makes network requests only in `jobs discover` and `jobs reconcile`**:
  HTTPS GETs to the public posting APIs of Greenhouse, Lever and Ashby, for the
  organisations you name. No credentials, no cookies, no telemetry. The
  `fixture` board reads a local file.
- Posting text from a board is third-party content. It is stored as plain text
  (HTML stripped) and only ever matched against keyword lists; it is never
  executed or rendered.

## Your data is personal

The data directory holds your resume, your facts sheet, where you applied and
how it went. Keep it out of public repositories. If you sync it with git, keep
the repository private (`careerloop init` writes a `.gitattributes` so study
logs merge cleanly between machines).

## If you use an AI tutor

[docs/tutor-rules.md](docs/tutor-rules.md) is text you give an assistant. A
question bank or tutor contract from someone else is advice the assistant will
follow: read it before you use it.

## Reporting

Please report security issues **privately**, using GitHub's "Report a vulnerability"
button on this repository (Security → Advisories). Do not open a public issue for a
vulnerability.
