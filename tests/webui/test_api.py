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
