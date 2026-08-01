from PIL import Image
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages.validate import validate

def test_zero_byte_png_flagged(mini_pack):
    root = mini_pack({"assets/minecraft/textures/block/stone.png": b""})
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert any(f.stage=="validate" and f.severity is Severity.ERROR
               for f in ctx.findings)

def test_bad_mcmeta_dims_flagged(mini_pack):
    root = mini_pack()
    b = root/"assets/minecraft/textures/block"
    b.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA",(16,20)).save(b/"fire_0.png")  # 20 not divisible by 16
    (b/"fire_0.png.mcmeta").write_text('{"animation":{}}')
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert any(f.stage=="validate" and f.severity is Severity.WARNING
               for f in ctx.findings)

def test_corrupt_png_with_animation_mcmeta_does_not_crash(mini_pack):
    root = mini_pack()
    b = root/"assets/minecraft/textures/block"
    b.mkdir(parents=True, exist_ok=True)
    (b/"fire_0.png").write_bytes(b"")  # zero-byte, unreadable
    (b/"fire_0.png.mcmeta").write_text('{"animation":{}}')
    ctx = ConversionContext(root=root)
    validate(ctx)  # must not raise
    assert any(f.stage=="validate" and f.severity is Severity.ERROR
               for f in ctx.findings)


def test_validate_survives_non_utf8_properties(mini_pack):
    """8 of the 173 corpus packs crashed the whole validate stage here.

    OptiFine .properties files in the wild are UTF-8, ISO-8859-1, or — for
    macOS AppleDouble '._' junk — not text at all. read_text() raised
    UnicodeDecodeError, run_pipeline swallowed it, and validation was then
    silently skipped for the entire pack.
    """
    root = mini_pack()
    of = root / "assets/minecraft/optifine/ctm/glass"
    of.mkdir(parents=True)
    (of / "glass.properties").write_bytes(
        b"# Natural Textures config\r\nmethod=ctm\r\nsource=caf\xe9.png\r\n")   # latin-1
    (of / "._glass.properties").write_bytes(
        b"\x00\x05\x16\x07\x00\x02\x00\x00Mac OS X        \x00\x02\x00\x00")
    ctx = ConversionContext(root=root)
    validate(ctx)                       # must not raise
    assert not any("stage crashed" in f.message for f in ctx.findings)


# --- output invariants: each maps to a bug that actually shipped -------------

def _json(root, rel, data):
    import json as _j
    p = root / "assets/minecraft" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_j.dumps(data))
    return p


def test_model_pointing_at_legacy_texture_folder_is_an_error(mini_pack):
    """7[9bluefault7]: 1595 models, 578 dead refs, ZERO warnings."""
    root = mini_pack()
    _json(root, "models/block/anvil.json", {"textures": {"top": "blocks/anvil_base"}})
    ctx = ConversionContext(root=root)
    validate(ctx)
    hits = [f for f in ctx.findings if "null texture" in f.message]
    assert hits and hits[0].severity is Severity.ERROR


def test_modern_texture_reference_is_not_flagged(mini_pack):
    """A model may name a modern texture the pack does not ship — vanilla has it."""
    root = mini_pack()
    _json(root, "models/block/x.json", {"textures": {"all": "block/stone"}})
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert not any("null texture" in f.message for f in ctx.findings)


def test_bare_blockstate_model_name_is_an_error(mini_pack):
    """The magenta cubes: 2596 refs with no folder."""
    root = mini_pack()
    _json(root, "blockstates/oak_stairs.json",
          {"variants": {"facing=east": {"model": "oak_stairs"}}})
    ctx = ConversionContext(root=root)
    validate(ctx)
    hits = [f for f in ctx.findings if "magenta cube" in f.message]
    assert hits and hits[0].severity is Severity.ERROR


def test_qualified_blockstate_model_name_is_fine(mini_pack):
    root = mini_pack()
    _json(root, "blockstates/x.json",
          {"variants": {"a": {"model": "minecraft:block/oak_stairs"}}})
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert not any("magenta cube" in f.message for f in ctx.findings)


def test_wrong_gui_canvas_aspect_is_an_error(mini_pack):
    """The villager screen: square canvas where modern samples 2:1."""
    root = mini_pack()
    p = root / "assets/minecraft/textures/gui/container/villager.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (512, 512), (1, 2, 3, 255)).save(p)
    ctx = ConversionContext(root=root)
    validate(ctx)
    hits = [f for f in ctx.findings if "squashed" in f.message]
    assert hits and hits[0].severity is Severity.ERROR


def test_correct_gui_canvas_aspect_is_fine(mini_pack):
    root = mini_pack()
    p = root / "assets/minecraft/textures/gui/container/villager.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (512, 256), (1, 2, 3, 255)).save(p)
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert not any("squashed" in f.message for f in ctx.findings)


def test_animation_strip_without_mcmeta_is_flagged(mini_pack):
    """The fire bug: 128x2048 kept, its .mcmeta left on the old filename.

    fire_0 is on vanilla's animated list, so this is a real defect.
    """
    root = mini_pack()
    p = root / "assets/minecraft/textures/block/fire_0.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (128, 2048), (1, 2, 3, 255)).save(p)
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert any("stretched still image" in f.message for f in ctx.findings)


def test_tall_texture_vanilla_does_not_animate_is_not_flagged(mini_pack):
    """environment/rain.png is a tall strip with no .mcmeta in vanilla too.

    The naive "tall and no .mcmeta" rule fired on 143 of 170 corpus packs.
    """
    root = mini_pack()
    p = root / "assets/minecraft/textures/environment/rain.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 1024), (1, 2, 3, 255)).save(p)
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert not any("stretched still image" in f.message for f in ctx.findings)


def test_animation_strip_with_mcmeta_is_fine(mini_pack):
    root = mini_pack()
    p = root / "assets/minecraft/textures/block/fire_0.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (128, 2048), (1, 2, 3, 255)).save(p)
    p.with_name("fire_0.png.mcmeta").write_text('{"animation":{}}')
    ctx = ConversionContext(root=root)
    validate(ctx)
    assert not any("stretched still image" in f.message for f in ctx.findings)
