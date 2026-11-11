"""`jobs digest`: every board read once, postings bucketed by family, level, place and [wants],
newest first; an unreachable board is named, never read as no new jobs."""
import datetime as dt
import json

import pytest

from kenloop.career import config as CC
from kenloop.career import digest as D
from kenloop.career import sources as S
from kenloop.core.errors import NotEvaluable

from conftest import run

CONFIG = """[ats]
packs = ["web"]

[wants]
pay_min = 85000
pay_currency = "USD"

[sources]
targets = [{board = "fixture", org = "acme"}]

[digest]
families = [
  {name = "SOC / IR", match = ["soc", "incident response", "security analyst"], prefer = true},
  {name = "Security engineering", match = ["security engineer"], prefer = true},
  {name = "Threat intel", match = ["threat intel"]},
]
near = ["lafayette", "louisiana"]
exclude = ["product manager", "account executive"]
fresh_days = 14
"""

TODAY = dt.date(2030, 3, 20)


def _board(home, rows, org="acme"):
    (home / "fixtures").mkdir(exist_ok=True)
    (home / "fixtures" / f"{org}.json").write_text(json.dumps(rows))


@pytest.fixture
def dcfg(home):
    (home / "config.toml").write_text(CONFIG)
    return CC.load(home)


def _rows(dcfg, write=False):
    rows, report, code = D.run(dcfg, dcfg.digest, today=TODAY, write=write)
    return {r["title"]: r for r in rows}, report, code


def test_buckets_by_family_level_place_and_pay(dcfg, home):
    _board(home, [
        {"ext_id": "1", "title": "SOC Analyst II", "location": "Remote - US", "posted": "2030-03-19",
         "jd": "Salary $90,000 - $110,000 per year"},
        {"ext_id": "2", "title": "Senior Security Engineer", "location": "Lafayette, LA", "workplace": "hybrid"},
        {"ext_id": "3", "title": "Threat Intel Analyst", "location": "Remote"},
        {"ext_id": "4", "title": "Security Engineer", "location": "Austin, TX"},
        {"ext_id": "8", "title": "Security Engineer II", "location": "London, UK"},
        {"ext_id": "9", "title": "Director, Incident Response", "location": "Remote - US"},
        {"ext_id": "10", "title": "Product Manager, Detection", "location": "Remote - US"},
        {"ext_id": "5", "title": "Incident Response Analyst", "location": "Remote - US",
         "jd": "Base pay $50,000 - $60,000 per year"},
        {"ext_id": "6", "title": "Threat Intel Lead", "location": "Berlin"},
        {"ext_id": "7", "title": "Account Executive", "location": "Remote - US"},
    ])
    rows, report, code = _rows(dcfg)
    assert code == 0 and report["reached"] == 1 and report["outside"] == 2      # the AE and the PM
    assert rows["SOC Analyst II"]["bucket"] == "apply first"
    assert rows["SOC Analyst II"]["pay"] == "$90,000-$110,000"
    assert rows["Senior Security Engineer"]["bucket"] == "stretch"              # near, but senior
    assert rows["Threat Intel Analyst"]["bucket"] == "worth a look"             # not preferred, remote
    assert rows["Security Engineer"]["bucket"] == "worth a look"                # preferred, a move in the US
    assert rows["Security Engineer"]["reason"] == "you would have to move"
    assert rows["Security Engineer II"]["reason"] == "outside the US"
    assert rows["Director, Incident Response"]["reason"] == "a management role"
    assert rows["Incident Response Analyst"]["bucket"] == "set aside"           # below the $85k floor
    assert "pay" in rows["Incident Response Analyst"]["reason"]
    assert rows["Threat Intel Lead"]["bucket"] == "set aside"                   # neither family nor place


def test_remote_outside_the_us_does_not_fit(dcfg, home):
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - Canada"}])
    rows, _, _ = _rows(dcfg)
    assert rows["SOC Analyst"]["bucket"] == "set aside"
    assert rows["SOC Analyst"]["reason"] == "outside the US"


def test_new_means_not_in_a_previous_digest(dcfg, home):
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"}])
    rows, _, _ = _rows(dcfg, write=True)
    assert rows["SOC Analyst"]["new"]
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"},
                  {"ext_id": "2", "title": "Security Analyst", "location": "Remote - US"}])
    rows, _, _ = _rows(dcfg, write=True)
    assert not rows["SOC Analyst"]["new"] and rows["Security Analyst"]["new"]
    seen = json.loads((home / "digests" / "seen.json").read_text())
    assert seen["fixture:acme:1"] == "2030-03-20"
    assert (home / "digests" / "2030-03-20.md").is_file()


def test_dry_run_writes_nothing(dcfg, home):
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"}])
    _rows(dcfg, write=False)
    assert not (home / "digests").exists()


def test_an_unreachable_board_is_named_and_not_evaluable(dcfg, home, capsys):
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"}])
    dcfg.targets.append({"board": "fixture", "org": "gone"})               # no fixture file: unreachable
    rows, report, code = _rows(dcfg)
    assert code == 2 and report["reached"] == 1 and len(report["errors"]) == 1
    text = D.render(list(rows.values()), report, TODAY, dcfg.digest)
    assert "Boards: 1 of 2 reached." in text and "NOT REACHED: fixture:gone" in text


def test_render_lists_apply_first_newest_first_and_counts_set_aside(dcfg, home):
    _board(home, [
        {"ext_id": "1", "title": "SOC Analyst A", "location": "Remote - US", "posted": "2030-03-01"},
        {"ext_id": "2", "title": "SOC Analyst B", "location": "Remote - US", "posted": "2030-03-19"},
        {"ext_id": "3", "title": "Threat Intel Lead", "location": "Berlin"},
    ])
    rows, report, _ = _rows(dcfg)
    text = D.render(list(rows.values()), report, TODAY, dcfg.digest)
    assert text.index("SOC Analyst B") < text.index("SOC Analyst A")
    assert "| NEW | 1d |" in text
    assert "## Set aside (1)" in text and "- 1: outside the US" in text


def test_no_families_is_not_evaluable(home):
    (home / "config.toml").write_text('[sources]\ntargets = [{board = "fixture", org = "acme"}]\n')
    with pytest.raises(NotEvaluable, match="families"):
        D.run(CC.load(home), CC.load(home).digest, today=TODAY, write=False)


def test_config_rejects_a_bad_digest_table(home):
    (home / "config.toml").write_text('[digest]\nfamilies = [{name = "x"}]\n')
    with pytest.raises(NotEvaluable, match="match"):
        CC.load(home)
    (home / "config.toml").write_text('[digest]\nwhatever = 1\n')
    with pytest.raises(NotEvaluable, match="unknown"):
        CC.load(home)


def test_cli_digest_writes_the_file(home, capsys):
    (home / "config.toml").write_text(CONFIG)
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"}])
    code, out = run(home, "jobs", "digest", capsys=capsys)
    assert code == 0 and "## Apply first (1, 1 new)" in out.out
    assert (home / "digests" / "2030-03-20.md").is_file()


# ── Workday ──────────────────────────────────────────────────────────────────────────────────

def test_workday_target_needs_host_and_site(home):
    (home / "config.toml").write_text('[sources]\ntargets = [{board = "workday", org = "acme"}]\n')
    with pytest.raises(NotEvaluable, match="host"):
        CC.load(home)
    (home / "config.toml").write_text('[sources]\ntargets = [{board = "workday", org = "acme", '
                                      'host = "acme.wd1.myworkdayjobs.com", site = "External"}]\n')
    assert CC.load(home).targets[0]["site"] == "External"


def test_workday_reads_detail_and_reports_a_partial_listing(home, monkeypatch):
    cfg = CC.load(home)
    target = {"board": "workday", "org": "acme", "host": "acme.wd1.myworkdayjobs.com", "site": "External"}
    posts = [{"title": f"SOC Analyst {i}", "externalPath": f"/job/x_{i}", "locationsText": "Remote"}
             for i in range(S.WORKDAY_PAGE)]
    calls = []

    def fake_post(url, payload):
        calls.append(payload["offset"])
        return {"total": 500, "jobPostings": posts}

    def fake_get(url):
        return {"jobPostingInfo": {"jobDescription": "<p>Do SOC work</p>", "startDate": "2030-03-18",
                                   "location": "Remote - US", "externalUrl": "https://acme.example/" + url[-3:]}}

    monkeypatch.setattr(S, "_post_json", fake_post)
    monkeypatch.setattr(S, "_get_json", fake_get)
    res = S.fetch("workday", "acme", cfg, keyword="soc", target=target)
    assert res.status == "ok" and not res.complete and res.total == 500
    assert len(res.postings) == S.WORKDAY_MAX and calls[-1] == S.WORKDAY_MAX - S.WORKDAY_PAGE
    p = res.postings[0]
    assert p["posted"] == "2030-03-18" and p["location"] == "Remote - US" and "SOC work" in p["jd"]


def test_reconcile_never_marks_gone_from_a_partial_listing(home, monkeypatch, capsys):
    from kenloop.career import jobs as J
    cfg = CC.load(home)
    cfg.targets = [{"board": "workday", "org": "acme", "host": "acme.wd1.myworkdayjobs.com", "site": "External"}]
    assert J.intake(cfg, "acme", "SOC Analyst", job_id="/job/old_1", board="workday", org="acme")[1]
    monkeypatch.setattr(S, "fetch", lambda *a, **k: S.FetchResult(
        "ok", [{"ext_id": "/job/other", "title": "x"}], total=900, complete=False))
    J.reconcile(cfg)
    assert "GONE" not in capsys.readouterr().out


def test_iso_day_reads_board_dates_and_refuses_the_rest():
    assert S.iso_day("2030-03-18T09:00:00-04:00") == "2030-03-18"
    assert S.iso_day(1900000000000) == "2030-03-17"
    assert S.iso_day("Posted 3 Days Ago") is None and S.iso_day(True) is None and S.iso_day(None) is None


def test_workday_reads_detail_only_for_titles_the_caller_wants(home, monkeypatch):
    cfg = CC.load(home)
    target = {"board": "workday", "org": "acme", "host": "acme.wd1.myworkdayjobs.com", "site": "External"}
    monkeypatch.setattr(S, "_post_json", lambda url, payload: {"total": 2, "jobPostings": [
        {"title": "SOC Analyst", "externalPath": "/job/a"}, {"title": "Account Executive", "externalPath": "/job/b"}]})
    got = []
    monkeypatch.setattr(S, "_get_json", lambda url: got.append(url) or {"jobPostingInfo": {"jobDescription": "x"}})
    res = S.fetch("workday", "acme", cfg, keyword="security", target=target, detail_for=lambda t: "SOC" in t)
    assert res.complete and len(res.postings) == 2 and got == ["https://acme.wd1.myworkdayjobs.com/wday/cxs/acme/External/job/a"]


# ---- tracked roles, follow-ups, the top picks ----

def _role(home, slug, **meta):
    d = home / "roles" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "meta.json").write_text(json.dumps({"company": "Acme", "role": slug, "status": "found", **meta}))


def _digest(dcfg):
    rows, report, _ = D.run(dcfg, dcfg.digest, today=TODAY, write=False)
    return {r["title"]: r for r in rows}, D.render(rows, report, TODAY, dcfg.digest)


def test_an_applied_role_leaves_the_tables_for_one_line(dcfg, home):
    _board(home, [{"ext_id": "77", "title": "SOC Analyst", "location": "Remote - US"},
                  {"ext_id": "78", "title": "Security Analyst", "location": "Remote - US"}])
    _role(home, "acme-soc", status="applied", job_id="77", applied="2030-03-18")
    rows, text = _digest(dcfg)
    assert rows["SOC Analyst"]["tracked"]["status"] == "applied"
    assert "tracked" not in rows["Security Analyst"]
    assert "## Apply first (1, 1 new)" in text                       # the applied one is not counted there
    assert "- acme: SOC Analyst: already applied 03-18 (`acme-soc`)" in text
    start = text.split("## Start here")[1].split("## Apply first")[0]
    assert "Security Analyst" in start and "SOC Analyst" not in start


@pytest.mark.parametrize("status,label", [("passed", "passed"), ("rejected", "rejected"),
                                          ("interviewing", "interviewing")])
def test_closed_and_in_flight_roles_are_not_offered_again(dcfg, home, status, label):
    _board(home, [{"ext_id": "77", "title": "SOC Analyst", "location": "Remote - US"}])
    _role(home, "acme-soc", status=status, job_id="77")
    _, text = _digest(dcfg)
    assert "## Apply first (0, 0 new)" in text and f"SOC Analyst: {label} (`acme-soc`)" in text


def test_a_work_queue_role_stays_marked_tracked(dcfg, home):
    _board(home, [{"ext_id": "77", "title": "SOC Analyst", "location": "Remote - US", "url": "https://x.test/j/77"}])
    _role(home, "acme-soc", status="scored", job_id="77")
    _, text = _digest(dcfg)
    assert "[SOC Analyst](https://x.test/j/77) (tracked: scored)" in text
    assert "Already tracked" not in text
    assert "## Start here (0 new to apply to first)" in text         # tracked is not a new pick


def test_match_by_url_and_by_workday_requisition(dcfg, home):
    roles = [("by-url", {"company": "Other Name", "role": "r", "status": "applied",
                         "source_url": "https://acme.wd5.myworkdayjobs.com/en-US/Careers/job/Remote/SOC_R1/?src=x"}),
             ("by-req", {"company": "Acme Corp", "role": "r", "status": "applied", "job_id": "R30634"}),
             ("by-path", {"company": "Acme", "role": "r", "status": "found", "job_id": "/job/Remote/IR_R9"})]
    row = {"org": "acme", "ext_id": "/job/Remote/SOC_R1",
           "url": "https://acme.wd5.myworkdayjobs.com/Careers/job/Remote/SOC_R1"}
    assert D.tracked_role(row, roles)[0] == "by-url"
    assert D.tracked_role({"org": "acme", "ext_id": "/job/USA/Detection-Engineer_R30634", "url": ""}, roles)[0] == "by-req"
    assert D.tracked_role({"org": "acme", "ext_id": "/job/Remote/IR_R9", "url": ""}, roles)[0] == "by-path"
    assert D.tracked_role({"org": "acme", "ext_id": "/job/Remote/Other_R30635", "url": ""}, roles) is None


def test_the_same_job_id_at_another_company_is_not_a_match(dcfg, home):
    roles = [("globex-soc", {"company": "Globex", "role": "r", "status": "applied", "job_id": "77",
                             "source_url": "https://boards.test/globex/jobs/77"})]
    assert D.tracked_role({"org": "acme", "ext_id": "77", "url": "https://boards.test/acme/jobs/77"}, roles) is None
    assert D.tracked_role({"org": "globex", "ext_id": "77", "url": ""}, roles)[0] == "globex-soc"


def test_the_role_furthest_along_wins_when_a_posting_is_tracked_twice(dcfg, home):
    roles = [("a", {"company": "Acme", "role": "r", "status": "found", "job_id": "77"}),
             ("b", {"company": "Acme", "role": "r", "status": "applied", "job_id": "77"})]
    assert D.tracked_role({"org": "acme", "ext_id": "77", "url": ""}, roles)[0] == "b"


def test_follow_ups_at_7_14_and_30_days(dcfg, home):
    _board(home, [{"ext_id": "9", "title": "SOC Analyst", "location": "Remote - US"}])
    _role(home, "d3", status="applied", applied="2030-03-17")
    _role(home, "d9", status="applied", applied="2030-03-11", job_id="9")
    _role(home, "d15", status="applied", applied="2030-03-05")
    _role(home, "d31", status="applied", applied="2030-02-17")
    _role(home, "undated", status="applied")
    _role(home, "not-applied", status="scored")
    _, text = _digest(dcfg)
    ups = text.split("## Follow-ups (5 applied)")[1].split("## Set aside")[0]
    assert "(`d9`): day 9. Check the portal, and that the posting is still up. It was in today's listing." in ups
    assert "(`d15`): day 15. Send a short note if you have a recruiter contact." in ups
    assert "(`d31`): day 31. If no reply has come: `ken jobs status d31 closed --reason no_response`." in ups
    assert "(`undated`): the applied date is not recorded" in ups
    assert "- 1 applied in the last 7 days: nothing due yet." in ups
    assert "not-applied" not in ups
    d15 = next(ln for ln in ups.splitlines() if "`d15`" in ln)
    assert "today's listing" not in d15          # not seen today is not claimed either way


def test_no_follow_up_section_without_an_applied_role(dcfg, home):
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"}])
    assert "Follow-ups" not in _digest(dcfg)[1]


def test_start_here_shows_five_and_counts_the_rest(dcfg, home):
    _board(home, [{"ext_id": str(i), "title": f"SOC Analyst {i}", "location": "Remote - US",
                   "posted": f"2030-03-{10 + i:02d}"} for i in range(1, 8)])
    _, text = _digest(dcfg)
    start = text.split("## Start here (7 new to apply to first)")[1].split("## Apply first")[0]
    assert start.count("| SOC Analyst") == 5 and "2 more new under Apply first." in start
    assert "SOC Analyst 7 " in start and "SOC Analyst 2 " not in start          # newest first


def test_place_order_ranks_the_top_picks(home):
    (home / "config.toml").write_text(CONFIG.replace(
        'near = ["lafayette", "louisiana"]',
        'near = ["lafayette", "houston"]\nplace_order = ["lafayette", "remote", "houston"]'))
    cfg = CC.load(home)
    _board(home, [{"ext_id": "1", "title": "SOC Analyst H", "location": "Houston, TX", "posted": "2030-03-19"},
                  {"ext_id": "2", "title": "SOC Analyst R", "location": "Remote - US", "posted": "2030-03-18"},
                  {"ext_id": "3", "title": "SOC Analyst L", "location": "Lafayette, LA", "posted": "2030-03-01"}])
    _, text = _digest(cfg)
    start = text.split("## Start here")[1].split("## Apply first")[0]
    assert start.index("Analyst L") < start.index("Analyst R") < start.index("Analyst H")


def test_a_damaged_role_record_is_named_not_ignored(dcfg, home):
    _board(home, [{"ext_id": "1", "title": "SOC Analyst", "location": "Remote - US"}])
    (home / "roles" / "broken").mkdir(parents=True)
    (home / "roles" / "broken" / "meta.json").write_text("{not json")
    _, text = _digest(dcfg)
    assert "TRACKED ROLES NOT FULLY READ: 1 role record(s) are damaged" in text
