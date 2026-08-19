

def _table():
    import json
    from pathlib import Path
    import mc_pack_converter.data as data
    return json.loads((Path(data.__file__).parent / "flattening.json").read_text())


def test_the_wood_and_gold_tools_are_renamed():
    """Mason found these reverting to vanilla in game. 1.8.9 calls them
    wood_/gold_; every modern name is wooden_/golden_. Gold ARMOR was already
    handled, which is how the tools went unnoticed."""
    t = _table()
    for tool in ("sword", "pickaxe", "axe", "shovel", "hoe"):
        assert t[f"textures/item/wood_{tool}.png"] == f"textures/item/wooden_{tool}.png"
        assert t[f"textures/item/gold_{tool}.png"] == f"textures/item/golden_{tool}.png"


def test_slimeball_is_renamed():
    assert _table()["textures/item/slimeball.png"] == "textures/item/slime_ball.png"


def test_the_records_became_music_discs():
    t = _table()
    for disc in ("11", "13", "cat", "chirp", "far", "mall", "mellohi",
                 "stal", "strad", "wait", "ward", "blocks"):
        assert t[f"textures/item/record_{disc}.png"] == \
               f"textures/item/music_disc_{disc}.png"


def _targets(dst):
    """A value is one name, or a list when modern Minecraft split the texture
    into several -- the enchant glint became a separate item and armor glint."""
    return dst if isinstance(dst, list) else [dst]


def test_no_rename_points_at_a_1_8_9_name():
    """A target that is itself an old name means the rename was half-done."""
    t = _table()
    old_shapes = ("wood_", "gold_", "record_", "minecart_", "seeds_",
                  "potion_bottle_", "mutton_", "porkchop_", "rabbit_")
    for src, dst in t.items():
        for one in _targets(dst):
            leaf = one.rsplit("/", 1)[-1]
            assert not leaf.startswith(old_shapes), \
                f"{src} -> {one} lands on an old name"


def test_no_two_sources_claim_the_same_target():
    """Two renames landing on one name means whichever runs last wins, which
    is a coin flip decided by dict order."""
    t = _table()
    seen = {}
    for src, dst in t.items():
        for one in _targets(dst):
            assert one not in seen, f"{src} and {seen[one]} both target {one}"
            seen[one] = src


def test_the_enchant_glint_reaches_both_of_its_modern_names():
    """1.8.9 has one glint for items and armor; modern Minecraft has two. Only
    renaming to one leaves the other rendering vanilla's fainter glint."""
    assert _table()["textures/misc/enchanted_item_glint.png"] == [
        "textures/misc/enchanted_glint_item.png",
        "textures/misc/enchanted_glint_armor.png",
    ]
