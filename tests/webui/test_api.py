import base64, io, queue, zipfile
from pathlib import Path
import pytest
from PIL import Image
from mc_pack_converter.gui import GuiState
from mc_pack_converter.webui.api import Api

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


def test_sheet_is_built_from_the_output_zip(done_api):
    sheet = done_api.sheet()
    assert sheet["total"] == 2
    assert {s["label"] for s in sheet["sections"]} == {"GUI", "Items"}


def test_sheet_is_built_once_and_cached(done_api):
    assert done_api.sheet() is done_api.sheet()


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


def test_the_page_wears_the_packs_own_background(done_api):
    d = done_api.poll()
    assert "background" not in d       # the fixture zip ships no gui background


def test_the_background_is_served_when_the_pack_has_one(tmp_path):
    out = tmp_path / "MyPack-26.2.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(A + "textures/gui/options_background.png", _png(16, 16))
    from types import SimpleNamespace
    from mc_pack_converter.pipeline import Severity
    state = GuiState(Path("MyPack.zip"), "26.2")
    api = Api(state, queue.Queue())
    state.handle(("done", SimpleNamespace(
        ctx=SimpleNamespace(findings=[]), out_path=out, reports={},
        wrote_zip=True, has_errors=False, counts={s: 0 for s in Severity})))
    assert api.poll()["background"].startswith("data:image/png;base64,")
