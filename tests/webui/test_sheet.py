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
    assert len(tile["frames"]) == 16
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
    tile = build_sheet(z)["sections"][0]["tiles"][0]
    assert len(tile["frames"]) == 3  # 0, 1, 1 -- index 5 dropped


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
