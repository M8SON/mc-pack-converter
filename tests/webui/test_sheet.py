from mc_pack_converter.webui.sheet import section_for, exclusion_for

A = "assets/minecraft/"


def test_the_seven_content_sections():
    assert section_for(A + "textures/gui/widgets.png") == "GUI"
    assert section_for(A + "textures/block/stone.png") == "Blocks"
    assert section_for(A + "textures/item/diamond_sword.png") == "Items"
    assert section_for(A + "textures/particle/particles.png") == "Particles"
    assert section_for(A + "textures/environment/sun.png") == "Sky"
    assert section_for(A + "textures/painting/kebab.png") == "Other"


def test_optifine_custom_sky_is_sky():
    assert section_for(A + "optifine/sky/world0/starfield03.png") == "Sky"


def test_armor_is_matched_before_the_mob_exclusion():
    """entity/equipment/ lives inside entity/, which is excluded wholesale.

    Measured: the pack has 147 entity textures, 12 of which are armor. Testing
    the exclusion first would hide every armor texture.
    """
    assert section_for(A + "textures/entity/equipment/humanoid/diamond.png") == "Armor"
    assert section_for(A + "textures/entity/creeper/creeper.png") is None
    assert exclusion_for(A + "textures/entity/creeper/creeper.png") == "Mob textures"


def test_the_four_exclusions():
    assert exclusion_for(A + "optifine/ctm/glass_stained/0.png") == "CTM tiles"
    assert exclusion_for(A + "textures/font/ascii.png") == "Font glyphs"
    assert exclusion_for(A + "optifine/colormap/grass.png") == "Colormaps"
    assert exclusion_for(A + "optifine/lightmap/world0.png") == "Colormaps"


def test_non_png_and_unknown_paths_are_neither_shown_nor_counted_as_excluded():
    assert section_for("pack.mcmeta") is None
    assert exclusion_for("pack.mcmeta") is None
    assert section_for(A + "sounds/random/click.ogg") is None


def test_pack_png_is_not_a_texture_section():
    assert section_for("pack.png") is None


import base64, io, zipfile
import pytest
from PIL import Image
from mc_pack_converter.webui.sheet import THUMB, build_sheet, thumb_data_uri


def _png(w, h, colour=(255, 0, 0, 255)):
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), colour).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def pack(tmp_path):
    """A zip with one entry per section plus one of each exclusion."""
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/gui/widgets.png", _png(256, 256))
        z.writestr(A + "textures/block/stone.png", _png(16, 16))
        z.writestr(A + "textures/item/apple.png", _png(16, 16))
        z.writestr(A + "textures/particle/particles.png", _png(128, 128))
        z.writestr(A + "textures/environment/sun.png", _png(32, 32))
        z.writestr(A + "textures/painting/kebab.png", _png(16, 16))
        z.writestr(A + "optifine/ctm/glass/0.png", _png(16, 16))
        z.writestr(A + "textures/entity/creeper/creeper.png", _png(64, 32))
        z.writestr(A + "textures/font/ascii.png", _png(128, 128))
        z.writestr("pack.mcmeta", b"{}")
    return path


def test_thumbnail_never_upscales_a_small_texture():
    uri = thumb_data_uri(Image.new("RGBA", (16, 16)))
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(io.BytesIO(raw)).size == (16, 16)


def test_thumbnail_downscales_to_the_box_preserving_aspect():
    uri = thumb_data_uri(Image.new("RGBA", (256, 64)))
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert Image.open(io.BytesIO(raw)).size == (THUMB, THUMB // 4)


def test_thumbnail_is_a_png_data_uri():
    assert thumb_data_uri(Image.new("RGBA", (8, 8))).startswith("data:image/png;base64,")


def test_build_sheet_sections_are_in_scroll_order(pack):
    sheet = build_sheet(pack)
    assert [s["label"] for s in sheet["sections"]] == \
        ["GUI", "Blocks", "Items", "Particles", "Sky", "Other"]


def test_a_missing_category_produces_no_empty_section(pack):
    """The fixture has no armor, so there must be no Armor heading at all."""
    assert "Armor" not in [s["label"] for s in build_sheet(pack)["sections"]]


def test_tiles_carry_the_true_source_size_not_the_thumbnail_size(pack):
    gui = next(s for s in build_sheet(pack)["sections"] if s["label"] == "GUI")
    tile = gui["tiles"][0]
    assert (tile["w"], tile["h"]) == (256, 256)
    assert tile["path"] == A + "textures/gui/widgets.png"
    assert tile["name"] == "widgets.png"


def test_exclusions_are_reported_with_counts(pack):
    excluded = {e["label"]: e["count"] for e in build_sheet(pack)["excluded"]}
    assert excluded == {"CTM tiles": 1, "Mob textures": 1, "Font glyphs": 1}


def test_total_counts_only_shown_tiles(pack):
    assert build_sheet(pack)["total"] == 6


def test_tiles_are_sorted_within_a_section(tmp_path):
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        for n in ("zebra", "apple", "mango"):
            z.writestr(A + f"textures/item/{n}.png", _png(16, 16))
    tiles = build_sheet(path)["sections"][0]["tiles"]
    assert [t["name"] for t in tiles] == ["apple.png", "mango.png", "zebra.png"]


def test_an_unreadable_png_is_skipped_rather_than_killing_the_sheet(tmp_path):
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/item/good.png", _png(16, 16))
        z.writestr(A + "textures/item/truncated.png", b"\x89PNG\r\n\x1a\n garbage")
    tiles = build_sheet(path)["sections"][0]["tiles"]
    assert [t["name"] for t in tiles] == ["good.png"]


import json
from mc_pack_converter.webui.sheet import frame_count


def _anim_zip(tmp_path, entries):
    path = tmp_path / "anim.zip"
    with zipfile.ZipFile(path, "w") as z:
        for name, blob in entries:
            z.writestr(name, blob)
    return path


def test_frame_count_derives_square_frames_because_mcmeta_never_declares_height():
    """No real .mcmeta in the corpus carries a frame height; all 10 carry only
    frames/frametime/interpolate. Minecraft's rule is square frames."""
    assert frame_count((16, 256)) == 16
    assert frame_count((32, 1024)) == 32
    assert frame_count((16, 16)) == 1


def test_frame_count_rejects_a_strip_that_is_not_a_whole_number_of_frames():
    assert frame_count((16, 40)) == 1
    assert frame_count((0, 40)) == 1


def test_a_multi_frame_strip_becomes_an_animated_tile(tmp_path):
    z = _anim_zip(tmp_path, [
        (A + "textures/block/fire_0.png", _png(16, 256)),
        (A + "textures/block/fire_0.png.mcmeta",
         json.dumps({"animation": {"frames": list(range(16))}}).encode()),
    ])
    sheet = build_sheet(z)
    assert [s["label"] for s in sheet["sections"]] == ["Animated"]
    tile = sheet["sections"][0]["tiles"][0]
    # The emitted frames are the cube SPIN, not the animation's own count --
    # angle and animation advance together in one loop.
    from mc_pack_converter.webui.sheet import SPIN
    assert len(tile["frames"]) == SPIN
    assert tile["frametime"] == 50  # one tick, the Minecraft default


def test_an_animated_texture_leaves_its_home_section(tmp_path):
    z = _anim_zip(tmp_path, [
        (A + "textures/block/stone.png", _png(16, 16)),
        (A + "textures/block/fire_0.png", _png(16, 256)),
        (A + "textures/block/fire_0.png.mcmeta",
         json.dumps({"animation": {}}).encode()),
    ])
    sheet = build_sheet(z)
    blocks = next(s for s in sheet["sections"] if s["label"] == "Blocks")
    assert [t["name"] for t in blocks["tiles"]] == ["stone.png"]
    assert sheet["total"] == 2


def test_a_sidecar_without_an_animation_key_is_not_animated(tmp_path):
    """misc/enchanted_item_glint.png.mcmeta is real and has no animation key.
    A sidecar is not proof of animation."""
    z = _anim_zip(tmp_path, [
        (A + "textures/misc/glint.png", _png(64, 64)),
        (A + "textures/misc/glint.png.mcmeta", b'{"texture": {"blur": true}}'),
    ])
    sheet = build_sheet(z)
    assert [s["label"] for s in sheet["sections"]] == ["Other"]
    assert sheet["sections"][0]["tiles"][0]["frames"] is None


def test_a_square_texture_declaring_animation_is_one_frame_and_stays_put(tmp_path):
    """block/prismarine.png is real: 16x16, with an animation block whose
    frames list indexes up to 3. One frame is not an animation."""
    z = _anim_zip(tmp_path, [
        (A + "textures/block/prismarine.png", _png(16, 16)),
        (A + "textures/block/prismarine.png.mcmeta",
         json.dumps({"animation": {"frametime": 300,
                                   "frames": [0, 1, 0, 2, 0, 3]}}).encode()),
    ])
    sheet = build_sheet(z)
    assert [s["label"] for s in sheet["sections"]] == ["Blocks"]


def test_an_out_of_range_frame_index_is_dropped_not_raised(tmp_path):
    z = _anim_zip(tmp_path, [
        (A + "textures/block/x.png", _png(16, 32)),
        (A + "textures/block/x.png.mcmeta",
         json.dumps({"animation": {"frames": [0, 1, 5, 1]}}).encode()),
    ])
    from mc_pack_converter.webui.sheet import SPIN, animation_frames
    # Assert on the SELECTION, not on the emitted tile: the tile now carries
    # SPIN frames whatever the animation says, so asserting its length here
    # would pass no matter how badly the index filter broke.
    im = Image.open(io.BytesIO(_png(16, 32)))
    picked = animation_frames(im, {"frames": [0, 1, 5, 1]})
    assert len(picked) == 3  # 0, 1, 1 -- index 5 dropped
    tile = build_sheet(z)["sections"][0]["tiles"][0]
    assert len(tile["frames"]) == SPIN


def test_frametime_is_converted_from_ticks_to_milliseconds(tmp_path):
    z = _anim_zip(tmp_path, [
        (A + "textures/block/lava_still.png", _png(16, 320)),
        (A + "textures/block/lava_still.png.mcmeta",
         json.dumps({"animation": {"frametime": 2}}).encode()),
    ])
    assert build_sheet(z)["sections"][0]["tiles"][0]["frametime"] == 100


def test_a_malformed_mcmeta_does_not_animate_and_does_not_raise(tmp_path):
    z = _anim_zip(tmp_path, [
        (A + "textures/block/x.png", _png(16, 32)),
        (A + "textures/block/x.png.mcmeta", b"{not json"),
    ])
    sheet = build_sheet(z)
    assert [s["label"] for s in sheet["sections"]] == ["Blocks"]


def test_armor_tiles_are_rendered_on_the_model_not_shown_flat(tmp_path):
    from mc_pack_converter.webui.armor import CANVAS
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/entity/equipment/humanoid/iron.png", _png(64, 32))
    tile = build_sheet(path)["sections"][0]["tiles"][0]
    raw = base64.b64decode(tile["thumb"].split(",", 1)[1])
    thumb = Image.open(io.BytesIO(raw))
    assert thumb.size != (64, 32)                      # not the flat sheet
    assert thumb.width / thumb.height == pytest.approx(CANVAS[0] / CANVAS[1], abs=0.05)
    assert (tile["w"], tile["h"]) == (64, 32)          # true source size kept


def test_armor_tiles_carry_a_large_render_for_the_lightbox(tmp_path):
    """Clicking an armor tile must open the MODEL, not the flat UV sheet.

    Every other tile opens its original texture on demand. For armor that
    original is the flat atlas, so without this the rendered model would only
    ever exist at thumbnail size -- too small to judge the art, which is the
    entire reason the renderer exists.
    """
    from mc_pack_converter.webui.armor import CANVAS
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/entity/equipment/humanoid/iron.png", _png(64, 32))
    tile = build_sheet(path)["sections"][0]["tiles"][0]
    assert tile["full"], "armor tile carries no large render"
    small = Image.open(io.BytesIO(base64.b64decode(tile["thumb"].split(",", 1)[1])))
    big = Image.open(io.BytesIO(base64.b64decode(tile["full"].split(",", 1)[1])))
    # Native canvas, not downscaled -- that is the most information there is,
    # since the source art is 64x32 and CSS pixelates the rest of the way up.
    assert big.size == CANVAS
    assert max(big.size) > max(small.size)


def test_only_armor_tiles_carry_a_large_render(tmp_path):
    """Blocks and items already open their true original; a baked copy would
    just be dead weight in the page."""
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/block/stone.png", _png(16, 16))
        z.writestr(A + "textures/item/apple.png", _png(16, 16))
    for section in build_sheet(path)["sections"]:
        for tile in section["tiles"]:
            assert tile.get("full") is None, f"{tile['name']} should carry no full render"




def test_an_animated_background_contributes_one_frame_not_a_strip(tmp_path):
    """A pack may animate its menu background; tiling the whole vertical strip
    would smear it down the page."""
    from mc_pack_converter.webui.wall import build_wall
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/gui/options_background.png", _png(16, 512))
    png = build_wall(path)
    with Image.open(io.BytesIO(png)) as im:
        assert im.size == (16, 16)


def test_the_background_is_the_packs_own_texture_verbatim(tmp_path):
    """Not composed, not generated: the pack's own bytes. Mason rejected two
    generated walls; the texture the pack ships is the one it should wear."""
    from mc_pack_converter.webui.wall import build_wall
    raw = _png(16, 16, (12, 34, 56, 255))
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/gui/options_background.png", raw)
        z.writestr(A + "textures/block/dirt.png", _png(16, 16))
    assert build_wall(path) == raw          # byte-for-byte, no re-encode


def test_dirt_stands_in_when_a_pack_has_no_menu_background(tmp_path):
    from mc_pack_converter.webui.wall import build_wall
    dirt = _png(16, 16, (99, 77, 55, 255))
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/block/dirt.png", dirt)
    assert build_wall(path) == dirt


def test_a_pack_with_none_of_them_gets_no_background(tmp_path):
    from mc_pack_converter.webui.wall import build_wall
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/item/apple.png", _png(16, 16))
    assert build_wall(path) is None


def test_fire_is_drawn_as_crossed_planes_not_a_cube(tmp_path):
    """Matched on the texture's own name, so a pack's fire_0/fire_1 both get
    it however the pack is organised."""
    import json as _json
    from mc_pack_converter.webui.armor import render_crossed, render_cube
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(A + "textures/block/fire_0.png", _png(16, 64))
        z.writestr(A + "textures/block/fire_0.png.mcmeta",
                   _json.dumps({"animation": {}}).encode())
        z.writestr(A + "textures/block/lava_still.png", _png(16, 64))
        z.writestr(A + "textures/block/lava_still.png.mcmeta",
                   _json.dumps({"animation": {}}).encode())
    tiles = {t["name"]: t for t in build_sheet(path)["sections"][0]["tiles"]}
    def width(uri):
        raw = base64.b64decode(uri.split(",", 1)[1])
        with Image.open(io.BytesIO(raw)) as im:
            box = im.getbbox()
            return box[2] - box[0]
    # Both spin, but fire is the narrower: crossed planes have no depth, and
    # it is that depth which gave the cube its floating top face.
    assert width(tiles["fire_0.png"]["frames"][0]) < \
           width(tiles["lava_still.png"]["frames"][0])


def test_the_background_ships_with_the_app_and_is_not_per_pack():
    """The window's background is a fixed asset: the terrain wall built once
    from the reference pack's own stone, ore and grass and committed. It is
    deliberately NOT rebuilt per conversion -- converting some other pack must
    not change what the program looks like. Rebuild it on purpose with
    `python -m mc_pack_converter.webui.wall <converted-pack.zip>`.
    """
    from pathlib import Path
    from PIL import Image
    import mc_pack_converter.webui as webui
    assets = Path(webui.__file__).parent / "assets"
    css = (assets / "app.css").read_text()

    for name, size in (("wall.png", (256, 256)), ("grass.png", (16, 16))):
        assert (assets / name).exists(), f"{name} must ship with the page"
        with Image.open(assets / name) as im:
            assert im.size == size
        assert f'url("{name}")' in css

    # A 16-tile field at 64px a block. Sizing it 64px would blow one block up
    # to fill the window.
    assert "background-size: 64px 64px, 1024px 1024px;" in css
    # No CSS variable to override: nothing may swap the background at runtime.
    assert "--pack-bg" not in css
    assert not (assets / "dirt.png").exists(), "the generated tile is gone"


# --- the terrain wall: grass on top, the pack's own ore in its own stone ----

STONE_RGB = (125, 125, 125, 255)
ORE_RGB = {"iron_ore": (200, 180, 160, 255),
           "gold_ore": (250, 220, 60, 255),
           "diamond_ore": (60, 220, 240, 255)}


def _speckled(colour, size=16):
    """A texture that is NOT one flat colour, so a test can tell a pasted
    tile apart from a redrawn one."""
    im = Image.new("RGBA", (size, size), colour)
    for i in range(1, size):          # (0,0) stays the flat colour: the tests probe it
        im.putpixel((i, (i * 7) % size), (0, 0, 0, 255))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _terrain_zip(tmp_path, ores=tuple(ORE_RGB), stone=True, grass=None,
                 ore_size=16):
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w") as z:
        if stone:
            z.writestr(A + "textures/block/stone.png", _png(16, 16, STONE_RGB))
        for name in ores:
            z.writestr(A + f"textures/block/{name}.png",
                       _speckled(ORE_RGB[name], ore_size))
        if grass is not None:
            z.writestr(A + "textures/block/grass_block_side.png", grass)
    return path


def _tiles(png):
    """The composed field as a list of 16x16 tile images, row-major."""
    with Image.open(io.BytesIO(png)) as im:
        im = im.convert("RGBA")
        assert im.size == (256, 256), "16 tiles of 16px a side"
        return [im.crop((x * 16, y * 16, x * 16 + 16, y * 16 + 16))
                for y in range(16) for x in range(16)]


def test_the_ground_is_the_packs_stone_with_its_own_ores_scattered_in_it(tmp_path):
    """Mason asked for stone with diamond, gold and iron spread through it.
    Iron is commonest and diamond rarest, the way the game ranks them."""
    from mc_pack_converter.webui.wall import build_wall
    from collections import Counter
    tiles = _tiles(build_wall(_terrain_zip(tmp_path)))
    counts = Counter(t.getpixel((0, 0)) for t in tiles)
    assert counts[ORE_RGB["iron_ore"]] == 12
    assert counts[ORE_RGB["gold_ore"]] == 7
    assert counts[ORE_RGB["diamond_ore"]] == 4
    assert counts[STONE_RGB] == 256 - 23


def test_every_ore_tile_is_the_packs_own_pixels_pasted_not_redrawn(tmp_path):
    """The whole point. Two generated ore walls were rejected; these tiles
    must be the pack's bytes, decoded and pasted whole."""
    from mc_pack_converter.webui.wall import build_wall
    sources = {ORE_RGB[n]: Image.open(io.BytesIO(_speckled(ORE_RGB[n]))).convert("RGBA")
               for n in ORE_RGB}
    ore_tiles = [t for t in _tiles(build_wall(_terrain_zip(tmp_path)))
                 if t.getpixel((0, 0)) in sources]
    assert len(ore_tiles) == 23
    for tile in ore_tiles:
        assert list(tile.getdata()) == list(sources[tile.getpixel((0, 0))].getdata())


def test_the_ores_do_not_land_in_the_same_place_every_row(tmp_path):
    """Scattered, not striped: a seeded shuffle that happened to deal one ore
    per row would read as a pattern, not as ore."""
    from mc_pack_converter.webui.wall import build_wall
    tiles = _tiles(build_wall(_terrain_zip(tmp_path)))
    per_row = [sum(1 for x in range(16)
                   if tiles[y * 16 + x].getpixel((0, 0)) != STONE_RGB)
               for y in range(16)]
    assert len(set(per_row)) > 1


def test_the_same_pack_always_gets_the_same_wall(tmp_path):
    """A wall that reshuffled every launch would look like a bug."""
    from mc_pack_converter.webui.wall import build_wall
    path = _terrain_zip(tmp_path)
    assert build_wall(path) == build_wall(path)


def test_stone_with_no_ore_textures_is_still_a_stone_field(tmp_path):
    from mc_pack_converter.webui.wall import build_wall
    tiles = _tiles(build_wall(_terrain_zip(tmp_path, ores=())))
    assert all(t.getpixel((0, 0)) == STONE_RGB for t in tiles)


def test_an_ore_at_a_different_resolution_is_left_out_rather_than_resized(tmp_path):
    """Resizing would invent pixels the pack never drew. A 32x ore in a 16x
    pack is simply not placed."""
    from mc_pack_converter.webui.wall import build_wall
    tiles = _tiles(build_wall(_terrain_zip(tmp_path, ores=("gold_ore",),
                                           ore_size=32)))
    assert all(t.getpixel((0, 0)) == STONE_RGB for t in tiles)


def test_the_grass_layer_is_the_packs_own_side_texture_verbatim(tmp_path):
    from mc_pack_converter.webui.wall import build_grass
    raw = _png(16, 16, (10, 200, 40, 255))
    assert build_grass(_terrain_zip(tmp_path, grass=raw)) == raw


def test_a_pack_with_no_grass_block_gets_no_grass_layer(tmp_path):
    from mc_pack_converter.webui.wall import build_grass
    assert build_grass(_terrain_zip(tmp_path)) is None


def test_the_stone_field_beats_a_custom_menu_background(tmp_path):
    """Asked for explicitly: the terrain wall is the point, so a pack that
    also ships gui/options_background.png still gets stone and ore."""
    from mc_pack_converter.webui.wall import build_wall
    path = _terrain_zip(tmp_path)
    with zipfile.ZipFile(path, "a") as z:
        z.writestr(A + "textures/gui/options_background.png",
                   _png(16, 16, (1, 1, 1, 255)))
    assert len(_tiles(build_wall(path))) == 256
