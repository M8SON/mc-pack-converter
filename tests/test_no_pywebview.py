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


def test_pyproject_declares_only_pillow():
    text = (ROOT / "pyproject.toml").read_text()
    assert 'dependencies = ["Pillow>=10.0"]' in text
    assert "pywebview" not in text
