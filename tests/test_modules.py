"""The commands seam: modules plug verbs in through kenloop/modules.py; every verb a
module registers carries its own handler, and cli.py names none of them. Grows into the module
standard's conformance test."""
import argparse
import importlib
import re
from pathlib import Path

from kenloop import cli, modules

ROOT = Path(__file__).resolve().parents[1]


def _registered() -> dict:
    """{module: [verb ...]} by registering each module alone into fresh groups."""
    out = {}
    for name in modules.MODULES:
        p = argparse.ArgumentParser()
        sub = p.add_subparsers(dest="cmd")
        groups = {"": sub, "jobs": sub.add_parser("jobs").add_subparsers(dest="verb")}
        before = set(sub.choices) | set(groups["jobs"].choices)
        importlib.import_module(name).commands(groups)
        verbs = []
        for grp in (sub, groups["jobs"]):
            for v, sp in grp.choices.items():
                if v in before or v == "jobs":
                    continue
                subs = [a for a in sp._actions if isinstance(a, argparse._SubParsersAction)]
                if subs:                                  # a module's own group (cert)
                    verbs += [(f"{v} {s}", ssp) for s, ssp in subs[0].choices.items()]
                else:
                    verbs.append((v, sp))
        out[name] = verbs
    return out


def test_every_module_registers_verbs_and_each_verb_has_a_handler():
    reg = _registered()
    for name, verbs in reg.items():
        assert verbs, f"{name} registers no command"
        for v, sp in verbs:
            assert callable(sp.get_default("run")), f"{name}: `{v}` has no run handler"


def test_cli_names_no_verb_a_module_registered():
    src = (ROOT / "src" / "kenloop" / "cli.py").read_text(encoding="utf-8")
    for name, verbs in _registered().items():
        for v, _sp in verbs:
            last = v.split()[-1]
            assert not re.search(rf'add_parser\("{re.escape(last)}"|v == "{re.escape(last)}"', src), \
                f"cli.py still names `{v}` ({name} registers it)"


def test_the_real_parser_carries_the_module_verbs():
    p = cli.build_parser()
    ns = p.parse_args(["settings", "x", "--intent", "pass"])
    assert ns.run and ns.intent == "pass"
    ns = p.parse_args(["cert", "passed", "x", "--on", "2030-01-01"])
    assert ns.run and ns.on == "2030-01-01"


# --- the module standard (docs/modules.md): what every module in MODULES must hold to -----------

FORBIDDEN = {
    r"\bapply_row\(": "moves credit (only core/learn.py may)",
    r"\bfsrs\.update\(": "moves the schedule (only the kernel may)",
    r"\bsave_state\(": "writes derived state (only the kernel may)",
    r"open\([^)]*[\"']a[\"']": "appends to a file by hand (use core/ledger.append)",
    r"facts\.md[\"']?\s*\)\s*\.write|write_text\([^)]*facts": "writes facts.md (nothing writes it but the learner)",
}


def _source(name):
    return Path(importlib.import_module(name).__file__).read_text(encoding="utf-8")


def test_every_module_keeps_out_of_the_kernel_s_writes():
    bad = [(name, why) for name in modules.MODULES for pat, why in FORBIDDEN.items()
           if re.search(pat, _source(name))]
    assert bad == [], bad


def test_every_ledger_a_module_names_is_declared():
    from kenloop.core import ledger as LG
    declared = {d.file for d in LG.LEDGERS}
    for name in modules.MODULES:
        m = importlib.import_module(name)
        if hasattr(m, "LEDGER"):
            assert m.LEDGER in declared, f"{name} writes {m.LEDGER}, which LEDGERS does not declare"


def test_rule_and_doctor_hooks_are_well_formed():
    from kenloop import loop
    for name, fn, after in modules.rules():
        assert callable(fn) and after in {n for n, _f in loop.RULES}, name
    for name, check in modules.doctors():
        assert callable(check), name


def test_the_module_standard_names_every_module():
    doc = (ROOT / "docs" / "modules.md").read_text(encoding="utf-8")
    assert [n for n in modules.MODULES if f"`{n}`" not in doc] == []


def test_scouting_is_one_module_line(tmp_path):
    """Acceptance for the module split: the core knows no scout; without the module there is no scout verb,
    no scout offer and no scout key, and branches still work. Run in a fresh interpreter with the
    module dropped from MODULES."""
    import subprocess
    import sys
    core = ROOT / "src" / "kenloop" / "core"
    assert not [p.name for p in core.glob("*.py")
                if re.search(r"import .*scouts|from \.\.? import scouts|kenloop\.scouts", p.read_text(encoding="utf-8"))]
    code = (
        "import kenloop.modules as M\n"
        "M.MODULES = tuple(m for m in M.MODULES if m != 'kenloop.scouts')\n"
        "from kenloop import cli\n"
        "from kenloop.core import branches as B\n"
        "p = cli.build_parser()\n"
        "sub = [a for a in p._actions if hasattr(a, 'choices') and isinstance(a.choices, dict)][0]\n"
        "assert 'scout' not in sub.choices and 'branch' in sub.choices, sorted(sub.choices)\n"
        "assert 'scout' not in B.PROVIDERS\n"
        f"h = {str(tmp_path / 'h')!r}\n"
        "assert cli.main(['--home', h, 'init']) == 0\n"
        "assert cli.main(['--home', h, 'plan', 't']) == 0\n"
        "assert cli.main(['--home', h, 'branch', 't']) == 0\n"
        "print('ok')\n")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       env={"PYTHONPATH": str(ROOT / "src"), "KENLOOP_TODAY": "2030-03-20", "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0 and r.stdout.strip().endswith("ok"), r.stderr[-800:]
