"""doctor compares ## Held with the study record. Held is your assertion (it may come from
work), so this warns and never fails: it says what the record shows."""
from kenloop.career import config as CC
from kenloop.career import graduate as G
from kenloop.core import learn as L

from conftest import run


def _topic(cfg, home, slug, title, concepts, outlets=()):
    L.plan(cfg, slug, title=title, outlets=outlets)
    (home / "topics" / slug / "syllabus.md").write_text("## Concepts\n" + "".join(f"- d :: {c} :: x\n" for c in concepts))
    L.sync(cfg, slug, quiet=True)


def test_a_curiosity_topic_on_the_held_list_is_named(cfg, home, capsys):
    _topic(cfg, home, "black-holes", "Black holes and neutron stars", ["Event horizon"])
    (home / "facts.md").write_text("## Held\n- Black hole physics\n- REST\n")
    w = G.held_vs_study(CC.load(home), (home / "facts.md").read_text())
    assert len(w) == 1 and "'Black hole physics'" in w[0] and "studied for its own sake" in w[0]
    code, out = run(home, "doctor", capsys=capsys)
    assert "studied for its own sake" in out.err and code != 1          # a warning, never a finding


def test_a_career_concept_held_before_it_is_mastered_is_named(cfg, home):
    _topic(cfg, home, "ops", "Operations", ["Docker", "Kubernetes"], outlets=("career",))
    L.record(cfg, "ops", "d:docker", "ok", quiet=True)
    w = G.held_vs_study(CC.load(home), "## Held\n- Docker\n")
    assert len(w) == 1 and "ops/d:docker is fair: not earned by study yet" in w[0]


def test_a_mastered_career_concept_and_an_unrelated_skill_are_quiet(cfg, home, monkeypatch):
    _topic(cfg, home, "ops", "Operations", ["Docker"], outlets=("career",))
    for day in ("2030-03-20", "2030-03-22", "2030-03-25"):
        monkeypatch.setenv("KENLOOP_TODAY", day)
        L.record(cfg, "ops", "d:docker", "ok", quiet=True)
    assert G.held_vs_study(CC.load(home), "## Held\n- Docker\n- Terraform\n") == []
