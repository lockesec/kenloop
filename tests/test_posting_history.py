"""A posting's history (changed on the board, reposted) and duplicates across boards.

Nothing is overwritten or deleted: a changed posting is marked and its stored text kept until
you re-intake it; a duplicate is reported and not taken in twice."""
import json

from kenloop import cli


def board(home, org, postings):
    (home / "fixtures").mkdir(exist_ok=True)
    (home / "fixtures" / f"{org}.json").write_text(json.dumps(postings))


def discover(home, capsys, org="acme", *extra):
    capsys.readouterr()
    code = cli.main(["--home", str(home), "jobs", "discover", "--board", "fixture", "--company", org,
                     "--intake", *extra])
    return code, capsys.readouterr().out


P1 = {"ext_id": "1", "title": "SOC Analyst", "location": "Remote", "jd": "Splunk and REST"}


def meta(home, slug):
    return json.loads((home / "roles" / slug / "meta.json").read_text())


def test_a_posting_whose_text_changed_on_the_board_is_marked_not_overwritten(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    old = (home / "roles" / "acme-soc-analyst" / "jd.txt").read_text()
    board(home, "acme", [dict(P1, jd="Splunk, REST and now Kafka")])
    _, out = discover(home, capsys)
    assert "CHANGED fixture:acme  1 SOC Analyst" in out and "jobs intake" in out
    assert (home / "roles" / "acme-soc-analyst" / "jd.txt").read_text() == old
    m = meta(home, "acme-soc-analyst")
    assert m["board_changed"] and any("changed on the board" in h for h in m["history"])
    _, out = discover(home, capsys)                 # the same change is reported, not re-recorded
    assert "CHANGED" in out
    assert sum("changed on the board" in h for h in meta(home, "acme-soc-analyst")["history"]) == 1


def test_an_unchanged_known_posting_is_quiet(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    _, out = discover(home, capsys)
    assert "CHANGED" not in out and "known" in out


def test_the_same_job_under_a_new_id_is_a_duplicate_and_not_taken_in_twice(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    board(home, "acme", [P1, dict(P1, ext_id="2")])
    _, out = discover(home, capsys)
    assert "DUPLICATE fixture:acme  2 SOC Analyst: same company, title and location as acme-soc-analyst" in out
    assert sorted(p.name for p in (home / "roles").iterdir()) == ["acme-soc-analyst"]


def test_a_job_back_after_it_closed_or_vanished_is_a_repost_and_is_taken_in(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    cli.main(["--home", str(home), "jobs", "status", "acme-soc-analyst", "closed", "--reason", "filled"])
    board(home, "acme", [dict(P1, ext_id="9")])
    _, out = discover(home, capsys)
    assert "REPOSTED fixture:acme  9 SOC Analyst: was acme-soc-analyst (closed)" in out
    new = [p.name for p in (home / "roles").iterdir() if p.name != "acme-soc-analyst"]
    assert len(new) == 1 and meta(home, new[0])["reposted_from"] == "acme-soc-analyst"


def test_the_same_job_on_two_boards_is_one_role(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    board(home, "acme-careers", [dict(P1, ext_id="77")])
    _, out = discover(home, capsys, "acme-careers")
    assert "DUPLICATE" not in out                     # another org name: not the same company
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n[sources]\naliases = {"acme-careers" = "acme"}\n')
    board(home, "acme-careers", [dict(P1, ext_id="78")])
    _, out = discover(home, capsys, "acme-careers")
    assert "DUPLICATE fixture:acme-careers  78" in out


# --- duplicates and history edge cases ---------------------------------------------------------------------------

def test_duplicates_inside_one_run_are_detected(home, capsys):
    (home / "config.toml").write_text(
        '[ats]\npacks = ["web"]\n[sources]\naliases = {"acme-careers" = "acme", "acme-jobs" = "acme"}\n'
        'targets = [{board = "fixture", org = "acme"}, {board = "fixture", org = "acme-careers"}, '
        '{board = "fixture", org = "acme-jobs"}]\n')
    for org, i in (("acme", "1"), ("acme-careers", "2"), ("acme-jobs", "3")):
        board(home, org, [dict(P1, ext_id=i)])
    capsys.readouterr()
    cli.main(["--home", str(home), "jobs", "discover", "--all", "--intake", "--keyword", "SOC"])
    out = capsys.readouterr().out
    assert out.count("DUPLICATE") == 2, out
    assert len(list((home / "roles").iterdir())) == 1
    assert "2 duplicate(s) not taken in" in out


def test_a_closed_role_does_not_mask_the_active_repost(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    cli.main(["--home", str(home), "jobs", "status", "acme-soc-analyst", "rejected"])
    board(home, "acme", [dict(P1, ext_id="9")])
    _, out = discover(home, capsys)
    assert "REPOSTED fixture:acme  9" in out
    repost = [p.name for p in (home / "roles").iterdir() if p.name != "acme-soc-analyst"][0]
    board(home, "acme", [dict(P1, ext_id="10")])
    _, out = discover(home, capsys)
    assert f"DUPLICATE fixture:acme  10 SOC Analyst: same company, title and location as {repost}" in out
    assert "REPOSTED fixture:acme  10" not in out


def test_an_active_role_is_found_whichever_order_the_roles_scan_in(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    cli.main(["--home", str(home), "jobs", "status", "acme-soc-analyst", "closed", "--reason", "filled"])
    board(home, "acme", [dict(P1, ext_id="9")])
    discover(home, capsys)
    repost = [p.name for p in (home / "roles").iterdir() if p.name != "acme-soc-analyst"][0]
    assert repost > "acme-soc-analyst"            # scan order puts the closed one first, then the active
    board(home, "acme", [dict(P1, ext_id="11")])
    _, out = discover(home, capsys)
    assert f"as {repost}" in out and "DUPLICATE" in out


def test_offer_and_on_hold_roles_are_active_for_duplicates(home, capsys):
    board(home, "acme", [P1])
    discover(home, capsys)
    for st in ("offer", "on-hold"):
        cli.main(["--home", str(home), "jobs", "status", "acme-soc-analyst", st])
        board(home, "acme", [dict(P1, ext_id=f"x-{st}")])
        _, out = discover(home, capsys)
        assert f"DUPLICATE fixture:acme  x-{st}" in out, (st, out)
        assert "REPOSTED" not in out


def test_a_whitespace_only_edit_is_not_a_change(home, capsys):
    board(home, "acme", [dict(P1, jd="Requirements\n- Splunk\n- REST\n\nBenefits\n- Pet insurance\n")])
    discover(home, capsys)
    for jd in ("Requirements  \r\n- Splunk\r\n- REST\r\n\r\n\r\nBenefits\r\n-   Pet   insurance\r\n",
               "\n\nRequirements\n\n- Splunk\n- REST\nBenefits\n- Pet insurance\n\n"):
        board(home, "acme", [dict(P1, jd=jd)])
        _, out = discover(home, capsys)
        assert "CHANGED" not in out and "known" in out, out
    board(home, "acme", [dict(P1, jd="Requirements\n- Splunk\n- REST\n- Kafka\nBenefits\n- Pet insurance\n")])
    _, out = discover(home, capsys)
    assert "CHANGED" in out


def test_an_old_role_with_a_raw_text_hash_is_compared_by_its_stored_text(home, capsys):
    board(home, "acme", [dict(P1, jd="Requirements\n- Splunk\n- REST\n")])
    discover(home, capsys)
    m = meta(home, "acme-soc-analyst")
    m["jd_sha"] = "0123456789abcdef"                 # a hash written by the old (raw-text) rule
    (home / "roles" / "acme-soc-analyst" / "meta.json").write_text(json.dumps(m))
    board(home, "acme", [dict(P1, jd="Requirements \n\n- Splunk\n- REST\n\n")])
    _, out = discover(home, capsys)
    assert "CHANGED" not in out


def test_a_board_that_lists_one_posting_twice_takes_it_in_once(home, capsys):
    """Paged search can repeat a posting across pages; the second copy is noted, not a crash."""
    board(home, "acme", [P1, dict(P1)])
    code, out = discover(home, capsys)
    assert code == 0, out
    assert "listed twice" in out
    assert len(list((home / "roles").iterdir())) == 1
