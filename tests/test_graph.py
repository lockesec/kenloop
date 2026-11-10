"""The study graph (core/graph.py) and `ken map`: one read-only answer to "what can I reach from
where I stand?" from the syllabus links, ladders and the scale. It never writes or credits."""
import json

from kenloop.core import graph as G
from kenloop.core import learn as L

from conftest import run


def _topic(home, body, capsys):
    run(home, "plan", "net", "--goal", "g", capsys=capsys)
    (home / "topics" / "net" / "syllabus.md").write_text(body)
    run(home, "sync", "net", capsys=capsys)


def _cfg(home):
    from kenloop.career import config as CC
    return CC.load(home)


SYL = """## Concepts
- net :: tcp :: transport
- net :: handshake :: x :: part-of:net:tcp
- net :: syn :: y :: part-of:net:tcp
- net :: ip :: z :: before:net:tcp
- net :: dns :: w
"""


def test_a_whole_waits_on_its_pieces_and_what_comes_before_it(home, capsys):
    _topic(home, SYL, capsys)
    t = G.build(_cfg(home), "net")
    why = G.waits(t, t.nodes["net:tcp"])
    assert any("made of 2 piece(s), 2 not climbed" in w for w in why)
    assert any("learn first: net:ip" in w for w in why)
    assert [n.cid for n in G.frontier(t)] == ["net:handshake", "net:syn", "net:ip", "net:dns"]


def test_climbing_the_pieces_makes_the_whole_ready(home, capsys, monkeypatch):
    _topic(home, SYL, capsys)
    for day in ("2030-03-01", "2030-03-02"):
        monkeypatch.setenv("KENLOOP_TODAY", day)
        for cid in ("net:handshake", "net:syn", "net:ip"):
            run(home, "record", "net", cid, "ok", capsys=capsys)
    t = G.build(_cfg(home), "net")
    assert all(t.nodes[c].climbed for c in ("net:handshake", "net:syn", "net:ip"))   # streak 2 = good
    assert G.waits(t, t.nodes["net:tcp"]) == []


def test_a_ladder_rung_waits_on_the_rungs_below_it(home, capsys):
    _topic(home, SYL, capsys)
    with open(home / "asks.jsonl", "a") as f:
        f.write(json.dumps({"event": "ask", "id": "q1", "date": "2030-03-01", "question": "why?"}) + "\n")
        for cid in ("net:dns", "net:ip", "net:dns"):          # a repeated rung is one rung
            f.write(json.dumps({"event": "rung", "ask": "q1", "date": "2030-03-01", "topic": "net",
                                "concept": cid}) + "\n")
    t = G.build(_cfg(home), "net")
    assert t.nodes["net:ip"].ladders == [("q1", 2, ["net:dns"])]
    assert "rung 2 of q1: climb net:dns first" in G.waits(t, t.nodes["net:ip"])


def test_map_shows_the_tree_and_the_frontier(home, capsys):
    _topic(home, SYL, capsys)
    code, out = run(home, "map", "net", capsys=capsys)
    lines = out.out.splitlines()
    assert code == 0
    tcp = next(i for i, x in enumerate(lines) if "net:tcp " in x)
    assert "net:handshake" in lines[tcp + 1] and "piece of net:tcp" in lines[tcp + 1]   # pieces nest
    assert "waits: made of 2 piece(s)" in lines[tcp]
    assert "frontier: 4 ready to study" in out.out


def test_map_survives_a_cycle_and_names_it(home, capsys):
    _topic(home, "## Concepts\n- net :: a :: x :: part-of:net:b\n- net :: b :: y :: part-of:net:a\n", capsys)
    code, out = run(home, "map", "net", capsys=capsys)
    assert "in a part-of cycle (see `validate net`): net:a, net:b" in out.out


def test_the_graph_writes_nothing(home, capsys):
    _topic(home, SYL, capsys)
    before = {p: p.read_bytes() for p in (home / "topics" / "net").rglob("*") if p.is_file()}
    run(home, "map", capsys=capsys)
    after = {p: p.read_bytes() for p in (home / "topics" / "net").rglob("*") if p.is_file()}
    assert before == after


def test_an_empty_home_is_not_evaluable(tmp_path, capsys):
    from kenloop import cli
    h = tmp_path / "h"
    assert cli.main(["--home", str(h), "init"]) == 0
    code, out = run(h, "map", capsys=capsys)
    assert code == 2 and "NOT EVALUABLE" in out.out


def test_talk_picks_a_ready_concept_before_one_that_waits(home, capsys):
    # tcp is first in the syllabus and least probed, but waits on its pieces and on ip
    _topic(home, SYL, capsys)
    code, out = run(home, "talk", "net", capsys=capsys)
    assert out.out.startswith("talk: handshake (net:handshake)")


def test_quiz_asks_ready_concepts_before_waiting_ones(home, capsys):
    _topic(home, SYL, capsys)
    code, out = run(home, "quiz", "net", "--n", "5", capsys=capsys)
    asked = [x.split()[1] for x in out.out.splitlines() if x.startswith("- ")]
    assert asked[-1] == "net:tcp" and len(asked) == 5          # asked, but last: it waits


def _answer(home, capsys, monkeypatch, day, *pairs):
    monkeypatch.setenv("KENLOOP_TODAY", day)
    for cid, res in pairs:
        run(home, "record", "net", cid, res, capsys=capsys)


def test_a_broken_piece_makes_its_whole_suspect_until_answered_again(home, capsys, monkeypatch):
    _topic(home, SYL, capsys)
    for day in ("2030-03-01", "2030-03-02", "2030-03-03"):
        _answer(home, capsys, monkeypatch, day, ("net:tcp", "ok"), ("net:handshake", "ok"))
    cfg = _cfg(home)
    assert L.suspects(cfg, "net") == {}
    _answer(home, capsys, monkeypatch, "2030-03-05", ("net:handshake", "miss"))
    assert L.suspects(cfg, "net") == {"net:tcp": ("net:handshake", "2030-03-05")}
    # flagged everywhere, revoked nowhere
    t = G.build(cfg, "net")
    assert t.nodes["net:tcp"].suspect and t.nodes["net:tcp"].badge == "mastered"
    assert "net:tcp" in [cid for cid, _c in L.due_list(cfg, "net")]
    code, out = run(home, "due", "net", capsys=capsys)
    assert "suspect: its piece net:handshake was answered wrong on 2030-03-05" in out.out
    assert "net:tcp" in L.graduation_evidence(cfg, "net")["suspect"]
    assert run(home, "rebuild", "net", "--check", capsys=capsys)[0] == 0       # no stored state moved
    # answering the piece right clears it; so does getting the whole right again
    _answer(home, capsys, monkeypatch, "2030-03-06", ("net:handshake", "ok"))
    assert L.suspects(cfg, "net") == {}


def test_a_miss_before_the_wholes_last_correct_is_not_suspect(home, capsys, monkeypatch):
    _topic(home, SYL, capsys)
    _answer(home, capsys, monkeypatch, "2030-03-01", ("net:handshake", "miss"))
    _answer(home, capsys, monkeypatch, "2030-03-02", ("net:tcp", "ok"))
    assert L.suspects(_cfg(home), "net") == {}
