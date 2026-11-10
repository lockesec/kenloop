"""The study verbs: plan a topic, bank and quiz, record, talk, place, branch, the views and the
integrity commands. Registered through the commands seam (kenloop/modules.py)."""
from __future__ import annotations

from .career import seed as SD
from .core import branches as B
from .core import dialogue as D
from .core import graph as SG
from .core import learn as L
from .core import onramp as O
from .core import questions as Q
from .core import recall as RC
from .core import views as V
from .core.args import count as _count
from .core.errors import OK


def _plan(cfg, ns) -> int:
    return SD.plan(cfg, ns.slug, ns.title, ns.goal, ns.from_gap, ns.top, ns.force, ns.career)


def _sync(cfg, ns) -> int:
    return L.sync(cfg, ns.slug)


def _bank(cfg, ns) -> int:
    return L.bank(cfg, ns.slug, ns.concept, ns.q, ns.a, ns.ref, ns.why, ns.qtype, ns.d)


def _quiz(cfg, ns) -> int:
    if ns.interactive:
        return L.quiz_interactive(cfg, ns.slug, ns.n, ns.weak, ns.concept)
    return L.quiz(cfg, ns.slug, ns.n, ns.weak, ns.concept)


def _record(cfg, ns) -> int:
    belief = {k: getattr(ns, k if k != "next" else "next_step") for k in L.BELIEF_FIELDS}
    L.record(cfg, ns.slug, ns.concept, ns.result, ns.note, ns.guess, ns.confidence,
             ns.hint_depth, ns.lookup, ns.mode, ns.qtype, ns.etype,
             rubric=L.parse_rubric(ns.rubric) if ns.rubric else None, grader=ns.grader,
             belief=belief, open_questions=ns.open, depth=ns.depth)
    return OK


def _dive(cfg, ns) -> int:
    return V.dive(cfg, ns.slug, ns.concept, ns.n)


def _foundations(cfg, ns) -> int:
    return V.foundations(cfg, ns.slug, ns.concept, ns.scaffold)


def _mastery(cfg, ns) -> int:
    return V.mastery(cfg, ns.slug)


def _board(cfg, ns) -> int:
    return V.board(cfg)


def _ask(cfg, ns) -> int:
    return Q.ask(cfg, ns.question)


def _rung(cfg, ns) -> int:
    return Q.rung(cfg, ns.qid, ns.topic, ns.line, ns.existing or None)


def _talk(cfg, ns) -> int:
    return D.talk(cfg, ns.slug, ns.concept, ns.protocol)


def _place(cfg, ns) -> int:
    return O.place(cfg, ns.slug, ns.rung, ns.result, ns.probe, ns.answer, ns.start, ns.clear_start)


def _branch(cfg, ns) -> int:
    if not ns.concept:
        return B.report(cfg, ns.slug)
    return O.branch(cfg, ns.slug, ns.concept, ns.line, ns.before, ns.topic or None, ns.title or None,
                    ns.by, ns.gap or None, ns.source, ns.note, ns.decline, ns.predict)


def _beliefs(cfg, ns) -> int:
    return D.beliefs(cfg, ns.slug, ns.concept)


def _due(cfg, ns) -> int:
    return L.due(cfg, ns.slug, ns.limit, ns.lane)


def _misconceptions(cfg, ns) -> int:
    return L.misconceptions(cfg, ns.slug)


def _calibration(cfg, ns) -> int:
    return L.calibration(cfg, ns.slug)


def _recall(cfg, ns) -> int:
    return RC.recall(cfg, ns.slug, ns.concept, ns.listed)


def _map(cfg, ns) -> int:
    return SG.map_(cfg, ns.slug)


def _rename(cfg, ns) -> int:
    return L.rename(cfg, ns.slug, ns.old, ns.new)


def _rebuild(cfg, ns) -> int:
    return L.rebuild(cfg, ns.slug, ns.check, ns.skip_damaged)


def _brief(cfg, ns) -> int:
    return L.brief(cfg, ns.slug)


def _validate(cfg, ns) -> int:
    return L.validate(cfg, ns.slug)


HANDLERS = {
        "plan": _plan,
        "sync": _sync,
        "bank": _bank,
        "quiz": _quiz,
        "record": _record,
        "dive": _dive,
        "foundations": _foundations,
        "mastery": _mastery,
        "board": _board,
        "ask": _ask,
        "rung": _rung,
        "talk": _talk,
        "place": _place,
        "branch": _branch,
        "beliefs": _beliefs,
        "due": _due,
        "misconceptions": _misconceptions,
        "calibration": _calibration,
        "recall": _recall,
        "map": _map,
        "rename": _rename,
        "rebuild": _rebuild,
        "brief": _brief,
        "validate": _validate,
}


def commands(groups) -> None:
    ls = groups[""]
    a = ls.add_parser("plan", help="create a topic, optionally seeded from a demand bucket")
    a.add_argument("slug")
    a.add_argument("--title")
    a.add_argument("--goal")
    a.add_argument("--from-gap", metavar="BUCKET")
    a.add_argument("--top", type=_count)
    a.add_argument("--force", action="store_true")
    a.add_argument("--career", action="store_true",
                   help="what you master here may graduate into facts.md (--from-gap implies it)")
    a = ls.add_parser("sync", help="read new concepts from syllabus.md")
    a.add_argument("slug")
    a = ls.add_parser("bank", help="add a question")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("--q", required=True)
    a.add_argument("--a", required=True)
    a.add_argument("--ref", required=True)
    a.add_argument("--why", default="")
    a.add_argument("--qtype", default="")
    a.add_argument("--d", action="append", default=[], help="'wrong option :: the misconception it encodes'")
    a = ls.add_parser("quiz", help="pick what to practise (weakest first)")
    a.add_argument("slug")
    a.add_argument("--n", type=_count, default=5)
    a.add_argument("--weak", action="store_true")
    a.add_argument("--concept")
    a.add_argument("--interactive", action="store_true", help="ask, hint, reveal and record here")
    a = ls.add_parser("record", help="record one attempt")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("result", choices=["ok", "partial", "miss"])
    a.add_argument("--note", default="")
    a.add_argument("--guess", action="store_true", help="right, but a guess: no credit")
    a.add_argument("--confidence", default="", help="low, med or high, stated before seeing the answer")
    a.add_argument("--hint-depth", type=int, default=0, help="0-4, the highest hint used (0 = none, the default)")
    a.add_argument("--lookup", action="store_true", help="read the answer (hint depth 4)")
    a.add_argument("--mode", default="practice", help="practice, exam, diagnose, learn, dialogue or predict "
                                                      "(their guess before the explanation: never credited)")
    a.add_argument("--depth", default="", choices=("exam", "mechanism", "first-principles"),
                   help="the depth of the question asked (default: the line/rung/topic depth setting)")
    a.add_argument("--qtype", default="")
    a.add_argument("--etype", default="")
    g = a.add_argument_group("dialogue (--mode dialogue)")
    g.add_argument("--rubric", default="", help="move=score,... (0-2 each, at least 3 probed moves)")
    g.add_argument("--grader", default="", help="who graded it (a model id); or set KENLOOP_GRADER")
    g.add_argument("--before", default="", help="what you believed at the start (with --confidence)")
    g.add_argument("--after", default="", help="what you believed at the end")
    g.add_argument("--after-confidence", default="", help="low, med or high, at the end")
    g.add_argument("--held", default="", help="the last step of your reasoning that held")
    g.add_argument("--broke", default="", help="the first step that did not")
    g.add_argument("--next", default="", dest="next_step", help="what to learn to get past it")
    g.add_argument("--open", action="append", default=[], help="a question left open (repeatable)")
    g.add_argument("--claude-wrong", default="", help="an error of the tutor's that you caught")
    a = ls.add_parser("talk", help="what is known about one concept and how your reasoning went; --protocol prints "
                                   "the graded-dialogue method")
    a.add_argument("slug")
    a.add_argument("concept", nargs="?")
    a.add_argument("--protocol", action="store_true", help="print the graded-dialogue method (only when grading one)")
    a = ls.add_parser("beliefs", help="how your beliefs moved, dialogue by dialogue, and the questions left open")
    a.add_argument("slug")
    a.add_argument("concept", nargs="?")
    a = ls.add_parser("dive", help="go over a concept together, answers open; alone, what is most worth going over")
    a.add_argument("slug")
    a.add_argument("concept", nargs="?")
    a.add_argument("--n", type=_count, default=8)
    a = ls.add_parser("foundations", help="a from-the-ground-up note per concept (--scaffold writes one)")
    a.add_argument("slug")
    a.add_argument("concept", nargs="?")
    a.add_argument("--scaffold", action="store_true")
    a = ls.add_parser("mastery", help="badges per concept, with calibration, reasoning and question types")
    a.add_argument("slug")
    ls.add_parser("board", help="every topic: mastery and what is due")
    a = ls.add_parser("ask", help="start a ladder from any question; alone, list your questions and how far you have climbed")
    a.add_argument("question", nargs="?")
    a = ls.add_parser("rung", help="add one rung to a question's ladder: a new concept line, or --existing")
    a.add_argument("qid")
    a.add_argument("topic")
    a.add_argument("line", nargs="?")
    a.add_argument("--existing", default="")
    a = ls.add_parser("place", help="find the rung of a topic's scale you start on (no credit); alone, where you stand")
    a.add_argument("slug")
    a.add_argument("--rung", type=int)
    a.add_argument("--result", choices=("pass", "partial", "miss"))
    a.add_argument("--probe", default="", help="the question asked, verbatim")
    a.add_argument("--answer", default="", help="the answer given, verbatim")
    a.add_argument("--start", type=int, help="start on rung N by choice: no probes (e.g. 0, to learn from the ground up)")
    a.add_argument("--clear-start", action="store_true", help="forget a chosen start; placement probes apply again")
    a = ls.add_parser("branch", help="a gap found while studying a concept: a piece of it, learned before it, a new "
                                     "topic, a note or declined; alone, the tool's offers and how well offers are picked")
    a.add_argument("slug", nargs="?")
    a.add_argument("concept", nargs="?", help="the concept being studied when the gap showed")
    a.add_argument("line", nargs="?", help='"DOMAIN :: CONCEPT :: DESCRIPTION"')
    a.add_argument("--by", choices=("learner", "tutor", "tool"), help="who raised the gap (required to decide one)")
    a.add_argument("--gap", default="", help="the gap in words (default: the line)")
    a.add_argument("--source", default="", help="the key of the offer being decided: a tool offer (with --by tool) "
                                                 "or scout:N (any --by; --by learner if you raised it first)")
    a.add_argument("--before", action="store_true", help="learned before the concept rather than a piece of it")
    a.add_argument("--topic", default="", help="a topic of its own: plan it, seeded with this concept")
    a.add_argument("--title", default="")
    a.add_argument("--note", help="keep it as a note only (the gap in words)")
    a.add_argument("--decline", help="an offer turned down (the gap in words)")
    a.add_argument("--predict", default="", choices=("",) + B.PREDICT,
                   help="your guess when adding a piece: will it be a problem or solid? read against later marks")
    a = ls.add_parser("due", help="reviews due today")
    a.add_argument("slug", nargs="?")
    a.add_argument("--lane", choices=("career", "interest"), help="only that lane's topics")
    a.add_argument("--limit", type=_count, default=20)
    a = ls.add_parser("misconceptions", help="recurring errors and what to do about them")
    a.add_argument("slug")
    a = ls.add_parser("calibration", help="are your confidence ratings honest?")
    a.add_argument("slug")
    a = ls.add_parser("recall", help="name a concept's pieces from memory; scored against the map (no credit)")
    a.add_argument("slug")
    a.add_argument("concept")
    a.add_argument("--listed", help='the pieces you named, separated by ";" (without it: the prompt)')
    a = ls.add_parser("map", help="each topic's concepts as wholes and pieces: climbed, ready, or waiting on what")
    a.add_argument("slug", nargs="?")
    a = ls.add_parser("rename", help="carry a concept's history to the new id you gave its syllabus line")
    a.add_argument("slug")
    a.add_argument("old", help="the concept id the log knows it by")
    a.add_argument("new", help="its id now (domain:name) in syllabus.md")
    a = ls.add_parser("rebuild", help="re-derive state from the log (--check: exit 3 on drift)")
    a.add_argument("slug")
    a.add_argument("--check", action="store_true")
    a.add_argument("--skip-damaged", action="store_true", help="rebuild from the readable log rows only")
    a = ls.add_parser("brief", help="a bundle for writing a topic's questions, in the bank's format")
    a.add_argument("slug")
    a = ls.add_parser("validate", help="integrity of topics and banks")
    a.add_argument("slug", nargs="?")
    for verb, run in HANDLERS.items():
        ls.choices[verb].set_defaults(run=run)
