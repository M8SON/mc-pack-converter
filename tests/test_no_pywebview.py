from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_nothing_in_the_package_mentions_pywebview():
    """The dependency is removed, so a surviving import is a crash on a
    machine that never had it -- which is every Linux machine."""
    hits = []
    for p in (ROOT / "mc_pack_converter").rglob("*"):
        if p.suffix in (".py", ".js", ".html", ".css"):
            if "pywebview" in p.read_text(encoding="utf-8", errors="replace"):
                hits.append(str(p.relative_to(ROOT)))
    assert hits == []


def test_pyproject_does_not_declare_pywebview():
    """The point is that the window's dependency is gone, not that Pillow is
    the only one there will ever be. Pinning the literal dependency line meant
    declaring numpy -- which sky.py had imported all along -- broke this test
    rather than the missing-dependency guard that should have caught it.
    tests/test_dependencies.py is what checks the list is complete."""
    text = (ROOT / "pyproject.toml").read_text()
    assert "pywebview" not in text
    assert "[gui]" not in text
