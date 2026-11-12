"""iCIMS boards (found in use 2026-11-11: an application on an iCIMS board was found by hand, too late,
because the digest watched no iCIMS board). The fixtures copy the real markup: each result is an
iCIMS_Anchor whose title attribute reads "ID - Title", the page says "Page X of Y", and a posting page
embeds a schema.org JobPosting whose unknown address parts read "UNAVAILABLE"."""
import json

import pytest

from kenloop.career import config as CC
from kenloop.career import sources as S
from kenloop.core.errors import NotEvaluable

HOST = "careers-acme.icims.com"


def _card(job_id, title, host=HOST):
    return (f'<li class="iCIMS_JobCardItem"><div class="col-xs-12 title">'
            f'<a href="https://{host}/jobs/{job_id}/{title.lower().replace(" ", "-")}/job?in_iframe=1" '
            f'class="iCIMS_Anchor" title="{job_id} - {title}">'
            f'<span class="sr-only field-label">Job Title</span><h3 >\n{title}</h3></a></div></li>')


def _search(cards, page, of):
    return f'<div class="iCIMS_Paging">Page {page} of {of}</div><ul>{"".join(cards)}</ul>'


def _posting(title, posted="2026-11-03T05:00:00.000Z"):
    ld = {"@type": "JobPosting", "title": title, "datePosted": posted,
          "description": "<p>Detect &amp; respond. Salary: $120,000 - $150,000</p>",
          "jobLocation": [{"address": {"addressLocality": "Draper", "addressRegion": "UT",
                                       "addressCountry": "US", "streetAddress": "UNAVAILABLE"}}]}
    return f'<html><script type="application/ld+json">{json.dumps(ld)}</script></html>'


def test_the_listing_reads_anchors_titles_and_pages_and_skips_other_hosts():
    page = _search([_card(8562, "Principal Cloud Security Engineer"), _card(8562, "Principal Cloud Security Engineer"),
                    _card(9, "Phish Bait", host="evil.example.com"), _card(8561, "SOC Analyst &amp; Responder")], 1, 2)
    rows, pages = S.icims_listing(page, HOST)
    assert pages == (1, 2)
    assert [(i, t) for i, _, t in rows] == [("8562", "Principal Cloud Security Engineer"),
                                            ("8561", "SOC Analyst & Responder")]
    assert rows[0][1] == f"https://{HOST}/jobs/8562/principal-cloud-security-engineer/job"
    assert S.icims_listing("<html>no results</html>", HOST) == ([], None)


def test_a_posting_page_gives_title_date_location_and_text():
    ld = S.job_posting_ld(_posting("SOC Analyst"))
    assert ld["title"] == "SOC Analyst" and S.iso_day(ld["datePosted"]) == "2026-11-03"
    assert S._ld_location(ld) == "Draper, UT, US"                     # UNAVAILABLE parts are dropped
    assert S.job_posting_ld("<html></html>") == {} and S.job_posting_ld(
        '<script type="application/ld+json">{not json</script>') == {}


def test_icims_reads_every_page_and_details_only_family_titles(home, monkeypatch):
    pages = {0: _search([_card(1, "SOC Analyst"), _card(2, "Sales Executive")], 1, 2),
             1: _search([_card(3, "Detection Engineer")], 2, 2)}
    fetched = []

    def fake(url):
        fetched.append(url)
        if "/jobs/search" in url:
            return pages[int(url.rsplit("pr=", 1)[1])]
        return _posting(url.split("/jobs/")[1].split("/")[1].replace("-", " ").title())

    monkeypatch.setattr(S, "_get_text", fake)
    cfg = CC.load(home)
    target = {"board": "icims", "org": "acme", "host": HOST}
    res = S.fetch("icims", "acme", cfg, keyword="security", target=target,
                  detail_for=lambda t: "sales" not in t.lower())
    assert res.status == "ok" and res.complete and [p["ext_id"] for p in res.postings] == ["1", "2", "3"]
    soc = res.postings[0]
    assert soc["posted"] == "2026-11-03" and soc["location"] == "Draper, UT, US" and "Detect & respond" in soc["jd"]
    assert res.postings[1]["jd"] == "" and res.postings[1]["title"] == "Sales Executive"   # not a family: no detail
    assert sum("/jobs/search" in u for u in fetched) == 2 and not any("/jobs/2/" in u for u in fetched)
    assert "searchKeyword=security" in fetched[0]


def test_a_listing_cut_at_the_page_cap_is_partial(home, monkeypatch):
    monkeypatch.setattr(S, "ICIMS_MAX_PAGES", 1)
    monkeypatch.setattr(S, "_get_text", lambda url: _search([_card(1, "SOC Analyst")], 1, 5)
                        if "/jobs/search" in url else _posting("SOC Analyst"))
    res = S.fetch("icims", "acme", CC.load(home), keyword="soc",
                  target={"board": "icims", "org": "acme", "host": HOST})
    assert res.status == "ok" and not res.complete


def test_an_icims_target_needs_an_icims_host(home):
    (home / "config.toml").write_text('[sources]\ntargets = [{board = "icims", org = "acme"}]\n')
    with pytest.raises(NotEvaluable, match="icims"):
        CC.load(home)
    (home / "config.toml").write_text('[sources]\ntargets = [{board = "icims", org = "acme", host = "evil.example.com"}]\n')
    with pytest.raises(NotEvaluable, match="icims"):
        CC.load(home)
    (home / "config.toml").write_text(f'[sources]\ntargets = [{{board = "icims", org = "acme", host = "{HOST}"}}]\n')
    assert CC.load(home).targets[0]["host"] == HOST
