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


def _ctm_pack(base, folder, body=b"method=ctm\ntiles=0-47\n"):
    """A minimal pack with one CTM folder, built under its own directory.

    Takes a base dir rather than the mini_pack fixture: these tests build one
    pack per case in a loop, and the fixture reuses a single path.
    """
    root = base
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.mcmeta").write_text('{"pack":{"pack_format":1,"description":"t"}}')
    d = root / "assets/minecraft/optifine/ctm" / folder
    d.mkdir(parents=True)
    (d / "x.properties").write_bytes(body)
    return root, d / "x.properties"


def test_ctm_folder_name_is_matched_after_normalising(tmp_path):
    """Pack authors spell the same folder every which way.

    The corpus produced 'glass gray', 'glass_gray', 'glass/Grey Glass' and
    'Glass/Light Grey Glass' for what is one block. All must resolve.
    """
    for i, folder in enumerate(("glass gray", "glass_gray", "glass/Grey Glass",
                                "Glass/Grey Glass")):
        root, prop = _ctm_pack(tmp_path / f"p{i}", folder)
        ctx = ConversionContext(root=root)
        optifine_translate(ctx)
        txt = prop.read_text()
        assert "matchBlocks=minecraft:gray_stained_glass" in txt, folder
        assert not any("no matchBlocks mapping" in f.message
                       for f in ctx.findings), folder


def test_ctm_families_resolve(tmp_path):
    cases = {
        "ore/ore_coal": "minecraft:coal_ore",
        "ore diamond": "minecraft:diamond_ore",
        "planks/planks_oak": "minecraft:oak_planks",
        "wood spruce ends": "minecraft:spruce_log",
        "wood_ends/wood_birch": "minecraft:birch_log",
        "hardened_clay/stained/hardened_clay_black": "minecraft:black_terracotta",
        "crafting table": "minecraft:crafting_table",
        "flowers/flower_houstonia": "minecraft:azure_bluet",
        "monster_spawner": "minecraft:spawner",
        "fence_wooden/gate": "minecraft:oak_fence_gate",
    }
    for i, (folder, want) in enumerate(cases.items()):
        root, prop = _ctm_pack(tmp_path / f"p{i}", folder)
        optifine_translate(ConversionContext(root=root))
        assert want in prop.read_text(), folder


def test_deliberately_unmapped_folders_still_warn(tmp_path):
    """Leaving a folder unmapped must stay visible, not silently pass."""
    root, prop = _ctm_pack(tmp_path / "p", "default")
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    assert any("no matchBlocks mapping" in f.message for f in ctx.findings)
    assert "matchBlocks" not in prop.read_text()


def test_every_shipped_mapping_is_namespaced_and_plausible():
    from mc_pack_converter.data import load_table
    t = load_table("ctm_blocks")
    assert t["blocks"], "table must not be empty"
    for key, val in t["blocks"].items():
        assert key == key.lower(), key
        for block in val.split():
            assert block.startswith("minecraft:"), (key, block)


def test_pre_2026_07_31_keys_still_resolve(tmp_path):
    """Regression guard: the rewrite to a normalised table dropped two keys.

    glass_clear and glass_pane were mapped by the original 19-entry table and
    stopped resolving when it was regenerated — 33 corpus hits on glass_clear
    alone. Any future regeneration must keep them.
    """
    for i, (folder, want) in enumerate({
            "glass_clear": "minecraft:glass",
            "glass_pane": "minecraft:glass_pane",
            "sandstone_smooth": "minecraft:cut_sandstone",
    }.items()):
        root, prop = _ctm_pack(tmp_path / f"p{i}", folder)
        optifine_translate(ConversionContext(root=root))
        assert want in prop.read_text(), folder


def _ctm_multi(base, folders):
    """A pack with several CTM folders; folders maps name -> properties body."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "pack.mcmeta").write_text('{"pack":{"pack_format":1,"description":"t"}}')
    out = {}
    for name, body in folders.items():
        d = base / "assets/minecraft/optifine/ctm" / name
        d.mkdir(parents=True)
        (d / "x.properties").write_bytes(body)
        out[name] = d / "x.properties"
    return base, out


def test_explicit_claim_beats_an_inferred_one(tmp_path):
    """A dormant folder must not steal a block from the one that names it.

    M8SON ships glass_gray (no matchBlocks — inert in 1.8.9) alongside
    glass_stained/glass_gray (legacy numeric matchBlocks). Mapping both made
    two folders claim gray_stained_glass, which OptiFine resolves arbitrarily.
    """
    root, props = _ctm_multi(tmp_path / "p", {
        "glass_gray": b"method=ctm\ntiles=0-46\n",                    # inferred
        "glass_stained/glass_gray": b"method=ctm\nmatchBlocks=95\ntiles=0-47\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    assert "matchBlocks" not in props["glass_gray"].read_text()
    assert ("matchBlocks=minecraft:gray_stained_glass"
            in props["glass_stained/glass_gray"].read_text())
    assert any("already claimed by a folder that names it explicitly" in f.message
               for f in ctx.findings)


def test_two_inferred_claims_resolve_deterministically(tmp_path):
    root, props = _ctm_multi(tmp_path / "p", {
        "glass": b"method=ctm\ntiles=0-47\n",
        "glass_clear": b"method=ctm\ntiles=0-47\n",
    })
    ctx = ConversionContext(root=root)
    optifine_translate(ctx)
    written = [n for n, p in props.items() if "matchBlocks" in p.read_text()]
    assert len(written) == 1, f"exactly one folder may claim glass, got {written}"
    assert written == ["glass"]            # first by sorted path
    assert any("already claimed by" in f.message for f in ctx.findings)


def test_non_conflicting_folders_are_all_written(tmp_path):
    root, props = _ctm_multi(tmp_path / "p", {
        "glass_gray": b"method=ctm\ntiles=0-46\n",
        "glass_red": b"method=ctm\ntiles=0-46\n",
        "bookshelf": b"method=ctm\ntiles=0-47\n",
    })
    optifine_translate(ConversionContext(root=root))
    for name, p in props.items():
        assert "matchBlocks" in p.read_text(), name
