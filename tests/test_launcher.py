"""The double-click launcher must not misreport gui.main's exit codes.

gui.main returns 2 for two ordinary cases -- a bare double-click with no pack
dropped, and a rejected pack -- printing its own message to stderr for both.
The launcher used to treat any nonzero exit as "an error" and point at
%LOCALAPPDATA%\\MCPackConverter\\last-run.log, a file _diag stopped writing
when the pywebview window was deleted. Both halves of that were wrong: the
usage message is not a crash, and the log does not exist.
"""
import re
from pathlib import Path

LAUNCHER = Path(__file__).resolve().parent.parent / "packaging" / "MCPackConverter.cmd"


def _text() -> str:
    return LAUNCHER.read_text()


def _echoed_lines() -> list[str]:
    """Only what the launcher actually prints, not its `rem` commentary."""
    return [l for l in _text().splitlines() if l.strip().lower().startswith("echo")]


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
