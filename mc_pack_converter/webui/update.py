"""Tell the user their copy is stale. Never act on it.

The installer pins no version -- pyproject says 0.1.0 forever -- so nothing
about an installed copy says which build it is. The installer therefore records
master's commit SHA at install time, and this compares that against master now.

Three rules hold this together, and each of them is a bug that already
happened:

  It never runs on the UI thread. pywebview builds its JS bridge by walking
  this process's objects, and one blocking property there stalled startup for
  sixty seconds. A network call reachable from poll() would be the same shape.

  Every failure is silence. Offline, DNS down, GitHub rate-limiting, a captive
  portal returning HTML with a 200 -- all produce no banner and no error. An
  update check must never be a reason the app misbehaves.

  It never installs anything. It prints a sentence naming the command.
"""
from __future__ import annotations
import re
from pathlib import Path

# The bare-SHA media type: GitHub answers with the 40 characters as plain text
# rather than a commit object, so there is no JSON to parse and nothing to
# misread. A few dozen bytes.
SHA_URL = "https://api.github.com/repos/M8SON/mc-pack-converter/commits/master"
SHA_ACCEPT = "application/vnd.github.sha"
TIMEOUT_S = 2.0
INSTALL_CMD = "Install-MCPackConverter.cmd"
FILENAME = "installed-sha"

_SHA = re.compile(r"\A[0-9a-f]{40}\Z")


def _clean(raw) -> str | None:
    """A 40-character hex SHA, or None. Everything else is not an answer."""
    if not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    return s if _SHA.match(s) else None


def _dir(root=None) -> Path:
    if root is not None:
        return Path(root)
    from .wall import cache_dir
    return cache_dir()


def record_sha(sha: str, root=None) -> None:
    """Store the SHA of the build being installed. Called AFTER pip succeeds:
    a SHA written before a failed install is a file that lies."""
    d = _dir(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / FILENAME).write_text(sha.strip(), encoding="ascii")


def installed_sha(root=None) -> str | None:
    """What was recorded, or None -- including for a copy installed before
    this existed, which has nothing to compare and so is never nagged."""
    try:
        raw = (_dir(root) / FILENAME).read_text(encoding="ascii")
    except OSError:
        return None
    return _clean(raw)


def _http_get(url: str, timeout: float) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={
        "Accept": SHA_ACCEPT,
        # GitHub rejects requests with no User-Agent outright.
        "User-Agent": "mc-pack-converter",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        # Bounded: a 40-character answer needs no more, and an error page is
        # not worth reading into memory.
        return r.read(256).decode("ascii", "replace")


def latest_sha(fetch=_http_get) -> str | None:
    """Master's SHA now, or None if the question could not be answered.

    The bare `except Exception` is the specification, not laziness: there is no
    failure of this call that should reach the user, and enumerating urllib's
    error surface would only be a list that goes stale.
    """
    try:
        return _clean(fetch(SHA_URL, TIMEOUT_S))
    except Exception:
        return None


def check(root=None, fetch=_http_get) -> str | None:
    """One sentence to show the user, or None. Never both halves missing."""
    have = installed_sha(root)
    if have is None:
        return None                      # nothing recorded: nothing to say
    there = latest_sha(fetch=fetch)
    if there is None or there == have:
        return None                      # unreachable, or already current
    return f"An update is available — re-run {INSTALL_CMD}"


def record_latest(root=None, fetch=_http_get) -> int:
    """Fetch master's SHA and record it. The installer's last step."""
    sha = latest_sha(fetch=fetch)
    if sha is None:
        # Not a failure of the install: the package is in place either way,
        # and an unrecorded SHA only means no update notice until next time.
        return 0
    record_sha(sha, root=root)
    return 0


def run_update_check(state, root=None, fetch=_http_get) -> None:
    """Do the check and store the answer on the state. Never raises.

    Separated from the thread that calls it so the outcome can be tested
    without testing scheduling.
    """
    try:
        state.update_notice = check(root=root, fetch=fetch)
    except Exception:
        # A background thread in a windowed app has no console to print to,
        # so an escaping traceback is invisible rather than merely untidy.
        state.update_notice = None


def start_update_check(state, root=None, fetch=_http_get):
    """Run the check off the UI thread and return the thread.

    Daemon, so a hung socket cannot keep the process alive after the window
    closes -- the timeout bounds the wait, this bounds the consequence of the
    timeout being wrong.
    """
    import threading
    t = threading.Thread(target=run_update_check, args=(state,),
                         kwargs={"root": root, "fetch": fetch}, daemon=True)
    t.start()
    return t


if __name__ == "__main__":       # python -m mc_pack_converter.webui.update
    raise SystemExit(record_latest())
