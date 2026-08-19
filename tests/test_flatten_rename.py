from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.flatten_rename import flatten_rename

def test_fire_is_renamed(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/block/fire_layer_0.png": b"x",
        "assets/minecraft/textures/block/fire_layer_0.png.mcmeta": b"{}",
    })
    ctx = ConversionContext(root=root)
    flatten_rename(ctx)
    b = root/"assets/minecraft/textures/block"
    assert (b/"fire_0.png").exists()
    assert (b/"fire_0.png.mcmeta").exists()
    assert not (b/"fire_layer_0.png").exists()


def test_source_named_file_wins_when_both_names_ship(mini_pack):
    """A pack_format 1 pack renders the 1.8.9 name; the modern one is inert.

    4OTF EUM3 ships blocks/fire_layer_0.png (32x1024, animated, with .mcmeta)
    AND blocks/fire_0.png (128x2048, no .mcmeta). Skipping the rename kept the
    modern-named file, which Minecraft then drew as one stretched still image
    because the animation .mcmeta was still attached to the old name.
    22 corpus packs hit this on fire alone.
    """
    root = mini_pack()
    b = root / "assets/minecraft/textures/block"
    b.mkdir(parents=True, exist_ok=True)
    (b / "fire_layer_0.png").write_bytes(b"ANIMATED-1.8.9")
    (b / "fire_layer_0.png.mcmeta").write_bytes(b'{"animation":{"frametime":1}}')
    (b / "fire_0.png").write_bytes(b"inert-modern-leftover")
    ctx = ConversionContext(root=root)
    monkey = {"textures/block/fire_layer_0.png": "textures/block/fire_0.png"}
    import mc_pack_converter.stages.flatten_rename as fr
    orig = fr.load_table
    fr.load_table = lambda n: monkey
    try:
        flatten_rename(ctx)
    finally:
        fr.load_table = orig
    assert (b / "fire_0.png").read_bytes() == b"ANIMATED-1.8.9"
    assert (b / "fire_0.png.mcmeta").exists(), "the animation metadata must follow"
    assert not (b / "fire_layer_0.png").exists()
    assert any("replaced" in f.message for f in ctx.findings)


def test_the_enchant_glint_gets_both_of_its_modern_names(mini_pack):
    """Reported from the game: "the enchants appear faint".

    1.8.9 has ONE glint, textures/misc/enchanted_item_glint.png, used for both
    enchanted items and enchanted armor. Modern Minecraft split it into
    enchanted_glint_item.png and enchanted_glint_armor.png. Renaming to only
    one of them leaves the other on vanilla's glint, which is far subtler than
    a 1.8.9 pack's -- so the enchantment shimmer reads as washed out in game.

    Both must therefore receive the pack's texture, and its .mcmeta with it:
    the pack's glint carries {"texture": {"blur": true}}, and an unblurred
    glint renders as hard diagonal bands.
    """
    root = mini_pack({
        "assets/minecraft/textures/misc/enchanted_item_glint.png": b"GLINT",
        "assets/minecraft/textures/misc/enchanted_item_glint.png.mcmeta":
            b'{"texture": {"blur": true}}',
    })
    ctx = ConversionContext(root=root)
    flatten_rename(ctx)

    misc = root / "assets/minecraft/textures/misc"
    for name in ("enchanted_glint_item.png", "enchanted_glint_armor.png"):
        assert (misc / name).exists(), f"{name} missing: it renders vanilla's"
        assert (misc / name).read_bytes() == b"GLINT"
        assert (misc / f"{name}.mcmeta").read_bytes() == b'{"texture": {"blur": true}}'
    assert not (misc / "enchanted_item_glint.png").exists()
    assert not (misc / "enchanted_item_glint.png.mcmeta").exists()
