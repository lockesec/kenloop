"""Acceptance: the demo walks the whole loop and every observation holds."""
import io
import json
import sys

from careerloop import cli

from conftest import rows


def cl(h, capsys, *argv, stdin=None, monkeypatch=None):
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    code = cli.main(["--home", str(h), *argv])
    return code, capsys.readouterr().out


def test_the_demo_directory_states_that_its_data_is_invented():
    from pathlib import Path
    marker = Path(__file__).resolve().parent.parent / "examples" / "demo" / "SYNTHETIC-DATA"
    assert marker.is_file()
    assert marker.read_text(encoding="utf-8").startswith("synthetic: true")


def test_the_loop(demo, capsys, monkeypatch):
    h = demo
    assert cl(h, capsys, "learn", "rebuild", "http-fundamentals", "--check")[0] == 0   # the seed is honest

    # 1-2. discover (senior filtered), score, close one
    code, out = cl(h, capsys, "jobs", "discover", "--board", "fixture", "--company", "example-folio",
                   "--intake", "--exclude-senior")
    assert code == 0 and "6 new role(s)" in out and "Senior Staff" not in out
    for slug, fit in (("web-developer", "4.5"), ("api-engineer", "3.5"), ("integration-engineer", "4.2")):
        assert cl(h, capsys, "jobs", "score", f"example-folio-{slug}", "--fit", fit)[0] == 0
    cl(h, capsys, "jobs", "status", "example-folio-support-engineer", "closed", "--reason", "filled")

    # 3. coverage
    for r in sorted((h / "roles").iterdir()):
        assert cl(h, capsys, "jobs", "check", r.name)[0] == 0
    cov = json.loads((h / "roles" / "example-folio-web-developer" / "coverage.json").read_text())
    miss = {m["term"]: m["held"] for m in cov["missing"]}
    assert miss == {"sql": True, "oauth": False, "cors": False}
    api = json.loads((h / "roles" / "example-folio-api-engineer" / "coverage.json").read_text())
    assert api["equiv"] == [{"term": "openapi", "via": "rest"}]

    # 4. demand
    assert cl(h, capsys, "jobs", "upskill")[0] == 0
    up = json.loads((h / "upskill.json").read_text())
    b = {x["name"]: x for x in up["buckets"]}
    sec = {i["term"]: i["count"] for i in b["Web security"]["items"]}
    assert sec == {"oauth": 3, "cors": 2, "csrf": 1, "rate limiting": 1, "tls": 1}   # closed role excluded
    assert "Unmapped: web/ops" in b and not any(i["noise"] for x in up["buckets"] for i in x["items"])
    assert [q["term"] for q in up["quick_wins"]] == ["cdn", "sql"]

    # 5-6. the seam into study
    code, out = cl(h, capsys, "learn", "gaps")
    assert 'suggest: careerloop learn plan web-security --from-gap "Web security"' in out
    cl(h, capsys, "learn", "plan", "web-security", "--from-gap", "Web security")
    syl = (h / "topics" / "web-security" / "syllabus.md").read_text()
    cl(h, capsys, "learn", "plan", "web-security", "--from-gap", "Web security")
    assert (h / "topics" / "web-security" / "syllabus.md").read_text() == syl            # idempotent
    assert syl.count("- web-security :: ") == 5

    # 7. an interactive session, scripted
    script = "c\nh\n2\n?\n?\nAccept\nm\no\nthe same headers repeat\nm\no\nHttpOnly\nh\no\n"
    code, out = cl(h, capsys, "learn", "quiz", "http-fundamentals", "--interactive", "--n", "4",
                   stdin=script, monkeypatch=monkeypatch)
    assert code == 0 and "4 item(s) recorded" in out
    new = rows(h, "http-fundamentals")[-4:]
    assert [r["concept"] for r in new] == ["semantics:caching-headers", "semantics:content-negotiation",
                                           "transport:header-compression", "semantics:cookies"]
    assert new[0]["result"] == "miss" and new[0]["note"] == "conflates no-cache with no-store"
    assert new[1]["hint_depth"] == 2
    assert cl(h, capsys, "learn", "rebuild", "http-fundamentals", "--check")[0] == 0

    # 8. graduation
    out = cl(h, capsys, "learn", "graduate", "http-fundamentals")[1]
    assert "Ready for facts.md (1)" in out and "semantics:status-codes" in out
    assert "drilled solo (1)" in out and "not retained (1)" in out

    # 9. the claims gate
    code, out = cl(h, capsys, "jobs", "check-claims", "resumes/draft-example-folio.md")
    assert code == 1 and "not held     oauth" in out and "1 violation(s)" in out
    assert cl(h, capsys, "jobs", "check-claims", "resumes/resume.md")[0] == 0

    # 10. next, as the loop turns
    out = cl(h, capsys, "next")[1]
    assert "NEXT: careerloop jobs tailor example-folio-integration-engineer" in out
    cl(h, capsys, "jobs", "status", "example-folio-integration-engineer", "applied")
    assert "learn graduate http-fundamentals --emit" in cl(h, capsys, "next")[1]
    emit = cl(h, capsys, "learn", "graduate", "http-fundamentals", "--emit")[1]
    with open(h / "facts.md", "a") as fh:
        fh.write(emit)
    out = cl(h, capsys, "next", "--all")[1]
    assert "NEXT: careerloop learn due http-fundamentals" in out and out.count("rule ") == 10

    # 11. reconcile: an empty board marks nothing; a later snapshot marks the vanished one
    (h / "fixtures" / "example-folio.json").write_text((h / "fixtures" / "example-folio-empty.json").read_text())
    assert cl(h, capsys, "jobs", "reconcile")[0] == 2
    (h / "fixtures" / "example-folio.json").write_text((h / "fixtures" / "example-folio-later.json").read_text())
    out = cl(h, capsys, "jobs", "reconcile")[1]
    assert "GONE    example-folio-platform-engineer" in out
    meta = json.loads((h / "roles" / "example-folio-platform-engineer" / "meta.json").read_text())
    assert meta["status"] == "found" and meta["posting_gone"] == "2030-03-20"
    code, out = cl(h, capsys, "doctor")
    assert code == 1 and "coverage is stale" in out          # the pasted facts changed what is held
    for r in sorted((h / "roles").iterdir()):
        cl(h, capsys, "jobs", "check", r.name)
    assert cl(h, capsys, "doctor")[0] == 0
