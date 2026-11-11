"""`[next] drop = true`: a role scored under the bar is dropped, and the drop says why (experience
length, or the named missing skills), which `jobs upskill` lists. Off by default."""
import json

import pytest

from kenloop.career import jobs as J
from kenloop.core.errors import UsageError


def meta(home, slug):
    return json.loads((home / "roles" / slug / "meta.json").read_text())


def drop_on(cfg):
    cfg.drop = True
    return cfg


def test_off_by_default_a_low_score_is_just_a_score(cfg, home):
    slug, _ = J.intake(cfg, "Acme", "Dev")
    J.score(cfg, slug, 3.0)
    m = meta(home, slug)
    assert m["status"] == "scored" and "drop" not in m


def test_under_the_bar_needs_a_reason_and_records_it(cfg, home):
    drop_on(cfg)
    slug, _ = J.intake(cfg, "Acme", "Dev")
    with pytest.raises(UsageError, match="--years"):
        J.score(cfg, slug, 3.5)
    assert meta(home, slug)["status"] == "found"                      # refused: nothing changed
    J.score(cfg, slug, 3.5, gaps="KQL, ZTNA (Zscaler, Cloudflare)", years=True)
    m = meta(home, slug)
    assert m["status"] == "passed" and m["drop"]["years"] is True
    assert m["drop"]["gaps"] == ["KQL", "ZTNA (Zscaler, Cloudflare)"]
    assert "DROPPED (< 4.0): experience length, KQL, ZTNA (Zscaler, Cloudflare)" in m["history"][-1]


def test_rescored_above_the_bar_is_back_in_play(cfg, home):
    drop_on(cfg)
    slug, _ = J.intake(cfg, "Acme", "Dev")
    J.score(cfg, slug, 3.0, gaps="KQL")
    J.score(cfg, slug, 4.5)
    m = meta(home, slug)
    assert m["status"] == "scored" and "drop" not in m


def test_a_reason_on_a_score_above_the_bar_is_refused(cfg, home):
    drop_on(cfg)
    slug, _ = J.intake(cfg, "Acme", "Dev")
    with pytest.raises(UsageError, match="not under the bar"):
        J.score(cfg, slug, 4.5, gaps="KQL")


def test_drop_lines_count_each_gap_by_company_and_years_apart(cfg, home):
    drop_on(cfg)
    a, _ = J.intake(cfg, "Acme", "Dev")
    b, _ = J.intake(cfg, "Globex", "Analyst")
    c, _ = J.intake(cfg, "Initech", "Engineer")
    J.score(cfg, a, 3.0, gaps="KQL, macOS")
    J.score(cfg, b, 3.0, gaps="KQL")
    J.score(cfg, c, 3.5, years=True)
    out = "\n".join(J.drop_lines(cfg))
    assert "3 role(s)" in out
    assert "- KQL: 2 role(s) (Acme, Globex)" in out and "- macOS: 1 role(s) (Acme)" in out
    assert out.index("- KQL") < out.index("- macOS")
    assert "experience length: 1 role(s) (Initech); not a study gap" in out
