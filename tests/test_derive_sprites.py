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


def test_offhand_does_not_scale_with_pack_resolution(mini_pack):
    """It used to, and that is what broke the hotbar.

    A 2x pack composed a 58x48 offhand, a 4x pack 116x96. The 4x one made
    hud/hotbar render magenta in 26.1.2 (bisected in-game 2026-08-02). The cap
    is vanilla size because that is the value actually proven on the failing
    pack; 2x is only known good on M8SON and was never tested on a 4x pack.
    Pixel content still comes from the pack's own art, just downsampled.
    """
    root = mini_pack()
    _hotbar(root, size=(512, 512))
    derive_sprites(ConversionContext(root=root))
    im = Image.open(root / OFF_L).convert("RGBA")
    assert im.size == (29, 24)
    assert im.getpixel((0, 1)) == (200, 30, 40, 255)


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


def test_offhand_is_capped_at_its_declared_size(mini_pack):
    """A 4x pack's composed offhand must not ship at 4x.

    Emitted at the pack's own scale, hotbar_offhand_left/right came out 116x96
    against vanilla's 29x24 — and their mere presence made hud/hotbar render as
    the magenta missing texture in 26.1.2. Bisected in-game 2026-08-02: the
    identical build with those two sprites downscaled to 29x24 renders fine, so
    it is the size, not the art. `max_scale` in the table is the cap.
    """
    root = mini_pack()
    p = root / WIDGETS
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))          # 4x pack
    im.paste(Image.new("RGBA", (11 * 4, 22 * 4), (90, 90, 90, 255)), (0, 0))
    im.paste(Image.new("RGBA", (11 * 4, 22 * 4), (60, 60, 60, 255)), (171 * 4, 0))
    im.save(p)
    derive_sprites(ConversionContext(root=root))
    assert Image.open(root / OFF_L).size == (29, 24)
    assert Image.open(root / OFF_R).size == (29, 24)


def test_derived_sprite_without_a_cap_keeps_pack_scale(mini_pack):
    """Only entries that declare max_scale are capped.

    effect_background_small has no vanilla counterpart in 26.1.2 to compare
    against and was never implicated, so a 2x pack still gets it at 2x.
    """
    root = mini_pack()
    _panel(root, (512, 512))
    derive_sprites(ConversionContext(root=root))
    assert Image.open(root / OUT).size == (64, 64)
