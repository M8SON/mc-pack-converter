"""The installer has to actually replace what is installed.

pip's --upgrade compares VERSION NUMBERS, and pyproject pins 0.1.0 with no
per-commit bump. Against a moving master branch that means pip fetches the
zip, finds the same version already present, prints "Requirement already
satisfied" and installs nothing. Mason ran the installer and then reported the
fire bug still present -- site-packages still held files three and a half hours
old, from before the fix existed.
"""
from pathlib import Path

INSTALLER = Path(__file__).resolve().parent.parent / "packaging" / "Install-MCPackConverter.cmd"


def _pip_line() -> str:
    lines = [l for l in INSTALLER.read_text().splitlines() if "pip install" in l]
    assert len(lines) == 1, f"expected one pip install line, found {len(lines)}"
    return lines[0]


def test_the_installer_forces_a_reinstall():
    """--upgrade alone is a no-op here and always will be until the version is
    bumped per release."""
    assert "--force-reinstall" in _pip_line()


def test_the_installer_does_not_serve_a_cached_archive():
    """The URL is a branch, so its contents change while its name does not.
    A cached download is a stale build wearing the right address."""
    assert "--no-cache-dir" in _pip_line()


def test_the_installer_still_asks_for_the_gui_extra():
    """Without [gui] there is no pywebview, and no window."""
    assert "[gui]" in _pip_line()


def _lines() -> list[str]:
    return INSTALLER.read_text().splitlines()


def test_the_installer_records_the_build_it_installed():
    """Without this nothing on disk says which build is installed, and the
    window can never tell the user their copy is stale."""
    assert any("mc_pack_converter.webui.update" in l for l in _lines())


def test_the_sha_is_recorded_after_the_install_not_before():
    """A SHA written first, then a failed pip, is a file that lies about what
    is installed -- and it lies in the direction of staying silent."""
    body = _lines()
    pip = next(i for i, l in enumerate(body) if "pip install" in l)
    record = next(i for i, l in enumerate(body)
                  if "mc_pack_converter.webui.update" in l)
    assert record > pip
