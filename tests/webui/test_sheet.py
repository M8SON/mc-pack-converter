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
