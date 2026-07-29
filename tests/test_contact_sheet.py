from PIL import Image

from mc_pack_converter.contact_sheet import ATLAS_1_14, DARK, LIGHT, build_contact_sheet


def _sprite(root, rel, size=(8, 8), color=(200, 40, 40, 255)):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(p)


def test_sheet_lays_out_one_tile_per_sprite(tmp_path):
    rels = [f"textures/particle/p{i}.png" for i in range(3)]
    for r in rels:
        _sprite(tmp_path, r)
    out = tmp_path / "sheet.png"
    assert build_contact_sheet(tmp_path, rels, out) is True
    with Image.open(out) as im:
        # 3 sprites -> one row of 8 columns
        assert im.size == (8 * 104, 1 * 88)
        assert im.getchannel("A").getbbox() is not None  # not blank


def test_sheet_wraps_to_multiple_rows(tmp_path):
    rels = [f"textures/particle/p{i}.png" for i in range(9)]
    for r in rels:
        _sprite(tmp_path, r)
    out = tmp_path / "sheet.png"
    build_contact_sheet(tmp_path, rels, out)
    with Image.open(out) as im:
        assert im.size == (8 * 104, 2 * 88)


def test_sheet_returns_false_with_nothing_to_draw(tmp_path):
    out = tmp_path / "sheet.png"
    assert build_contact_sheet(tmp_path, [], out) is False
    assert not out.exists()


def test_sheet_ignores_missing_files(tmp_path):
    _sprite(tmp_path, "textures/particle/real.png")
    out = tmp_path / "sheet.png"
    assert build_contact_sheet(
        tmp_path, ["textures/particle/real.png", "textures/particle/gone.png"],
        out) is True
    with Image.open(out) as im:
        assert im.size == (8 * 104, 1 * 88)


def test_sheet_handles_sprites_larger_than_a_tile(tmp_path):
    # A 2x painting sprite is 128x96; it must scale down, not overflow.
    _sprite(tmp_path, "textures/painting/pigscene.png", size=(128, 96))
    out = tmp_path / "sheet.png"
    build_contact_sheet(tmp_path, ["textures/painting/pigscene.png"], out)
    with Image.open(out) as im:
        assert im.size == (8 * 104, 1 * 88)


def test_sheet_shows_checkerboard_through_transparent_region(tmp_path):
    # A 64x64 sprite (exactly one tile, no scaling ambiguity): left half
    # opaque, right half fully transparent. The transparent half must let
    # the checkerboard show through, not the sprite's own (absent) colour.
    rel = "textures/particle/half.png"
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    sprite_color = (10, 20, 230, 255)
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    im.paste(Image.new("RGBA", (32, 64), sprite_color), (0, 0))
    im.save(p)

    out = tmp_path / "sheet.png"
    assert build_contact_sheet(tmp_path, [rel], out) is True
    with Image.open(out) as sheet:
        sheet = sheet.convert("RGBA")
        # The single tile sits at sheet-space (20, 6)-(84, 70): opaque sprite
        # half covers local x in [20, 52), transparent half [52, 84).
        assert sheet.getpixel((30, 30)) == sprite_color

        # Two points in the transparent half landing on opposite checkerboard
        # squares confirm the actual pattern shows through, not a solid fill.
        assert sheet.getpixel((60, 30)) == LIGHT
        assert sheet.getpixel((70, 30)) == DARK


def test_atlas_set_names_the_three_1_14_sources():
    assert ATLAS_1_14 == {
        "assets/minecraft/textures/particle/particles.png",
        "assets/minecraft/textures/entity/explosion.png",
        "assets/minecraft/textures/painting/paintings_kristoffer_zetterstrand.png",
    }
