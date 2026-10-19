"""[wants] filters: what you want from a job, one module per field.

Each filter answers pass / fail (with the reason) / unknown; an unknown is kept unless that
filter's own `*_unknown` policy says `drop`. Nothing is deleted: an excluded posting is
named with its reason."""
import json

import pytest

from careerloop import cli, sources, wants
from careerloop import home as H
from careerloop.errors import NotEvaluable


def cfg_with(home, body):
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n' + body)
    return H.load_config(home)


# --- reading pay and workplace ----------------------------------------------------------------

@pytest.mark.parametrize("line,expect", [
    ("The base salary range is $120,000 - $150,000 per year.", (120000, 150000, "USD", "year")),
    ("Pay: $120K–$150K + equity", (120000, 150000, "USD", "year")),
    ("Salary: USD 95,000 to 110,000", (95000, 110000, "USD", "year")),
    ("£45,000 - £55,000 per annum", (45000, 55000, "GBP", "year")),
    ("$55 - $65 per hour", (55, 65, "USD", "hour")),
])
def test_pay_ranges_in_posting_text(line, expect):
    p = wants.pay_from_text("Intro line\n" + line + "\n")
    assert (p["min"], p["max"], p["currency"], p["interval"]) == expect
    assert p["source"].startswith("posting text")


@pytest.mark.parametrize("line", ["Monthly digital allowance ($185 AUD)", "New starter office set up ($800)",
                                  "We raised $120M in Series C", "401(k) match up to 4%", "Ages 21-65"])
def test_amounts_that_are_not_a_pay_range_are_not_read_as_one(line):
    assert wants.pay_from_text(line) is None


def test_ashby_and_lever_fields_are_read(monkeypatch):
    ashby = {"jobs": [{"id": "1", "title": "SOC", "location": "NYC", "jobUrl": "u", "descriptionPlain": "x",
                       "workplaceType": "Remote", "isRemote": True,
                       "compensation": {"compensationTiers": [{"components": [
                           {"compensationType": "EquityPercentage", "minValue": None, "maxValue": None},
                           {"compensationType": "Salary", "interval": "1 YEAR", "currencyCode": "USD",
                            "minValue": 130000, "maxValue": 160000}]}]}}]}
    monkeypatch.setattr(sources, "_get_json", lambda url: ashby)
    (p,) = sources._ashby("acme")
    assert p["workplace"] == "remote"
    assert p["pay"] == {"min": 130000, "max": 160000, "currency": "USD", "interval": "year",
                        "source": "board field"}
    lever = [{"id": "2", "text": "SOC", "categories": {"location": "Austin"}, "hostedUrl": "u",
              "descriptionPlain": "x", "workplaceType": "onsite",
              "salaryRange": {"min": 90000, "max": 100000, "currency": "USD", "interval": "per-year-salary"}}]
    monkeypatch.setattr(sources, "_get_json", lambda url: lever)
    (p,) = sources._lever("acme")
    assert p["workplace"] == "onsite" and p["pay"]["max"] == 100000


# --- the filters ------------------------------------------------------------------------------

def meta(**kw):
    return dict({"company": "Acme", "role": "SOC", "location": ""}, **kw)


def verdicts(cfg, m, jd=""):
    return {r["filter"]: (r["verdict"], r["reason"]) for r in wants.evaluate(cfg, m, jd)}


def test_workplace(home):
    cfg = cfg_with(home, '[wants]\nworkplace = ["remote"]\n')
    assert verdicts(cfg, meta(workplace="remote"))["workplace"][0] == "pass"
    v, why = verdicts(cfg, meta(workplace="hybrid"))["workplace"]
    assert v == "fail" and "hybrid" in why and "board field" in why
    assert verdicts(cfg, meta(location="Remote - US"))["workplace"][0] == "pass"     # location text
    v, why = verdicts(cfg, meta(location="Austin, TX"))["workplace"]
    assert v == "unknown" and "not stated" in why


def test_pay_floor_and_the_no_range_policy(home):
    cfg = cfg_with(home, '[wants]\npay_min = 120000\n')
    pay = {"min": 90000, "max": 110000, "currency": "USD", "interval": "year", "source": "board field"}
    v, why = verdicts(cfg, meta(pay=pay))["pay"]
    assert v == "fail" and "110,000" in why and "120,000" in why
    pay = dict(pay, max=130000)
    assert verdicts(cfg, meta(pay=pay))["pay"][0] == "pass"                  # the range reaches the floor
    assert verdicts(cfg, meta(), jd="no money talk here")["pay"][0] == "unknown"
    assert verdicts(cfg, meta(location="Remote US"), jd="Salary: $140,000 - $170,000")["pay"][0] == "pass"
    hourly = {"min": 50, "max": 55, "currency": "USD", "interval": "hour", "source": "board field"}
    v, why = verdicts(cfg, meta(pay=hourly))["pay"]
    assert v == "fail" and "2,080" in why                                  # converted, and says how
    eur = dict(pay, currency="EUR")
    v, why = verdicts(cfg, meta(pay=eur))["pay"]
    assert v == "unknown" and "EUR" in why


def test_an_unknown_is_kept_unless_its_own_policy_drops_it(home):
    keep = cfg_with(home, '[wants]\npay_min = 120000\n')
    assert wants.decide(keep, wants.evaluate(keep, meta(), ""))[0] == "keep"
    drop = cfg_with(home, '[wants]\npay_min = 120000\npay_unknown = "drop"\n')
    d, why = wants.decide(drop, wants.evaluate(drop, meta(), ""))
    assert d == "exclude" and "no pay range stated" in why and "pay_unknown = drop" in why
    flag = cfg_with(home, '[wants]\nworkplace = ["remote"]\nworkplace_unknown = "flag"\n')
    assert wants.decide(flag, wants.evaluate(flag, meta(location="Austin"), ""))[0] == "flag"


def test_no_wants_means_no_filter(home):
    cfg = cfg_with(home, "")
    assert wants.evaluate(cfg, meta(), "") == []
    assert wants.decide(cfg, [])[0] == "keep"


@pytest.mark.parametrize("body", ['[wants]\nworkplace = ["moon"]\n', '[wants]\npay_unknown = "maybe"\n',
                                  '[wants]\npay_min = "lots"\n', '[wants]\nnope = 1\n'])
def test_a_bad_wants_value_is_not_evaluable(home, body):
    with pytest.raises(NotEvaluable):
        cfg_with(home, body)


# --- the commands -----------------------------------------------------------------------------

BOARD = [
    {"ext_id": "1", "title": "Remote Analyst", "location": "Remote US", "jd": "Salary $130,000 - $150,000",
     "workplace": "remote"},
    {"ext_id": "2", "title": "Office Analyst", "location": "Austin, TX", "jd": "Salary $130,000 - $150,000",
     "workplace": "onsite"},
    {"ext_id": "3", "title": "Cheap Analyst", "location": "Remote US", "jd": "Salary $60,000 - $70,000",
     "workplace": "remote"},
    {"ext_id": "4", "title": "Quiet Analyst", "location": "Remote US", "jd": "We value focus.",
     "workplace": "remote"},
]


def board_home(home, body):
    (home / "fixtures").mkdir(exist_ok=True)
    (home / "fixtures" / "acme.json").write_text(json.dumps(BOARD))
    return cfg_with(home, body)


def test_discover_sets_aside_what_fails_with_the_reason_and_keeps_unknowns(home, capsys):
    board_home(home, '[wants]\nworkplace = ["remote"]\npay_min = 100000\n')
    assert cli.main(["--home", str(home), "jobs", "discover", "--board", "fixture", "--company", "acme",
                     "--intake"]) == 0
    out = capsys.readouterr().out
    assert "EXCLUDED fixture:acme  2" in out and "on-site" in out
    assert "EXCLUDED fixture:acme  3" in out and "70,000" in out
    taken = sorted(p.name for p in (home / "roles").iterdir())
    assert taken == ["acme-quiet-analyst", "acme-remote-analyst"]          # 4 is unknown pay: kept
    assert "2 excluded by [wants]" in out


def test_jobs_wants_reports_each_filter_with_its_unknown_count(home, capsys):
    board_home(home, "")
    cli.main(["--home", str(home), "jobs", "discover", "--board", "fixture", "--company", "acme", "--intake"])
    (home / "config.toml").write_text('[ats]\npacks = ["web"]\n[wants]\nworkplace = ["remote"]\n'
                                      'pay_min = 100000\npay_unknown = "drop"\n')
    capsys.readouterr()
    assert cli.main(["--home", str(home), "jobs", "wants"]) == 0
    out = capsys.readouterr().out
    assert "workplace: 3 pass · 1 fail · 0 unknown of 4 role(s)" in out
    assert "pay: 2 pass · 1 fail · 1 unknown of 4 role(s)" in out
    assert "acme-quiet-analyst" in out and "no pay range stated" in out
    # reporting changes nothing: every role is still there
    assert len(list((home / "roles").iterdir())) == 4


# --- found on live Huntress postings ------------------------------------------------------------

def test_a_currency_code_after_the_range_wins():
    p = wants.pay_from_text("Compensation Range: $110,000 to $140,000 AUD base plus bonus")
    assert (p["min"], p["max"], p["currency"]) == (110000, 140000, "AUD")


def test_a_bare_dollar_sign_outside_the_us_is_an_unstated_currency(home):
    cfg = cfg_with(home, '[wants]\npay_min = 120000\n')
    jd = "Compensation Range: $110,000 to $140,000 base plus bonus"
    v, why = verdicts(cfg, meta(location="Australia"), jd)["pay"]
    assert v == "unknown" and "currency" in why and "Australia" in why
    assert verdicts(cfg, meta(location="Remote US"), jd)["pay"][0] == "pass"


def test_greenhouse_escaped_html_is_stored_as_text(monkeypatch):
    escaped = "&lt;h3&gt;Requirements&lt;/h3&gt;&lt;ul&gt;&lt;li&gt;Splunk&lt;/li&gt;&lt;/ul&gt;"
    monkeypatch.setattr(sources, "_get_json", lambda url: {"jobs": [
        {"id": 1, "title": "SOC", "location": {"name": "Remote US"}, "absolute_url": "u", "content": escaped}]})
    (p,) = sources._greenhouse("acme")
    assert "<" not in p["jd"] and "## Requirements" in p["jd"] and "- Splunk" in p["jd"]


# --- benefits (each wanted benefit is its own row) --------------------------------------------

BENEFITS_POSTING = """## Requirements
- Splunk
## What we offer
- Unlimited paid time off
- Medical, dental and vision
- 401(k) with employer match
"""


def test_a_stated_benefit_passes_and_an_unmentioned_one_is_unknown_not_fail(home):
    cfg = cfg_with(home, '[wants]\nbenefits = ["unlimited pto", "pet insurance", "401k match"]\n')
    v = verdicts(cfg, meta(), BENEFITS_POSTING)
    assert v["benefit: unlimited pto"][0] == "pass" and "Unlimited paid time off" in v["benefit: unlimited pto"][1]
    assert v["benefit: 401k match"][0] == "pass"
    assert v["benefit: pet insurance"] == ("unknown", "not mentioned in the posting")


def test_a_contradicting_statement_fails(home):
    cfg = cfg_with(home, '[wants]\nbenefits = ["unlimited pto"]\n')
    v, why = verdicts(cfg, meta(), "## Benefits\n- 20 days of paid time off a year\n")["benefit: unlimited pto"]
    assert v == "fail" and "20 days of paid time off" in why


def test_a_benefit_named_only_in_requirements_does_not_count(home):
    cfg = cfg_with(home, '[wants]\nbenefits = ["pet insurance"]\n')
    jd = "## Requirements\n- Experience selling pet insurance\n"
    assert verdicts(cfg, meta(), jd)["benefit: pet insurance"][0] == "unknown"


def test_a_benefit_outside_the_catalogue_is_matched_as_written_and_extra_spellings_count(home):
    cfg = cfg_with(home, '[wants]\nbenefits = ["four day week"]\n[wants.benefit_phrases]\n'
                         '"four day week" = ["4-day work week", "32-hour week"]\n')
    assert verdicts(cfg, meta(), "## Perks\n- A 32-hour week\n")["benefit: four day week"][0] == "pass"
    assert verdicts(cfg, meta(), "## Perks\n- Four day week\n")["benefit: four day week"][0] == "pass"


def test_benefits_unknown_policy_applies_to_every_benefit_row(home):
    cfg = cfg_with(home, '[wants]\nbenefits = ["pet insurance"]\nbenefits_unknown = "drop"\n')
    d, why = wants.decide(cfg, wants.evaluate(cfg, meta(), BENEFITS_POSTING))
    assert d == "exclude" and "pet insurance" in why and "benefits_unknown = drop" in why


def test_a_legal_line_is_not_a_benefit_statement(home):
    cfg = cfg_with(home, '[wants]\nbenefits = ["equity"]\n')
    jd = "## Equal Opportunity\nWe are committed to pay equity.\n## Benefits\n- Health insurance\n"
    assert verdicts(cfg, meta(), jd)["benefit: equity"][0] == "unknown"


def test_equity_from_the_board_field_counts(home, monkeypatch):
    ashby = {"jobs": [{"id": "1", "title": "SOC", "location": "NYC", "jobUrl": "u", "descriptionPlain": "x",
                       "compensation": {"compensationTiers": [{"components": [
                           {"compensationType": "EquityPercentage", "minValue": None, "maxValue": None}]}]}}]}
    monkeypatch.setattr(sources, "_get_json", lambda url: ashby)
    (p,) = sources._ashby("acme")
    assert p["board_benefits"] == ["equity"]
    cfg = cfg_with(home, '[wants]\nbenefits = ["equity"]\n')
    v, why = verdicts(cfg, meta(board_benefits=["equity"]), "no text")["benefit: equity"]
    assert v == "pass" and "board field" in why


# --- pay ranges are read with their label, interval and currency ------------------

def _pay(cfg_home, jd, loc="Austin, TX", floor=120000):
    cfg = cfg_with(cfg_home, f'[wants]\npay_min = {floor}\n')
    return verdicts(cfg, meta(location=loc), jd)["pay"]


def test_a_stipend_range_before_the_salary_range_is_not_the_pay(home):
    v, why = _pay(home, "Relocation stipend: $1,500 - $2,500\nSalary: $150,000 - $170,000")
    assert v == "pass" and "170,000" in why


@pytest.mark.parametrize("jd,top", [
    ("Sign-on bonus: $10,000 - $20,000\nBase salary: $140,000 - $160,000", "160,000"),
    ("Equity grant worth $200,000 - $400,000\nBase: $90,000 - $100,000", "100,000"),
])
def test_bonus_and_equity_ranges_are_ignored_whichever_comes_first(home, jd, top):
    v, why = _pay(home, jd)
    assert top in why
    assert v == ("pass" if top == "160,000" else "fail")


def test_only_non_pay_ranges_is_unknown_and_says_so(home):
    v, why = _pay(home, "Relocation stipend: $1,500 - $2,500\nAnnual bonus: $10,000 - $20,000")
    assert v == "unknown" and "not pay" in why and "no pay range stated" in why


def test_monthly_and_weekly_ranges_are_annualised_and_say_so(home):
    v, why = _pay(home, "Pay: $10,000 - $12,000 per month")
    assert v == "pass" and "144,000" in why and "12" in why
    v, why = _pay(home, "Pay: $2,000 - $3,000 per week")
    assert v == "pass" and "156,000" in why and "52" in why
    v, why = _pay(home, "Pay: $5,000 - $8,000 a month", floor=120000)
    assert v == "fail" and "96,000" in why


def test_several_salary_ranges_are_judged_on_the_highest_and_say_so(home):
    jd = "NYC/SF: $100,000 - $110,000\nRemote US: $130,000 - $150,000\nSalary tiers by location"
    v, why = _pay(home, jd)
    assert v == "pass" and "150,000" in why and "2 pay ranges stated" in why and "highest" in why
    v, why = _pay(home, jd, floor=200000)
    assert v == "fail" and "2 pay ranges stated" in why


@pytest.mark.parametrize("jd", [
    "CAD $120,000 - $150,000", "AUD $100,000 - $120,000", "Salary (CAD): $120,000 - $150,000",
    "MXN $500,000 - $700,000", "HK$900,000 - $1,200,000", "NZD 150,000 - 170,000",
    "SGD 150,000 - 170,000", "₹5,000,000 - 7,000,000", "CHF 150,000 - 170,000",
])
def test_a_currency_before_or_labelled_is_not_read_as_usd(home, jd):
    v, why = _pay(home, jd)
    assert v == "unknown" and "USD" in why and "no conversion" in why


def test_currency_codes_and_symbols_are_read():
    for text, cur in [("CAD $120,000 - $150,000", "CAD"), ("Salary (CAD): $120,000 - $150,000", "CAD"),
                      ("HK$900,000 - $1,200,000", "HKD"), ("MXN 500,000 - 700,000", "MXN"),
                      ("JPY 9,000,000 - 12,000,000", "JPY"), ("US$120,000 - $150,000", "USD")]:
        assert wants.pay_from_text(text)["currency"] == cur, text


def test_a_bare_dollar_is_unknown_unless_the_location_says_us(home):
    jd = "Salary: $150,000 - $170,000"
    assert _pay(home, jd, loc="Toronto, ON")[0] == "unknown"
    assert _pay(home, jd, loc="")[0] == "unknown"
    assert "United States" in _pay(home, jd, loc="Toronto, ON")[1] or "US" in _pay(home, jd, loc="")[1]
    for loc in ("Remote - US", "United States", "USA", "Austin, TX", "Remote, California"):
        assert _pay(home, jd, loc=loc)[0] == "pass", loc
    assert _pay(home, "Salary: USD 150,000 - 170,000", loc="Toronto, ON")[0] == "pass"   # the posting names USD


# --- benefits: negation and word sense --------------------------------------------------------

def _ben(home, benefit, jd):
    cfg = cfg_with(home, f'[wants]\nbenefits = ["{benefit}"]\n')
    return verdicts(cfg, meta(), jd)[f"benefit: {benefit}"]


@pytest.mark.parametrize("jd", [
    "## Benefits\n- Not eligible for equity.\n",
    "## Benefits\nContractors are ineligible for stock options.\n",
    "## Benefits\n- Equity is not offered. No equity.\n",
])
def test_a_negated_equity_line_rules_equity_out(home, jd):
    v, why = _ben(home, "equity", jd)
    assert v == "fail" and ("equity" in why.lower() or "stock" in why.lower())


def test_negated_unlimited_pto_with_a_fixed_allowance_fails(home):
    v, why = _ben(home, "unlimited pto", "## Benefits\n- We do not offer unlimited PTO; 15 days of vacation.\n")
    assert v == "fail" and "do not offer unlimited PTO" in why


@pytest.mark.parametrize("jd", [
    "## About\nWe care about diversity, equity and inclusion.\n## Benefits\n- Health insurance\n",
    "## About\nPay equity is part of how we work.\n",
    "## Responsibilities\n- Manage the equity plan and cap table\n",
    "## Benefits\n- Diversity, equity and inclusion groups\n",
])
def test_equity_needs_a_compensation_sense(home, jd):
    assert _ben(home, "equity", jd)[0] == "unknown"


def test_equity_stated_as_compensation_passes(home):
    for line in ("Equity grant", "We offer equity", "Stock options", "Competitive equity package", "RSUs"):
        assert _ben(home, "equity", f"## Benefits\n- {line}\n")[0] == "pass", line
    assert _ben(home, "equity", "## Compensation\nBase plus equity compensation.\n")[0] == "pass"


def test_a_benefit_in_responsibilities_or_company_text_does_not_count(home):
    assert _ben(home, "pet insurance", "## Responsibilities\n- Sell pet insurance\n")[0] == "unknown"
    assert _ben(home, "pet insurance", "## About us\nWe sell pet insurance.\n")[0] == "unknown"


# --- unlimited PTO against a real posting ------------------------------------------------------

PALANTIR = """## Benefits
- Take what you need paid time off, not accrual based
- 2 weeks paid time off built into the end of each year (subject to team and business needs)
"""


def test_palantirs_open_pto_with_a_year_end_block_is_not_ruled_out(home):
    v, why = _ben(home, "unlimited pto", PALANTIR)
    assert v == "pass" and "Take what you need" in why


@pytest.mark.parametrize("phrase", ["Take what you need time off", "Not accrual based", "Untracked PTO",
                                    "Discretionary time off", "Open time off", "no set limit on vacation"])
def test_open_pto_spellings(home, phrase):
    assert _ben(home, "unlimited pto", f"## Benefits\n- {phrase}\n")[0] == "pass"


def test_a_fixed_allowance_rules_out_unlimited_pto_only_when_no_line_says_open(home):
    assert _ben(home, "unlimited pto", "## Benefits\n- 20 days of vacation\n")[0] == "fail"
    assert _ben(home, "unlimited pto", "## Benefits\n- 15 days of PTO per year\n")[0] == "fail"
    v, _ = _ben(home, "unlimited pto", "## Benefits\n- 20 days of vacation\n- Unlimited PTO for senior staff\n")
    assert v == "pass"
    # a shutdown or holiday block is not an allowance statement
    assert _ben(home, "unlimited pto", "## Benefits\n- 2 weeks company shutdown at year end\n")[0] == "unknown"


# --- workplace text: negation and word sense --------------------------------------------------

@pytest.mark.parametrize("loc,got", [
    ("New York (not remote)", None), ("Onsite - no remote", "onsite"), ("Non-remote, Boston", None),
    ("Hybrid / Remote", "remote/hybrid"), ("Remote or hybrid", "remote/hybrid"), ("Hybrid", "hybrid"), ("Remote - US", "remote"),
])
def test_workplace_text_negation_and_both_words(loc, got):
    assert wants.workplace_from_text({"location": loc})[0] == got


def test_remote_sensing_is_not_a_workplace():
    assert wants.workplace_from_text({"role": "Remote Sensing Analyst", "location": "Seattle, WA"}) == (None, None)
    assert wants.workplace_from_text({"role": "Remote Sensing Analyst", "location": "Remote"})[0] == "remote"


def test_remote_and_hybrid_together_is_unknown_not_remote(home):
    cfg = cfg_with(home, '[wants]\nworkplace = ["remote"]\n')
    v, why = verdicts(cfg, meta(location="Hybrid / Remote"))["workplace"]
    assert v == "unknown" and "remote and hybrid" in why


@pytest.mark.parametrize("loc", ["Remote, Latin America", "South America", "North America",
                                 "Hybrid OR Remote", "São Paulo, Brazil - IN OFFICE", "Remote ME region"])
def test_words_that_only_look_american_are_not_us_evidence(loc):
    from careerloop.wants import _us_evidence
    assert _us_evidence({"location": loc}) is False


@pytest.mark.parametrize("loc", ["Remote (US)", "Austin, TX", "Washington, DC", "Remote - CA",
                                 "Boston, MA 02110", "United States of America", "Remote, USA",
                                 "New York", "OR / WA"])
def test_real_us_locations_still_are(loc):
    from careerloop.wants import _us_evidence
    assert _us_evidence({"location": loc}) is True
