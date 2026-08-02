"""Nine-slice GUI sprites need metadata matching their actual size.

Vanilla's widget/button.png is 200x20 and its .mcmeta says so. A pack shipping
an 800x80 button without its own .mcmeta keeps vanilla's, which still claims
200x20 — and the sprite renders as the missing texture. 72 of 170 corpus packs
were affected, with no warning, because nothing is wrong with the texture.
"""
import json
from PIL import Image
from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.gui_scaling import gui_scaling

SPR = "assets/minecraft/textures/gui/sprites"


def _sprite(root, name, size):
    p = root / SPR / f"{name}.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (1, 2, 3, 255)).save(p)
    return p


def _meta(p):
    return json.loads(p.with_name(p.name + ".mcmeta").read_text())["gui"]["scaling"]


def test_button_metadata_scales_to_a_4x_pack(mini_pack):
    root = mini_pack()
    p = _sprite(root, "widget/button", (800, 80))
    gui_scaling(ConversionContext(root=root))
    m = _meta(p)
    assert (m["width"], m["height"]) == (800, 80)
    assert m["border"] == 12                      # vanilla 3 at 4x
    assert m["type"] == "nine_slice"


def test_button_metadata_scales_to_a_2x_pack(mini_pack):
    root = mini_pack()
    p = _sprite(root, "widget/button", (400, 40))
    gui_scaling(ConversionContext(root=root))
    m = _meta(p)
    assert (m["width"], m["height"], m["border"]) == (400, 40, 6)


def test_one_x_pack_gets_matching_metadata(mini_pack):
    root = mini_pack()
    p = _sprite(root, "widget/button", (200, 20))
    gui_scaling(ConversionContext(root=root))
    m = _meta(p)
    assert (m["width"], m["height"], m["border"]) == (200, 20, 3)


def test_per_edge_borders_scale_on_the_right_axis(mini_pack):
    """toast/system has border {left:17, top:30, right:4, bottom:4}."""
    root = mini_pack()
    p = _sprite(root, "toast/system", (320, 128))          # 160x64 at 2x
    gui_scaling(ConversionContext(root=root))
    m = _meta(p)
    assert (m["width"], m["height"]) == (320, 128)
    assert m["border"] == {"left": 34, "top": 60, "right": 8, "bottom": 8}


def test_sprites_the_pack_does_not_ship_get_nothing(mini_pack):
    root = mini_pack()
    ctx = ConversionContext(root=root)
    gui_scaling(ctx)
    assert not (root / SPR).exists() or not list((root / SPR).rglob("*.mcmeta"))
    assert any("0 sprites" in f.message for f in ctx.findings)
