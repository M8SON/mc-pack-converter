import io

from PIL import Image

from mc_pack_converter.pipeline import ConversionContext
from mc_pack_converter.stages.glint import glint

MISC = "assets/minecraft/textures/misc"
NAMES = ("enchanted_glint_item.png", "enchanted_glint_armor.png")


def _png(size: int) -> bytes:
    """A texture whose every pixel is distinguishable from every other."""
    im = Image.new("RGB", (size, size))
    im.putdata([(x * 4 % 256, y * 4 % 256, (x + y) % 256)
                for y in range(size) for x in range(size)])
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_the_glint_is_tiled_two_by_two(mini_pack):
    """Measured against vanilla's own glint across versions.

    1.8.9 and 1.12.2 ship a 64x64 glint carrying 2 streaks across the texture;
    1.16.5 onward ships 128x128 carrying 4. Mojang doubled the streak count
    rather than upscaling the art, and their in-game glint did not double in
    density -- so the game now tiles the glint half as far. A 1.8.9 pack's
    glint therefore renders at half the on-screen density it had in 1.8.9,
    which reads as streaks twice as wide.

    Tiling it 2x2 doubles the streaks across the texture and cancels that out.
    """
    src = _png(64)
    root = mini_pack({f"{MISC}/{n}": src for n in NAMES})
    ctx = ConversionContext(root=root)

    glint(ctx)

    original = Image.open(io.BytesIO(src)).convert("RGB")
    for name in NAMES:
        out = Image.open(root / MISC / name).convert("RGB")
        assert out.size == (128, 128), f"{name} was not tiled"
        for ox, oy in ((0, 0), (64, 0), (0, 64), (64, 64)):
            quadrant = out.crop((ox, oy, ox + 64, oy + 64))
            assert list(quadrant.getdata()) == list(original.getdata()), \
                f"{name} quadrant at {(ox, oy)} is not the source art"


def test_the_pipeline_runs_the_glint_stage_after_the_rename():
    """It corrects the two modern names, which flatten_rename is what creates."""
    from mc_pack_converter.stages import STAGES

    names = [name for name, _ in STAGES]
    assert "glint" in names, "the stage never runs, so no pack is corrected"
    assert names.index("glint") > names.index("flatten_rename")


def test_a_pack_with_no_glint_is_left_alone(mini_pack):
    root = mini_pack({f"{MISC}/shadow.png": _png(8)})
    ctx = ConversionContext(root=root)

    glint(ctx)

    assert Image.open(root / MISC / "shadow.png").size == (8, 8)
    for name in NAMES:
        assert not (root / MISC / name).exists()
