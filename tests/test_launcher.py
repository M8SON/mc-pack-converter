"""The one file a user downloads has to do the whole job.

There used to be two: Install-MCPackConverter.cmd and MCPackConverter.cmd.
Downloading both meant hunting two raw files out of the GitHub tree -- which
is what Mason himself ended up doing, and both landed loose in his Downloads
folder five minutes apart -- and running the wrong one of two near-identical
names did nothing useful. This file is now the only artifact, so everything
the installer guaranteed has to be guaranteed here.
"""
import re
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent.parent / "packaging" / "MCPackConverter.cmd"


def _text() -> str:
    return LAUNCHER.read_text()


def _echoed_lines() -> list[str]:
    """Only what the launcher actually prints, not its `rem` commentary."""
    return [l for l in _text().splitlines() if l.strip().lower().startswith("echo")]


# --- exit codes: an ordinary refusal is not a crash --------------------------

def test_the_launcher_does_not_name_a_log_that_does_not_exist():
    echoed = "\n".join(_echoed_lines())
    assert "last-run.log" not in echoed
    assert "LOCALAPPDATA" not in echoed


def test_the_launcher_distinguishes_exit_2_from_a_crash():
    """Exit 2 is gui.main's usage/rejection path, already printed to stderr.
    It must not fall into the same branch as a real crash."""
    text = _text()
    assert '"%EC%"=="2"' in text or "%EC%==2" in text


def test_exit_2_is_not_reported_as_an_error():
    """The branch handling exit 2 must not echo the word "error" -- that
    would misdescribe a bare double-click (no pack dropped) as a failure."""
    text = _text()
    m = re.search(r'"%EC%"=="2"\s*\((.*?)\n\)', text, re.S)
    assert m, "expected an EC==2 branch in the launcher"
    assert "error" not in m.group(1).lower()


def test_a_real_crash_is_still_reported():
    """Some nonzero exit code other than 2 (an unhandled exception, which
    Python reports with its own traceback and exit code 1) must still pause
    the window open so the traceback above it can be read."""
    text = _text()
    assert "crashed" in text.lower()
    assert "pause" in text


# --- installing: what Install-MCPackConverter.cmd used to guarantee ----------

def _pip_line() -> str:
    lines = [l for l in _text().splitlines() if "pip install" in l]
    assert len(lines) == 1, f"expected one pip install line, found {len(lines)}"
    return lines[0]


def test_the_install_forces_a_reinstall():
    """pip's --upgrade compares VERSION NUMBERS, and pyproject pins 0.1.0 with
    no per-commit bump. Against a moving master branch pip finds the same
    version already present and installs nothing. Mason once re-ran the
    installer and kept a build three and a half hours old."""
    assert "--force-reinstall" in _pip_line()


def test_the_install_does_not_serve_a_cached_archive():
    """The URL names a branch, so its contents change while its name does not.
    A cached download is a stale build wearing the right address."""
    assert "--no-cache-dir" in _pip_line()


def test_the_install_does_not_ask_for_a_gui_extra():
    """pywebview is gone: the report is a file, not a window."""
    assert "[gui]" not in _pip_line()


def test_the_build_is_recorded_after_the_install_not_before():
    """A SHA written first, then a failed pip, is a file that lies about what
    is installed -- and it lies in the direction of staying silent."""
    body = _text().splitlines()
    pip = next(i for i, l in enumerate(body) if "pip install" in l)
    record = next(i for i, l in enumerate(body)
                  if "webui.update" in l and "--check" not in l)
    assert record > pip


# --- the three things a non-technical user hits ------------------------------

def test_a_missing_python_is_explained_not_left_to_fail():
    """`python` with nothing installed hits the Windows App Execution Alias,
    which opens the Store with no explanation of why. The user is told."""
    text = _text()
    assert "python" in text.lower()
    echoed = "\n".join(_echoed_lines()).lower()
    assert "python" in echoed, "the launcher must say what is missing"


def test_the_python_message_names_where_to_get_it():
    """A non-technical reader needs the link, not the diagnosis. The Store
    build is the one that matters: it is Microsoft-signed, so Smart App
    Control allows it where a python.org install can be blocked."""
    echoed = "\n".join(_echoed_lines()).lower()
    assert "store" in echoed or "ms-windows-store" in echoed


def test_installing_says_it_is_installing_and_how_long():
    """A silent minute reads as a hang; pip's raw output reads as an error
    wall. Neither is acceptable for the audience this file exists for."""
    echoed = "\n".join(_echoed_lines()).lower()
    assert "install" in echoed
    assert "minute" in echoed


def test_the_install_output_is_quiet():
    """pip's default output is a wall of resolver chatter that a
    non-technical user reads as failure."""
    assert "--quiet" in _pip_line() or "-q " in _pip_line()


def test_a_stale_copy_updates_itself_before_converting():
    """With one file there is no separate installer to re-run, so the
    launcher is the only thing that can keep the copy current. It asks
    webui.update, which is bounded by a 2s timeout and answers "no" whenever
    it cannot reach GitHub."""
    text = _text()
    assert "--check" in text


def test_the_launcher_never_points_at_a_second_file():
    """The whole point of collapsing the two. A message naming a file the
    user does not have is worse than no message.

    Echoed lines only: the `rem` commentary explains why the second file went
    away, which is history worth keeping and is never shown to anyone."""
    assert "Install-MCPackConverter" not in "\n".join(_echoed_lines())


def test_the_old_installer_is_gone():
    """Two near-identical names in a Downloads folder is the trap this
    removes; leaving the file behind would recreate it."""
    old = LAUNCHER.parent / "Install-MCPackConverter.cmd"
    assert not old.exists(), "the second file must not come back"


# --- the README has to tell people where to get the file ---------------------

README = LAUNCHER.parent.parent / "README.md"


def test_the_readme_links_the_download():
    """The word "download" did not appear once in 241 lines. Step 2 said "Run
    packaging/Install-MCPackConverter.cmd" as if the reader already had it,
    and the Releases page -- where anyone actually looks -- had no assets."""
    assert "releases/latest/download/MCPackConverter.zip" in README.read_text()


def test_the_readme_does_not_send_anyone_after_the_deleted_installer():
    assert "Install-MCPackConverter" not in README.read_text()


def test_the_launcher_has_windows_line_endings():
    """It is a Windows batch file and it is authored on Linux. cmd.exe is
    unreliable with LF-only files -- labels and `goto` in particular -- and
    the failure is silent: the script simply stops doing anything. The file
    that shipped before this one was CRLF; keeping it that way is not
    cosmetic.
    """
    raw = LAUNCHER.read_bytes()
    assert b"\r\n" in raw, "batch file must use CRLF"
    assert raw.count(b"\n") == raw.count(b"\r\n"), "every newline must be CRLF"


def test_pip_does_not_advertise_its_own_upgrade():
    """--quiet does not suppress pip's "[notice] A new release of pip is
    available" banner. Observed leaking through a real install on Windows,
    where it reads to a non-technical user as a warning about the thing they
    just ran."""
    assert "--disable-pip-version-check" in _pip_line()
