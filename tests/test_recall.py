"""`ken recall`: name a concept's pieces from memory, scored against the map. No credit; a piece
you missed shows on the map and comes first among pieces in next."""
from kenloop import loop
from kenloop.core import graph as G
from kenloop.core import learn as L
from kenloop.core import recall as RC

from conftest import run

SYL = """## Concepts
- net :: tcp :: transport
- net :: three-way handshake :: x :: part-of:net:tcp
- net :: sequence numbers :: y :: part-of:net:tcp
- net :: flow control :: z :: part-of:net:tcp
"""


def _cfg(home):
    from kenloop.career import config as CC
    return CC.load(home)


def _topic(home, capsys):
    run(home, "plan", "net", "--goal", "g", capsys=capsys)
    (home / "topics" / "net" / "syllabus.md").write_text(SYL)
    run(home, "sync", "net", capsys=capsys)


def test_match_by_name_or_id_ignoring_case_and_punctuation():
    pieces = {"net:three-way-handshake": "three-way handshake", "net:flow-control": "flow control"}
    got, miss, extra = RC.match(["Three Way Handshake", "congestion window"], pieces)
    assert got == ["net:three-way-handshake"] and miss == ["net:flow-control"] and extra == ["congestion window"]


def test_without_a_list_it_only_asks(home, capsys):
    _topic(home, capsys)
    code, out = run(home, "recall", "net", "net:tcp", capsys=capsys)
    assert code == 0 and "Name them from memory" in out.out
    assert not (home / "topics" / "net" / "recall.jsonl").exists()


def test_a_recall_scores_records_and_earns_nothing(home, capsys):
    _topic(home, capsys)
    before = L.load_state(_cfg(home), "net")
    code, out = run(home, "recall", "net", "net:tcp", "--listed", "three-way handshake; congestion window",
                    capsys=capsys)
    assert code == 1 and "recalled 1 of 3 piece(s)" in out.out
    assert "missed    net:sequence-numbers" in out.out and "not on the map: 'congestion window'" in out.out
    assert L.load_state(_cfg(home), "net") == before                     # no credit, no schedule
    assert RC.missed(_cfg(home), "net") == {"net:sequence-numbers": ("net:tcp", "2030-03-20"),
                                            "net:flow-control": ("net:tcp", "2030-03-20")}


def test_a_missed_piece_shows_on_the_map_and_comes_first_in_next(home, capsys):
    _topic(home, capsys)
    run(home, "recall", "net", "net:tcp", "--listed", "three-way handshake; flow control", capsys=capsys)
    t = G.build(_cfg(home), "net")
    assert t.nodes["net:sequence-numbers"].recall_missed == ("net:tcp", "2030-03-20")
    code, out = run(home, "map", "net", capsys=capsys)
    assert "missed in your recall of net:tcp on 2030-03-20" in out.out
    e = next(e for e in loop.evaluate(_cfg(home)) if e["rule"] == "study")
    assert e["argv"][-1] == "net:sequence-numbers" and "missed when recalling it" in e["reason"]


def test_a_concept_with_no_pieces_is_not_evaluable(home, capsys):
    _topic(home, capsys)
    code, out = run(home, "recall", "net", "net:flow-control", capsys=capsys)
    assert code == 2 and "has no pieces on the map" in out.out


def test_a_damaged_recall_line_fails_validate(home, capsys):
    _topic(home, capsys)
    (home / "topics" / "net" / "recall.jsonl").write_text("not json\n")
    code, out = run(home, "validate", "net", capsys=capsys)
    assert code == 1 and "damaged recall.jsonl line 1" in out.out
