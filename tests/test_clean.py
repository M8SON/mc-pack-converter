from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.clean import clean

def test_clean_removes_junk(mini_pack):
    root = mini_pack({
        "assets/minecraft/textures/blocks/stone.png:Zone.Identifier": b"x",
        "assets/minecraft/textures/blocks/Thumbs.db": b"x",
        "assets/minecraft/textures/gui/widgets.png~": b"x",
        "assets/minecraft/textures/blocks/stone.png": b"realpng",
    })
    ctx = ConversionContext(root=root)
    clean(ctx)
    tex = root/"assets/minecraft/textures"
    assert not (tex/"blocks/stone.png:Zone.Identifier").exists()
    assert not (tex/"blocks/Thumbs.db").exists()
    assert not (tex/"gui/widgets.png~").exists()
    assert (tex/"blocks/stone.png").exists()
    assert any("3" in f.message for f in ctx.findings if f.severity is Severity.INFO)
