# tests/test_optifine.py
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.optifine import optifine_translate, parse_properties

def test_parse_properties():
    assert parse_properties("a=1\n# c\nb=2\n") == {"a":"1","b":"2"}

def test_sky_missing_source_layer_removed(mini_pack):
    # A sky layer whose source image is absent renders as the magenta
    # missing-texture; the stage removes the broken layer (and keeps others).
    root = mini_pack({
        "assets/minecraft/optifine/sky/world0/sky4.properties":
            b"source=./starfield01.png\nblend=add\n",
        "assets/minecraft/optifine/sky/world0/sky1.properties":
            b"source=./clouds.png\nblend=add\n",
        "assets/minecraft/optifine/sky/world0/clouds.png": b"\x89PNG",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    sky = root / "assets/minecraft/optifine/sky/world0"
    assert not (sky / "sky4.properties").exists()   # broken layer removed
    assert (sky / "sky1.properties").exists()        # good layer kept
    assert any(f.severity is Severity.INFO and "starfield01" in f.message
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

def test_ctm_numeric_matchblocks_replaced(mini_pack):
    root = mini_pack({
        "assets/minecraft/optifine/ctm/glass_stained/glass_black/glass_black.properties":
            b"method=ctm\nmatchBlocks=160 95\nmetadata=15\ntiles=0-47\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    path = root/"assets/minecraft/optifine/ctm/glass_stained/glass_black/glass_black.properties"
    txt = path.read_text()
    lines = txt.splitlines()
    assert "matchBlocks=minecraft:black_stained_glass minecraft:black_stained_glass_pane" in lines
    assert not any(l.startswith("matchBlocks=") and any(c.isdigit() for c in l) for l in lines)
    assert "method=ctm" in lines
    assert "metadata=15" in lines
    assert "tiles=0-47" in lines
    assert any(f.severity is Severity.INFO and "matchBlocks" in f.message for f in ctx.findings)

def test_ctm_numeric_unknown_folder_kept(mini_pack):
    original = b"method=ctm\nmatchBlocks=5 6\n"
    root = mini_pack({
        "assets/minecraft/optifine/ctm/weird/weird.properties": original,
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (root/"assets/minecraft/optifine/ctm/weird/weird.properties").read_text()
    assert "matchBlocks=5 6" in txt
    assert any(f.severity is Severity.WARNING and "weird" in f.message for f in ctx.findings)

def test_ctm_modern_matchblocks_untouched(mini_pack):
    original = b"method=ctm\nmatchBlocks=minecraft:glass\n"
    root = mini_pack({
        "assets/minecraft/optifine/ctm/clear/clear.properties": original,
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (root/"assets/minecraft/optifine/ctm/clear/clear.properties").read_text()
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

def test_sky_replace_with_black_texture_becomes_add(mini_pack):
    from PIL import Image
    root = mini_pack({
        "assets/minecraft/optifine/sky/world0/sky1.properties":
            b"source=./cloud2.png\nblend=replace\nrotate=true\n",
    })
    sky = root / "assets/minecraft/optifine/sky/world0"
    # opaque, mostly-black cloud texture
    Image.new("RGBA", (16, 16), (0, 0, 0, 255)).save(sky / "cloud2.png")
    from mc_pack_converter.stages.optifine import optifine_translate
    from mc_pack_converter.pipeline import ConversionContext
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    txt = (sky / "sky1.properties").read_text()
    assert "blend=add" in txt and "blend=replace" not in txt

def test_sky_replace_with_opaque_nonblack_stays_replace(mini_pack):
    from PIL import Image
    root = mini_pack({
        "assets/minecraft/optifine/sky/world0/sky3.properties":
            b"source=./cloud1.png\nblend=replace\n",
    })
    sky = root / "assets/minecraft/optifine/sky/world0"
    Image.new("RGBA", (16, 16), (120, 160, 255, 255)).save(sky / "cloud1.png")  # day sky, no black
    from mc_pack_converter.stages.optifine import optifine_translate
    from mc_pack_converter.pipeline import ConversionContext
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    assert "blend=replace" in (sky / "sky3.properties").read_text()
