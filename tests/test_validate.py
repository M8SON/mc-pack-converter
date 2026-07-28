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
