from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.restructure import restructure

def test_restructure_renames_dirs(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/items/apple.png": b"x",
        "assets/minecraft/mcpatcher/sky/world0/sky1.properties": b"x",
    })
    ctx = ConversionContext(root=root)
    restructure(ctx)
    mc = root/"assets/minecraft"
    assert (mc/"textures/block").is_dir()
    assert (mc/"textures/item/apple.png").exists()
    assert (mc/"optifine/sky/world0/sky1.properties").exists()
    assert not (mc/"mcpatcher").exists()
