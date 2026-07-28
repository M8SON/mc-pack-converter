# tests/test_optifine.py
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.optifine import optifine_translate, parse_properties

def test_parse_properties():
    assert parse_properties("a=1\n# c\nb=2\n") == {"a":"1","b":"2"}

def test_sky_dangling_source_warns(mini_pack):
    root = mini_pack({
        "assets/minecraft/optifine/sky/world0/sky4.properties":
            b"source=./starfield01.png\nblend=add\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    assert any(f.severity is Severity.WARNING and "starfield01" in f.message
               for f in ctx.findings)

def test_ctm_matchblocks_appended(mini_pack):
    root = mini_pack({
        "assets/minecraft/optifine/ctm/glass/glass.properties":
            b"method=ctm\ntiles=0-46\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (root/"assets/minecraft/optifine/ctm/glass/glass.properties").read_text()
    assert "matchBlocks=minecraft:glass" in txt

def test_ctm_no_method_is_skipped(mini_pack):
    original = b"tiles=0-3\n"
    root = mini_pack({
        "assets/minecraft/optifine/ctm/foo/config.properties": original,
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (root/"assets/minecraft/optifine/ctm/foo/config.properties").read_text()
    assert txt == original.decode()
    assert not any("matchBlocks" in f.message for f in ctx.findings)

def test_ctm_unknown_folder_warns(mini_pack):
    original = b"method=ctm\ntiles=0-3\n"
    root = mini_pack({
        "assets/minecraft/optifine/ctm/mystery/mystery.properties": original,
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (root/"assets/minecraft/optifine/ctm/mystery/mystery.properties").read_text()
    assert txt == original.decode()
    assert "matchBlocks" not in txt
    assert any(f.severity is Severity.WARNING and "mystery" in f.message
               for f in ctx.findings)
