"""The learning core never imports a sidecar (kenloop.career, kenloop.certs).

Only the shell (cli, loop) may import both. Read from the source with ast, so a lazy import
inside a function counts too."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "kenloop"
SIDECARS = ("kenloop.career", "kenloop.certs")

# Edges allowed while a move is in progress. A listed edge that no longer exists fails the test,
# so this only shrinks. Empty since 2026-10-22: the core imports no sidecar.
STILL_CUTTING: set = set()


def imported(path: Path, module: str) -> set:
    """Every module `module` (the dotted name of `path`) imports, relative imports resolved."""
    package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parts = parts[:len(parts) - node.level + 1]
                base = ".".join(parts + ([node.module] if node.module else []))
            out.add(base)
            out |= {f"{base}.{a.name}" for a in node.names}
    return out


def core_edges(root: Path) -> set:
    edges = set()
    for f in sorted((root / "core").rglob("*.py")):
        rel = f.relative_to(root.parent).with_suffix("")
        module = ".".join(rel.parts[:-1] if rel.name == "__init__" else rel.parts)
        edges |= {(module, m) for m in imported(f, module) if m.startswith(SIDECARS)}
    return edges


def _modules(edges):
    """Collapse 'pkg' + 'pkg.name' pairs to the most specific module named."""
    return {(a, b) for a, b in edges if not any(c == a and d.startswith(b + ".") for c, d in edges)}


def test_the_core_imports_no_sidecar():
    found = _modules(core_edges(ROOT))
    assert found - STILL_CUTTING == set(), "the core imports a sidecar"
    assert STILL_CUTTING - found == set(), "an edge listed in STILL_CUTTING is gone: remove it from the list"


def test_the_check_reads_every_core_module():
    names = {f.stem for f in (ROOT / "core").glob("*.py")}
    assert {"learn", "home", "fsrs", "errors", "names"} <= names


def test_the_check_sees_a_violation(tmp_path):
    core = tmp_path / "kenloop" / "core"
    core.mkdir(parents=True)
    (core / "__init__.py").write_text("")
    (core / "bad.py").write_text("def f():\n    from ..career import facts\n    from .. import certs\n")
    assert _modules(core_edges(tmp_path / "kenloop")) == {
        ("kenloop.core.bad", "kenloop.career.facts"), ("kenloop.core.bad", "kenloop.certs")}
