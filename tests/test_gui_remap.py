from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages import gui_remap as mod
from mc_pack_converter.stages.gui_remap import gui_remap


def test_move_shifts_region_and_clears_old_at_2x(mini_pack, monkeypatch):
    root = mini_pack()
    p = root / "assets/minecraft/textures/gui/container/inventory.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))  # transparent, 2x
    # put an opaque 8x8 marker at ref (78,24) -> 2x (156,48)
    for x in range(156, 172):
        for y in range(48, 64):
            img.putpixel((x, y), (255, 0, 0, 255))
    img.save(p)
    monkeypatch.setattr(mod, "load_table", lambda n: {
        "textures/gui/container/inventory.png": {
            "ref": [256, 256], "moves": [{"from": [78, 24, 8, 8], "to": [88, 16]}]}})
    ctx = ConversionContext(root=root)
    gui_remap(ctx)
    out = Image.open(p).convert("RGBA")
    # marker moved to ref (88,16) -> 2x (176,32); old spot (156,48) cleared
    assert out.getpixel((178, 34))[3] > 0      # present at new location
    assert out.getpixel((158, 50))[3] == 0     # cleared at old location


def test_comment_key_skipped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"_comment": "x"})
    ctx = ConversionContext(root=root)
    gui_remap(ctx)  # must not raise on the comment key
