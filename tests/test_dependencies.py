"""Everything the package imports has to be something pip will install.

sky.py imported numpy from the day it was written and pyproject declared only
Pillow. Nothing local caught it -- the dev venv had numpy pulled in by
something else -- and the Windows install test passed because it installed
from a master that predated the sky renderer. The moment that renderer
reached master, a clean install of this package could not build a QA sheet at
all. CI on a bare runner is what found it.

A missing dependency does not fail at install time. It fails the first time a
user drags a pack onto the launcher, which is the worst possible moment.
"""
import ast
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "mc_pack_converter"

# Import name -> distribution name, where they differ.
DISTRIBUTION = {"PIL": "pillow"}


def _imported_top_level() -> set[str]:
    found: set[str] = set()
    for path in PKG.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def _declared() -> set[str]:
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = set()
    for spec in meta["project"]["dependencies"]:
        # "Pillow>=10.0" -> "pillow"
        names.add(spec.split(">")[0].split("<")[0].split("=")[0].split("[")[0]
                  .strip().lower())
    return names


def test_every_third_party_import_is_a_declared_dependency():
    third_party = {
        name for name in _imported_top_level()
        if name not in sys.stdlib_module_names and name != "mc_pack_converter"
    }
    declared = _declared()
    missing = sorted(
        name for name in third_party
        if DISTRIBUTION.get(name, name).lower() not in declared
    )
    assert not missing, (
        f"imported but not declared in pyproject: {missing}. A user installing "
        f"this gets a package that fails when they drag a pack onto it.")


def test_the_scan_actually_sees_the_packages_imports():
    """A guard that silently scanned nothing would pass forever."""
    found = _imported_top_level()
    assert "numpy" in found and "PIL" in found, found
