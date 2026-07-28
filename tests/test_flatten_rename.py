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
