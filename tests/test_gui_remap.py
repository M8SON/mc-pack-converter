from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages import gui_remap as mod
from mc_pack_converter.stages.gui_remap import gui_remap


def test_inventory_remapped_in_place_at_2x(mini_pack, monkeypatch):
    root = mini_pack()
    p = root / "assets/minecraft/textures/gui/container/inventory.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (512, 512), (100, 100, 100, 255)).save(p)  # 2x resolution
    monkeypatch.setattr(mod, "load_table", lambda n: {
        "textures/gui/container/inventory.png": {
            "ref": [256, 256],
            "ops": [[0, 0, 256, 256, 0, 0, ""], [0, 166, 16, 198, 0, 198, ""]],
        }})
    ctx = ConversionContext(root=root)
    gui_remap(ctx)
    assert p.exists()
    assert Image.open(p).size == (512, 512)  # stays at pack resolution


def test_comment_key_skipped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(mod, "load_table", lambda n: {"_comment": "x"})
    ctx = ConversionContext(root=root)
    gui_remap(ctx)  # must not raise on the comment key
