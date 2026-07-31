from PIL import Image
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages import derive_sprites as derive_mod
from mc_pack_converter.stages.derive_sprites import derive_sprites

SRC = "assets/minecraft/textures/gui/container/inventory.png"
OUT = "assets/minecraft/textures/gui/sprites/container/inventory/effect_background_small.png"

# Two 16-wide pieces of a 120x32 panel, joined into a 32x32 sprite.
TABLE = {
    OUT: {"source": SRC, "ref": [256, 256], "size": [32, 32],
          "pieces": [{"from": [0, 166, 16, 32], "to": [0, 0]},
                     {"from": [104, 166, 16, 32], "to": [16, 0]}]}
}


def _panel(root, size, left=(200, 30, 40, 255), right=(30, 60, 200, 255)):
    """Atlas whose panel's left 16 and right 16 ref-columns are distinct colours."""
    p = root / SRC
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    s = size[0] // 256
    im.paste(Image.new("RGBA", (16 * s, 32 * s), left), (0, 166 * s))
    im.paste(Image.new("RGBA", (16 * s, 32 * s), right), (104 * s, 166 * s))
    im.save(p)
    return p


def test_pieces_are_joined_at_standard_res(mini_pack, monkeypatch):
    root = mini_pack()
    _panel(root, (256, 256))
    monkeypatch.setattr(derive_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)
    im = Image.open(root / OUT).convert("RGBA")
    assert im.size == (32, 32)
    assert im.getpixel((0, 0)) == (200, 30, 40, 255)     # left piece
    assert im.getpixel((15, 31)) == (200, 30, 40, 255)
    assert im.getpixel((16, 0)) == (30, 60, 200, 255)    # right piece
    assert im.getpixel((31, 31)) == (30, 60, 200, 255)


def test_pieces_scale_with_resolution(mini_pack, monkeypatch):
    # M8SON ships a 512x512 inventory.png; ref-space coords must scale.
    root = mini_pack()
    _panel(root, (512, 512))
    monkeypatch.setattr(derive_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)
    im = Image.open(root / OUT).convert("RGBA")
    assert im.size == (64, 64)
    assert im.getpixel((0, 0)) == (200, 30, 40, 255)
    assert im.getpixel((32, 0)) == (30, 60, 200, 255)
    assert im.getpixel((63, 63)) == (30, 60, 200, 255)


def test_overwrites_what_the_slicer_wrote(mini_pack, monkeypatch):
    # The whole point: slice.py writes a wrong sprite here for 1.8.9 input
    # (the 1.20.2 slicer reads y=198, which is the effect ICON grid in 1.8.9).
    root = mini_pack()
    _panel(root, (256, 256))
    stale = root / OUT
    stale.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (32, 32), (1, 2, 3, 255)).save(stale)
    monkeypatch.setattr(derive_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)
    assert Image.open(stale).convert("RGBA").getpixel((0, 0)) == (200, 30, 40, 255)


def test_missing_source_is_skipped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(derive_mod, "load_table", lambda n: TABLE)
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)  # must not raise
    assert not (root / OUT).exists()


def test_shipped_table_derives_the_effect_background(mini_pack):
    """The real data/derived_sprites.json, not a fixture."""
    root = mini_pack()
    _panel(root, (512, 512))
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)
    im = Image.open(root / OUT).convert("RGBA")
    assert im.size == (64, 64)
    assert any(f.stage == "derive_sprites" and f.severity is Severity.INFO
               for f in ctx.findings)
