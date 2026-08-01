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


def test_brewing_potion_slots_move_down_five(mini_pack):
    """1.9 moved the three potion slots down 5px and 1.8.9 packs never followed.

    Derived by cross-correlating vanilla 1.8.9 against modern over the slot
    cluster: best match at (0,+5), SAD 196,608 -> 32,226. The ingredient slot
    above them did NOT move, which the same measurement confirms at (0,0).
    Reported from in-game testing as "brewing potion boxes slightly off on
    every pack".
    """
    root = mini_pack()
    p = root / "assets/minecraft/textures/gui/container/brewing_stand.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (256, 256), (200, 200, 200, 255))
    im.paste(Image.new("RGBA", (64, 26), (10, 20, 30, 255)), (55, 45))   # slot cluster
    im.save(p)
    gui_remap(ConversionContext(root=root))
    out = Image.open(p).convert("RGBA")
    assert out.getpixel((56, 51)) == (10, 20, 30, 255), "cluster must land 5px lower"
    assert out.getpixel((56, 46)) != (10, 20, 30, 255), "old position must be healed"


def test_brewing_gains_a_blaze_powder_slot_box(mini_pack):
    """Modern has a fuel slot at (16,16); 1.8.9 has nothing there.

    Copied from the pack's own empty ingredient slot at (78,16), so the box is
    the pack's art rather than invented. The source must survive the copy.
    """
    root = mini_pack()
    p = root / "assets/minecraft/textures/gui/container/brewing_stand.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (256, 256), (200, 200, 200, 255))
    im.paste(Image.new("RGBA", (18, 18), (90, 40, 60, 255)), (78, 16))   # ingredient slot
    im.save(p)
    gui_remap(ConversionContext(root=root))
    out = Image.open(p).convert("RGBA")
    assert out.getpixel((20, 20)) == (90, 40, 60, 255), "blaze slot box copied in"
    assert out.getpixel((80, 20)) == (90, 40, 60, 255), "source slot must remain"
