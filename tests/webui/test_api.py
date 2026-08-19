import base64, io, queue, zipfile
from pathlib import Path
import pytest
from PIL import Image
from mc_pack_converter.gui import GuiState
from mc_pack_converter.webui.api import EMPTY_SHEET, Api

A = "assets/minecraft/"


def _png(w, h):
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (0, 200, 0, 255)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def done_api(tmp_path):
    out = tmp_path / "MyPack-26.2.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(A + "textures/item/apple.png", _png(16, 16))
        z.writestr(A + "textures/gui/big.png", _png(256, 256))
    from types import SimpleNamespace
    from mc_pack_converter.pipeline import Severity
    result = SimpleNamespace(
        ctx=SimpleNamespace(findings=[]), out_path=out, reports={},
        wrote_zip=True, has_errors=False,
        counts={s: 0 for s in Severity})
    state = GuiState(Path("MyPack.zip"), "26.2")
    q = queue.Queue()
    api = Api(state, q)
    q.put(("done", result))
    api.poll()
    return api


def test_poll_drains_the_queue_into_the_state():
    state = GuiState(Path("MyPack.zip"), "26.2")
    q = queue.Queue()
    api = Api(state, q)
    q.put(("stage", "ingest", 1, 20))
    q.put(("stage", "atlas_remap", 8, 20))
    d = api.poll()
    assert (d["screen"], d["done"], d["total"]) == ("progress", 8, 20)


def test_poll_on_an_empty_queue_still_returns_the_current_state():
    api = Api(GuiState(Path("MyPack.zip"), "26.2"), queue.Queue())
    assert api.poll()["screen"] == "progress"


def test_sheet_is_handed_over_once_the_worker_has_built_it(done_api):
    """api.sheet() must stay CHEAP: pywebview runs js_api calls on the UI
    thread, so building the sheet here froze the window. The worker builds it
    and posts it; this is a handoff."""
    from mc_pack_converter.webui.sheet import build_sheet
    state = done_api._state
    assert done_api.sheet() == EMPTY_SHEET      # nothing built yet
    state.handle(("sheet", build_sheet(state.result.out_path)))
    sheet = done_api.sheet()
    assert sheet["total"] == 2
    assert {s["label"] for s in sheet["sections"]} == {"GUI", "Items"}


def test_sheet_is_built_once_and_cached(done_api):
    assert done_api.sheet() is done_api.sheet()


def test_sheet_never_builds_on_the_ui_thread(done_api, monkeypatch):
    """A guard, not a nicety: if anyone reintroduces a build inside sheet(),
    the window freezes on Windows and no test would otherwise notice."""
    import mc_pack_converter.webui.api as api_mod
    def boom(*a, **k):
        raise AssertionError("build_sheet must not run inside api.sheet()")
    monkeypatch.setattr(api_mod, "build_sheet", boom, raising=False)
    done_api.sheet()


def test_sheet_before_the_result_screen_is_empty_rather_than_an_error():
    api = Api(GuiState(Path("MyPack.zip"), "26.2"), queue.Queue())
    assert api.sheet() == {"sections": [], "excluded": [], "total": 0}


def test_texture_serves_the_full_size_original_not_the_thumbnail(done_api):
    uri = done_api.texture(A + "textures/gui/big.png")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(io.BytesIO(raw)).size == (256, 256)


def test_texture_refuses_a_path_that_is_not_in_the_zip(done_api):
    """The path comes from JavaScript. Anything not an entry of this zip is
    refused -- no filesystem read reachable from the page."""
    assert done_api.texture("../../../etc/passwd") == ""
    assert done_api.texture("/etc/passwd") == ""
    assert done_api.texture(A + "textures/item/nope.png") == ""


def test_a_malformed_message_does_not_break_poll():
    state = GuiState(Path("MyPack.zip"), "26.2")
    q = queue.Queue()
    api = Api(state, q)
    q.put(("stage",))
    q.put(None)
    assert api.poll()["screen"] == "progress"


def _idle_api(tmp_path):
    state = GuiState(None, "26.2")
    started = []
    return Api(state, queue.Queue(), on_start=started.append), state, started


def test_start_rejects_a_pack_that_cannot_be_read(tmp_path):
    """The reason is RETURNED, not raised: a windowed exe has nowhere to raise
    to, and the page shows the message in place."""
    api, state, started = _idle_api(tmp_path)
    problem = api.start(str(tmp_path / "nope.zip"))
    assert "no such pack" in problem
    assert state.screen == "idle"      # still waiting for a good one
    assert started == []


def test_start_rejects_a_file_that_is_not_a_zip(tmp_path):
    junk = tmp_path / "renamed.zip"
    junk.write_bytes(b"not a zip at all")
    api, state, started = _idle_api(tmp_path)
    assert "not a readable zip" in api.start(str(junk))
    assert started == []


def test_start_accepts_a_real_pack_and_launches_the_worker(tmp_path):
    pack = tmp_path / "ok.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("pack.mcmeta", "{}")
    api, state, started = _idle_api(tmp_path)
    assert api.start(str(pack)) == ""
    assert state.screen == "progress"
    assert started == [pack]


def test_a_second_drop_while_converting_is_ignored(tmp_path):
    """Otherwise a stray drop would start a second conversion over the first."""
    pack = tmp_path / "ok.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("pack.mcmeta", "{}")
    api, state, started = _idle_api(tmp_path)
    api.start(str(pack))
    assert api.start(str(pack)) == ""
    assert started == [pack]           # not started twice


def test_no_background_when_the_pack_ships_no_stone(done_api):
    """No stone, no wall: the app falls back to its own rather than inventing
    something from whatever textures happen to be there."""
    assert "background" not in done_api.poll()


def test_the_background_is_built_from_the_packs_own_blocks(tmp_path, monkeypatch):
    """The window wears the pack you converted: its stone, its dirt, its ores."""
    import mc_pack_converter.webui.api as api_mod
    monkeypatch.setattr(api_mod, "remember_wall", lambda png: None)
    out = tmp_path / "MyPack-26.2.zip"
    with zipfile.ZipFile(out, "w") as z:
        for b in ("stone", "dirt", "grass_block_side", "coal_ore"):
            z.writestr(A + f"textures/block/{b}.png", _png(16, 16))
    from types import SimpleNamespace
    from mc_pack_converter.pipeline import Severity
    state = GuiState(Path("MyPack.zip"), "26.2")
    api = Api(state, queue.Queue())
    state.handle(("done", SimpleNamespace(
        ctx=SimpleNamespace(findings=[]), out_path=out, reports={},
        wrote_zip=True, has_errors=False, counts={s: 0 for s in Severity})))
    assert api.poll()["background"].startswith("data:image/png;base64,")


def test_the_page_is_offered_every_target_the_cli_has(tmp_path):
    """The window must not drift from the CLI's list -- a version one can
    produce and the other cannot is a bug waiting to be reported as 'it made
    the wrong pack'."""
    from mc_pack_converter.cli import TARGETS
    api, state, _ = _idle_api(tmp_path)
    offered = api.targets()
    assert offered["targets"] == TARGETS
    assert offered["current"] == state.target


def test_choosing_a_target_converts_to_that_version(tmp_path):
    pack = tmp_path / "ok.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("pack.mcmeta", "{}")
    api, state, started = _idle_api(tmp_path)
    assert api.start(str(pack), "26.1.2") == ""
    assert state.target == "26.1.2"
    assert started == [pack]


def test_an_unknown_target_is_refused_rather_than_guessed(tmp_path):
    pack = tmp_path / "ok.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("pack.mcmeta", "{}")
    api, state, started = _idle_api(tmp_path)
    assert "unknown version" in api.start(str(pack), "1.8.9")
    assert state.screen == "idle"
    assert started == []


def test_no_target_given_keeps_the_default(tmp_path):
    from mc_pack_converter.job import DEFAULT_TARGET
    pack = tmp_path / "ok.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("pack.mcmeta", "{}")
    api, state, _ = _idle_api(tmp_path)
    api.start(str(pack))
    assert state.target == DEFAULT_TARGET


def test_the_background_appears_when_the_run_finishes_not_only_at_launch(tmp_path, monkeypatch):
    """The bug Mason hit: polling on the drop screen cached the empty answer,
    and "" is not None, so the wall was never built when the conversion
    finished -- and so never cached for next launch either. Black forever."""
    # patch where api.py LOOKS them up, not where they are defined: it does
    # `from .wall import ...`, so the module attribute is a separate binding
    import mc_pack_converter.webui.api as api_mod
    remembered = []
    monkeypatch.setattr(api_mod, "remember_wall", remembered.append)
    monkeypatch.setattr(api_mod, "remembered_wall", lambda: "")

    out = tmp_path / "MyPack-26.2.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(A + "textures/gui/options_background.png", _png(16, 16))

    state = GuiState(None, "26.2")
    api = Api(state, queue.Queue())
    assert "background" not in api.poll()      # drop screen, nothing cached

    from types import SimpleNamespace
    from mc_pack_converter.pipeline import Severity
    state.start(out)
    state.handle(("done", SimpleNamespace(
        ctx=SimpleNamespace(findings=[]), out_path=out, reports={},
        wrote_zip=True, has_errors=False, counts={s: 0 for s in Severity})))

    assert api.poll()["background"].startswith("data:image/png;base64,")
    assert remembered, "the wall was not kept for the next launch"


def _dressed_api(tmp_path, monkeypatch, blocks):
    """An Api sitting on a finished run whose output ships `blocks`."""
    import mc_pack_converter.webui.api as api_mod
    from types import SimpleNamespace
    from mc_pack_converter.pipeline import Severity
    monkeypatch.setattr(api_mod, "remember_wall", lambda png: None)
    monkeypatch.setattr(api_mod, "remember_grass", lambda png: None)
    out = tmp_path / "MyPack-26.2.zip"
    with zipfile.ZipFile(out, "w") as z:
        for b in blocks:
            z.writestr(A + f"textures/block/{b}.png", _png(16, 16))
    state = GuiState(Path("MyPack.zip"), "26.2")
    api = Api(state, queue.Queue())
    state.handle(("done", SimpleNamespace(
        ctx=SimpleNamespace(findings=[]), out_path=out, reports={},
        wrote_zip=True, has_errors=False, counts={s: 0 for s in Severity})))
    return api


def test_the_page_is_given_the_grass_layer_and_the_grounds_measured_size(
        tmp_path, monkeypatch):
    """The ground is a 16-tile field, not a single tile, so the page cannot
    guess its background-size -- it has to be measured and sent."""
    d = _dressed_api(tmp_path, monkeypatch,
                     ("stone", "grass_block_side", "iron_ore")).poll()
    assert d["background"].startswith("data:image/png;base64,")
    assert d["grass"].startswith("data:image/png;base64,")
    assert d["backgroundSize"] == "1024px 1024px"      # 16 tiles at 64px each


def test_no_grass_layer_when_the_pack_ships_no_grass_block(tmp_path, monkeypatch):
    d = _dressed_api(tmp_path, monkeypatch, ("stone",)).poll()
    assert "grass" not in d
    assert d["background"].startswith("data:image/png;base64,")


def test_a_single_tile_background_is_still_sized_at_one_block(tmp_path, monkeypatch):
    """The verbatim fallback is one 16px texture; sizing it like a field would
    blow one block up to fill the window."""
    d = _dressed_api(tmp_path, monkeypatch, ("dirt",)).poll()
    assert d["backgroundSize"] == "64px 64px"


# --- converting a second pack without restarting the app -------------------

def test_a_second_pack_can_be_dropped_once_the_first_has_finished(tmp_path, monkeypatch):
    """Reported from the exe: dropping another pack on the result screen did
    nothing and the window kept showing the previous pack, so the only way to
    convert a second one was Task Manager. start() refused on the result
    screen AND returned "" -- which the page reads as 'started fine'."""
    api = _dressed_api(tmp_path, monkeypatch, ("stone",))
    started: list = []
    api._on_start = started.append
    second = tmp_path / "Other.zip"
    with zipfile.ZipFile(second, "w") as z:
        z.writestr("pack.mcmeta", '{"pack": {"pack_format": 1}}')
        z.writestr(A + "textures/block/stone.png", _png(16, 16))

    assert api.start(str(second)) == ""
    assert started == [second]
    assert api._state.screen == "progress"


def test_a_drop_mid_conversion_is_still_ignored(tmp_path):
    """Only a FINISHED run may be replaced. A drop while the worker is still
    going would race two conversions onto the same output zip."""
    pack = tmp_path / "p.zip"
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("pack.mcmeta", '{"pack": {"pack_format": 1}}')
    api, state, started = _idle_api(tmp_path)
    api.start(str(pack))
    assert api.start(str(pack)) == ""
    assert started == [pack]


def test_the_page_announces_itself_so_a_dead_bridge_is_visible_in_the_log(
        tmp_path, monkeypatch):
    """If the launch log has no "page ready" line, JavaScript never reached
    Python -- which is the difference between a window that is merely idle and
    one whose bridge never started."""
    import mc_pack_converter.gui as gui
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(gui, "_diag_file", None)
    api, state, started = _idle_api(tmp_path)

    assert api.ready() is True
    assert "page ready" in (tmp_path / "MCPackConverter" / "last-run.log").read_text()


# --- what pywebview walks when it builds the JS bridge ---------------------

def _bridge_walk(obj, seen=None, out=None):
    """pywebview's own algorithm for deciding what to expose to JavaScript.

    Copied from webview/util.py inject_pywebview. The part that matters is
    that it recurses into every PUBLIC non-callable attribute, and that
    getattr() RUNS property getters while it does so.
    """
    if seen is None:
        seen, out = [], []
    if id(obj) in seen:
        return out
    seen.append(id(obj))
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(obj, name)
        except Exception:
            continue
        if callable(attr):
            out.append(name)
        elif hasattr(attr, "__module__"):
            _bridge_walk(attr, seen, out)
    return out


class _TouchyWindow:
    """Stands in for pywebview's Window, whose width/height/x/y properties
    each wait up to 15 seconds on its 'shown' event."""

    def __init__(self):
        self.touched = []

    def _blocking(self):
        self.touched.append("property")
        raise AssertionError("a blocking Window property was read")

    width = property(_blocking)
    height = property(_blocking)
    x = property(_blocking)
    y = property(_blocking)

    def destroy(self):
        pass

    def create_file_dialog(self, *a, **k):
        pass


def test_the_window_is_held_privately_so_the_bridge_never_walks_into_it(tmp_path):
    """Holding the pywebview window under a PUBLIC name stalled the page.

    pywebview builds the bridge on a background thread by walking dir() on
    this object; every public attribute is recursed into and every property
    getter runs. Window.width/height/x/y each wait up to 15s on the window's
    'shown' event, so a public reference stalls injection for up to a minute
    before JavaScript can reach Python at all -- measured at 60.0s public
    versus 0.0s private. The user saw a live window on the stand-in
    background with no version list and nothing wired up.
    """
    api, state, started = _idle_api(tmp_path)
    win = _TouchyWindow()
    api._window = win

    exposed = _bridge_walk(api)

    assert win.touched == []
    assert set(exposed) == {"ready", "targets", "start", "poll", "sheet",
                            "texture", "open_folder", "pick"}


def test_the_api_holds_nothing_public_that_is_not_a_method(tmp_path):
    """The guard for the bug above, at its source. Any public non-callable on
    this object is something pywebview will recurse into when it builds the
    bridge -- so the window, the state and the queue must all stay private.
    """
    api, state, started = _idle_api(tmp_path)
    public = [n for n in dir(api) if not n.startswith("_")]
    assert [n for n in public if not callable(getattr(api, n))] == []
