from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages import gui_remap as mod
from mc_pack_converter.stages.gui_remap import gui_remap

_MOVE = {"textures/gui/container/inventory.png": {
    "ref": [256, 256], "moves": [{"from": [78, 24, 8, 8], "to": [88, 16]}]}}


def _run(root, monkeypatch, img):
    p = root / "assets/minecraft/textures/gui/container/inventory.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(p)
    monkeypatch.setattr(mod, "load_table", lambda n: _MOVE)
    gui_remap(ConversionContext(root=root))
    return Image.open(p).convert("RGBA")


def test_see_through_pack_heals_transparent(mini_pack, monkeypatch):
    # transparent background, opaque marker at ref (78,24) -> 2x (156,48)
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    for x in range(156, 172):
        for y in range(48, 64):
            img.putpixel((x, y), (255, 0, 0, 255))
    out = _run(mini_pack(), monkeypatch, img)
    assert out.getpixel((178, 34))[3] > 0        # marker present at new location
    assert out.getpixel((158, 50)) == (0, 0, 0, 0)  # old spot healed to transparent


def test_solid_panel_pack_heals_with_panel_colour(mini_pack, monkeypatch):
    panel = (198, 198, 198, 255)
    img = Image.new("RGBA", (512, 512), panel)   # SOLID panel everywhere
    for x in range(156, 172):
        for y in range(48, 64):
            img.putpixel((x, y), (255, 0, 0, 255))  # marker on the panel
    out = _run(mini_pack(), monkeypatch, img)
    assert out.getpixel((178, 34)) == (255, 0, 0, 255)  # marker moved to new location
    # old spot healed with the panel colour (NOT transparent hole, NOT leftover marker)
    assert out.getpixel((158, 50)) == panel


def test_comment_key_skipped(mini_pack, monkeypatch):
    monkeypatch.setattr(mod, "load_table", lambda n: {"_comment": "x"})
    gui_remap(ConversionContext(root=mini_pack()))  # must not raise
