"""The window tells you when your copy is stale. It never installs anything.

This exists because the fix for a bug Mason reported sat on master while he ran
a build from three and a half hours earlier, and nothing in the app could have
told him. The check is advisory, silent on every failure, and never touches the
UI thread -- a blocking call on the pywebview bridge already cost this app a
60-second startup stall once.
"""
import pytest

SHA_A = "a" * 40
SHA_B = "b" * 40


def test_a_recorded_sha_is_read_back(tmp_path):
    from mc_pack_converter.webui.update import installed_sha, record_sha
    record_sha(SHA_A, root=tmp_path)
    assert installed_sha(root=tmp_path) == SHA_A


def test_no_recorded_sha_is_not_an_error(tmp_path):
    """A copy installed before this feature has nothing to compare against."""
    from mc_pack_converter.webui.update import installed_sha
    assert installed_sha(root=tmp_path) is None


def test_a_recorded_sha_is_stored_bare(tmp_path):
    """Whitespace and newlines round-trip away, or every comparison differs."""
    from mc_pack_converter.webui.update import installed_sha, record_sha
    record_sha("  " + SHA_A + "\n", root=tmp_path)
    assert installed_sha(root=tmp_path) == SHA_A


def test_the_latest_sha_comes_back_bare():
    from mc_pack_converter.webui.update import latest_sha
    assert latest_sha(fetch=lambda url, timeout: SHA_B + "\n") == SHA_B


def test_a_failed_fetch_is_silent_not_raised():
    """Offline, DNS failure, rate limit -- all the same: no answer, no error,
    no banner. An update check must never be a reason the app misbehaves."""
    from mc_pack_converter.webui.update import latest_sha

    def boom(url, timeout):
        raise OSError("no network")

    assert latest_sha(fetch=boom) is None


def test_a_reply_that_is_not_a_sha_is_rejected():
    """A captive portal or an error page returns 200 with HTML in it."""
    from mc_pack_converter.webui.update import latest_sha
    assert latest_sha(fetch=lambda url, timeout: "<html>nope</html>") is None
    assert latest_sha(fetch=lambda url, timeout: "") is None
    assert latest_sha(fetch=lambda url, timeout: "z" * 40) is None


def test_the_fetch_is_time_bounded():
    """A hung socket must not keep the check thread alive forever."""
    from mc_pack_converter.webui.update import TIMEOUT_S, latest_sha
    seen = {}

    def spy(url, timeout):
        seen["timeout"] = timeout
        return SHA_B

    latest_sha(fetch=spy)
    assert seen["timeout"] == TIMEOUT_S
    assert TIMEOUT_S <= 5


def test_matching_shas_say_nothing(tmp_path):
    from mc_pack_converter.webui.update import check, record_sha
    record_sha(SHA_A, root=tmp_path)
    assert check(root=tmp_path, fetch=lambda url, timeout: SHA_A) is None


def test_a_moved_master_is_reported(tmp_path):
    from mc_pack_converter.webui.update import check, record_sha
    record_sha(SHA_A, root=tmp_path)
    out = check(root=tmp_path, fetch=lambda url, timeout: SHA_B)
    assert out and "Install-MCPackConverter.cmd" in out


@pytest.mark.parametrize("recorded, fetched", [
    (None, SHA_B),      # never recorded: nothing to compare
    (SHA_A, None),      # offline: nothing to compare
    (None, None),
])
def test_a_missing_half_says_nothing(tmp_path, recorded, fetched):
    from mc_pack_converter.webui.update import check, record_sha
    if recorded:
        record_sha(recorded, root=tmp_path)
    assert check(root=tmp_path, fetch=lambda url, timeout: fetched) is None


# --- wiring: the notice reaches the page without touching the UI thread ------


def test_the_state_carries_no_notice_until_one_is_set():
    """Absent, not empty-string: the page hides the line on a falsy value, and
    a window that has never checked must look identical to one that found
    nothing."""
    from mc_pack_converter.gui import DEFAULT_TARGET, GuiState
    st = GuiState(None, DEFAULT_TARGET, [])
    assert st.to_dict().get("update") in (None, "")


def test_a_notice_set_on_the_state_reaches_the_page_model():
    from mc_pack_converter.gui import DEFAULT_TARGET, GuiState
    st = GuiState(None, DEFAULT_TARGET, [])
    st.update_notice = "An update is available — re-run Install-MCPackConverter.cmd"
    assert st.to_dict()["update"] == st.update_notice


def test_a_new_run_does_not_clear_the_notice():
    """start() resets result, sheet, counters and error so a second pack does
    not show the first one's output. The update notice is not per-pack."""
    from mc_pack_converter.gui import DEFAULT_TARGET, GuiState
    st = GuiState(None, DEFAULT_TARGET, [])
    st.update_notice = "stale"
    st.start(__import__("pathlib").Path("x.zip"))
    assert st.to_dict()["update"] == "stale"


def test_polling_never_reaches_the_network(monkeypatch):
    """The whole safety argument in one assertion. poll() runs on the UI
    thread; a network call there is the sixty-second stall all over again."""
    import queue as _q
    from mc_pack_converter.gui import DEFAULT_TARGET, GuiState
    from mc_pack_converter.webui import update as up
    from mc_pack_converter.webui.api import Api

    def forbidden(*a, **k):
        raise AssertionError("poll() performed a network call")

    monkeypatch.setattr(up, "_http_get", forbidden, raising=True)
    monkeypatch.setattr(up, "latest_sha", forbidden, raising=True)
    monkeypatch.setattr(up, "check", forbidden, raising=True)
    api = Api(GuiState(None, DEFAULT_TARGET, []), _q.Queue())
    api.poll()


def test_the_checker_stores_what_it_finds_and_swallows_what_it_cannot(tmp_path):
    """start_update_check runs on its own thread; here it is driven directly so
    the assertion is about the outcome, not about scheduling."""
    from mc_pack_converter.gui import DEFAULT_TARGET, GuiState
    from mc_pack_converter.webui.update import record_sha, run_update_check
    st = GuiState(None, DEFAULT_TARGET, [])
    record_sha("a" * 40, root=tmp_path)
    run_update_check(st, root=tmp_path, fetch=lambda url, timeout: "b" * 40)
    assert "Install-MCPackConverter.cmd" in st.to_dict()["update"]

    st2 = GuiState(None, DEFAULT_TARGET, [])
    def boom(url, timeout):
        raise OSError("no network")
    run_update_check(st2, root=tmp_path, fetch=boom)
    assert not st2.to_dict().get("update")


def test_the_check_thread_is_a_daemon_and_never_raises(tmp_path):
    """A background thread that raises on a machine with no network would
    print a traceback into a windowed app that has no console."""
    from mc_pack_converter.gui import DEFAULT_TARGET, GuiState
    from mc_pack_converter.webui.update import start_update_check
    st = GuiState(None, DEFAULT_TARGET, [])
    def boom(url, timeout):
        raise OSError("no network")
    t = start_update_check(st, root=tmp_path, fetch=boom)
    assert t.daemon
    t.join(timeout=5)
    assert not t.is_alive()
    assert not st.to_dict().get("update")


def _asset(name: str) -> str:
    from pathlib import Path
    import mc_pack_converter.webui as w
    return (Path(w.__file__).parent / "assets" / name).read_text()


def test_the_page_has_somewhere_to_put_the_notice():
    assert 'id="update"' in _asset("index.html")


def test_the_page_actually_binds_the_notice():
    """A model field nothing reads is the failure this app has already shipped
    twice: a page that is live and wired to nothing."""
    js = _asset("app.js")
    assert 'M.update' in js
    assert '$("update")' in js


def test_the_notice_starts_hidden():
    """It must not flash an empty line before the first poll answers."""
    html = _asset("index.html")
    line = next(l for l in html.splitlines() if 'id="update"' in l)
    assert "hidden" in line
