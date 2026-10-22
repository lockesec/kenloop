"""The qualifier word list, now a contradiction detector under `## Held`.

These sheets put every line under `## Held`: a qualifier word there makes the
line not held (and reported by F.contradictions). Heldness itself is pinned in
test_held_section.py.
"""
from kenloop.career import facts as F

HELD = "## Held\n"


def test_unqualified_block_holds():
    assert F.holds("docker", HELD + "- Docker for local dev")


def test_every_mention_qualified_is_not_held():
    for q in ("planned", "in progress", "pursuing", "not held", "do not claim", "never claim",
              "[verify]", "TODO", "aspirational", "no active", "not claimed"):
        assert not F.holds("oauth", HELD + f"- OAuth — {q}"), q


def test_one_qualified_mention_does_not_poison_a_clean_one():
    facts = HELD + "- Caching: CDN rules for static assets\n- Caching strategy review planned\n"
    assert F.holds("caching", facts)


def test_hard_wrapped_continuation_joins_its_bullet_before_the_qualifier_scan():
    facts = HELD + "- Kubernetes cluster work, not\n  claimed on any resume\n"
    assert not F.holds("kubernetes", facts)


def test_heading_qualifier_governs_its_section_only():
    facts = HELD + "- Python\n\n### Planned\n\n- Rust\n\n#### Sub\n\n- Go\n\n### Skills\n\n- Java\n"
    assert not F.holds("rust", facts)
    assert not F.holds("go", facts)          # nested under the planned sub-heading
    assert F.holds("python", facts)
    assert F.holds("java", facts)            # the next same-level sub-heading ends it


def test_empty_facts_hold_nothing():
    assert not F.holds("http", "")
    assert not F.holds("http", HELD)


def test_token_boundaries():
    assert not F.token_in("soc", "associate")
    assert not F.token_in("git", "digital")
    assert F.token_in("att&ck", "mitre att&ck framework")
    assert F.token_in("ci/cd", "own the ci/cd pipeline")
    assert F.token_in("api", "rest apis") is True        # plural for 3+ chars
    assert not F.token_in("wa", "it was")                 # never for 2 chars


def test_a_qualifier_disqualifies_every_term_in_its_block():
    # documented limit: split the line to hold one and not the other
    assert not F.holds("docker", HELD + "- Docker; Kubernetes planned")


# --- ordinary phrasings of "not really held" ------------------------

UNHELD = [
    ("docker", "- Learning Docker"),
    ("kubernetes", "- Plan to learn Kubernetes"),
    ("graphql", "- Haven't used GraphQL in production"),
    ("graphql", "- Haven’t used GraphQL in production"),
    ("javascript", "- JavaScript (basic)"),
    ("javascript", "- JavaScript, basic"),
    ("oauth", "- Familiar with OAuth from a course"),
    ("tls", "- I'd like to use TLS"),
    ("redis", "- Exploring Redis"),
    ("websockets", "- Interested in WebSockets"),
    ("docker", "- Docker - not hands-on"),
    ("terraform", "- Terraform: no production experience"),
    ("sql", "- SQL, basic knowledge"),
    ("rest", "- Dabbled in REST"),
    ("aws", "- AWS, limited experience"),
    ("rust", "- Hope to use Rust someday"),
    ("cors", "- CORS, did not use it directly"),
]


def test_ordinary_unheld_phrasings_are_not_held():
    for term, line in UNHELD:
        assert not F.holds(term, HELD + line), line


NEAR_MISS = [      # contain a word a loose rule would catch, but state a held skill
    ("python", "- Machine learning pipelines in Python"),
    ("sql", "- Learning Management System admin: SQL reporting"),
    ("sql", "- E-learning platform backend, SQL and caching"),
    ("http", "- HTTP Basic auth middleware"),
    ("docker", "- Hands-on experience with Docker in production"),
    ("docker", "- Docker, 10 years of production experience"),
    ("kubernetes", "- Wrote the migration plan for the Kubernetes cutover"),
    ("graphql", "- Led a team to ship GraphQL APIs"),
    ("redis", "- Taught Redis to a team of five"),
    ("terraform", "- Notified on-call, then ran Terraform daily"),
    ("oauth", "- Presented OAuth design to interested stakeholders"),
]


def test_near_misses_still_read_held():
    for term, line in NEAR_MISS:
        assert F.holds(term, HELD + line), line


def test_every_documented_qualifier_family_is_in_the_docs():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[1] / "docs" / "trust-rules.md").read_text()
    for label, example in F.QUALIFIER_FAMILIES:
        assert label in doc and example in doc, label
