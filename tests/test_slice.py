from PIL import Image
from mc_pack_converter.pipeline import ConversionContext, Severity
from mc_pack_converter.stages import slice as slice_mod
from mc_pack_converter.stages.slice import slice_atlases


def _put(root, rel, size, color=(10, 20, 30, 255)):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, color).save(p)
    return p


def test_crop_proportional_standard_res(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (256, 256))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    out = root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png"
    assert out.exists()
    assert Image.open(out).size == (182, 22)


def test_crop_scales_with_resolution(mini_pack, monkeypatch):
    # A 2x-resolution atlas: a 256-ref box must scale up proportionally.
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/widgets.png", (512, 512))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/widgets.png",
         "output": "assets/minecraft/textures/gui/sprites/hud/hotbar.png",
         "box": [0, 0, 182, 22, 256, 256], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert Image.open(root / "assets/minecraft/textures/gui/sprites/hud/hotbar.png").size == (364, 44)


def test_copy_op_relocates_whole_file(mini_pack, monkeypatch):
    root = mini_pack()
    _put(root, "assets/minecraft/textures/gui/title/mojangstudios.png", (128, 128))
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/title/mojangstudios.png",
         "output": "assets/minecraft/textures/gui/sprites/title/mojangstudios.png",
         "box": [0, 0, 1, 1, 1, 1], "op": "copy"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)
    assert (root / "assets/minecraft/textures/gui/sprites/title/mojangstudios.png").exists()


def test_missing_atlas_is_skipped(mini_pack, monkeypatch):
    root = mini_pack()
    monkeypatch.setattr(slice_mod, "load_table", lambda n: [
        {"input": "assets/minecraft/textures/gui/nonexistent.png",
         "output": "assets/minecraft/textures/gui/sprites/x.png",
         "box": [0, 0, 8, 8, 16, 16], "op": "crop"}])
    ctx = ConversionContext(root=root)
    slice_atlases(ctx)  # must not raise
    assert any(f.stage == "slice" and f.severity is Severity.INFO for f in ctx.findings)
