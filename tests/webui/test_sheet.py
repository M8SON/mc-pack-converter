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
