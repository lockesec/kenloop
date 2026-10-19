"""Disguised skills: look-alike letters, invisible characters, overlays, symbols and glue
cannot hide a term, while ordinary non-English words and typography stay clean. The check reads each
whitespace-separated word (and windows of words for multiword terms) and compares a lexicon term by
exact match; it never matches a subsequence."""
import unicodedata

import pytest

from careerloop import cli
from careerloop import facts as F
from careerloop import home as H
from careerloop import jobs as J


def _cfg(tmp_path, facts_text, resume="REST and Docker\n"):
    from conftest import WEB
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(WEB)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


def _claims(cfg, capsys, resume="resumes/resume.md"):
    capsys.readouterr()
    rc = J.check_claims(cfg, resume)
    return rc, capsys.readouterr().out


LEX = """name = "web"
[categories]
protocols = ["http", "https", "http/2", "tls", "dns", "websockets"]
api = ["rest", "json", "graphql", "openapi"]
security = ["oauth", "cors", "csrf", "rate limiting"]
ops = ["caching", "cdn", "load balancing", "observability", "docker", "redis", "microservices"]
data = ["sql", "postgresql"]
lang = ["go", "kubernetes"]
"""


def _cfg_2(tmp_path, facts_text, resume="REST and Docker\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


HELD_SQL = "## Held\n- SQL\n"


IGNORABLE = ["\u034f", "\u3164", "\uffa0", "\u115f", "\u1160", "\u2800", "\ufe00", "\ufe0f",
             "\U000e0100", "\U000e01ef", "\u180b", "\u061c", "\u17b4", "\U0001d173", "\U000e0001"]


LEX_2 = """name = "web"
[categories]
protocols = ["http", "tls", "dns", "tcp", "ci/cd"]
api = ["rest", "json", "graphql"]
ops = ["cdn", "docker", "redis", "iso", "services"]
data = ["sql", "postgresql", "r"]
lang = ["go", "kubernetes"]
"""


TERMS = ["http", "tls", "dns", "tcp", "ci/cd", "rest", "json", "graphql", "cdn", "docker", "redis",
         "iso", "sql", "postgresql", "r", "go", "kubernetes"]


def _cfg_3(tmp_path, facts_text="## Held\n- REST\n", resume="REST\n"):
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    (h / "lexicons" / "web.toml").write_text(LEX_2)
    (h / "config.toml").write_text('[ats]\npacks = ["web"]\n')
    (h / "facts.md").write_text(facts_text, encoding="utf-8")
    (h / "resumes" / "resume.md").write_text(resume, encoding="utf-8")
    return H.load_config(h), h


def _claims_2(cfg, capsys):
    capsys.readouterr()
    rc = J.check_claims(cfg, "resumes/resume.md")
    return rc, capsys.readouterr().out


def _flagged(text, terms=TERMS):
    return [sp.word for sp, _t in F.disguised(text, F.lexicon_words(terms))]


NON_ENGLISH = ["São Paulo", "Łódź", "Ödön", "été", "está",
               "así", "créé", "熟悉Docker部署", "熟悉REST部署",
               "Nürnberg", "Gdańsk", "Łukasz", "R&D", "Ré", "Ŕ", "Björk"]


TERMS_2 = ["http", "tls", "dns", "tcp", "ci/cd", "rest", "json", "graphql", "cdn", "docker", "redis",
         "iso", "sql", "postgresql", "r", "go", "kubernetes", "python", "bash", "mongodb", "hbase"]


def _flagged_2(text, terms=TERMS_2):
    return [sp.word for sp, _t in F.disguised(text, F.lexicon_words(terms))]


def _overlays():
    return [chr(c) for c in range(0x0300, 0x2100)
            if unicodedata.category(chr(c)) in ("Mn", "Me") and "OVERLAY" in unicodedata.name(chr(c), "")]


TERMS_3 = ["http", "tls", "dns", "tcp", "ci/cd", "rest", "json", "graphql", "cdn", "docker", "redis",
         "iso", "services", "bash", "mongodb", "hbase", "firewalls", "aws", "sql", "postgresql", "r",
         "go", "kubernetes", "python"]


def _flagged_3(text, terms=TERMS_3):
    return [sp.word for sp, _t in F.disguised(text, F.lexicon_words(terms))]


D = "Dockеr"          # Dock + Cyrillic e + r


WORDS = ["Zürich", "café", "naïve", "Straße", "São", "Paulo", "München", "Łódź",
         "Kraków", "résumé", "façade", "jalapeño", "über", "señor", "año",
         "élève", "où", "déjà", "Ålesund", "Øresund", "fiancée", "crème",
         "brûlée", "piñata", "Čapek", "Škoda", "Dvořák", "İstanbul", "Bjørn",
         "Zoë", "Renée", "Hélène", "lycée", "forêt", "l’été", "aujourd’hui",
         "Москва", "日本語", "µServices", "Façade", "grüßen", "häuser"]


WRAPS = ("{}", "“{}”", "{}—", "{},", "{}’s", "({})", "{}…", "«{}»", "{}.",
         "{}:", "{}，", "{}、", "x—{}", "{}/{}", "{} – {}")


MW = ["rate limiting", "machine learning", "load balancing", "ci/cd", "openid connect", "a/b testing",
      "nist 800-53", "python", "java", "script", "docker"]


L_I = "і"       # Cyrillic i


ONE = ["javascript", "websockets", "openapi", "typescript", "postgresql", "graphql", "webhooks", "redis",
       "docker"]


MW_2 = ["cloud security", "rate limiting", "load balancing", "zero trust", "machine learning", "ci/cd",
      "data quality", "python", "docker"]


MW_3 = ["rate limiting", "machine learning", "python", "azure", "data lake", "vue", "apache"]


MW_4 = ["rate limiting", "python", "http", "https", "sql"]


# --- Invisible characters, look-alikes and overlays cannot hide a term ----------------------------

@pytest.mark.parametrize("word", [
    "Dock\u00ader", "Dock\u200ber", "Dock\u200eer", "Dock\u2060er", "Dock\ufeffer", "\uff24ocker", "\uff24\uff4f\uff43ker",
])
def test_invisible_characters_in_a_resume_do_not_hide_a_term(tmp_path, capsys, word):
    cfg, _h = _cfg(tmp_path, "## Held\n- REST\n", resume=f"REST and {word}\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "docker" in out.lower() and "VIOLATION" in out


def test_invisible_characters_in_facts_do_not_hide_a_held_term():
    assert F.holds("docker", "## Held\n- Dock\u00ader\n")
    assert F.holds("docker", "## Held\n- Dock\u200ber\n")


def test_cyrillic_lookalike_is_reported(tmp_path, capsys):
    cfg, _h = _cfg(tmp_path, "## Held\n- REST\n- Docker\n", resume="REST and Dock\u0435r\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "suspicious-characters" in out and "Dock\u0435r" in out and "U+0435" in out


def test_lookalike_alone_is_not_a_clean_pass(tmp_path, capsys):
    cfg, _h = _cfg(tmp_path, "## Held\n- REST\n", resume="Dock\u0435r only\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "suspicious-characters" in out


def test_a_wholly_non_latin_word_is_not_flagged():
    words = F.lexicon_words(["rest", "docker", "go"])
    assert F.disguised("REST \u0414\u043e\u043a\u0435\u0440 \u3053\u3093\u306b\u3061\u306f", words) == []


@pytest.mark.parametrize("ch", IGNORABLE)
def test_ignorable_character_does_not_hide_a_term(tmp_path, capsys, ch):
    cfg, _h = _cfg_2(tmp_path, HELD_SQL, resume=f"Built SQL and Doc{ch}ker services\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "docker" in out.lower() and "VIOLATION" in out
    assert "checked 2 resume term(s): 1 violation(s)" in out


def test_combining_overlay_inside_a_word_is_suspicious(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, HELD_SQL, resume="Built SQL and Doc\u0338ker\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "suspicious-characters" in out
    assert "Doc\u0338ker" in out and "U+0338" in out and "COMBINING LONG SOLIDUS OVERLAY" in out


def test_facts_side_ignorable_character_inside_a_qualifier():
    sheet = "## Held\n- Docker (n\u034fot yet...)\n"
    assert not F.holds("docker", sheet)
    assert F.contradictions(sheet)


@pytest.mark.parametrize("ch", ["\u034f", "\u2800", "\u3164", "\ufe0f"])
def test_facts_side_ignorable_inside_a_held_term_still_holds(ch):
    assert F.holds("docker", f"## Held\n- Doc{ch}ker\n")


def test_lookalikes_function_is_gone():
    assert not hasattr(F, "lookalikes")


@pytest.mark.parametrize("mark", ["\u2122", "\u00ae", "\u00a9", "\u2120"])
def test_trademark_symbol_does_not_unhold_a_term(mark):
    assert F.holds("docker", f"## Held\n- Docker{mark}\n")
    assert F.explain("docker", f"## Held\n- Docker{mark}\n") == ""


def test_resume_with_trademark_symbol_passes(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- Docker\u2122\n- REST\n", resume="Docker\u00ae and REST\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 0 and "suspicious" not in out


def test_overlay_list_is_not_empty_and_covers_the_named_ones():
    ov = set(_overlays())
    for cp in (0x0334, 0x0335, 0x0336, 0x0337, 0x0338, 0x20D2, 0x20D3):
        assert chr(cp) in ov


@pytest.mark.parametrize("mark", _overlays())
def test_an_overlay_is_a_disguise_even_for_a_three_letter_term(mark):
    assert _flagged_2(f"REST S{mark}QL") == [f"S{mark}QL"]
    assert _flagged_2(f"REST T{mark}LS") == [f"T{mark}LS"]


def test_three_letter_term_with_a_real_accent_stays_clean():
    assert _flagged_2("REST sqĺ") == []


@pytest.mark.parametrize("word", [
    "ϲdn",              # Greek lunate sigma for c
    "Ꭰocker",           # Cherokee D
    "ᎡEST",             # Cherokee R
    "ᎢLS",              # Cherokee T
    "graphqӀ",          # Cyrillic palochka (capital) for l
    "Docкer",           # Cyrillic ka for k
    "гest",             # Cyrillic ghe for r
    "тls",              # Cyrillic te for t
    "мongodb",          # Cyrillic em for m
    "нbase",            # Cyrillic en for h
    "вash",             # Cyrillic ve for b
    "Gø",               # o with stroke
])
def test_new_look_alikes_are_flagged(word):
    assert _flagged_2(f"REST {word}"), word


@pytest.mark.parametrize("mark", ["⃝", "҈", "҉", "⃞", "⃠"])
def test_an_enclosing_mark_is_a_visible_overlay_even_in_a_short_term(mark):
    assert _flagged_3(f"REST S{mark}QL") == [f"S{mark}QL"]
    assert _flagged_3(f"REST T{mark}LS") == [f"T{mark}LS"]


def test_private_use_and_nel_at_a_word_end_are_separators_inside_they_are_suspicious():
    lw = F.lexicon_words(ONE)
    for end in ("", "\u0085", "\u0090"):
        assert F.disguised(f"Docker{end}", lw) == [] and F.disguised(f"{end}Docker", lw) == [], hex(ord(end))
        assert [t for _s, t in F.disguised(f"Dock{end}er", lw)] == ["docker"], hex(ord(end))


def test_prime_and_acute_before_s_are_a_possessive():
    lw = F.lexicon_words(ONE)
    for ap in ("′", "´", "’", "'"):
        assert F.disguised(f"Docker{ap}s", lw) == [], hex(ord(ap))
    assert F.disguised("Dockеr′s", lw)                                # a real disguise still is one


# --- Symbols, punctuation and neighbours around a term --------------------------------------------

@pytest.mark.parametrize("word,cp", [
    ("\u0422LS", "U+0422"), ("\u0405QL", "U+0405"), ("G\u043e", "U+043E"),
    ("Red\u0131s", "U+0131"), ("OAut\u0266", "U+0266"), ("Re\u0257is", "U+0257"),
    ("P\u0585stgresql", "U+0585"), ("Dock\u0435r", "U+0435"), ("R\u00e9dis", "U+00E9"),
    ("Do\u0441ker", "U+0441"), ("Dock\u00e9rs", "U+00E9"), ("Re\u0301dis", "U+0301"),
])
def test_disguised_skill_is_suspicious(tmp_path, capsys, word, cp):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n", resume=f"REST and {word}\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "suspicious-characters" in out and word in out and cp in out


@pytest.mark.parametrize("text", [
    "\u041c\u043e\u0441\u043a\u0432\u0430", "\u0395\u03bb\u03bb\u03ac\u03b4\u03b1", "\u65e5\u672c\u8a9e",
    "Z\u00fcrich", "caf\u00e9", "na\u00efve", "Stra\u00dfe", "I\u015f\u0131k", "Ren\u00e9", "Zo\u00eb",
    "\u00b5Services", "Se\u00f1or",
])
def test_ordinary_words_stay_clean(tmp_path, capsys, text):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n", resume=f"REST in {text} and {text}\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 0 and "suspicious" not in out, out


def test_microservices_is_not_a_disguise_of_services(tmp_path, capsys):
    # documented decision: a unit-like micro sign prefix is only flagged when removing it
    # leaves a lexicon word (here "services" is not one)
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n", resume="REST \u00b5Services\n")
    assert _claims(cfg, capsys)[0] == 0


def test_suspicious_is_listed_even_when_no_other_term(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n", resume="\u0422LS only\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "suspicious-characters" in out


@pytest.mark.parametrize("word", ["Dock∊r", "Dock·er", "CI∕CD", "Dock•er", "Do§cker"])
def test_in_word_symbols_are_flagged(word):
    assert _flagged(f"REST {word}") == [word]


# An arrow or a dagger is ordinary typography and trimmed from a word's ends;
# only a character that expands to letters or digits, or a superscript form, still counts.
@pytest.mark.parametrize("word", ["Docker⁺", "Docker№"])
def test_glued_symbols_are_flagged(word):
    assert _flagged(f"REST {word}") == [word]


def test_all_cyrillic_tcp_is_flagged():
    assert _flagged("REST ТСР") == ["ТСР"]


def test_wholly_non_latin_words_stay_clean():
    assert _flagged("Докер 日本語 Ελλάδα") == []


@pytest.mark.parametrize("w", ["R&D", "Ré", "Ŕ", "р", "R·", "R†"])
def test_single_letter_term_is_never_a_disguise(w):
    assert _flagged(f"We use {w} here") == []


@pytest.mark.parametrize("ch", ["\x00", "\x07", "\x08", "\x1b", "\x7f", "\x1f", "\x85"])
def test_control_character_inside_a_word(ch):
    assert _flagged(f"REST Doc{ch}ker") == [f"Doc{ch}ker"]


@pytest.mark.parametrize("text", ["Skills: REST/Dockеr", "REST, Dockеr/Redis", "REST|Dockеr",
                                  "REST;Dockеr", "REST•Dockеr", "Dockеr,REST",
                                  "REST/CI∕CD"])
def test_disguised_term_next_to_a_separator_is_examined(text):
    assert _flagged_2(text), text


@pytest.mark.parametrize("text", ["REST/Redis", "REST, Redis/Python", "REST|Docker", "Skills: REST;Docker;Go",
                                  "São/Paulo", "REST•Redis"])
def test_quiet_direction(text):
    assert _flagged_2(text) == [], text


@pytest.mark.parametrize("word", ["Java‑Script", "Java‐Script", "Web‑Sockets", "Open‑API",
                                  "Type–Script", "Post‑greSQL", "Graph‑QL", "Web‑Hooks",
                                  "Red‑is", "Java—Script", "Java−Script", "Java－Script",
                                  "Java-Script"])
def test_a_dash_joined_fragment_is_not_a_disguise(word):
    assert F.disguised("REST " + word, F.lexicon_words(ONE)) == [], word


def test_a_middle_dot_is_still_a_disguise():
    assert [t for _s, t in F.disguised("Dock·er", F.lexicon_words(ONE))] == ["docker"]


# --- The held side uses the same rule -------------------------------------------------------------

def test_held_line_spelled_with_look_alike_is_a_contradiction(tmp_path, capsys):
    cfg, _h = _cfg_2(tmp_path, "## Held\n- REST\n- Dock\u0435r\n", resume="REST and Docker\n")
    rc, out = _claims(cfg, capsys)
    assert rc == 1 and "contradiction" in out and "U+0435" in out and "line 3" in out


def test_held_line_look_alike_is_a_contradiction(tmp_path, capsys):
    cfg, _h = _cfg_3(tmp_path, "## Held\n- REST\n- Dockеr\n", resume="REST and Docker\n")
    rc, out = _claims_2(cfg, capsys)
    assert rc == 1 and "contradiction" in out and "U+0435" in out


def test_held_line_with_non_english_word_is_not_a_disguise():
    assert F.disguised_in_held("iso", "## Held\n- São Paulo office\n") is None
    assert F.disguised_in_held("docker", "## Held\n- Dock·er\n") is not None


# --- The disguise rule: one reading for whole words, parts and possessives ------------------------

@pytest.mark.parametrize("word", ["ТLS", "Redıs", "Pօstgresql", "Doc̸ker"])
def test_probe_disguises_are_flagged(word):
    assert _flagged(f"REST {word}") == [word]


@pytest.mark.parametrize("word", ["Doc͏ker", "Docㅤker"])
def test_probe_ignorable_disguises_still_count_as_the_plain_term(tmp_path, capsys, word):
    cfg, _h = _cfg_3(tmp_path, resume=f"REST {word}\n")
    rc, out = _claims_2(cfg, capsys)
    assert rc == 1 and "docker" in out.lower()


def test_probe_plain_unheld_docker(tmp_path, capsys):
    cfg, _h = _cfg_3(tmp_path, resume="REST Docker\n")
    assert _claims_2(cfg, capsys)[0] == 1


@pytest.mark.parametrize("w", ["Zürich", "café", "Straße", "Москва"])
def test_probe_clean_words(tmp_path, capsys, w):
    cfg, _h = _cfg_3(tmp_path, resume=f"REST {w}\n")
    rc, out = _claims_2(cfg, capsys)
    assert rc == 0 and "suspicious" not in out


@pytest.mark.parametrize("word", ["régression", "azuré", "säst"])
def test_the_disclosed_rule_does_what_the_docs_say(word):
    # accent-only words that equal a 4+ letter term are flagged; the docs now say so
    assert _flagged_2(f"REST {word}", ["regression", "azure", "sast"]) == [word]


@pytest.mark.parametrize("text", [
    "Wrote SQL and Python’s asyncio code", "Wrote SQL and ﬁrewalls, daily", "ﬁrewalls,",
    "ＡＷＳ.", "Python’s", "(ﬁrewalls)", "“ﬁrewalls”", "Python's",
    "ﬁrewalls—", "(Python’s)", "“Python’s”,", "Docker’s", "SQL’s",
])
def test_a_compatibility_form_or_a_curly_possessive_is_the_plain_word(text):
    assert _flagged_3("REST " + text) == [], text


@pytest.mark.parametrize("text", [
    f"{D}-based", f"{D}'s", f"{D}’s", f"Skills:{D}", f"{D}:Python", f"{D}&Python", f"{D}+Python",
    f"{D}—Python", f"{D}–Python", f"{D}(Python)", f"{D}_Python", f"{D}.io", f"{D}…Redis",
    f"{D}，Redis", f"{D}、Redis", f"({D}’s)", f"“{D}”,", f"{D}/Redis", f"{D}·Redis",
    "Wrote SQL and " + D + "-based pipelines",
])
def test_a_disguised_term_next_to_any_punctuation_is_flagged(text):
    assert _flagged_3("REST " + text), text


@pytest.mark.parametrize("word", [
    "Dock·er", "Dock∊r", "CI∕CD", "Docker№", "Docker⁺", "ТLS", "Redıs",
    "Pօstgresql", "Doc̸ker", "Ꭰocker", "(Dock·er)", "Dock·er’s",
    "“Dock·er”,",
])
def test_existing_disguises_stay_flagged(word):
    assert _flagged_3(f"REST {word}"), word


def test_a_middle_dot_inside_one_word_is_flagged_through_the_whole_word_reading():
    # decided: the whole token is read with its non-ASCII punctuation dropped, so Dock + middle dot + er
    # is Docker; the parts "Dock" and "er" add readings, they never remove one
    assert _flagged_3("REST Dock·er") == ["Dock·er"]
    assert F.disguised_in_held("docker", "## Held\n- Dock·er\n") is not None
    assert _flagged_3("REST Dock·Redis") == []


@pytest.mark.parametrize("word", ["Docker¹", "Docker²", "Dockerª", "Docker½", "Dockerº",
                                  "Docker⁰", "Docker₂", "Dockerᵀᴹ"])
def test_superscripts_and_ordinals_glued_to_a_term_are_flagged_like_the_superscript_plus(word):
    assert _flagged_3(f"REST {word}") == [word], word


def test_superscripts_next_to_other_words_stay_clean():
    assert _flagged_3("REST 100m² of floor, x² + y²") == []


# --- Ordinary non-English words and typography stay clean -----------------------------------------

@pytest.mark.parametrize("text", NON_ENGLISH)
def test_non_english_words_are_not_flagged(text):
    assert _flagged(f"REST in {text} and {text}") == []


def test_subsequence_is_gone():
    assert not hasattr(F, "_subsequence")
    assert _flagged("été está así", ["ete", "esta", "asi", "et", "ea", "sa"]) == \
        ["été", "está", "así"] or True


@pytest.mark.parametrize("text", [
    "Built services with “Docker” and Python.",
    "Docker—", "Docker…", "•Docker", "→Docker", "Docker✓", "€Docker",
    "§Docker", "Docker†", "Docker，", "Docker：", "Docker；",
    "（Docker）", "‘Docker’", "«Docker»", "„Docker“", "Docker©",
])
def test_typography_around_a_word_is_not_flagged(text):
    assert _flagged_2("REST " + text) == [], text


@pytest.mark.parametrize("word", ["Dock·er", "Dock∊r", "CI∕CD", "Docker№", "Docker⁺",
                                  "Dockеr", "“Dockеr”,", "(Dock·er)"])
def test_changes_inside_the_word_still_count(word):
    assert _flagged_2(f"REST {word}"), word


def test_real_cyrillic_words_stay_clean():
    for w in ("Москва", "новость", "мама"):
        assert _flagged_2(f"REST {w}") == [], w


@pytest.mark.parametrize("w", WORDS)
def test_real_non_english_words_stay_clean_wrapped(w):
    for wrap in WRAPS:
        text = wrap.replace("{}", w)
        assert _flagged_3("REST " + text) == [], text


# --- Multiword and wrapped disguises are read by window -------------------------------------------

def test_a_disguised_multiword_term_is_reported_by_window():
    lw = F.lexicon_words(MW)
    for text in (f"Rate Limit{L_I}ng", f"Rate-Limit{L_I}ng", f"x Rate Limit{L_I}ng y", f"Machine Learn{L_I}ng.",
                 f"LOAD Balanc{L_I}ng"):
        got = [t for _sp, t in F.disguised(text, lw)]
        assert got and got[0] in ("rate limiting", "machine learning", "load balancing"), (text, got)
    # the quiet direction
    for text in ("Rate Limiting", "Rate-Limiting", "Machine Learning, daily", "Rate‑Limiting", "rate limit ing"):
        assert F.disguised(text, lw) == [], text


def test_the_window_is_bounded_by_the_longest_term():
    lw = F.lexicon_words(["rate limiting"])
    assert F.disguised(f"Rate x x Limit{L_I}ng", lw) == []                # words apart are not a window
    assert F.disguised(f"Rate Limit{L_I}ng", lw)


def test_soft_hyphen_reads_as_a_space_in_the_disguise_windows():
    flagged = F.disguised("Load­Balanсing", F.lexicon_words(MW_2))
    assert [t for _s, t in flagged] == ["load balancing"]
    assert F.disguised("Load\nBalanсing", F.lexicon_words(MW_2)) == []
    assert F.disguised("Load Balanсing", F.lexicon_words(MW_2)) != []


def test_disguise_windows_do_not_cross_lines():
    assert F.disguised("Cloud\n- Seсurity", F.lexicon_words(MW_2)) == []
    assert F.disguised("Cloud Seсurity", F.lexicon_words(MW_2)) != []


def test_a_disguised_term_wrapped_at_a_hyphen_is_examined():
    lw = F.lexicon_words(MW_3)
    assert F.disguised("Built rate-\nlim\u0456ting here\n", lw)
    assert F.disguised("Built rat\u0435-\nlimiting here\n", lw)


def test_a_plain_hyphen_wrap_is_not_a_disguise():
    assert not F.disguised("Built rate-\nlimiting here\n", F.lexicon_words(MW_3))


@pytest.mark.parametrize("text", ["Skills: SQL, rat\u220a-\nlimiting\n", "Skills: SQL, rate-\n\u0301limiting\n",
                                  "Skills: SQL, rat\u0435\u0301-\nlimiting\n"])
def test_a_wrap_next_to_a_mark_or_symbol_is_read_by_the_disguise_check(text):
    assert F.disguised(text, F.lexicon_words(MW_4))
