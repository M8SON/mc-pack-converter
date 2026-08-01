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
