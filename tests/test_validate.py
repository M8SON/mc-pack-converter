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
