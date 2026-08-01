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


WIDGETS = "assets/minecraft/textures/gui/widgets.png"
OFF_L = "assets/minecraft/textures/gui/sprites/hud/hotbar_offhand_left.png"
OFF_R = "assets/minecraft/textures/gui/sprites/hud/hotbar_offhand_right.png"


def _hotbar(root, size=(256, 256), left=(200, 30, 40, 255), right=(30, 60, 200, 255)):
    """widgets.png whose hotbar has distinctly coloured left and right ends."""
    p = root / WIDGETS
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    s = size[0] // 256
    im.paste(Image.new("RGBA", (11 * s, 22 * s), left), (0, 0))
    im.paste(Image.new("RGBA", (11 * s, 22 * s), right), (171 * s, 0))
    im.save(p)
    return p


def test_offhand_is_composed_from_both_hotbar_ends(mini_pack):
    """1.8.9 has no offhand art, so it is built from the pack's own hotbar.

    Both outer borders must be real pack pixels — a single cut from one end
    leaves the box asymmetric (outer border one side, inter-slot divider the
    other).
    """
    root = mini_pack()
    _hotbar(root)
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)
    im = Image.open(root / OFF_L).convert("RGBA")
    assert im.size == (29, 24)
    assert im.getpixel((0, 1)) == (200, 30, 40, 255)      # hotbar left end
    assert im.getpixel((21, 1)) == (30, 60, 200, 255)     # hotbar right end
    assert im.getpixel((28, 12))[3] == 0                  # padding stays clear
    right = Image.open(root / OFF_R).convert("RGBA")
    assert right.getpixel((7, 1)) == (200, 30, 40, 255)   # box offset by 7
    assert right.getpixel((0, 12))[3] == 0


def test_offhand_scales_with_pack_resolution(mini_pack):
    root = mini_pack()
    _hotbar(root, size=(512, 512))
    derive_sprites(ConversionContext(root=root))
    im = Image.open(root / OFF_L).convert("RGBA")
    assert im.size == (58, 48)
    assert im.getpixel((0, 2)) == (200, 30, 40, 255)


def test_offhand_skipped_when_the_pack_has_no_widgets(mini_pack):
    root = mini_pack()
    derive_sprites(ConversionContext(root=root))   # must not raise
    assert not (root / OFF_L).exists()


def test_all_blank_sources_leave_the_sprite_to_vanilla(mini_pack):
    """A composed sprite that is entirely transparent must not be written.

    Writing it would OVERRIDE vanilla with an invisible sprite instead of
    falling back — docs/known-issues.md #1, reachable here because a pack's
    source region can be empty even when the file exists.
    """
    root = mini_pack()
    p = root / WIDGETS
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(p)   # blank widgets.png
    ctx = ConversionContext(root=root)
    derive_sprites(ctx)
    assert not (root / OFF_L).exists()
    assert any("left to vanilla" in f.message for f in ctx.findings)
