

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


def test_no_rename_points_at_a_1_8_9_name():
    """A target that is itself an old name means the rename was half-done."""
    t = _table()
    old_shapes = ("wood_", "gold_", "record_", "minecart_", "seeds_",
                  "potion_bottle_", "mutton_", "porkchop_", "rabbit_")
    for src, dst in t.items():
        leaf = dst.rsplit("/", 1)[-1]
        assert not leaf.startswith(old_shapes), f"{src} -> {dst} lands on an old name"
